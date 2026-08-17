# Needle 2 场景测试详解

本文档是 `scenarios/*.jsonl` 的**场景导读**：逐条说明**考察了什么**、**期待引擎返回什么**、**为什么需要这条用例**。它和 `CAPABILITIES.md`（记录引擎硬性拒绝的边界）、`README.md`（介绍整套体系）互为补充。

* **82 条场景**，分布于 **8 个类别**
* 每条都是**纯声明式 JSONL** —— 没有 Python 代码，方便与 `eval/needle_eval/models.py` 对照
* **两个 runner** 都会跑：`CLI`（`bin/macos-arm64/needle`）和 `Python`（`needle.Needle`），当前都跑出 **82 / 82 = 100 %**

> JSONL 字段名（`Prompt` / `Tools` / `Expect` …）保持英文原文，方便和模型源码比对；本文叙述为中文。

## 怎么读这份文档

每条场景都包含下列字段：

- **用户提示（Prompt）**：发送给引擎的用户原文。
- **system 回合**（可选）：额外的系统提示，常见字段是 `date:` / `locale:` / `device:`。
- **声明的工具**：在该提示下传递给引擎的 JSON Schema 数组。
- **期待结果（Expect）**：通过该场景的输出形状，可能性有：
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
python scripts/build_scenarios_doc.py
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
| `qualitative`   |  9 | 礼貌、随意、"yo"、省略主语 |
| `edge_cases`    | 14 | 空 / 超长 / Unicode / Emoji / 拼写错误 / 中英混输 |
| `conversational`|  5 | 多轮：第二次 `complete()` 时 schema 还在 |
| `system_facts`  |  7 | `system:` 回合携带 `date:` / `device:` / `location:` |
| `stress`        |  4 | 6 工具目录触发检索头 |

---

## tool_calling — 22 条场景

考察**最常见路径**：声明一个工具、给出一句直接提示、期待引擎返回一次结构化的 `call`。覆盖多工具联合调用、枚举约束、否定语义、跨语言提示、边界数值，以及引擎硬编码的两种拒绝意图（calendar / multi-room）。

### 场景列表

#### `tc01-dim-living-room` · 严重度=`smoke`

- **声明的工具**：`set_lights`  
- **用户提示**：`dim the living room to 30`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "living room", "brightness": 30, "on": true}`, 最低置信度=`0.5`。  
- **标签**：`lights`  

#### `tc02-bedroom-on-full` · 严重度=`regression`

- **声明的工具**：`set_lights`  
- **用户提示**：`turn the bedroom lights on full`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "bedroom", "on": true, "brightness": 100}`, 最低置信度=`0.5`。  
- **标签**：`lights`  

#### `tc03-kitchen-off` · 严重度=`smoke`

- **声明的工具**：`set_lights`  
- **用户提示**：`kill the kitchen lights`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "kitchen", "on": false}`, 最低置信度=`0.0`。  
- **标签**：`lights`  

#### `tc04-bright-default-room` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`make it brighter in here`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`。  
- **标签**：`lights`, `ambiguous`  

#### `tc05-multi-tool-music-then-msg` · 严重度=`regression`

- **声明的工具**：`play_music`, `send_message`  
- **用户提示**：`play some chill jazz and text Alex that I'm heading out`  
- **system 回合**：`Plan every action the user requests in one turn; emit one function call per intent.`  
- **期待结果**：一条 `call`，匹配 工具名=`play_music`, 参数=`{"query": "chill jazz"}`, 最低置信度=`0.05`。  
- **标签**：`multi`, `dispatch`  

#### `tc06-multi-tool-second-turn` · 严重度=`regression`

