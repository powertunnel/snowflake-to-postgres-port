"""Agent-evaluation harness — the local equivalent of Snowflake Agent Evaluation.

For each question in eval_dataset.yaml it runs the agent, then uses DeepSeek as an
LLM judge to score two metrics (0..1), matching the lab:
  - answer_correctness  : does the answer satisfy the ground-truth expectation?
  - logical_consistency : are the tool choices + reasoning + answer internally
                          coherent and grounded in tool output? (reference-free)
It prints a per-question table + averages, and writes full results to JSON.

Usage:
  python -m aiagent.evaluate                       # run all, default role
  python -m aiagent.evaluate --only q4_ski_boot_returns
  python -m aiagent.evaluate --out eval_results.json
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

from . import agent, llm, config

DATASET = Path(__file__).resolve().parent.parent / "eval_dataset.yaml"
PASS_THRESHOLD = 0.7

_JUDGE_SYS = """You are a strict evaluator of an AI data-analytics agent.
Score ONE metric on a 0.0–1.0 scale. Return ONLY JSON:
{"score": <float 0..1>, "rationale": "<= 2 sentences"}
Be calibrated: 1.0 fully meets the bar, 0.5 partial, 0.0 fails. Do not reward
fluent text that lacks the required substance."""


def _judge(metric_instructions: str) -> dict:
    msg = llm.chat(
        [{"role": "system", "content": _JUDGE_SYS},
         {"role": "user", "content": metric_instructions}],
        temperature=0.0, max_tokens=250,
    )
    try:
        d = llm.extract_json(msg["content"])
        score = max(0.0, min(1.0, float(d.get("score", 0))))
        return {"score": score, "rationale": d.get("rationale", "")}
    except Exception as e:
        return {"score": 0.0, "rationale": f"judge parse error: {e}"}


def _tools_used(transcript):
    return [t["tool"] for t in transcript]


def _trace_summary(transcript):
    """Judge-friendly view of what the agent did, carrying enough of the ACTUAL
    tool output (rows + full search hits, incl. bodies) that the consistency judge
    can verify grounding instead of mistaking real citations for fabrication."""
    out = []
    for t in transcript:
        item = {"tool": t["tool"], "args": t.get("args", {})}
        res = t.get("result", {})
        if "error" in res:
            item["outcome"] = f"ERROR: {res['error'][:160]}"
        elif "per_source" in res:  # count_feedback_mentions
            item["outcome"] = f"total={res.get('total')} (terms='{res.get('terms')}')"
            item["per_source"] = res.get("per_source")
        elif "row_count" in res:
            item["outcome"] = f"{res['row_count']} rows; sql={res.get('sql','')[:200]}"
            item["rows"] = res.get("rows", [])[:15]      # the data the agent saw
        elif "result_count" in res:
            item["outcome"] = f"{res['result_count']} search hits"
            # Show ALL hits the agent received (search limit is 10) so the judge
            # does not mistake a lower-ranked but real citation for fabrication.
            item["hits"] = res.get("results", [])
        out.append(item)
    return out


def score_answer_correctness(q, ground_truth, answer, tools_used):
    prompt = (
        f"METRIC: answer_correctness\n"
        f"Question: {q}\n\n"
        f"Ground-truth expectation (what a correct answer should do/contain):\n{ground_truth}\n\n"
        f"Tools the agent actually used: {tools_used}\n\n"
        f"Agent's answer:\n{answer}\n\n"
        f"Score how well the answer satisfies the ground-truth expectation "
        f"(correct data, right analysis, concrete specifics). Ignore minor wording."
    )
    return _judge(prompt)


def score_logical_consistency(q, trace_summary, answer):
    prompt = (
        f"METRIC: logical_consistency (reference-free)\n"
        f"Question: {q}\n\n"
        f"Agent reasoning trace (tool calls, outcomes, and the rows/hits the agent saw):\n"
        f"{json.dumps(trace_summary, indent=2, default=str)[:8000]}\n\n"
        f"Final answer:\n{answer}\n\n"
        f"Score whether the tool selection, intermediate results, and final answer "
        f"are internally coherent and the answer is grounded in the tool outputs "
        f"(no unsupported claims, no contradiction, appropriate tools for the question)."
    )
    return _judge(prompt)


def run(dataset_path=DATASET, role=None, only=None, verbose=True):
    role = role or config.DEFAULT_ROLE
    items = yaml.safe_load(Path(dataset_path).read_text())
    if only:
        items = [it for it in items if it["id"] == only]
    results = []
    for it in items:
        if verbose:
            print(f"\n=== {it['id']}: {it['query']}", file=sys.stderr)
        out = agent.run(it["query"], role=role, verbose=verbose)
        answer, transcript = out["answer"], out["transcript"]
        tools_used = _tools_used(transcript)
        trace = _trace_summary(transcript)

        ac = score_answer_correctness(it["query"], it["ground_truth"], answer, tools_used)
        lc = score_logical_consistency(it["query"], trace, answer)
        expected = it.get("expected_tools", [])
        routing_ok = set(expected).issubset(set(tools_used)) if expected else None

        results.append({
            "id": it["id"], "query": it["query"], "role": role,
            "expected_tools": expected, "tools_used": tools_used,
            "routing_ok": routing_ok,
            "answer_correctness": ac, "logical_consistency": lc,
            "answer": answer, "trace": trace,
        })
    return results


def _avg(results, metric):
    return sum(r[metric]["score"] for r in results) / len(results) if results else 0.0


def print_report(results):
    print("\n" + "=" * 78)
    print("AGENT EVALUATION REPORT")
    print("=" * 78)
    hdr = f"{'question':<26} {'route':>5} {'correct':>8} {'logic':>6} {'pass':>5}"
    print(hdr)
    print("-" * 78)
    for r in results:
        ac, lc = r["answer_correctness"]["score"], r["logical_consistency"]["score"]
        passed = ac >= PASS_THRESHOLD and lc >= PASS_THRESHOLD
        route = "ok" if r["routing_ok"] else ("-" if r["routing_ok"] is None else "MISS")
        print(f"{r['id']:<26} {route:>5} {ac:>8.2f} {lc:>6.2f} {('Y' if passed else 'N'):>5}")
    print("-" * 78)
    ac_avg, lc_avg = _avg(results, "answer_correctness"), _avg(results, "logical_consistency")
    n_pass = sum(1 for r in results
                 if r["answer_correctness"]["score"] >= PASS_THRESHOLD
                 and r["logical_consistency"]["score"] >= PASS_THRESHOLD)
    print(f"{'AVERAGE':<26} {'':>5} {ac_avg:>8.2f} {lc_avg:>6.2f}")
    print(f"\nPassed (both >= {PASS_THRESHOLD}): {n_pass}/{len(results)}")


def main():
    ap = argparse.ArgumentParser(description="Evaluate the Postgres AI agent.")
    ap.add_argument("--role", default=config.DEFAULT_ROLE)
    ap.add_argument("--only", default=None, help="Run a single question id.")
    ap.add_argument("--out", default="eval_results.json", help="Write full JSON here.")
    args = ap.parse_args()

    results = run(role=args.role, only=args.only)
    print_report(results)
    Path(args.out).write_text(json.dumps(results, indent=2, default=str))
    print(f"\nFull results + rationales written to {args.out}")


if __name__ == "__main__":
    main()
