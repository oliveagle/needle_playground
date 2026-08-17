"""End-to-end harness check: every reported scenario should be replayable in a unit test.

This keeps the eval JSONL fixtures honest without re-running the (slow) Needle
engine for every regression.  We freeze one deterministic per-row output via
`FakeRunner` and confirm the harness yields the right Result.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from eval.needle_eval.models import Result, Scenario, load_corpus, load_jsonl
from eval.needle_eval.scoring import aggregate, score


# ---------------------------------------------------------------------------
# Fake runner — the contract tests rely on this, not on a real engine.
# ---------------------------------------------------------------------------
class FakeRunner:
    """A runner that returns canned outputs keyed by scenario id."""

    def __init__(self, fixtures: dict[str, dict]):
        self.fixtures = fixtures
        self.calls: list[str] = []

    def __call__(self, scenario: Scenario, *, max_new_tokens: int = 128) -> Result:
        self.calls.append(scenario.id)
        if scenario.id not in self.fixtures:
            return Result(scenario.id, scenario.category, scenario.severity,
                          passed=False, score=0.0,
                          notes=[f"no fixture for {scenario.id}"],
                          error="no-fixture")
        return score(scenario, self.fixtures[scenario.id])


def test_fake_runner_satisfies_off_topic_contract():
    runner = FakeRunner({
        "ot01-no-tools-defined": {"function_calls": [], "confidence": 1.0,
                                  "peak_ram_mb": 25.0},
        "ot02-joke-with-lights-schema": {"function_calls": [], "confidence": 0.8,
                                          "peak_ram_mb": 25.0},
        "ot03-life-meaning": {"function_calls": [], "confidence": 0.6,
                              "peak_ram_mb": 25.0},
        "ot04-recipe-with-receipt-schema": {"function_calls": [], "confidence": 0.8,
                                            "peak_ram_mb": 25.0},
        "ot05-math-out-of-scope": {"function_calls": [], "confidence": 0.4,
                                   "peak_ram_mb": 25.0},
    })
    scenarios = [s for s in load_corpus() if s.category == "off_topic"]
    results = [runner(s) for s in scenarios]
    assert all(r.passed for r in results), [r.notes for r in results]
    assert runner.calls == [s.id for s in scenarios]


def test_aggregate_uses_fake_runner_to_summarise():
    runner = FakeRunner({
        "x1": {"function_calls": [], "confidence": 1.0},
        "x2": {"function_calls": [], "confidence": 0.0},
    })
    scenarios = [
        Scenario(id="x1", category="a", severity="smoke", tools=None,
                 system=None, prompt="hi",
                 expect=__import__("eval.needle_eval.models", fromlist=["Expect"]).Expect(
                     kind=__import__("eval.needle_eval.models", fromlist=["ExpectKind"]).ExpectKind.EMPTY)),
        Scenario(id="x2", category="a", severity="smoke", tools=None,
                 system=None, prompt="",
                 expect=__import__("eval.needle_eval.models", fromlist=["Expect"]).Expect(
                     kind=__import__("eval.needle_eval.models", fromlist=["ExpectKind"]).ExpectKind.ANY,
                     min_confidence=0.5)),
    ]
    results = [runner(s) for s in scenarios]
    summary = aggregate(results)
    assert summary["passed"] == 1
    assert summary["by_category"]["a"]["failures"] == ["x2"]
