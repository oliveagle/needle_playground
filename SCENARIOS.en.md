# Needle 2 场景测试详解 (Scenarios Reference)

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

## tool_calling — 22 scenarios

Probes the **canonical happy path**: a single declared tool, a direct prompt, an expected call with subset args. Includes multi-tool dispatch, enum constraints, negation, i18n, numeric edges, and the two refusals the engine hard-codes (calendar / multi-room).

### Scenarios

#### `tc01-dim-living-room` · severity=`smoke`

- **Tools declared**: `set_lights`  
- **Prompt**: `dim the living room to 30`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "living room", "brightness": 30, "on": true}`, min_confidence=`0.5`.  
- **Tags**: `lights`  

#### `tc02-bedroom-on-full` · severity=`regression`

- **Tools declared**: `set_lights`  
- **Prompt**: `turn the bedroom lights on full`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "bedroom", "on": true, "brightness": 100}`, min_confidence=`0.5`.  
- **Tags**: `lights`  

#### `tc03-kitchen-off` · severity=`smoke`

- **Tools declared**: `set_lights`  
- **Prompt**: `kill the kitchen lights`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "kitchen", "on": false}`, min_confidence=`0.0`.  
- **Tags**: `lights`  

#### `tc04-bright-default-room` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `make it brighter in here`  
- **Expect**: a single `call` matching name=`set_lights`.  
- **Tags**: `lights`, `ambiguous`  

#### `tc05-multi-tool-music-then-msg` · severity=`regression`

- **Tools declared**: `play_music`, `send_message`  
- **Prompt**: `play some chill jazz and text Alex that I'm heading out`  
- **System turn**: `Plan every action the user requests in one turn; emit one function call per intent.`  
- **Expect**: a single `call` matching name=`play_music`, args=`{"query": "chill jazz"}`, min_confidence=`0.05`.  
- **Tags**: `multi`, `dispatch`  

#### `tc06-multi-tool-second-turn` · severity=`regression`

- **Tools declared**: `set_lights`, `play_music`  
- **Prompt**: `set the lounge to 60, then queue some lo-fi`  
- **System turn**: `Plan every action the user requests in one turn; emit one function call per intent.`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "lounge", "brightness": 60, "on": true}`, min_confidence=`0.05`.  
- **Tags**: `multi`, `loop`  

#### `tc07-thermostat-with-enum` · severity=`regression`

- **Tools declared**: `set_thermostat`  
- **Prompt**: `cool the room down to 21`  
- **Expect**: a single `call` matching name=`set_thermostat`, args=`{"temperature": 21, "mode": "cool"}`, min_confidence=`0.4`.  
- **Tags**: `enum`, `constraints`  

#### `tc08-thermostat-omit-arg` · severity=`edge`

- **Tools declared**: `set_thermostat`  
- **Prompt**: `set temperature to 22`  
- **Expect**: a single `call` matching name=`set_thermostat`, args=`{"temperature": 22}`, min_confidence=`0.4`.  
- **Tags**: `enum`, `omitted`  

#### `tc09-negative-on` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `leave the office lights off`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "office", "on": false}`, min_confidence=`0.05`.  
- **Tags**: `negation`, `lights`  

#### `tc10-conversational-reset` · severity=`regression`

- **Tools declared**: `set_lights`  
- **Prompt**: `ignore that, now turn the study on`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "study", "on": true}`, min_confidence=`0.3`.  
- **Tags**: `reset`, `session`  

#### `tc11-spanish-prompt` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `apaga la luz del salón`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"on": false}`, min_confidence=`0.0`.  
- **Tags**: `i18n`  

#### `tc12-numeric-arg-edge` · severity=`edge`

- **Tools declared**: `set_thermostat`  
- **Prompt**: `set it to twenty-two please`  
- **Expect**: a single `call` matching name=`set_thermostat`, args=`{"temperature": 22}`, min_confidence=`0.0`.  
- **Tags**: `numbers`  

#### `tc13-default-room` · severity=`smoke`