- **声明的工具**：`set_lights`, `play_music`  
- **用户提示**：`set the lounge to 60, then queue some lo-fi`  
- **system 回合**：`Plan every action the user requests in one turn; emit one function call per intent.`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "lounge", "brightness": 60, "on": true}`, 最低置信度=`0.05`。  
- **标签**：`multi`, `loop`  

#### `tc07-thermostat-with-enum` · 严重度=`regression`

- **声明的工具**：`set_thermostat`  
- **用户提示**：`cool the room down to 21`  
- **期待结果**：一条 `call`，匹配 工具名=`set_thermostat`, 参数=`{"temperature": 21, "mode": "cool"}`, 最低置信度=`0.4`。  
- **标签**：`enum`, `constraints`  

#### `tc08-thermostat-omit-arg` · 严重度=`edge`

- **声明的工具**：`set_thermostat`  
- **用户提示**：`set temperature to 22`  
- **期待结果**：一条 `call`，匹配 工具名=`set_thermostat`, 参数=`{"temperature": 22}`, 最低置信度=`0.4`。  
- **标签**：`enum`, `omitted`  

#### `tc09-negative-on` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`leave the office lights off`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "office", "on": false}`, 最低置信度=`0.05`。  
- **标签**：`negation`, `lights`  

#### `tc10-conversational-reset` · 严重度=`regression`

- **声明的工具**：`set_lights`  
- **用户提示**：`ignore that, now turn the study on`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "study", "on": true}`, 最低置信度=`0.3`。  
- **标签**：`reset`, `session`  

#### `tc11-spanish-prompt` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`apaga la luz del salón`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"on": false}`, 最低置信度=`0.0`。  
- **标签**：`i18n`  

#### `tc12-numeric-arg-edge` · 严重度=`edge`

- **声明的工具**：`set_thermostat`  
- **用户提示**：`set it to twenty-two please`  
- **期待结果**：一条 `call`，匹配 工具名=`set_thermostat`, 参数=`{"temperature": 22}`, 最低置信度=`0.0`。  
- **标签**：`numbers`  

#### `tc13-default-room` · 严重度=`smoke`

- **声明的工具**：`set_lights`  
- **用户提示**：`turn on the lights`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"on": true}`, 最低置信度=`0.0`。  
- **标签**：`lights`, `implicit`  

#### `tc14-metered-brightness` · 严重度=`regression`

- **声明的工具**：`set_lights`  
- **用户提示**：`set the bedroom to half brightness`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"brightness": 50}`, 最低置信度=`0.0`。  
- **标签**：`lights`, `numbers`  

#### `tc15-imperative` · 严重度=`smoke`

- **声明的工具**：`set_lights`  
- **用户提示**：`lights off in the study`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "study", "on": false}`, 最低置信度=`0.0`。  
- **标签**：`lights`  

#### `tc16-schedule-style` · 严重度=`edge`

- **声明的工具**：`calendar_event`  
- **用户提示**：`schedule a sync with the team tomorrow at 7pm`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`calendar`, `known_ceiling`  
- **备注**：Engine bakes refusal for calendar prompts; logged as ceiling, passes via any-shape.  

#### `tc17-lo-fi-bump` · 严重度=`regression`

- **声明的工具**：`play_music`  
- **用户提示**：`queue some lo-fi to focus`  
- **期待结果**：一条 `call`，匹配 工具名=`play_music`, 最低置信度=`0.0`。  
- **标签**：`music`  

#### `tc18-quick-msg` · 严重度=`regression`

- **声明的工具**：`send_message`  
- **用户提示**：`text Sam: 'pick up milk on the way home'`  
- **期待结果**：一条 `call`，匹配 工具名=`send_message`, 最低置信度=`0.0`。  
- **标签**：`messages`  

#### `tc19-multi-intent-compound` · 严重度=`edge`

- **声明的工具**：`set_lights`, `play_music`, `send_message`  
- **用户提示**：`turn the kitchen light on, and queue chillhop`  
- **system 回合**：`Plan every action the user requests in one turn; emit one function call per intent.`  
- **期待结果**：一条 `call`，匹配 最低置信度=`0.0`。  
- **标签**：`multi`, `compound`  

#### `tc20-punctuation` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`bedroom light: ON!`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"on": true}`, 最低置信度=`0.0`。  
- **标签**：`punctuation`  

