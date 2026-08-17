"""Measure the Chinese-prompt pass rate under different mitigation strategies.

Empirical findings (captured in CAPABILITIES.md):

  * Direct Chinese prompts + bilingual tool description: 40.7% (16 of 27 fail)
  * Same prompts translated to English first: ~85% (extrapolated)

This script illustrates the delta. It does NOT translate automatically — it
relies on a hand-curated dictionary so the script stays deterministic.
"""
from __future__ import annotations

import json, subprocess, tempfile
from pathlib import Path

import argparse

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "scenarios_zh"

# Hand-curated translations of every Chinese prompt.
TRANSLATIONS = {
    "zh-tc01-客厅调暗": "dim the living room to 30",
    "zh-tc02-关掉卧室灯": "turn off the bedroom lights",
    "zh-tc03-打开厨房灯": "turn on the kitchen light",
    "zh-tc04-调到半亮": "dim the bedroom to 50",
    "zh-tc05-关掉所有灯": "turn off all the lights",
    "zh-tc06-调到最暗": "dim the living room to the minimum",
    "zh-tc07-打开书房": "turn on the study light",
    "zh-tc08-把温度调到22": "set the thermostat to 22",
    "zh-tc09-播放爵士乐": "play some jazz music",
    "zh-tc10-给张三发短信": "text Sam: remember the meeting tomorrow",
    "zh-ex01-acme发票": "Acme invoice, total 1200 USD",
    "zh-ex02-globex欧元": "Globex invoice, total 2500 EUR",
    "zh-ex03-订单号": "DHL delivered parcel AB1234567890",
    "zh-ex04-金额": "the total is 99",
    "zh-ex05-收件邮箱": "email me at wang.lei@example.com",
    "zh-ot01-笑话": "tell me a joke",
    "zh-ot02-天气": "what's the weather in Beijing today?",
    "zh-ot03-数学": "what is 13 * 7?",
    "zh-ot04-翻译": "translate hello into Chinese",
    "zh-edge01-emoji": "💡 living room on",
    "zh-edge02-混合": "play some chill Chinese music",
    "zh-edge03-汉字错": "dim the living room to 30",
    "zh-edge04-口语化": "make the living room brighter",
    "zh-edge05-隐含": "turn it off",
    "zh-sf01-日期事实": "add a meeting tomorrow at 7pm",
    "zh-sf02-设备电量": "what's my battery at?",
    "zh-sf03-位置": "where am I?",
}


def run_needle(prompt: str, tool_json: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        f.write(tool_json); path = f.name
    out = subprocess.run([str(ROOT / "bin" / "macos-arm64" / "needle"),
                          "--tools", path, "--prompt", prompt, "--max", "128"],
                         capture_output=True, text=True, timeout=30)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--filter", help="only run scenarios whose id starts with this")
    args = p.parse_args()

    n_pass_zh = n_fail_zh = n_pass_en = n_fail_en = 0
    rows = []
    for path in sorted(CORPUS.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if not line.strip(): continue
            row = json.loads(line)
            sid = row["id"]
            if args.filter and not sid.startswith(args.filter):
                continue
            zh_pass = bool(run_needle(row["prompt"], json.dumps(row["tools"] or [])).get("function_calls"))
            en_prompt = TRANSLATIONS.get(sid)
            en_pass = None
            if en_prompt is not None:
                en_pass = bool(run_needle(en_prompt, json.dumps(row["tools"] or [])).get("function_calls"))
            rows.append((sid, zh_pass, en_pass))
            n_pass_zh += int(bool(zh_pass)); n_fail_zh += int(not zh_pass)
            if en_pass is not None:
                n_pass_en += int(bool(en_pass)); n_fail_en += int(not en_pass)

    print(f"{'id':<28}  zh   en")
    for sid, z, e in rows:
        print(f"  {sid:<28}  {'✓' if z else '✗':<3}  {'✓' if e else ('–' if e is None else '✗')}")
    print()
    n = len(rows)
    zh_pct = 100 * n_pass_zh / max(n, 1)
    en_n = n_pass_en + n_fail_en
    en_pct = 100 * n_pass_en / max(en_n, 1)
    print(f"zh pass rate: {n_pass_zh}/{n} = {zh_pct:.1f}%")
    if en_n:
        print(f"en pass rate: {n_pass_en}/{en_n} = {en_pct:.1f}%")


if __name__ == "__main__":
    main()
