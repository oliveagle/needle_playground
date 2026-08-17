"""Tests for the eval framework itself: loading JSONL, scoring, aggregation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.needle_eval.models import (
    Expect, ExpectKind, Followup, Scenario, category_counts, load_corpus, load_jsonl,
)
from eval.needle_eval.scoring import _subset_match, aggregate, score


# ---------------------------------------------------------------------------
# Scenario loader
# ---------------------------------------------------------------------------
def test_load_corpus_returns_every_scenario(tmp_path: Path):
    rows = [
        {"id": "a", "category": "tool_calling", "severity": "smoke",
         "tools": [], "prompt": "x", "expect": {"kind": "empty"}},
        {"id": "b", "category": "extraction", "severity": "smoke",
         "tools": [{"name": "x"}], "prompt": "y",
         "expect": {"kind": "call", "name": "x"}},
    ]
    p = tmp_path / "c.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    scenarios = list(load_jsonl(p))
    assert [s.id for s in scenarios] == ["a", "b"]
    assert category_counts(scenarios) == {"tool_calling": 1, "extraction": 1}


def test_load_jsonl_skips_blank_and_comment_lines(tmp_path: Path):
    p = tmp_path / "c.jsonl"
    p.write_text(
        "# schema doc line, not a scenario\n"
        "\n"
        '{"id":"a","prompt":"x","expect":{"kind":"any"}}\n'
    )
    scenarios = list(load_jsonl(p))
    assert len(scenarios) == 1
    assert scenarios[0].id == "a"


def test_load_jsonl_rejects_invalid_lines(tmp_path: Path):
    p = tmp_path / "c.jsonl"
    p.write_text('{"id":"a","prompt":"x"}\nbroken-not-json\n')
    with pytest.raises(ValueError):
        list(load_jsonl(p))


def test_corpus_loader_accepts_directory(Path=Path):
    """load_corpus() can take a directory and walk it."""
    scenarios = load_corpus()
    ids = [s.id for s in scenarios]
    # Spot-check that categories we know we wrote are present.
    assert any(s.category == "tool_calling" for s in scenarios)
    assert "tc01-dim-living-room" in ids
    # Sorted by id; assertion above is unconditional.
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Scenario.from_dict
# ---------------------------------------------------------------------------
def test_scenario_from_dict_defaults():
    raw = {"id": "foo", "prompt": "bar"}
    s = Scenario.from_dict(raw)
    assert s.category == "uncategorised"
    assert s.severity == "smoke"
    assert s.tags == ()
    assert s.expect.kind is ExpectKind.ANY
    assert s.expect.followup is None


def test_scenario_from_dict_followup_unwrapped():
    raw = {"id": "foo", "prompt": "x", "expect": {
        "kind": "call", "name": "x",
        "followup": {"prompt": "y", "expect": {"kind": "empty"}},
    }}
    s = Scenario.from_dict(raw)
    assert s.expect.followup is not None
    assert s.expect.followup.prompt == "y"
    assert s.expect.followup.expect.kind is ExpectKind.EMPTY


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _scenario(**kw):
    base = dict(id="s1", category="tool_calling", severity="smoke",
                tools=None, system=None, prompt="x",
                expect=Expect(kind=ExpectKind.ANY))
    base.update(kw)
    return Scenario(**base)


def test_score_call_match_with_subtle_arg():
    s = _scenario(expect=Expect(
        kind=ExpectKind.CALL, name="set_lights",
        args={"room": "living room", "brightness": 30},
        min_confidence=0.5,
    ))
    out = {"type": "call", "function_calls": [{
        "name": "set_lights",
        "arguments": {"room": "living room", "brightness": 30, "on": True},
    }], "confidence": 0.9, "peak_ram_mb": 25.0}
    res = score(s, out)
    assert res.passed, res.notes
    assert res.notes == []


def test_score_call_fails_when_args_disagree():
    s = _scenario(expect=Expect(
        kind=ExpectKind.CALL, name="set_lights", args={"brightness": 30},
    ))
    out = {"function_calls": [{
        "name": "set_lights",
        "arguments": {"brightness": 50, "on": True},
    }], "confidence": 0.9}
    res = score(s, out)
    assert not res.passed
    assert any("brightness" in n for n in res.notes)


def test_score_empty_when_expected_empty():
    s = _scenario(expect=Expect(kind=ExpectKind.EMPTY))
    out = {"function_calls": [], "confidence": 1.0}
    res = score(s, out)
    assert res.passed, res.notes


def test_score_empty_fails_when_calls_returned():
    s = _scenario(expect=Expect(kind=ExpectKind.EMPTY))
    out = {"function_calls": [{"name": "x", "arguments": {}}],
           "confidence": 0.9}
    res = score(s, out)
    assert not res.passed


def test_score_records_low_confidence_as_failure():
    s = _scenario(expect=Expect(kind=ExpectKind.ANY, min_confidence=0.7))
    out = {"confidence": 0.1}
    res = score(s, out)
    assert not res.passed
    assert any("confidence" in n for n in res.notes)


def test_score_handles_engine_no_output():
    s = _scenario()
    res = score(s, None)
    assert not res.passed
    assert res.error == "no-output"


def test_subset_match_is_loose_on_extras():
    ok, notes = _subset_match({"brightness": 30}, {"brightness": 30, "room": "x"})
    assert ok
    assert notes == []


def test_aggregate_counts_failures_per_category():
    from eval.needle_eval.models import Result
    res = [
        Result("a", "tool_calling", "smoke", True, 0.9),
        Result("b", "tool_calling", "smoke", False, 0.2,
               notes=["nope"]),
        Result("c", "extraction", "smoke", True, 0.5),
    ]
    summary = aggregate(res)
    assert summary["total"] == 3
    assert summary["passed"] == 2
    assert summary["score"] == pytest.approx((0.9 + 0.2 + 0.5) / 3, rel=1e-3)
    assert summary["by_category"]["tool_calling"]["failures"] == ["b"]
