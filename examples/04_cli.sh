#!/usr/bin/env bash
# Drive the native needle CLI directly. Useful as a smoke test in CI or for
# in-process integration from non-Python runtimes.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
NEEDLE="$ROOT/bin/macos-arm64/needle"
TOOLS="$ROOT/fixtures/tools/lights.json"
[ -x "$NEEDLE" ] || { echo "missing $NEEDLE — run scripts/bootstrap.sh"; exit 1; }
[ -f "$TOOLS" ] || { echo "missing $TOOLS"; exit 1; }

echo "## 1) Empty toolset, asks a non-tool question"
echo '[]' > /tmp/_empty.json
"$NEEDLE" --tools /tmp/_empty.json --prompt "what time is it in Tokyo?" --max 64
echo

echo "## 2) Canonical tool call"
"$NEEDLE" --tools "$TOOLS" --prompt "dim the living room to 30" --max 128
echo

echo "## 3) Extraction (single declared schema)"
SCHEMA="$ROOT/fixtures/tools/receipt.json"
"$NEEDLE" --tools "$SCHEMA" \
  --prompt "GreenMart receipt: oat milk 3.50, total 7.75 paid by visa" \
  --max 128
echo

echo "## 4) Off-topic (should refuse)"
"$NEEDLE" --tools "$TOOLS" --prompt "tell me a joke about cats" --max 64
