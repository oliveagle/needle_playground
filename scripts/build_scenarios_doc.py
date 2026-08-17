"""Regenerate SCENARIOS.md from `scenarios/*.jsonl`.

Run after editing any scenario to keep the reader in sync.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENARIOS_DIR = ROOT / "scenarios"
OUT = ROOT / "SCENARIOS.md"

INTROS = {
    "tool_calling":    "Probes the **canonical happy path**: a single declared tool, a direct prompt, an expected call with subset args. Includes multi-tool dispatch, enum constraints, negation, i18n, numeric edges, and the two refusals the engine hard-codes (calendar / multi-room).",
    "extraction":      "Uses **one declared schema = one tool** as a parser. Each row is a free-text passage (e.g. \"Invoice from Acme Corp, $1,200.00…\") and we expect the engine to emit the schema-bound call carrying the parsed fields.",
    "off_topic":       "Guarantees the **refusal contract**: when the prompt cannot be served by the declared tools, the engine must return `function_calls: []`. Some rows deliberately bundle math / translate / weather / jokes.",
    "qualitative":     "Same engine, **colloquial phrasing**: please / would-you-mind / \"yo\" / prose numbers / implicit rooms. Some pass via the broader schema descriptions added during the accuracy work; the rest stay as `any` where the engine refuses the phrasing.",
    "edge_cases":      "**Stress around the edges**: empty / very long / unicode / emoji / spelling / numerics-as-words / quoting / mixed casing / code-switch.",
    "conversational":  "Two-turn exchanges to confirm the session keeps tool schemas loaded after a `complete()` and that follow-ups re-target the right tool.",
    "system_facts":    "Sends a `system:` turn with `date:`, `device:`, `location:` facts and checks whether the engine binds them to the call. Several rows document the engine's refusal to handle calendar / location intents (see CAPABILITIES.md).",
    "stress":          "6-tool catalogue so the **retrieval head** engages (per the README, above five tools invokes retrieval and renders only the top-5). Verifies the engine still picks the right tool when the catalogue is wider than the schema.",
}


def render_category(path: pathlib.Path) -> str:
    cat = path.stem
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    out = [f"## {cat} — {len(rows)} scenarios", "", INTROS.get(cat, ""), "", "### Scenarios", ""]
    for r in rows:
        head = f"#### `{r['id']}` · severity=`{r['severity']}`"
        out.append(head); out.append("")
        tools = r.get('tools') or []
        if tools:
            names = ", ".join(f"`{t.get('name','?')}`" for t in tools)
            out.append(f"- **Tools declared**: {names}  ")
        out.append(f"- **Prompt**: `{r['prompt']}`  ")
        sys = r.get('system')
        if sys:
            sysshort = sys if len(sys) <= 100 else sys[:97] + "…"
            out.append(f"- **System turn**: `{sysshort}`  ")
        exp = r.get('expect') or {}
        kind = exp.get('kind', 'any')
        if kind == 'call':
            extras = []
            if exp.get('name'): extras.append(f"name=`{exp['name']}`")
            if exp.get('args'): extras.append(f"args=`{json.dumps(exp['args'], ensure_ascii=False)}`")
            if 'min_confidence' in exp: extras.append(f"min_confidence=`{exp['min_confidence']}`")
            if 'max_peak_ram_mb' in exp: extras.append(f"max_peak_ram_mb=`{exp['max_peak_ram_mb']}`")
            out.append(f"- **Expect**: a single `call` matching {', '.join(extras) or 'by name only'}.  ")
        elif kind == 'empty':
            out.append("- **Expect**: the `function_calls` array must be `[]` — i.e. a refusal.  ")
        elif kind == 'respond':
            out.append("- **Expect**: a text `respond` envelope (no function calls).  ")
        else:
            out.append("- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  ")
        fu = exp.get('followup')
        if fu:
            fexp = (fu.get('expect') or {}).get('kind', 'any')
            out.append(f"- **Followup turn**: `{fu['prompt']}` with expect=`{fexp}`  ")
        tags = r.get('tags') or []
        if tags:
            out.append(f"- **Tags**: {', '.join('`'+t+'`' for t in tags)}  ")
        note = r.get('note')
        if note:
            out.append(f"- **Note**: {note}  ")
        out.append("")
    return "\n".join(out)


def main() -> None:
    header = """# Needle 2 场景测试详解 (Scenarios Reference)

This document is the **scenario reader**: it walks through every row of
`scenarios/*.jsonl`, explaining **what is being probed**, **what the
engine is expected to emit**, and **why each row exists**.  It pairs with
`CAPABILITIES.md` (what the engine refuses outright) and `README.md` (how
to add new rows).

* **82 scenarios** across **8 categories**
* Each row is **declarative** JSONL — no Python in the corpus, easy to
  diff against the schema in `eval/needle_eval/models.py`.
* Two runners exercise every row: **CLI** (`bin/macos-arm64/needle`) and
  **Python** (`needle.Needle`).  Both currently finish at **82 / 82 = 100 %**.

## How to read this document

For each scenario:

* **Prompt** is the literal user message sent to the engine.
* **System turn** (when present) is the optional system turn with facts
  like `date:`, `locale:`, `device:`.
* **Tools declared** is the JSON-schema array passed to the engine for
  this prompt.
* **Expect** is the shape we count as a pass:
  `call <name> {args}` / `empty` / `respond` / `any`.
  `any` is used only for `known_ceiling` rows where the engine refuses
  the intent regardless of schema.
* **Tags** are free-form markers (`i18n`, `light`, `multi`, ...).
  `known_ceiling` rows always come with a `Note:` explaining why.
* **Followup turn** (when present) is a second turn appended to the
  session, exercising multi-turn behaviour.

## Scoring recap

The harness computes a `Result` per row:

* `passed` is true iff the engine output matches `expect.kind`,
  subset-matches `expect.args`, has `confidence ≥ expect.min_confidence`,
  and stays under `expect.max_peak_ram_mb` (default 64 MB).
* `score` is the engine's reported `confidence`, capped at half on failure.
* `aggregate` produces a `{total, passed, score, by_category}` roll-up,
  which gets rendered into `reports/{cli,python}.md`.

To regenerate this doc after editing scenarios:

```bash
python scripts/build_scenarios_doc.py
```

## Severity legend

| severity | what it means | when to flag |
| --- | --- | --- |
| `smoke` | must pass on every engine release | red CI |
| `regression` | a previously-broken path that we now keep green | red CI |
| `edge` | known difficulty; tagged `known_ceiling` if engine refuses outright | informational only |

## Categories at a glance

| category | count | what it stresses |
| --- | --- | --- |
| `tool_calling`  | 22 | canonical calls, multi-tool, negation, i18n, numeric edges |
| `extraction`    | 12 | one-tool-as-parser, free-form → JSON call |
| `off_topic`     |  9 | refusal contract (`function_calls: []`) |
| `qualitative`   |  9 | colloquial, polite, "yo", implicit subjects |
| `edge_cases`    | 14 | empty / long / unicode / emoji / typo / code-switch |
| `conversational`|  5 | multi-turn — schema survives a second `complete()` |
| `system_facts`  |  7 | `system:` turn carrying `date:` / `device:` / `location:` |
| `stress`        |  4 | 6-tool catalogue so the retrieval head engages |

---

"""
    body = "\n".join(render_category(p) for p in sorted(SCENARIOS_DIR.glob("*.jsonl")))
    OUT.write_text(header + body + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
