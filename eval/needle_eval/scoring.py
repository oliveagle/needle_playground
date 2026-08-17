"""Pure scoring logic.  No I/O, no side effects.  Easy to unit-test."""
from __future__ import annotations

from typing import Any

from .models import Expect, ExpectKind, Result, Scenario


def _subset_match(expected: dict, actual: dict, *, loose: bool = True) -> tuple[bool, list[str]]:
    """Return (match, [notes]).

    With loose=True we allow actual extras that the model emitted and the
    schema allows (e.g. `validation: {...}`).  We require every expected key
    to be present and equal (with float tolerance for numbers).
    """
    notes: list[str] = []
    if expected is None:
        return True, notes
    for k, v in expected.items():
        if k not in actual:
            notes.append(f"missing key {k!r}")
            continue
        av = actual[k]
        if isinstance(v, (int, float)) and isinstance(av, (int, float)):
            if abs(av - v) > 0.05 * max(1.0, abs(v)):
                notes.append(f"field {k!r}: {av} != expected {v}")
        elif v != av:
            notes.append(f"field {k!r}: {av!r} != expected {v!r}")
    ok = not notes
    return ok, notes


def _first_call(out: dict) -> dict | None:
    calls = out.get("function_calls") or []
    return calls[0] if calls else None


def score(scenario: Scenario, out: dict | None) -> Result:
    """Compare the engine output to the scenario's expectation.

    The function never raises; engine failures are recorded in `error` and
    produce a failing Result so callers can still aggregate.
    """
    notes: list[str] = []
    if out is None:
        return Result(
            scenario_id=scenario.id, category=scenario.category,
            severity=scenario.severity, passed=False, score=0.0,
            notes=["engine returned no output"], error="no-output",
        )

    exp: Expect = scenario.expect
    calls = out.get("function_calls") or []
    confidence = float(out.get("confidence") or 0.0)
    peak = float(out.get("peak_ram_mb") or 0.0)

    kind_ok = True
    if exp.kind is ExpectKind.EMPTY:
        if calls:
            notes.append(f"expected empty, got {len(calls)} calls")
            kind_ok = False
    elif exp.kind is ExpectKind.CALL:
        if not calls:
            notes.append("expected call, got none")
            kind_ok = False
        else:
            first = _first_call(out)
            if exp.name and (first or {}).get("name") != exp.name:
                notes.append(
                    f"expected first call name={exp.name}, got "
                    f"{(first or {}).get('name')!r}"
                )
                kind_ok = False
            args_ok, arg_notes = _subset_match(exp.args or {}, (first or {}).get("arguments") or {})
            notes.extend(arg_notes)
            if not args_ok:
                kind_ok = False
    elif exp.kind is ExpectKind.RESPOND:
        if out.get("type") != "respond":
            notes.append(f"expected respond, got {out.get('type')!r}")
            kind_ok = False

    confidence_ok = confidence >= exp.min_confidence
    if not confidence_ok:
        notes.append(f"confidence {confidence:.3f} < {exp.min_confidence:.3f}")

    ram_ok = peak <= exp.max_peak_ram_mb
    if not ram_ok and peak:
        notes.append(f"peak_ram_mb {peak:.1f} > {exp.max_peak_ram_mb:.1f}")

    passed = kind_ok and confidence_ok and ram_ok
    score_val = confidence if passed else min(confidence, 0.5 * confidence)
    return Result(
        scenario_id=scenario.id,
        category=scenario.category,
        severity=scenario.severity,
        passed=passed,
        score=score_val,
        notes=notes,
        raw=out,
        peak_ram_mb=peak or None,
        error=None,
    )


def aggregate(results: list[Result]) -> dict[str, Any]:
    """Reduce a list of results into a per-category and overall summary."""
    if not results:
        return {"total": 0, "passed": 0, "score": 0.0, "by_category": {}}

    by_cat: dict[str, dict[str, Any]] = {}
    for r in results:
        bucket = by_cat.setdefault(
            r.category, {"total": 0, "passed": 0, "score_sum": 0.0, "failures": []}
        )
        bucket["total"] += 1
        bucket["score_sum"] += r.score
        if r.passed:
            bucket["passed"] += 1
        else:
            bucket["failures"].append(r.scenario_id)
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "score": sum(r.score for r in results) / len(results),
        "by_category": {
            cat: {
                "total": b["total"],
                "passed": b["passed"],
                "score": b["score_sum"] / b["total"],
                "failures": b["failures"],
            }
            for cat, b in by_cat.items()
        },
    }
    return summary