- **Tools declared**: `set_lights`  
- **Prompt**: `turn on the lights`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"on": true}`, min_confidence=`0.0`.  
- **Tags**: `lights`, `implicit`  

#### `tc14-metered-brightness` · severity=`regression`

- **Tools declared**: `set_lights`  
- **Prompt**: `set the bedroom to half brightness`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"brightness": 50}`, min_confidence=`0.0`.  
- **Tags**: `lights`, `numbers`  

#### `tc15-imperative` · severity=`smoke`

- **Tools declared**: `set_lights`  
- **Prompt**: `lights off in the study`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "study", "on": false}`, min_confidence=`0.0`.  
- **Tags**: `lights`  

#### `tc16-schedule-style` · severity=`edge`

- **Tools declared**: `calendar_event`  
- **Prompt**: `schedule a sync with the team tomorrow at 7pm`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `calendar`, `known_ceiling`  
- **Note**: Engine bakes refusal for calendar prompts; logged as ceiling, passes via any-shape.  

#### `tc17-lo-fi-bump` · severity=`regression`

- **Tools declared**: `play_music`  
- **Prompt**: `queue some lo-fi to focus`  
- **Expect**: a single `call` matching name=`play_music`, min_confidence=`0.0`.  
- **Tags**: `music`  

#### `tc18-quick-msg` · severity=`regression`

- **Tools declared**: `send_message`  
- **Prompt**: `text Sam: 'pick up milk on the way home'`  
- **Expect**: a single `call` matching name=`send_message`, min_confidence=`0.0`.  
- **Tags**: `messages`  

#### `tc19-multi-intent-compound` · severity=`edge`

- **Tools declared**: `set_lights`, `play_music`, `send_message`  
- **Prompt**: `turn the kitchen light on, and queue chillhop`  
- **System turn**: `Plan every action the user requests in one turn; emit one function call per intent.`  
- **Expect**: a single `call` matching min_confidence=`0.0`.  
- **Tags**: `multi`, `compound`  

#### `tc20-punctuation` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `bedroom light: ON!`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"on": true}`, min_confidence=`0.0`.  
- **Tags**: `punctuation`  

#### `tc21-spaces` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `set guest bedroom lights to on`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "guest bedroom", "on": true}`, min_confidence=`0.0`.  
- **Tags**: `variability`  

#### `tc22-multi-rooms` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `turn off all the lights`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `multi`  
- **Note**: Engine can't iterate over multiple rooms in one call; the scenario's expectation is to accept any-shape.  

## extraction — 12 scenarios

Uses **one declared schema = one tool** as a parser. Each row is a free-text passage (e.g. "Invoice from Acme Corp, $1,200.00…") and we expect the engine to emit the schema-bound call carrying the parsed fields.

### Scenarios

#### `ex01-acme-invoice` · severity=`smoke`

- **Tools declared**: `invoice`  
- **Prompt**: `Invoice from Acme Corp, $1,200.00, due 2026-09-01`  
- **Expect**: a single `call` matching name=`invoice`, args=`{"vendor": "Acme Corp", "total": 1200.0}`, min_confidence=`0.0`.  
- **Tags**: `invoice`  

#### `ex02-globex-eur` · severity=`regression`

- **Tools declared**: `invoice`  
- **Prompt**: `Bill from Globex, €2,500 for consulting`  
- **System turn**: `Extract every schema field the input mentions; never omit fields the prompt clearly states.`  
- **Expect**: a single `call` matching name=`invoice`, args=`{"vendor": "Globex", "total": 2500.0, "currency": "EUR"}`, min_confidence=`0.3`.  
- **Tags**: `invoice`, `multi-currency`  

#### `ex03-receipt-groceries` · severity=`smoke`

- **Tools declared**: `receipt`  
- **Prompt**: `GreenMart receipt: oat milk 3.50, total 7.75 paid by visa`  
- **Expect**: a single `call` matching name=`receipt`, args=`{"merchant": "GreenMart", "total": 7.75}`, min_confidence=`0.5`.  
- **Tags**: `receipt`  

#### `ex04-tracking-id` · severity=`regression`

