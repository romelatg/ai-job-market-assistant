"""Runs every test question through the chatbot and has Claude judge each answer.
Usage: python eval.py   ->  prints the score and saves eval_results.csv"""
import csv
import json
import re
from datetime import datetime

from ask import ask, client, MODEL, run_sql

JUDGE_PROMPT = """You are grading an AI assistant that answers questions about a job postings database.

Question: {question}

{reference_label}:
{reference}

Assistant's answer:
{answer}

Grade the answer. It is CORRECT if every number, name, or item the question asks for matches the
reference. Extra context, caveats, and different formatting are fine. Rounding is fine.
It is INCORRECT if it gives a wrong number, leaves out items the question asks for, includes items
the reference contradicts, or fails to answer.

Reply with ONLY a JSON object: {{"correct": true or false, "reason": "one short sentence"}}"""


def judge(question, reference_label, reference, answer):
    resp = client.messages.create(
        model=MODEL, max_tokens=300,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(
            question=question, reference_label=reference_label, reference=reference, answer=answer)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        return json.loads(match.group(0))
    except Exception:
        return {"correct": False, "reason": f"Judge reply could not be parsed: {text[:200]}"}


def main():
    with open("eval_questions.json", encoding="utf-8") as f:
        tests = json.load(f)

    results = []
    for i, t in enumerate(tests, 1):
        q = t["question"]
        print(f"[{i}/{len(tests)}] {q}")

        if "gold_sql" in t:
            kind = "sql"
            reference = json.loads(run_sql(t["gold_sql"]))["rows"]
            reference_label = "Correct data (from a hand-written reference query)"
            reference = json.dumps(reference, ensure_ascii=False, default=str)
        else:
            kind = "text"
            reference_label = "Expected facts"
            reference = t["expected"]

        steps = []
        try:
            answer = ask(q, steps=steps, show_steps=False)
        except Exception as e:
            answer = f"ERROR: {e}"

        verdict = judge(q, reference_label, reference, answer)
        mark = "PASS" if verdict.get("correct") else "FAIL"
        print(f"    {mark}: {verdict.get('reason', '')}")

        results.append({
            "question": q, "type": kind, "correct": bool(verdict.get("correct")),
            "reason": verdict.get("reason", ""), "steps": len(steps),
            "tools_used": ", ".join(sorted({s["type"] for s in steps})),
            "answer": answer, "reference": reference,
        })

    total = len(results)
    passed = sum(r["correct"] for r in results)
    print(f"\nScore: {passed}/{total} correct ({passed / total:.0%})")
    for kind in ("sql", "text"):
        subset = [r for r in results if r["type"] == kind]
        if subset:
            ok = sum(r["correct"] for r in subset)
            print(f"  {kind:>4} questions: {ok}/{len(subset)}")

    failed = [r for r in results if not r["correct"]]
    if failed:
        print("\nFailed:")
        for r in failed:
            print(f"  - {r['question']}\n    {r['reason']}")

    filename = f"eval_results_{datetime.now():%Y%m%d_%H%M}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\nFull results saved to {filename}")


if __name__ == "__main__":
    main()
