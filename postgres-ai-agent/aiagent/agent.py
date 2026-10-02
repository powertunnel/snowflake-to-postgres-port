"""Orchestrator — the Cortex Agent / CoWork equivalent.

DeepSeek plans and routes across the two tools (text-to-SQL + feedback search),
then synthesizes a final answer with the evidence it used. Runs every DB query
under a chosen read-only role, so the RLS policy applies transparently.
"""
import argparse
import json
import sys
from . import llm, tools, config

_SYSTEM = """You are a retail analytics assistant for a snow-sports company.
You answer questions by calling tools:
- query_business_data: structured/quantitative facts (text-to-SQL over the warehouse).
- search_customer_feedback: qualitative 'why' / example quotes from reviews & tickets.
- count_feedback_mentions: ACCURATE counts & breakdowns of feedback mentioning terms.
For "what happened" use query_business_data; for "why" / example quotes use
search_customer_feedback; for "how many mention X" or "which products are most
affected" use count_feedback_mentions (NEVER count search results — search is capped).
Call several tools when a question needs both a count and examples.

GROUNDING (critical):
- Use ONLY facts, numbers, and text returned by the tools. Never invent review or
  ticket wording, product names, counts, categories, or themes.
- When you quote feedback, quote verbatim from a returned row. Do not paraphrase a
  quote into something more specific than what was returned.
- Do not assert a theme/pattern unless the returned rows actually support it. If the
  evidence is thin, limited, or a search returned 0 hits, say so plainly rather than
  filling the gap.
- A count is only valid if it comes from a tool result. Search results are capped and
  are NOT a reliable total; to count, use query_business_data, otherwise say the count
  is approximate/based on the sample.

EFFICIENCY:
- Be economical: aim for at most ~4 tool calls. Do not repeat a search with near-
  identical terms. If a search returns nothing useful, change strategy or conclude.
- Map rating wording exactly via the filters arg ('below 3' -> {"rating_lt": 3}).

After gathering evidence, give a concise, grounded answer citing concrete returned
numbers and example quotes. If a SQL call errors, retry once with a simpler question."""


def run(question: str, role: str = None, max_steps: int = 5, verbose: bool = True):
    role = role or config.DEFAULT_ROLE
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": question}]
    transcript = []

    for _ in range(max_steps):
        msg = llm.chat(messages, tools=tools.TOOL_SCHEMAS, tool_choice="auto",
                       temperature=0.0, max_tokens=900)
        tool_calls = msg.get("tool_calls")
        # The assistant turn must be recorded before any tool results.
        messages.append({"role": "assistant",
                         "content": msg.get("content") or "",
                         "tool_calls": tool_calls or []})

        if not tool_calls:
            return {"answer": msg.get("content", ""), "transcript": transcript, "role": role}

        for call in tool_calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            if verbose:
                print(f"  → tool: {name}({json.dumps(args)})", file=sys.stderr)
            result = tools.DISPATCH[name](args, role)
            transcript.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, default=str)[:6000]})

    # Out of steps: ask for a final synthesis without tools.
    messages.append({"role": "user",
                     "content": "Summarize your findings now from the evidence gathered."})
    final = llm.chat(messages, temperature=0.0, max_tokens=700)
    return {"answer": final.get("content", ""), "transcript": transcript, "role": role}


def main():
    ap = argparse.ArgumentParser(description="Local Postgres AI agent (DeepSeek).")
    ap.add_argument("question", nargs="*", help="Question to ask.")
    ap.add_argument("--role", default=config.DEFAULT_ROLE,
                    help="DB role to run as: analyst_ro (all data) or west_coast_manager (RLS).")
    ap.add_argument("--json", action="store_true", help="Print full JSON (answer+transcript).")
    args = ap.parse_args()

    questions = [" ".join(args.question)] if args.question else None
    if not questions:  # interactive REPL
        print(f"Postgres AI agent — role={args.role}. Ctrl-D to exit.")
        while True:
            try:
                q = input("\n> ").strip()
            except EOFError:
                break
            if not q:
                continue
            out = run(q, role=args.role)
            print("\n" + out["answer"])
        return

    out = run(questions[0], role=args.role)
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print("\n" + out["answer"])


if __name__ == "__main__":
    main()
