"""Run the PlanB vs baseline evaluation.

Examples:
  python evaluation/run_eval.py --mock                         # pipeline test, no API key needed
  python evaluation/run_eval.py --methods direct,structured,planb,planb_gold --run-name qwen7b
  python evaluation/run_eval.py --scenarios s01_extend_known_cost --methods planb

Outputs (evaluation/results/<run-name>/): per_case.csv, summary.csv, summary.md, raw_outputs.jsonl, summary.png
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from baselines import run_llm_baseline, run_planb  # noqa: E402
from common import ROOT, load_scenarios  # noqa: E402
from metrics import score_case  # noqa: E402

from planb.llm import LLMClient  # noqa: E402

ALL_METHODS = ["direct", "structured", "planb", "planb_gold"]


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for m, g in df.groupby("method", sort=False):
        ok = g[g.expected_status == "ok"]
        inf = g[g.expected_status == "infeasible"]
        unknown_ids = {s for s, r in zip(g.scenario, g.get("cost_hallucinated", [None] * len(g))) if pd.notna(r)}
        unk = g[g.scenario.isin(unknown_ids)]
        known = ok[~ok.scenario.isin(unknown_ids)]
        rows.append({
            "method": m,
            "cases": len(g),
            "task_success": g.success.mean(),
            "json_valid": g.json_ok.mean(),
            "status_accuracy": g.status_correct.mean(),
            "feasibility_rate(ok cases)": ok.feasible.fillna(False).astype(float).mean() if len(ok) else None,
            "avg_hard_violations": ok.hard_violations.dropna().mean() if "hard_violations" in ok else None,
            "plan_preservation": ok.preservation.mean() if len(ok) else None,
            "booking_f1": ok.booking_f1.mean() if len(ok) else None,
            "cost_exact_match(known)": known.cost_correct.mean() if len(known) else None,
            "unknown_cost_handled": (~unk.cost_hallucinated.astype(bool)).mean() if len(unk) else None,
            "infeasible_detected": inf.status_correct.mean() if len(inf) else None,
            "unsafe_plan_refused": inf.success.mean() if len(inf) else None,
            "avg_latency_s": g.latency_s.mean(),
            "avg_tokens": g.tokens.mean(),
            "avg_llm_calls": g.llm_calls.mean(),
        })
    return pd.DataFrame(rows)


def plot(summary: pd.DataFrame, path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = ["task_success", "feasibility_rate(ok cases)", "plan_preservation", "booking_f1",
               "cost_exact_match(known)", "infeasible_detected"]
    labels = ["Task\nsuccess", "Feasibility", "Preservation", "Booking F1", "Cost exact", "Infeasible\ndetected"]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    n = len(summary)
    width = 0.8 / max(n, 1)
    colors = ["#9AA5B1", "#5B8DB8", "#2E7D5B", "#A3C9A8"]
    for i, (_, row) in enumerate(summary.iterrows()):
        vals = [float(row[m]) if pd.notna(row[m]) else 0 for m in metrics]
        xs = [j + (i - (n - 1) / 2) * width for j in range(len(metrics))]
        ax.bar(xs, vals, width=width * 0.95, label=row["method"], color=colors[i % len(colors)])
    ax.set_xticks(range(len(metrics)), labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("rate")
    ax.set_title(title)
    ax.legend(frameon=False, ncols=n, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", default=",".join(ALL_METHODS))
    ap.add_argument("--scenarios", default="", help="comma separated scenario ids")
    ap.add_argument("--split", default=None)
    ap.add_argument("--mock", action="store_true", help="force mock LLM (pipeline test only)")
    ap.add_argument("--run-name", default=None)
    args = ap.parse_args()

    llm = LLMClient(provider="mock") if args.mock else LLMClient()
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    scenarios = load_scenarios(args.split, [x for x in args.scenarios.split(",") if x] or None)
    run_name = args.run_name or (("mock-" if llm.is_mock else "") + datetime.now().strftime("%Y%m%d-%H%M%S"))
    out_dir = ROOT / "evaluation" / "results" / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"LLM: {llm.describe()} | methods: {methods} | scenarios: {len(scenarios)} -> {out_dir}")

    rows, raw = [], []
    for s in scenarios:
        for m in methods:
            if m == "direct":
                out = run_llm_baseline(s, llm, structured=False)
            elif m == "structured":
                out = run_llm_baseline(s, llm, structured=True)
            elif m == "planb":
                out = run_planb(s, llm)
            elif m == "planb_gold":
                out = run_planb(s, None, use_gold_event=True)
            else:
                raise SystemExit(f"unknown method {m}")
            row = score_case(s, out)
            rows.append(row)
            raw.append({"scenario": s.id, "method": m, "status": out.status, "cost_minor": out.cost_minor,
                        "affected_booking_ids": out.affected_booking_ids, "parse_method": out.parse_method,
                        "parsed_event": out.parsed_event, "error": out.error, "raw_text": out.raw_text,
                        "itinerary": [a.model_dump(mode="json") for a in out.trip.activities] if out.trip else None})
            print(f"  {s.id:40s} {m:11s} status={str(out.status):17s} success={row['success']}")

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "per_case.csv", index=False)
    summary = summarize(df)
    summary.to_csv(out_dir / "summary.csv", index=False)
    with open(out_dir / "raw_outputs.jsonl", "w") as f:
        for r in raw:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    header = (f"# Evaluation run `{run_name}`\n\n- LLM: {llm.describe()}\n- Scenarios: {len(scenarios)}\n"
              f"- Methods: {', '.join(methods)}\n")
    if llm.is_mock:
        header += ("\n> **MOCK RUN — pipeline test only.** Baselines return the unchanged itinerary; "
                   "these numbers are NOT experimental results.\n")
    (out_dir / "summary.md").write_text(header + "\n" + summary.round(3).to_markdown(index=False) + "\n")
    plot(summary, out_dir / "summary.png", f"PlanB vs baselines — {llm.describe()}")
    print("\n" + summary.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
