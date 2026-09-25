import json
import pandas as pd
import streamlit as st
from ask import ask

st.set_page_config(page_title="AI Job Market Assistant", page_icon="💼")

EXAMPLES = [
    "What are the 10 most requested skills?",
    "How many jobs are remote, hybrid, and onsite?",
    "What benefits do the companies offer?",
    "What do remote AI engineer jobs say about working hours?",
]

if "messages" not in st.session_state:
    st.session_state.messages = []  # each: {"role", "content", "steps"}

# ---------- sidebar ----------
with st.sidebar:
    st.header("Try asking")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True):
            st.session_state.pending = ex
    st.divider()
    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.caption("Answers come from SQL queries on the job database and semantic search "
               "over the full posting text. Expand 'How I got this' under any answer to check.")


def show_steps(steps):
    if not steps:
        return
    with st.expander(f"How I got this ({len(steps)} step{'s' if len(steps) > 1 else ''})"):
        for s in steps:
            if s["type"] == "sql":
                st.markdown("**SQL query**")
                st.code(s["input"], language="sql")
                rows = json.loads(s["output"])["rows"]
                if rows:
                    st.dataframe(pd.DataFrame(rows), hide_index=True)
            elif s["type"] == "search":
                scope = f" (within jobs {s['job_ids']})" if s.get("job_ids") else ""
                st.markdown(f"**Text search:** {s['input']}{scope}")
                hits = json.loads(s["output"])
                if hits:
                    st.dataframe(pd.DataFrame(hits)[["similarity", "job_title", "company", "text"]],
                                 hide_index=True)
            else:
                st.markdown("**Error (Claude retried)**")
                st.code(s["output"])


# ---------- chat history ----------
st.title("AI Job Market Assistant")
st.caption("Questions about AI job postings in Mexico and remote LATAM roles.")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if m["role"] == "assistant":
            show_steps(m.get("steps"))
        st.markdown(m["content"])

# ---------- new question ----------
question = st.chat_input("Ask about skills, salaries, benefits, work mode...")
question = question or st.session_state.pop("pending", None)

if question:
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        steps = []
        with st.spinner("Querying the database..."):
            try:
                answer = ask(question, history=history, steps=steps, show_steps=False)
            except Exception as e:
                answer = f"Something went wrong: {e}"
        show_steps(steps)
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer, "steps": steps})