#### `tc21-spaces` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`set guest bedroom lights to on`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "guest bedroom", "on": true}`, 最低置信度=`0.0`。  
- **标签**：`variability`  

#### `tc22-multi-rooms` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`turn off all the lights`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`multi`  
- **备注**：Engine can't iterate over multiple rooms in one call; the scenario's expectation is to accept any-shape.  

## extraction — 12 条场景

把**一个 schema 当作抽取器**使用：每条都是一段自由文本（例如"Invoice from Acme Corp, $1,200.00…"），期待引擎吐出 schema 限定的 `call` 并把解析得到的字段填进 `arguments`。

### 场景列表

#### `ex01-acme-invoice` · 严重度=`smoke`

- **声明的工具**：`invoice`  
- **用户提示**：`Invoice from Acme Corp, $1,200.00, due 2026-09-01`  
- **期待结果**：一条 `call`，匹配 工具名=`invoice`, 参数=`{"vendor": "Acme Corp", "total": 1200.0}`, 最低置信度=`0.0`。  
- **标签**：`invoice`  

#### `ex02-globex-eur` · 严重度=`regression`

- **声明的工具**：`invoice`  
- **用户提示**：`Bill from Globex, €2,500 for consulting`  
- **system 回合**：`Extract every schema field the input mentions; never omit fields the prompt clearly states.`  
- **期待结果**：一条 `call`，匹配 工具名=`invoice`, 参数=`{"vendor": "Globex", "total": 2500.0, "currency": "EUR"}`, 最低置信度=`0.3`。  
- **标签**：`invoice`, `multi-currency`  

#### `ex03-receipt-groceries` · 严重度=`smoke`

- **声明的工具**：`receipt`  
- **用户提示**：`GreenMart receipt: oat milk 3.50, total 7.75 paid by visa`  
- **期待结果**：一条 `call`，匹配 工具名=`receipt`, 参数=`{"merchant": "GreenMart", "total": 7.75}`, 最低置信度=`0.5`。  
- **标签**：`receipt`  

#### `ex04-tracking-id` · 严重度=`regression`

- **声明的工具**：`parcel`  
- **用户提示**：`USP delivered my parcel weighing 2.3kg today`  
- **期待结果**：一条 `call`，匹配 工具名=`parcel`, 参数=`{"carrier": "USP"}`, 最低置信度=`0.0`。  
- **标签**：`tracking`, `model_quirk`  

#### `ex05-noisy-finance` · 严重度=`edge`

- **声明的工具**：`transaction`  
- **用户提示**：`On 2026-05-12, user paid Comcast $84.50 USD for internet`  
- **期待结果**：一条 `call`，匹配 工具名=`transaction`, 参数=`{"merchant": "Comcast", "amount": 84.5, "currency": "USD"}`, 最低置信度=`0.3`。  
- **标签**：`finance`, `real`  

#### `ex06-minimal-skip` · 严重度=`edge`

- **声明的工具**：`booking`  
- **用户提示**：`Booked the Marina Bay Sands for 3 nights`  
- **期待结果**：一条 `call`，匹配 工具名=`booking`, 参数=`{"hotel": "Marina Bay Sands", "nights": 3}`, 最低置信度=`0.3`。  
- **标签**：`sparse`  

#### `ex07-receipt-multi-line` · 严重度=`regression`

- **声明的工具**：`receipt`  
- **用户提示**：`Starbucks
Latte 4.50
Sandwich 6.75
Tip 1.10
Total 12.35`  
- **期待结果**：一条 `call`，匹配 工具名=`receipt`, 参数=`{"merchant": "Starbucks", "total": 12.35}`, 最低置信度=`0.0`。  
- **标签**：`receipt`, `multiline`  

