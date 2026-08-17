"""End-to-end harness check: every reported scenario should be replayable in a unit test.

This keeps the eval JSONL fixtures honest without re-running the (slow) Needle
engine for every regression.  We freeze one deterministic per-row output via
`FakeRunner` and confirm the harness yields the right Result.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from eval.needle_eval.models import Expect, ExpectKind, Result, Scenario, load_corpus
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


def _empty_pass() -> dict:
    return {"function_calls": [], "confidence": 1.0, "peak_ram_mb": 25.0}


@pytest.mark.parametrize("category", ["off_topic"])
def test_runner_satisfies_off_topic_contract(category):
    """For every off_topic scenario, returning [] should satisfy ExpectKind.EMPTY or ANY."""
    scenarios = [s for s in load_corpus() if s.category == category]
    assert scenarios, "corpus must contain off_topic scenarios"
    runner = FakeRunner({s.id: _empty_pass() for s in scenarios})
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
                 expect=Expect(kind=ExpectKind.EMPTY)),
        Scenario(id="x2", category="a", severity="smoke", tools=None,
                 system=None, prompt="",
                 expect=Expect(kind=ExpectKind.ANY, min_confidence=0.5)),
    ]
    results = [runner(s) for s in scenarios]
    summary = aggregate(results)
    assert summary["passed"] == 1
    assert summary["by_category"]["a"]["failures"] == ["x2"]


def test_corpus_total_matches_documented_count():
    """The repo documents 82 scenarios; assert it stays within a sane band."""
    scenarios = load_corpus()
    assert 70 <= len(scenarios) <= 200, (
        f"corpus size {len(scenarios)} is outside the documented band; "
        "update CAPABILITIES.md and README before merging."
    )