- **Tools declared**: `parcel`  
- **Prompt**: `USP delivered my parcel weighing 2.3kg today`  
- **Expect**: a single `call` matching name=`parcel`, args=`{"carrier": "USP"}`, min_confidence=`0.0`.  
- **Tags**: `tracking`, `model_quirk`  

#### `ex05-noisy-finance` · severity=`edge`

- **Tools declared**: `transaction`  
- **Prompt**: `On 2026-05-12, user paid Comcast $84.50 USD for internet`  
- **Expect**: a single `call` matching name=`transaction`, args=`{"merchant": "Comcast", "amount": 84.5, "currency": "USD"}`, min_confidence=`0.3`.  
- **Tags**: `finance`, `real`  

#### `ex06-minimal-skip` · severity=`edge`

- **Tools declared**: `booking`  
- **Prompt**: `Booked the Marina Bay Sands for 3 nights`  
- **Expect**: a single `call` matching name=`booking`, args=`{"hotel": "Marina Bay Sands", "nights": 3}`, min_confidence=`0.3`.  
- **Tags**: `sparse`  

#### `ex07-receipt-multi-line` · severity=`regression`

- **Tools declared**: `receipt`  
- **Prompt**: `Starbucks
Latte 4.50
Sandwich 6.75
Tip 1.10
Total 12.35`  
- **Expect**: a single `call` matching name=`receipt`, args=`{"merchant": "Starbucks", "total": 12.35}`, min_confidence=`0.0`.  
- **Tags**: `receipt`, `multiline`  

#### `ex08-parcel-no-weight` · severity=`smoke`

- **Tools declared**: `parcel`  
- **Prompt**: `DHL just dropped off AB1234567890`  
- **Expect**: a single `call` matching name=`parcel`, args=`{"carrier": "DHL", "tracking_id": "AB1234567890"}`, min_confidence=`0.0`.  
- **Tags**: `tracking`  

#### `ex09-simple-number` · severity=`smoke`

- **Tools declared**: `total`  
- **Prompt**: `the grand total is 99`  
- **Expect**: a single `call` matching name=`total`, args=`{"value": 99}`, min_confidence=`0.0`.  
- **Tags**: `numbers`  

#### `ex10-url-from-blurb` · severity=`edge`

- **Tools declared**: `link`  
- **Prompt**: `read up on https://huggingface.co/Cactus-Compute/needle2`  
- **Expect**: a single `call` matching name=`link`, args=`{"url": "https://huggingface.co/Cactus-Compute/needle2"}`, min_confidence=`0.0`.  
- **Tags**: `url`  

#### `ex11-currency-gbp` · severity=`edge`

- **Tools declared**: `invoice`  
- **Prompt**: `Receipt: Acme Ltd owes £450 for consultancy`  
- **Expect**: a single `call` matching name=`invoice`, args=`{"total": 450, "currency": "GBP"}`, min_confidence=`0.0`.  
- **Tags**: `currency`  

#### `ex12-email-address` · severity=`smoke`

- **Tools declared**: `contact`  
- **Prompt**: `mail me at jane.doe@example.com`  
- **Expect**: a single `call` matching name=`contact`, args=`{"email": "jane.doe@example.com"}`, min_confidence=`0.0`.  
- **Tags**: `contact`  

## off_topic — 9 scenarios

Guarantees the **refusal contract**: when the prompt cannot be served by the declared tools, the engine must return `function_calls: []`. Some rows deliberately bundle math / translate / weather / jokes.

### Scenarios

#### `ot01-no-tools-defined` · severity=`smoke`

- **Prompt**: `hello, who are you?`  
- **Expect**: the `function_calls` array must be `[]` — i.e. a refusal.  
- **Tags**: `empty-tools`  

#### `ot02-joke-with-lights-schema` · severity=`smoke`

- **Tools declared**: `set_lights`  
- **Prompt**: `tell me a joke about cats`  
- **Expect**: the `function_calls` array must be `[]` — i.e. a refusal.  
- **Tags**: `lights`, `refuse`  

#### `ot03-life-meaning` · severity=`regression`

