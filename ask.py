import json
import anthropic
from dotenv import load_dotenv
from db import get_connection
from search import search_postings

load_dotenv()
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env
MODEL = "claude-sonnet-4-6"

SYSTEM = """You are a data analyst assistant for a database of AI-related job postings
(Mexico and remote LATAM roles). You have two tools:

1. run_sql: queries structured fields (counts, averages, filters, skills, salaries).
   The database is Microsoft SQL Server, so write T-SQL: use TOP n, never LIMIT.
2. search_postings: semantic search over the full posting text. Use it for things that
   aren't columns: benefits, schedules, culture, responsibilities, interview process,
   how companies describe the role. It finds text by meaning, in Spanish or English.
   Pass job_ids to search only within certain jobs (get the ids with run_sql first).

Use both when needed, e.g. "what benefits do remote AI engineer jobs offer?":
run_sql to get the ids of remote AI engineer jobs, then search_postings with those ids.

Schema:
dbo.jobs (
  job_id INT PRIMARY KEY,
  job_title NVARCHAR,
  role_category NVARCHAR,  -- 'AI engineer','ML engineer','MLOps engineer','AI automation',
                           -- 'data scientist','AI researcher','AI product','AI consultant','other'
  company NVARCHAR,
  location NVARCHAR,       -- city name like 'Ciudad de México', 'Guadalajara', or 'Remote'
  work_mode NVARCHAR,      -- 'remote','hybrid','onsite'
  seniority NVARCHAR,      -- 'junior','mid','senior'
  experience_years_min INT,
  experience_years_max INT,
  language_required NVARCHAR, -- 'spanish','english','both'
  salary_min_mxn INT,      -- monthly gross MXN
  salary_max_mxn INT,
  description NVARCHAR(MAX), -- full posting text (don't SELECT it whole; use search_postings)
  submitted_at DATETIME2
)
dbo.job_skills (job_id INT, skill NVARCHAR)  -- one row per skill per job

Rules:
- Only SELECT queries.
- Any column can be NULL (not stated in the posting). Exclude NULLs when averaging and say
  how many jobs a figure is based on.
- Skill names are standardized (e.g. 'Python', 'LLMs', 'RAG', 'LangChain', 'AI Agents').
  If unsure of the exact name, run SELECT DISTINCT skill FROM dbo.job_skills first.
- Use LIKE for partial matches on job_title, company, and location.
- Always state how many postings an answer is based on, e.g. "18 of 20 postings".
  Run SELECT COUNT(*) FROM dbo.jobs if you need the total.
- When using search_postings, only report what the returned text actually says, and name
  the job and company it came from.
- Search returns only the closest passages, not every posting. Never claim a posting
  doesn't mention something, and never say "all" or "most" postings based on search.
  Say "the search found..." instead. For broad questions, you can raise k up to 20.
- No emojis. Keep formatting simple.
- Report what the data shows. Don't speculate about causes or trends beyond the results.
- Answer in the language of the question. Be concise.

Examples:
Q: What are the most requested skills?
SQL: SELECT TOP 10 skill, COUNT(*) AS jobs FROM dbo.job_skills GROUP BY skill ORDER BY jobs DESC;

Q: Which remote AI engineer jobs are there?
SQL: SELECT job_title, company FROM dbo.jobs WHERE role_category = 'AI engineer' AND work_mode = 'remote';

Q: Average salary by seniority?
SQL: SELECT seniority, COUNT(*) AS jobs, AVG(salary_min_mxn) AS avg_min, AVG(salary_max_mxn) AS avg_max
     FROM dbo.jobs WHERE salary_min_mxn IS NOT NULL GROUP BY seniority;
"""

TOOLS = [
    {
        "name": "run_sql",
        "description": "Run a read-only T-SQL SELECT query on the AIJobMarket database. Returns up to 50 rows.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A single T-SQL SELECT query"}},
            "required": ["query"],
        },
    },
    {
        "name": "search_postings",
        "description": "Semantic search over the full text of job postings. Returns the most relevant passages "
                       "with their job_id, title, and company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "What to look for, in natural language"},
                "job_ids": {"type": "array", "items": {"type": "integer"},
                            "description": "Optional: only search within these jobs"},
                "k": {"type": "integer", "description": "Number of passages to return (default 8, max 20)"},
            },
            "required": ["text"],
        },
    },
]


def run_sql(query):
    q = query.strip().rstrip(";")
    if not q.lower().startswith(("select", "with")):
        raise ValueError("Only SELECT queries are allowed.")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(q)
        cols = [c[0] for c in cursor.description]
        rows = cursor.fetchmany(51)
        data = [dict(zip(cols, r)) for r in rows[:50]]
        return json.dumps({"rows": data, "truncated": len(rows) > 50}, default=str, ensure_ascii=False)
    finally:
        conn.close()


def run_tool(name, args, show_steps, steps):
    if name == "run_sql":
        if show_steps:
            print(f"\n[SQL]\n{args['query']}\n")
        output = run_sql(args["query"])
        steps.append({"type": "sql", "input": args["query"], "output": output})
        return output
    if name == "search_postings":
        k = min(int(args.get("k", 8)), 20)
        if show_steps:
            ids = f" (in jobs {args['job_ids']})" if args.get("job_ids") else ""
            print(f"\n[SEARCH] {args['text']}{ids}\n")
        output = json.dumps(search_postings(args["text"], k=k, job_ids=args.get("job_ids")), ensure_ascii=False)
        steps.append({"type": "search", "input": args["text"], "job_ids": args.get("job_ids"), "output": output})
        return output
    raise ValueError(f"Unknown tool: {name}")


def ask(question, history=None, steps=None, show_steps=True):
    """history: earlier turns as [{"role": "user"/"assistant", "content": text}].
    steps: optional list that collects every SQL query and search, for display."""
    steps = [] if steps is None else steps
    messages = list(history or [])[-6:] + [{"role": "user", "content": question}]
    for _ in range(8):  # max tool rounds, so it can never loop forever
        resp = client.messages.create(
            model=MODEL, max_tokens=2000,
            system=SYSTEM, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")

        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            try:
                output = run_tool(block.name, block.input, show_steps, steps)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
            except Exception as e:
                # send the error back so Claude can fix its call
                steps.append({"type": "error", "input": block.input, "output": str(e)})
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": f"Error: {e}", "is_error": True})
        messages.append({"role": "user", "content": results})

    return "Stopped: too many steps without an answer."


if __name__ == "__main__":
    print("Ask about the AI job market. Type 'exit' to quit.")
    while True:
        q = input("\nQuestion: ").strip()
        if q.lower() in ("exit", "quit", ""):
            break
        print("\n" + ask(q))
