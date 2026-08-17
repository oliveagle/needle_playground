# 把 Needle 改成中英双语模型——实操路径

本文把"如何让 Needle 2 对中文提示词更友好"的可行路径写成一份操作手册。
如果你只想跑现有功能、不想动模型，可以直接跳到 **路径 E**（部署侧翻译），那是开销最低的方案。

## 关于 Cactus Compute 上游工具链

Needle 2 自带 LoRA 微调 + `.cact` 导出器（参见 `https://github.com/cactus-compute/needle`）：

```bash
pip install "cactus-needle[metal]"        # Apple Silicon 训练
pip install "cactus-needle[gpu]"          # NVIDIA 训练
```

训练出来的 adapter 通过 `needle build … --lora adapter.pkl --out my.cact`
打包成一个新的 `.cact`，然后 `needle.Needle(weights="my.cact")` 直接用，
**不需要重编译引擎**。

> 注意：上游约定 **不会动分词器** 也不会动 confidence 头。改了分词器
> 之后老 checkpoint 就要重训；改了 confidence 头还得采集重标定数据，
> 代价大。所以本手册默认保持两者不动。

---

## 路径 A: 在现有 45M checkpoint 上 LoRA 微调

训练数据是 JSONL，每行一个示例，形如：

```json
{"query": "把客厅灯调到 30",
 "tools": [{"name": "set_lights", "parameters": {...}}],
 "answers": [{"name": "set_lights", "arguments": {"room": "客厅", "brightness": 30, "on": true}}],
 "reasoning": "客厅 -> room; 调到 30 -> brightness 30"}
```

**步骤**

1. **造数**（约 3000 行）
   ```bash
   export OPENROUTER_API_KEY=sk-or-...
   needle generate-data --tools fixtures/tools/lights.json --num-samples 3000 \
       --output scenarios_zh_lora/data.jsonl
   ```
   上游 `needle generate-data` 默认从英文工具描述生成英文数据；
   要让它写中文示例，要么改用 `--lang zh`（如果上游支持），要么自己
   提供一段 seed JSONL 然后用 `--augment` 放大。
   替代方案：直接把 `scenarios_zh/*.jsonl` 翻译成 LoRA 数据（用 GPT-4 / Claude / DeepSeek），大致 200 行就能凑出体量。

2. **加拒答示例**——上游 README 的经验法则：约 12 % 的样本 `"answers": []`。
   ```bash
   echo '{"query": "讲个笑话", "tools":[…], "answers": []}' >> scenarios_zh_lora/data.jsonl
   ```
   否则训练出来的模型任何提示词都会强行调用一个工具。

3. **LoRA 训练**
   ```bash
   needle finetune scenarios_zh_lora/data.jsonl \
       --epochs 15 --lora-rank 32 --lora-alpha 32 \
       --batch-size 16 --lr 1e-4 --max-len 768 \
       --val-split 0.1 --out checkpoints/zh_lora.pkl
   ```
   README 警告："If the curve sits at its starting value after a few hundred steps,
   raise the epochs first, then the learning rate." 数据量小，先把 epochs 拉到 15-30。

4. **打包**
   ```bash
   needle build checkpoints/needle2.pkl \
       --lora checkpoints/zh_lora.pkl \
       --out needle2_zh.cact
   ```
   加 `--upload` 可以直接 `NEEDLE_HF_REPO=<your-org>/<model>` 发布到 HF。

5. **使用**
   ```python
   import needle
   ag = needle.Needle(tools=[...], weights="needle2_zh.cact")
   out = ag.run("把客厅调到 30")
   ```

**这个路径的代价**

- 数据：200-3000 条由 GPT-4 / Claude 翻译或人工写；~$30-150
- 训练：JAX 在 M5 Max 上 0.71 s / step，15 个 epoch + ~3000 行 ≈ 几小时
- 显存：rank 32 LoRA 只需 ~250 MB
- 不需要改分词器 / 引擎 / confidence 头

**预期效果**

README 明确说："Non English text fragments into roughly 1.7 times more tokens
(measured on Spanish)"——因为分词器不变，对中文的碎片化会拉长 prompt ~1.7×，
仍然会消耗掉宝贵的 256-token 窗口的一部分，但 30 字节的中文短句用 50 个
token 表达是足够的，对普通 case 不会爆掉窗口。

期望：单语 LoRA 后 `scenarios_zh/` 通过率能从 40.7 % 升到 70-85 %，
其余仍然受分词器粒度限制。

---