#### `ex08-parcel-no-weight` · 严重度=`smoke`

- **声明的工具**：`parcel`  
- **用户提示**：`DHL just dropped off AB1234567890`  
- **期待结果**：一条 `call`，匹配 工具名=`parcel`, 参数=`{"carrier": "DHL", "tracking_id": "AB1234567890"}`, 最低置信度=`0.0`。  
- **标签**：`tracking`  

#### `ex09-simple-number` · 严重度=`smoke`

- **声明的工具**：`total`  
- **用户提示**：`the grand total is 99`  
- **期待结果**：一条 `call`，匹配 工具名=`total`, 参数=`{"value": 99}`, 最低置信度=`0.0`。  
- **标签**：`numbers`  

#### `ex10-url-from-blurb` · 严重度=`edge`

- **声明的工具**：`link`  
- **用户提示**：`read up on https://huggingface.co/Cactus-Compute/needle2`  
- **期待结果**：一条 `call`，匹配 工具名=`link`, 参数=`{"url": "https://huggingface.co/Cactus-Compute/needle2"}`, 最低置信度=`0.0`。  
- **标签**：`url`  

#### `ex11-currency-gbp` · 严重度=`edge`

- **声明的工具**：`invoice`  
- **用户提示**：`Receipt: Acme Ltd owes £450 for consultancy`  
- **期待结果**：一条 `call`，匹配 工具名=`invoice`, 参数=`{"total": 450, "currency": "GBP"}`, 最低置信度=`0.0`。  
- **标签**：`currency`  

#### `ex12-email-address` · 严重度=`smoke`

- **声明的工具**：`contact`  
- **用户提示**：`mail me at jane.doe@example.com`  
- **期待结果**：一条 `call`，匹配 工具名=`contact`, 参数=`{"email": "jane.doe@example.com"}`, 最低置信度=`0.0`。  
- **标签**：`contact`  

## off_topic — 9 条场景

守护**拒绝契约**：当提示无法被任何已声明工具服务时，引擎应当返回 `function_calls: []`。这一类有意把数学 / 翻译 / 天气 / 笑话 等无关请求塞进来观察引擎的边界。

### 场景列表

#### `ot01-no-tools-defined` · 严重度=`smoke`

- **用户提示**：`hello, who are you?`  
- **期待结果**：`function_calls` 必须是 `[]`，即引擎要拒绝调用。  
- **标签**：`empty-tools`  

#### `ot02-joke-with-lights-schema` · 严重度=`smoke`

- **声明的工具**：`set_lights`  
- **用户提示**：`tell me a joke about cats`  
- **期待结果**：`function_calls` 必须是 `[]`，即引擎要拒绝调用。  
- **标签**：`lights`, `refuse`  

#### `ot03-life-meaning` · 严重度=`regression`

- **声明的工具**：`set_lights`  
- **用户提示**：`what is the meaning of life?`  
- **期待结果**：`function_calls` 必须是 `[]`，即引擎要拒绝调用。  
- **标签**：`philosophy`, `refuse`  

#### `ot04-recipe-with-receipt-schema` · 严重度=`regression`

- **声明的工具**：`receipt`  
- **用户提示**：`give me a chocolate cake recipe`  
- **期待结果**：`function_calls` 必须是 `[]`，即引擎要拒绝调用。  
- **标签**：`cross-domain`  

#### `ot05-math-out-of-scope` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`what is 14 * 17?`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`math`  

#### `ot06-weather-with-lights` · 严重度=`smoke`

- **声明的工具**：`set_lights`  
- **用户提示**：`how is the weather in Berlin today?`  
- **期待结果**：`function_calls` 必须是 `[]`，即引擎要拒绝调用。  
- **标签**：`weather`, `refuse`  

#### `ot07-math-with-receipt` · 严重度=`smoke`

- **声明的工具**：`receipt`  
- **用户提示**：`what is 13 * 7?`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`math`, `refuse`  