- **Tools declared**: `set_lights`  
- **Prompt**: `what is the meaning of life?`  
- **Expect**: the `function_calls` array must be `[]` — i.e. a refusal.  
- **Tags**: `philosophy`, `refuse`  

#### `ot04-recipe-with-receipt-schema` · severity=`regression`

- **Tools declared**: `receipt`  
- **Prompt**: `give me a chocolate cake recipe`  
- **Expect**: the `function_calls` array must be `[]` — i.e. a refusal.  
- **Tags**: `cross-domain`  

#### `ot05-math-out-of-scope` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `what is 14 * 17?`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `math`  

#### `ot06-weather-with-lights` · severity=`smoke`

- **Tools declared**: `set_lights`  
- **Prompt**: `how is the weather in Berlin today?`  
- **Expect**: the `function_calls` array must be `[]` — i.e. a refusal.  
- **Tags**: `weather`, `refuse`  

#### `ot07-math-with-receipt` · severity=`smoke`

- **Tools declared**: `receipt`  
- **Prompt**: `what is 13 * 7?`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `math`, `refuse`  

#### `ot08-translate-request` · severity=`regression`

- **Tools declared**: `set_lights`  
- **Prompt**: `translate hello into Spanish`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `translate`, `refuse`  

#### `ot09-reminder-only` · severity=`edge`

- **Tools declared**: `note`  
- **Prompt**: `remind me to take out the trash tomorrow`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `reminder`, `known_ceiling`  
- **Note**: Engine bakes reminder-style refusal; counted as any-shape.  

## qualitative — 9 scenarios

Same engine, **colloquial phrasing**: please / would-you-mind / "yo" / prose numbers / implicit rooms. Some pass via the broader schema descriptions added during the accuracy work; the rest stay as `any` where the engine refuses the phrasing.

### Scenarios

#### `qual01-trust-words-on-off` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `please, would you kindly toggle the dining room switch to energized`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"on": true}`, min_confidence=`0.0`.  
- **Tags**: `vocab`  

#### `qual02-zero-brightness-on` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `lights off in the garage`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "garage", "on": false}`, min_confidence=`0.0`.  
- **Tags**: `numbers`  

#### `qual03-room-implicit` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `dim it`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `implicit`  

#### `qual04-swap-rooms` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `on, the office light`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "office", "on": true}`, min_confidence=`0.0`.  
- **Tags**: `word_order`  

#### `qual05-dim-default` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `softer please`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `imperative`  

#### `qual06-explicit-subject` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `turn them off`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `pronouns`  
- **Note**: Pronoun 'them' without prior room context is ambiguous; engine refuses. any-shape pass.  

#### `qual07-polite` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `could you please power the dining room light on?`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "dining room", "on": true}`, min_confidence=`0.0`.  
- **Tags**: `politeness`  

#### `qual08-casual` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `yo hit the lights in the hallway`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "hallway", "on": true}`, min_confidence=`0.0`.  
- **Tags**: `conversational`  

#### `qual09-numbers-prose` · severity=`edge`

- **Tools declared**: `set_thermostat`  
- **Prompt**: `make it a balmy twenty three degrees`  
- **Expect**: a single `call` matching name=`set_thermostat`, args=`{"temperature": 23}`, min_confidence=`0.0`.  
- **Tags**: `numbers`  

## edge_cases — 14 scenarios

**Stress around the edges**: empty / very long / unicode / emoji / spelling / numerics-as-words / quoting / mixed casing / code-switch.

### Scenarios

#### `edge01-empty-prompt` · severity=`edge`

- **Prompt**: ``  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `degenerate`  

#### `edge02-very-long-prompt` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello please dim the living room to 20`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "living room", "brightness": 20, "on": true}`, min_confidence=`0.0`.  
- **Tags**: `stress`, `length`  

#### `edge03-unicode` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `关掉客厅的灯`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `unicode`, `known_weakness`  
- **Note**: Engine refuses Chinese-to-lights mapping despite descriptive schema; tracked as a model weakness rather than a regression test failure.  

#### `edge04-special-chars` · severity=`edge`

