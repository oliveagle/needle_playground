"""Pluggable runners: invoke Needle through the CLI or the Python API."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .models import Result, Scenario


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------
class CLIRunner:
    """Drive the bundled native needle CLI on macOS ARM64.

    Why two runners?  The CLI bakes a different default tool-discovery path
    (uses our fetched asset), so testing both guards against drift between
    the wheel distribution and the binary distribution Needle ships.
    """

    def __init__(self, bin_path: str | Path) -> None:
        self.bin = Path(bin_path)
        if not self.bin.exists():
            raise FileNotFoundError(self.bin)

    def __call__(self, scenario: Scenario, *, max_new_tokens: int = 128) -> Result:
        notes: list[str] = []
        cmd: list[str] = [str(self.bin)]
        if scenario.tools is not None:
            tools_path = Path("/tmp") / f"needle_tools_{scenario.id}.json"
            tools_path.write_text(json.dumps(scenario.tools))
            cmd += ["--tools", str(tools_path)]
        else:
            cmd += ["--tools", "/tmp/needle_tools_empty.json"]
            Path("/tmp/needle_tools_empty.json").write_text("[]")
        if scenario.system:
            cmd += ["--system", scenario.system]
        cmd += ["--prompt", scenario.prompt, "--max", str(max_new_tokens)]
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if proc.returncode != 0:
                return Result(
                    scenario_id=scenario.id, category=scenario.category,
                    severity=scenario.severity, passed=False, score=0.0,
                    notes=[f"exit={proc.returncode}", proc.stderr[:300]],
                    error="cli-failed", latency_ms=elapsed_ms,
                )
            line = proc.stdout.strip().splitlines()[-1]
            out = json.loads(line)
        except subprocess.TimeoutExpired:
            return Result(
                scenario_id=scenario.id, category=scenario.category,
                severity=scenario.severity, passed=False, score=0.0,
                notes=["timeout"], error="timeout",
            )
        except (json.JSONDecodeError, IndexError) as e:
            return Result(
                scenario_id=scenario.id, category=scenario.category,
                severity=scenario.severity, passed=False, score=0.0,
                notes=[f"decode: {e!r}", proc.stdout[:200]],
                error="decode",
            )
        from .scoring import score as score_fn  # avoid circular at module top
        result = score_fn(scenario, out)
        result.latency_ms = elapsed_ms
        return result


# ---------------------------------------------------------------------------
# Python runner
# ---------------------------------------------------------------------------
class PythonRunner:
    """Drive Needle via the cactus-needle Python package.

    Uses the same engine binary on disk (dylib in bin/macos-arm64/lib/), and
    mirrors the CLI by reinitialising for every scenario so tool schemas
    don't leak between rows.
    """

    def __init__(self) -> None:
        try:
            import needle  # noqa: F401
        except Exception as e:  # pragma: no cover
            raise RuntimeError("cactus-needle is not installed") from e

    def _run_once(self, scenario: Scenario, *, max_new_tokens: int) -> Result:
        import needle
        notes: list[str] = []
        if scenario.tools:
            agent = needle.Needle(
                tools=scenario.tools,
                system=scenario.system,
            )
        else:
            agent = needle.Needle(tools=[], system=scenario.system or None)

        start = time.perf_counter()
        try:
            out = agent.complete(scenario.prompt, max_new_tokens=max_new_tokens)
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return Result(
                scenario_id=scenario.id, category=scenario.category,
                severity=scenario.severity, passed=False, score=0.0,
                notes=[repr(e)], error="engine-exception",
                latency_ms=elapsed_ms,
            )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        # `complete()` returns a "call" envelope; `run()` returns a "respond"
        # after executing the tool.  We expose the structured call shape to
        # the scorer; runner-specific semantics live in the test layer.
        from .scoring import score as score_fn
        result = score_fn(scenario, out)
        result.latency_ms = elapsed_ms
        return result

    def __call__(self, scenario: Scenario, *, max_new_tokens: int = 128) -> Result:
        return self._run_once(scenario, max_new_tokens=max_new_tokens)
