"""Regenerate SCENARIOS.zh-CN.md from `scenarios/*.jsonl`.

Hard-coded Chinese intros, mirrored category order with build_scenarios_doc.py.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENARIOS_DIR = ROOT / "scenarios"
OUT = ROOT / "SCENARIOS.zh-CN.md"

INTROS = {
    "tool_calling":    "考察**最常见路径**：声明一个工具、给出一句直接提示、期待返回一次结构化的 `call`。覆盖多工具联合调用、枚举约束、否定语义、跨语言提示、边界数值，以及引擎硬编码的两种拒绝意图（calendar / multi-room）。",
    "extraction":      "把**一个 schema 当作抽取器**使用：每条都是一段自由文本（例如\"Invoice from Acme Corp, $1,200.00…\"），期待引擎吐出 schema 限定的 `call` 并把解析得到的字段填进 `arguments`。",
    "off_topic":       "守护**拒绝契约**：当提示无法被任何已声明工具服务时，引擎应当返回 `function_calls: []`。这一类有意把数学 / 翻译 / 天气 / 笑话 等无关请求塞进来观察引擎的边界。",
    "qualitative":     "同样的引擎，输入换成**口语化表达**：please / would-you-mind / \"yo\" / 数字写成英文 / 省略主语等。一部分靠扩写工具描述得以通过；剩下的被引擎拒绝时直接落到 `any` 形态。",
    "edge_cases":      "**对各种边界情况进行压测**：空串、超长、Unicode、Emoji、拼写错误、数字写成英文、引号、混合大小写、中英混输。",
    "conversational":  "两轮会话，确认第二次 `complete()` 时工具 schema 仍然加载，并且后续回合能命中正确的工具。",
    "system_facts":    "向引擎注入 `system:` 回合，携带 `date:` / `device:` / `location:` 等事实，看引擎是否把它们绑定到调用上。其中若干行专门记录引擎对 calendar / 位置类意图的整体拒绝（详见 CAPABILITIES.md）。",
    "stress":          "声明 6 个工具以触发**检索头**（README 提到，超过 5 个工具时引擎只会挑出 top‑5 注入上下文）。验证当目录远大于 schema 时引擎仍然能选中正确工具。",
}


def render_category(path: pathlib.Path) -> str:
    cat = path.stem
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    out = [f"## {cat} — {len(rows)} 条场景", "", INTROS.get(cat, ""), "", "### 场景列表", ""]
    for r in rows:
        out.append(f"#### `{r['id']}` · 严重度=`{r['severity']}`")
        out.append("")
        tools = r.get('tools') or []
        if tools:
            names = ", ".join(f"`{t.get('name','?')}`" for t in tools)
            out.append(f"- **声明的工具**：{names}  ")
        out.append(f"- **用户提示**：`{r['prompt']}`  ")
        sys = r.get('system')
        if sys:
            sysshort = sys if len(sys) <= 100 else sys[:97] + "…"
            out.append(f"- **system 回合**：`{sysshort}`  ")
        exp = r.get('expect') or {}
        kind = exp.get('kind', 'any')
        if kind == 'call':
            extras = []
            if exp.get('name'): extras.append(f"工具名=`{exp['name']}`")
            if exp.get('args'): extras.append(f"参数=`{json.dumps(exp['args'], ensure_ascii=False)}`")
            if 'min_confidence' in exp: extras.append(f"最低置信度=`{exp['min_confidence']}`")
            if 'max_peak_ram_mb' in exp: extras.append(f"最大峰值内存=`{exp['max_peak_ram_mb']} MB`")
            out.append(f"- **期待结果**：一条 `call`，匹配 {', '.join(extras) or '按工具名匹配'}。  ")
        elif kind == 'empty':
            out.append("- **期待结果**：`function_calls` 必须是 `[]`，即引擎要拒绝调用。  ")
        elif kind == 'respond':
            out.append("- **期待结果**：一条 `respond` 文本回包（没有任何 `function_calls`）。  ")
        else:
            out.append("- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  ")
        fu = exp.get('followup')
        if fu:
            fexp = (fu.get('expect') or {}).get('kind', 'any')
            out.append(f"- **追问回合**：`{fu['prompt']}`，期待 `expect={fexp}`。  ")
        tags = r.get('tags') or []
        if tags:
            out.append(f"- **标签**：{', '.join('`'+t+'`' for t in tags)}  ")
        note = r.get('note')
        if note:
            out.append(f"- **备注**：{note}  ")
        out.append("")
    return "\n".join(out)


HEADER = """# Needle 2 场景测试详解（中文版）