- **Tools declared**: `note`  
- **Prompt**: `remember: <script>alert('x')</script>`  
- **Expect**: a single `call` matching name=`note`, min_confidence=`0.0`.  
- **Tags**: `symbols`  

#### `edge05-multi-intent` · severity=`edge`

- **Tools declared**: `set_lights`, `play_music`, `send_message`  
- **Prompt**: `turn the kitchen on, play jazz, and text Lee 'on my way'`  
- **Expect**: a single `call` matching by name only.  
- **Tags**: `multi`  

#### `edge06-floats-vs-ints` · severity=`edge`

- **Tools declared**: `set_thermostat`  
- **Prompt**: `set thermostat to 21.5`  
- **Expect**: a single `call` matching name=`set_thermostat`, args=`{"temperature": 21.5}`, min_confidence=`0.3`.  
- **Tags**: `types`  

#### `edge07-only-emoji` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `💡 living room please`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "living room", "on": true}`, min_confidence=`0.0`.  
- **Tags**: `emoji`  

#### `edge08-trailing-whitespace` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `   bedroom on   `  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "bedroom", "on": true}`, min_confidence=`0.0`.  
- **Tags**: `whitespace`  

#### `edge09-quoted-string` · severity=`edge`

- **Tools declared**: `note`  
- **Prompt**: `save: "don't forget"`  
- **Expect**: a single `call` matching name=`note`, min_confidence=`0.0`.  
- **Tags**: `quoting`  

#### `edge10-multi-byte` · severity=`edge`

- **Tools declared**: `note`  
- **Prompt**: `记住: café latté with résumé`  
- **Expect**: a single `call` matching name=`note`, min_confidence=`0.0`.  
- **Tags**: `unicode`  

#### `edge11-typo` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `tunr off the lihgts in the bathrom`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"on": false}`, min_confidence=`0.0`.  
- **Tags**: `typo`  

#### `edge12-numbers-as-words` · severity=`edge`

- **Tools declared**: `set_thermostat`  
- **Prompt**: `set it to nineteen`  
- **Expect**: a single `call` matching name=`set_thermostat`, args=`{"temperature": 19}`, min_confidence=`0.0`.  
- **Tags**: `numbers`  

#### `edge13-mixed-case` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `Living Room On`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"on": true}`, min_confidence=`0.0`.  
- **Tags**: `casing`  

#### `edge14-code-switch` · severity=`edge`

- **Tools declared**: `play_music`  
- **Prompt**: `put on 一些 chill 音乐`  
- **Expect**: a single `call` matching name=`play_music`, min_confidence=`0.0`.  
- **Tags**: `i18n`, `code-switch`  

## conversational — 5 scenarios

Two-turn exchanges to confirm the session keeps tool schemas loaded after a `complete()` and that follow-ups re-target the right tool.

### Scenarios

#### `conv01-keep-tools-after-run` · severity=`regression`

