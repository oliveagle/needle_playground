"""CLI entry point for the eval harness.

Usage:
    python -m needle_eval.cli scenarios/ --runner cli
    python -m needle_eval.cli scenarios/ --runner python --max-new-tokens 96
    python -m needle_eval.cli scenarios/ --runner cli --filter extraction --json report.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .models import load_corpus
from .runners import CLIRunner, PythonRunner
from .scoring import aggregate


def _make_runner(kind: str) -> object:
    kind = kind.lower()
    if kind == "cli":
        bin_path = Path(__file__).resolve().parents[2] / "bin" / "macos-arm64" / "needle"
        if not bin_path.exists():
            raise SystemExit(f"CLI binary missing at {bin_path}")
        return CLIRunner(bin_path)
    if kind == "python":
        return PythonRunner()
    raise SystemExit(f"unknown runner: {kind}")


def _filter(scenarios, args):
    if args.category:
        scenarios = [s for s in scenarios if s.category == args.category]
    if args.id:
        scenarios = [s for s in scenarios if s.id == args.id]
    if args.severity:
        scenarios = [s for s in scenarios if s.severity == args.severity]
    return scenarios


def _print_summary(summary: dict) -> None:
    print("\n=== Summary ===")
    print(f"total={summary['total']}  passed={summary['passed']}  "
          f"avg-score={summary['score']:.3f}")
    for cat, b in sorted(summary["by_category"].items()):
        print(f"  {cat:>16}: {b['passed']}/{b['total']} (avg {b['score']:.3f})"
              + (f"  failures={b['failures']}" if b["failures"] else ""))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="needle_eval")
    p.add_argument("corpus", type=Path, nargs="?", default="scenarios")
    p.add_argument("--runner", choices=("cli", "python"), default="cli")
    p.add_argument("--max-new-tokens", type=int, default=128)
    p.add_argument("--category", help="only run scenarios in this category")
    p.add_argument("--severity", help="only run scenarios of this severity")
    p.add_argument("--id", help="only run this scenario id")
    p.add_argument("--json", type=Path, help="write a JSON report to this path")
    p.add_argument("--markdown", type=Path, help="write a Markdown report")
    p.add_argument("--quiet", action="store_true", help="suppress per-row output")
    args = p.parse_args(argv)

    runner = _make_runner(args.runner)
    corpus = load_corpus(args.corpus)
    corpus = _filter(corpus, args)
    if not corpus:
        print(f"no scenarios match filter (root={args.corpus})", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"running {len(corpus)} scenario(s) via {args.runner}")

    start = time.perf_counter()
    results = [runner(s, max_new_tokens=args.max_new_tokens) for s in corpus]
    duration = time.perf_counter() - start

    summary = aggregate(results)
    summary["duration_seconds"] = duration
    summary["runner"] = args.runner

    if not args.quiet:
        for r in results:
            mark = "PASS" if r.passed else "FAIL"
            print(f"  [{mark}] {r.scenario_id:<32} score={r.score:.3f} "
                  f"({'; '.join(r.notes[:3]) or 'ok'})")

    _print_summary(summary)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(
            {"summary": summary, "results": [r.to_dict() for r in results]},
            indent=2,
        ))
        print(f"wrote {args.json}")

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(_to_markdown(summary, [r.to_dict() for r in results]))
        print(f"wrote {args.markdown}")

    return 0 if summary["passed"] == summary["total"] else 1


def _to_markdown(summary: dict, results: list[dict]) -> str:
    lines = ["# Needle 2 Eval Report", ""]
    lines.append(f"- runner: `{summary['runner']}`")
    lines.append(f"- duration: {summary['duration_seconds']:.1f}s")
    lines.append(f"- total / passed / avg-score: **{summary['total']}** / "
                 f"**{summary['passed']}** / {summary['score']:.3f}")
    lines.append("")
    lines.append("## By category")
    lines.append("")
    lines.append("| category | passed | total | avg-score |")
    lines.append("|---|---|---|---|")
    for cat, b in sorted(summary["by_category"].items()):
        lines.append(f"| {cat} | {b['passed']} | {b['total']} | {b['score']:.3f} |")
    lines.append("")
    lines.append("## Failures")
    fail = [r for r in results if not r["passed"]]
    if fail:
        lines.append("")
        for r in fail:
            lines.append(f"- **{r['scenario_id']}** ({r['category']}): "
                         + "; ".join(r["notes"][:3]))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