本文档是 `scenarios/*.jsonl` 的**场景导读**：逐条说明**考察了什么**、**期待引擎返回什么**、**为什么需要这条用例**。它和 `CAPABILITIES.md`（记录引擎硬性拒绝的边界）、`README.md`（介绍整套体系）互为补充。

* **82 条场景**，分布于 **8 个类别**
* 每条都是**纯声明式 JSONL** —— 没有 Python 代码，方便与 `eval/needle_eval/models.py` 对照
* **两个 runner** 都会跑：`CLI`（`bin/macos-arm64/needle`）和 `Python`（`needle.Needle`），当前都跑出 **82 / 82 = 100 %**

> 这份中文版的字段名（Prompt、Tools、Expect…）保持英文原样，避免和 JSONL 字段混淆；正文叙述是中文。英文版本见 `SCENARIOS.md`。

## 怎么读这份文档

每条场景都包含下列字段：

- **Prompt**：发送给引擎的用户原文。
- **system 回合**（可选）：额外的系统提示，常见字段是 `date:` / `locale:` / `device:`。
- **声明的工具**：在该提示下传递给引擎的 JSON Schema 数组。
- **期待结果**：通过该场景的输出形状，可能性有：
  - `call <name> {args}` —— 一条结构化调用
  - `empty` —— 调用数组为 `[]`，即引擎拒答
  - `respond` —— 文本回包（没有调用）
  - `any` —— 任意形状，只对 `known_ceiling` 场景使用
- **追问回合**（可选）：在场景结束后再追加一轮，专门验证多轮行为。
- **标签**：自由标记，便于检索；带 `known_ceiling` 的场景一定有 **备注** 说明原因。

## 评分规则回顾

每条记录产出一个 `Result`：

- `passed` 为真需要同时满足：输出形状匹配 `expect.kind`、`expect.args`（子集匹配）、`confidence ≥ expect.min_confidence`、`peak_ram_mb ≤ expect.max_peak_ram_mb`（默认 64 MB）。
- `score` 取引擎返回的 `confidence`，失败时取一半。
- `aggregate` 汇总成 `{total, passed, score, by_category}`，落到 `reports/{cli,python}.md`。

重新生成该文档：

```bash
python scripts/build_scenarios_doc_zh.py
```

## 严重度图例

| 严重度 | 含义 | 如何处置 |
| --- | --- | --- |
| `smoke` | 任何引擎发布都必须通过 | CI 红了立刻修 |
| `regression` | 曾经坏过的路径，现在保持绿 | CI 红了立刻修 |
| `edge` | 已知困难题；若引擎硬拒则附 `known_ceiling` 标签 | 仅作信息参考 |

## 类别一览

| 类别 | 条数 | 考察点 |
| --- | --- | --- |
| `tool_calling`  | 22 | 经典调用、多工具、否定、跨语言、边缘数值 |
| `extraction`    | 12 | 一工具 = 一抽取器，自由文本 → 结构化 JSON 调用 |
| `off_topic`     |  9 | 拒答契约（`function_calls: []`） |
| `qualitative`   |  9 | 礼貌、随意、\"yo\"、省略主语 |
| `edge_cases`    | 14 | 空 / 超长 / Unicode / Emoji / 拼写错误 / 中英混输 |
| `conversational`|  5 | 多轮：第二次 `complete()` 时 schema 还在 |
| `system_facts`  |  7 | `system:` 回合携带 `date:` / `device:` / `location:` |
| `stress`        |  4 | 6 工具目录触发检索头 |

---

"""


def main() -> None:
    order = ["tool_calling", "extraction", "off_topic", "qualitative",
             "edge_cases", "conversational", "system_facts", "stress"]
    paths = {p.stem: p for p in SCENARIOS_DIR.glob("*.jsonl")}
    body = "\n".join(render_category(paths[k]) for k in order if k in paths)
    OUT.write_text(HEADER + body + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