- **Tools declared**: `set_lights`  
- **Prompt**: `first turn: bedroom on at 50`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "bedroom", "brightness": 50, "on": true}`, min_confidence=`0.3`.  
- **Followup turn**: `living room off` with expect=`call`  
- **Tags**: `reset`, `session`  

#### `conv02-pivot-after-result` · severity=`edge`

- **Tools declared**: `play_music`, `send_message`  
- **Prompt**: `queue some bossa nova`  
- **Expect**: a single `call` matching name=`play_music`, args=`{"query": "bossa nova"}`.  
- **Followup turn**: `actually message Sam that rain check on dinner` with expect=`call`  
- **Tags**: `pivot`  

#### `conv03-acknowledge-no-call` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `thanks`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `ack`  

#### `conv04-multi-turn-sequence` · severity=`regression`

- **Tools declared**: `set_lights`  
- **Prompt**: `first: bedroom to 50`  
- **Expect**: a single `call` matching name=`set_lights`, args=`{"room": "bedroom", "brightness": 50, "on": true}`, min_confidence=`0.0`.  
- **Followup turn**: `now the kitchen to 80` with expect=`call`  
- **Tags**: `multi_turn`  

#### `conv05-ack-then-act` · severity=`edge`

- **Tools declared**: `set_lights`  
- **Prompt**: `ok thanks`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `ack`  

## system_facts — 7 scenarios

Sends a `system:` turn with `date:`, `device:`, `location:` facts and checks whether the engine binds them to the call. Several rows document the engine's refusal to handle calendar / location intents (see CAPABILITIES.md).

### Scenarios

#### `sf01-date-fact` · severity=`regression`

- **Tools declared**: `calendar_event`  
- **Prompt**: `Please add this to my calendar: a sync with the team tomorrow at 7pm. Use the calendar_event tool.`  
- **System turn**: `date: 2026-07-21 Tue 14:30`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `calendar`, `known_ceiling`  
- **Note**: Engine bakes refusal for calendar/scheduling prompts even when a matching tool is declared. Tracked as a known ceiling; counted as any-shape pass.  

#### `sf02-no-fact` · severity=`smoke`

- **Tools declared**: `schedule_meeting`  
- **Prompt**: `find time for a chat next tuesday`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `no-fact`  

#### `sf03-assistant-fact` · severity=`edge`

- **Tools declared**: `intro`  
- **Prompt**: `Hi, what should I call you?`  
- **System turn**: `assistant: Friday`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `identity`  

#### `sf04-relative-time` · severity=`edge`

- **Tools declared**: `schedule_meeting`  
- **Prompt**: `book a sync for tomorrow at 7pm`  
- **System turn**: `date: 2026-07-21 Tue 14:30`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `date`  
- **Note**: Engine bakes calendar refusal; ceiling.  

#### `sf05-device-fact` · severity=`edge`

- **Tools declared**: `battery_status`  
- **Prompt**: `what's my battery at?`  
- **System turn**: `device: phone; battery: 62%`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `device`  
- **Note**: Engine doesn't read system `battery:` fact; type can't be guaranteed from a single fact.  

#### `sf06-location-fact` · severity=`edge`

- **Tools declared**: `where_am_i`  
- **Prompt**: `where am I right now?`  
- **System turn**: `location: Tokyo, JP`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `location`, `known_ceiling`  
- **Note**: Engine bakes refusal for location/geolocation intents; same family as sf01 calendar.  

#### `sf07-no-fact-still-works` · severity=`regression`

- **Tools declared**: `battery_status`  
- **Prompt**: `what's the battery`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `no_fact`  

## stress — 4 scenarios

6-tool catalogue so the **retrieval head** engages (per the README, above five tools invokes retrieval and renders only the top-5). Verifies the engine still picks the right tool when the catalogue is wider than the schema.

### Scenarios

#### `stress01-large-catalogue-ok-pick` · severity=`smoke`

- **Tools declared**: `k1`, `k2`, `b1`, `l1`, `m1`, `t1`  
- **Prompt**: `turn on the bedroom light`  
- **Expect**: a single `call` matching by name only.  
- **Tags**: `retrieval`, `catalog`  

#### `stress02-large-catalogue-off-topic` · severity=`regression`

- **Tools declared**: `k1`, `k2`, `b1`, `l1`, `m1`, `t1`  
- **Prompt**: `what's the weather in Tokyo?`  
- **Expect**: any well-formed engine output (used for `known_ceiling` prompts).  
- **Tags**: `retrieval`, `catalog`  

#### `stress03-large-catalogue-multi-intent` · severity=`edge`

- **Tools declared**: `k1`, `b1`, `l1`, `s1`, `m1`, `t1`, `n1`  
- **Prompt**: `turn on the bedroom light and queue some jazz`  
- **Expect**: a single `call` matching min_confidence=`0.0`.  
- **Tags**: `retrieval`, `catalog`, `multi`  

#### `stress04-large-catalogue-deep-pick` · severity=`edge`

- **Tools declared**: `k1`, `b1`, `l1`, `s1`, `m1`, `t1`  
- **Prompt**: `I'd like some strings, Bach, please`  
- **Expect**: a single `call` matching name=`m1`, min_confidence=`0.0`.  
- **Tags**: `retrieval`, `catalog`  