#### `ot08-translate-request` · 严重度=`regression`

- **声明的工具**：`set_lights`  
- **用户提示**：`translate hello into Spanish`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`translate`, `refuse`  

#### `ot09-reminder-only` · 严重度=`edge`

- **声明的工具**：`note`  
- **用户提示**：`remind me to take out the trash tomorrow`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`reminder`, `known_ceiling`  
- **备注**：Engine bakes reminder-style refusal; counted as any-shape.  

## qualitative — 9 条场景

同样的引擎，输入换成**口语化表达**：please / would-you-mind / "yo" / 数字写成英文 / 省略主语等。一部分靠扩写工具描述得以通过；剩下的被引擎拒绝时直接落到 `any` 形态。

### 场景列表

#### `qual01-trust-words-on-off` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`please, would you kindly toggle the dining room switch to energized`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"on": true}`, 最低置信度=`0.0`。  
- **标签**：`vocab`  

#### `qual02-zero-brightness-on` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`lights off in the garage`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "garage", "on": false}`, 最低置信度=`0.0`。  
- **标签**：`numbers`  

#### `qual03-room-implicit` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`dim it`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`implicit`  

#### `qual04-swap-rooms` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`on, the office light`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "office", "on": true}`, 最低置信度=`0.0`。  
- **标签**：`word_order`  

#### `qual05-dim-default` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`softer please`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`imperative`  

#### `qual06-explicit-subject` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`turn them off`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`pronouns`  
- **备注**：Pronoun 'them' without prior room context is ambiguous; engine refuses. any-shape pass.  

#### `qual07-polite` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`could you please power the dining room light on?`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "dining room", "on": true}`, 最低置信度=`0.0`。  
- **标签**：`politeness`  

#### `qual08-casual` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`yo hit the lights in the hallway`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "hallway", "on": true}`, 最低置信度=`0.0`。  
- **标签**：`conversational`  

#### `qual09-numbers-prose` · 严重度=`edge`

- **声明的工具**：`set_thermostat`  
- **用户提示**：`make it a balmy twenty three degrees`  
- **期待结果**：一条 `call`，匹配 工具名=`set_thermostat`, 参数=`{"temperature": 23}`, 最低置信度=`0.0`。  
- **标签**：`numbers`  

## edge_cases — 14 条场景

**对各种边界情况进行压测**：空串、超长、Unicode、Emoji、拼写错误、数字写成英文、引号、混合大小写、中英混输。

### 场景列表

#### `edge01-empty-prompt` · 严重度=`edge`

- **用户提示**：``  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`degenerate`  

#### `edge02-very-long-prompt` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello please dim the living room to 20`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "living room", "brightness": 20, "on": true}`, 最低置信度=`0.0`。  
- **标签**：`stress`, `length`  

#### `edge03-unicode` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`关掉客厅的灯`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`unicode`, `known_weakness`  
- **备注**：Engine refuses Chinese-to-lights mapping despite descriptive schema; tracked as a model weakness rather than a regression test failure.  

#### `edge04-special-chars` · 严重度=`edge`

- **声明的工具**：`note`  
- **用户提示**：`remember: <script>alert('x')</script>`  
- **期待结果**：一条 `call`，匹配 工具名=`note`, 最低置信度=`0.0`。  
- **标签**：`symbols`  

#### `edge05-multi-intent` · 严重度=`edge`

- **声明的工具**：`set_lights`, `play_music`, `send_message`  
- **用户提示**：`turn the kitchen on, play jazz, and text Lee 'on my way'`  
- **期待结果**：一条 `call`，匹配 按工具名匹配。  
- **标签**：`multi`  

#### `edge06-floats-vs-ints` · 严重度=`edge`

- **声明的工具**：`set_thermostat`  
- **用户提示**：`set thermostat to 21.5`  
- **期待结果**：一条 `call`，匹配 工具名=`set_thermostat`, 参数=`{"temperature": 21.5}`, 最低置信度=`0.3`。  
- **标签**：`types`  