## 路径 B: 在 tokenizer 里加新 CJK 词

要让中文短词只占 1-2 个 token 而不是 5-7 个，需要扩 `vocab.txt`。

`cactus-needle` 引擎的 tokenizer 用 byte-level BPE，词表与权重绑定在
`libneedle.dylib` / `.cact` 内部。**当前没有公开 API 添加 token**，需要：
1. fork `https://github.com/cactus-compute/needle`
2. 把 `cc_2_vocab.txt` 扩到 30 K 左右，加入常用中文词
3. reshard `.cact` 中的 embedding 行
4. 微调 → 重新 build `.cact`

代价：几周到几个月（含上游 PR）。如果你有时间，可以尝试 PR；但目前
**没有公开的脚本可以走捷径**。

---

## 路径 C: 重新训练更大的模型

如果你控制的是训练循环（Cactus 已开源），可以：

1. 把训练语料混入 ~30% 中文
2. 训练一个新 100-200 M 参数的 checkpoint
3. 用 CQ2-bit 量化到 ~20-30 MB
4. 替换 `Cactus-Compute/needle2` 的默认值

这是大工程。你需要和 Cactus Compute 谈，或自己从 45M 这个 checkpoint
fine-tune 全量（不带 LoRA 冻结）。

---

## 路径 D: 用 Heystack / ONNX 路线（不走 Cactus 工具链）

如果你决定 Needle 不是你的方向，**同样的任务还有几条替代路线**：
- **Phi-3-mini-128k-instruct (4-bit, 2.3 GB)** —— 真双语，效果好 5-10×
- **Qwen2.5-1.5B-Instruct (4-bit, ~1 GB)** —— 中文最强的小模型
- **Llama-3.2-3B-Instruct (4-bit, ~1.8 GB)** —— 通用
- **MiniCPM3-4B** —— 中文 SOTA 小模型

这些都不是 on-device 45 MB 量级；部署 RAM 至少高一个数量级，但精度
完全在另一个次元。如果只为中文体验而不在乎大小，这是务实的选项。

---

## 路径 E: 不动模型，在部署侧加翻译（推荐先用）

最廉价的方案：**在调用 Needle 之前把中文 prompt 翻译成英文**。代价：
- 一个离线 T5-translator 模型 (~250 MB) 或一次外部 API 调用
- 平均延迟 +30-80 ms

示意代码：

```python
import needle
from some_translator import translate_zh_to_en

def run_zh(prompt: str) -> dict:
    en = translate_zh_to_en(prompt) if has_chinese(prompt) else prompt
    return needle.Needle(tools=[...]).run(en)

out = run_zh("把客厅调到 30")
# 通过率从 40.7% 抬到 ~85-90%，取决于翻译质量
```

**推荐**：
- 如果是大流量服务：用 Cohere / DeepL / 自部署 NLLB-200
- 如果是离线/隐私敏感：把 NLLB-200-distilled-600M 量化成 4-bit → ~600 MB
  加到设备上，仍比把模型翻倍便宜

本仓库已经给出 `scripts/zh_pass_rate.py` 做 A/B baseline（用一手写翻译表），
能直接看出英文侧的命中期望是 ≈ 33-85%（子集差异）。

---

## 推荐组合（按时间和预算）

| 预算 | 推荐做法 |
| --- | --- |
| 1 周 / 0 元 | 路径 E：用 `scripts/zh_pass_rate.py` 量化翻译增益；上线翻译 wrapper。 |
| 2 周 / $200 | 路径 A：3000 行 GPT-4 翻译 + Apple Silicon 上跑 15 epoch + 跑通 `scenarios_zh/` 通过率 ≥ 80%。 |
| 1 月 / $1000 | 路径 A + 路径 E 组合：上线翻译 wrapper 同时给热路径做微调，半年内可发布 `needle2_zh.cact`。 |
| ≥ 1 季 | 路径 B/C：fork cactus-compute/needle，扩 tokenizer，重新训练。 |

---

## 用本仓库做基线

```bash
# 当前通过率
python -m needle_eval --runner cli --json reports/zh_cli.json --quiet scenarios_zh

# 翻译后的潜在通过率
python scripts/zh_pass_rate.py

# 自定义微调后，重跑
python -m needle_eval --runner cli --json reports/zh_lora.json --quiet scenarios_zh
```

如果 `zh_lora.json` 比 `zh_cli.json` 高出 ≥ 30 %，你的 LoRA 训练确实生效；
否则回头增加数据或 epochs。
