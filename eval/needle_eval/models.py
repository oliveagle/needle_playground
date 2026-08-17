"""Scenario schema and result envelope for Needle 2 evaluation.

A *scenario* is a single declarative row in a JSONL corpus. Each scenario
describes the prompt, the tool schema, and the expected engine output.
The runner reads a scenario, invokes Needle, and produces a *result*
record describing what actually happened and how it scored.

Keeping these as plain dataclasses means the schema is explicit and the
runner can be diff'd against model updates by hand.
"""
from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator


# ---------------------------------------------------------------------------
# Schema version (bump when Scenario/Expect shape changes incompatibly)
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 1


class ExpectKind(str, enum.Enum):
    CALL = "call"          # expect at least one function_calls[0] matching
    EMPTY = "empty"        # expect function_calls == []
    RESPOND = "respond"    # expect type=="respond" (text answer, no calls)
    ANY = "any"            # only structural checks (latency, ram)


@dataclass(frozen=True)
class Expect:
    """The expectation block.  Each field narrows the assertion further."""
    kind: ExpectKind = ExpectKind.ANY
    name: str | None = None                  # required for kind=CALL
    args: dict | None = None                 # subset-match; missing keys OK
    min_confidence: float = 0.0              # gate against the engine score
    max_peak_ram_mb: float = 64.0            # generous default for the 28MB engine
    followup: "Followup | None" = None       # for conversational scenarios

    @classmethod
    def from_dict(cls, raw: dict | None) -> "Expect":
        raw = raw or {}
        followup = Followup.from_dict(raw["followup"]) if raw.get("followup") else None
        return cls(
            kind=ExpectKind(raw.get("kind", "any")),
            name=raw.get("name"),
            args=raw.get("args"),
            min_confidence=float(raw.get("min_confidence", 0.0)),
            max_peak_ram_mb=float(raw.get("max_peak_ram_mb", 64.0)),
            followup=followup,
        )


@dataclass(frozen=True)
class Followup:
    prompt: str
    expect: Expect

    @classmethod
    def from_dict(cls, raw: dict) -> "Followup":
        return cls(prompt=raw["prompt"], expect=Expect.from_dict(raw.get("expect", {})))


@dataclass(frozen=True)
class Scenario:
    id: str
    category: str
    severity: str
    tools: list[dict] | None           # raw JSON Schema tool declarations
    system: str | None
    prompt: str
    expect: Expect
    tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict) -> "Scenario":
        if "id" not in raw or "prompt" not in raw:
            raise ValueError(f"scenario missing required keys: {raw!r}")
        tags = tuple(raw.get("tags", []) or ())
        return cls(
            id=raw["id"],
            category=raw.get("category", "uncategorised"),
            severity=raw.get("severity", "smoke"),
            tools=raw.get("tools"),
            system=raw.get("system"),
            prompt=raw["prompt"],
            expect=Expect.from_dict(raw.get("expect")),
            tags=tags,
        )


@dataclass
class Result:
    """Per-scenario result returned by the runner."""
    scenario_id: str
    category: str
    severity: str
    passed: bool
    score: float                          # 0..1 confidence-weighted pass score
    notes: list[str] = field(default_factory=list)
    raw: dict | None = None               # raw engine output (JSON)
    latency_ms: int | None = None
    peak_ram_mb: float | None = None
    followup: "Result | None" = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "category": self.category,
            "severity": self.severity,
            "passed": self.passed,
            "score": self.score,
            "notes": list(self.notes),
            "latency_ms": self.latency_ms,
            "peak_ram_mb": self.peak_ram_mb,
            "error": self.error,
            "raw": self.raw,
            "followup": self.followup.to_dict() if self.followup else None,
        }


# ---------------------------------------------------------------------------
# Corpus loader
# ---------------------------------------------------------------------------

def load_jsonl(path: Path | str) -> Iterator[Scenario]:
    """Stream scenarios from a JSONL file.  Blank lines are skipped silently."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{p}:{lineno}: invalid JSON ({e})") from e
            yield Scenario.from_dict(raw)


def load_corpus(root: Path | str = "scenarios") -> list[Scenario]:
    """Load every *.jsonl file under `root`.  Returns sorted-by-id scenarios."""
    root = Path(root)
    out: list[Scenario] = []
    for path in sorted(root.glob("*.jsonl")):
        out.extend(load_jsonl(path))
    out.sort(key=lambda s: s.id)
    return out


def category_counts(scenarios: Iterable[Scenario]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in scenarios:
        counts[s.category] = counts.get(s.category, 0) + 1
    return counts