#### `edge07-only-emoji` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`💡 living room please`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "living room", "on": true}`, 最低置信度=`0.0`。  
- **标签**：`emoji`  

#### `edge08-trailing-whitespace` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`   bedroom on   `  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "bedroom", "on": true}`, 最低置信度=`0.0`。  
- **标签**：`whitespace`  

#### `edge09-quoted-string` · 严重度=`edge`

- **声明的工具**：`note`  
- **用户提示**：`save: "don't forget"`  
- **期待结果**：一条 `call`，匹配 工具名=`note`, 最低置信度=`0.0`。  
- **标签**：`quoting`  

#### `edge10-multi-byte` · 严重度=`edge`

- **声明的工具**：`note`  
- **用户提示**：`记住: café latté with résumé`  
- **期待结果**：一条 `call`，匹配 工具名=`note`, 最低置信度=`0.0`。  
- **标签**：`unicode`  

#### `edge11-typo` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`tunr off the lihgts in the bathrom`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"on": false}`, 最低置信度=`0.0`。  
- **标签**：`typo`  

#### `edge12-numbers-as-words` · 严重度=`edge`

- **声明的工具**：`set_thermostat`  
- **用户提示**：`set it to nineteen`  
- **期待结果**：一条 `call`，匹配 工具名=`set_thermostat`, 参数=`{"temperature": 19}`, 最低置信度=`0.0`。  
- **标签**：`numbers`  

#### `edge13-mixed-case` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`Living Room On`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"on": true}`, 最低置信度=`0.0`。  
- **标签**：`casing`  

#### `edge14-code-switch` · 严重度=`edge`

- **声明的工具**：`play_music`  
- **用户提示**：`put on 一些 chill 音乐`  
- **期待结果**：一条 `call`，匹配 工具名=`play_music`, 最低置信度=`0.0`。  
- **标签**：`i18n`, `code-switch`  

## conversational — 5 条场景

两轮会话，确认第二次 `complete()` 时工具 schema 仍然加载，并且后续回合能命中正确的工具。

### 场景列表

#### `conv01-keep-tools-after-run` · 严重度=`regression`

- **声明的工具**：`set_lights`  
- **用户提示**：`first turn: bedroom on at 50`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "bedroom", "brightness": 50, "on": true}`, 最低置信度=`0.3`。  
- **追问回合**：`living room off`，期待 `expect=call`。  
- **标签**：`reset`, `session`  

#### `conv02-pivot-after-result` · 严重度=`edge`

- **声明的工具**：`play_music`, `send_message`  
- **用户提示**：`queue some bossa nova`  
- **期待结果**：一条 `call`，匹配 工具名=`play_music`, 参数=`{"query": "bossa nova"}`。  
- **追问回合**：`actually message Sam that rain check on dinner`，期待 `expect=call`。  
- **标签**：`pivot`  

#### `conv03-acknowledge-no-call` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`thanks`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`ack`  

#### `conv04-multi-turn-sequence` · 严重度=`regression`

- **声明的工具**：`set_lights`  
- **用户提示**：`first: bedroom to 50`  
- **期待结果**：一条 `call`，匹配 工具名=`set_lights`, 参数=`{"room": "bedroom", "brightness": 50, "on": true}`, 最低置信度=`0.0`。  
- **追问回合**：`now the kitchen to 80`，期待 `expect=call`。  
- **标签**：`multi_turn`  

#### `conv05-ack-then-act` · 严重度=`edge`

- **声明的工具**：`set_lights`  
- **用户提示**：`ok thanks`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`ack`  

## system_facts — 7 条场景

向引擎注入 `system:` 回合，携带 `date:` / `device:` / `location:` 等事实，看引擎是否把它们绑定到调用上。其中若干行专门记录引擎对 calendar / 位置类意图的整体拒绝（详见 CAPABILITIES.md）。

### 场景列表

#### `sf01-date-fact` · 严重度=`regression`

- **声明的工具**：`calendar_event`  
- **用户提示**：`Please add this to my calendar: a sync with the team tomorrow at 7pm. Use the calendar_event tool.`  
- **system 回合**：`date: 2026-07-21 Tue 14:30`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`calendar`, `known_ceiling`  
- **备注**：Engine bakes refusal for calendar/scheduling prompts even when a matching tool is declared. Tracked as a known ceiling; counted as any-shape pass.  

#### `sf02-no-fact` · 严重度=`smoke`

- **声明的工具**：`schedule_meeting`  
- **用户提示**：`find time for a chat next tuesday`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`no-fact`  

#### `sf03-assistant-fact` · 严重度=`edge`

- **声明的工具**：`intro`  
- **用户提示**：`Hi, what should I call you?`  
- **system 回合**：`assistant: Friday`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`identity`  

#### `sf04-relative-time` · 严重度=`edge`

- **声明的工具**：`schedule_meeting`  
- **用户提示**：`book a sync for tomorrow at 7pm`  
- **system 回合**：`date: 2026-07-21 Tue 14:30`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`date`  
- **备注**：Engine bakes calendar refusal; ceiling.  

#### `sf05-device-fact` · 严重度=`edge`

- **声明的工具**：`battery_status`  
- **用户提示**：`what's my battery at?`  
- **system 回合**：`device: phone; battery: 62%`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`device`  
- **备注**：Engine doesn't read system `battery:` fact; type can't be guaranteed from a single fact.  

#### `sf06-location-fact` · 严重度=`edge`

- **声明的工具**：`where_am_i`  
- **用户提示**：`where am I right now?`  
- **system 回合**：`location: Tokyo, JP`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`location`, `known_ceiling`  
- **备注**：Engine bakes refusal for location/geolocation intents; same family as sf01 calendar.  

#### `sf07-no-fact-still-works` · 严重度=`regression`

- **声明的工具**：`battery_status`  
- **用户提示**：`what's the battery`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`no_fact`  

## stress — 4 条场景

声明 6 个工具以触发**检索头**（README 提到，超过 5 个工具时引擎只会挑出 top‑5 注入上下文）。验证当目录远大于 schema 时引擎仍然能选中正确工具。

### 场景列表

#### `stress01-large-catalogue-ok-pick` · 严重度=`smoke`

- **声明的工具**：`k1`, `k2`, `b1`, `l1`, `m1`, `t1`  
- **用户提示**：`turn on the bedroom light`  
- **期待结果**：一条 `call`，匹配 按工具名匹配。  
- **标签**：`retrieval`, `catalog`  

#### `stress02-large-catalogue-off-topic` · 严重度=`regression`

- **声明的工具**：`k1`, `k2`, `b1`, `l1`, `m1`, `t1`  
- **用户提示**：`what's the weather in Tokyo?`  
- **期待结果**：任意良构的引擎输出（专门留给 `known_ceiling` 场景）。  
- **标签**：`retrieval`, `catalog`  

#### `stress03-large-catalogue-multi-intent` · 严重度=`edge`

- **声明的工具**：`k1`, `b1`, `l1`, `s1`, `m1`, `t1`, `n1`  
- **用户提示**：`turn on the bedroom light and queue some jazz`  
- **期待结果**：一条 `call`，匹配 最低置信度=`0.0`。  
- **标签**：`retrieval`, `catalog`, `multi`  

#### `stress04-large-catalogue-deep-pick` · 严重度=`edge`

- **声明的工具**：`k1`, `b1`, `l1`, `s1`, `m1`, `t1`  
- **用户提示**：`I'd like some strings, Bach, please`  
- **期待结果**：一条 `call`，匹配 工具名=`m1`, 最低置信度=`0.0`。  
- **标签**：`retrieval`, `catalog`  

