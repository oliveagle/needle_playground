"""Schema-driven extraction.

We pin two patterns side by side so you can pick the one that fits:

* **Tool-driven**  — declare a tool, run `agent.complete(prompt)` and inspect
  the single returned function call.
* **`needle.extract`**  — one-shot; pass the text, the engine re-inits with one
  schema, you get a Pydantic-flavoured dict back.
"""
import json
from typing import Annotated

import needle


@needle.tool
def get_invoice(
    vendor: Annotated[str, needle.Field(description="vendor name")],
    total: Annotated[float, needle.Field(ge=0, description="amount due")],
    currency: Annotated[str, needle.Field(description="ISO 4217 code")] = "USD",
):
    """A purchase invoice."""
    return {"vendor": vendor, "total": total, "currency": currency}


def tool_driven() -> None:
    print("=== tool-driven (complete) ===")
    agent = needle.Needle(tools=[get_invoice])
    passages = [
        "Invoice from Acme Corp, $1,200.00, due 2026-09-01",
        "Bill from Globex, €2,500 for consulting",
        "Receipt: Initech Inc. owes us 87.5 USD for tooling",
    ]
    for txt in passages:
        call = agent.complete(txt)
        print(json.dumps({"input": txt, "call": call}, indent=2, ensure_ascii=False))
        # Free the per-call state so the next prompt starts fresh.
        agent.reset()


def low_level_extract() -> None:
    print("\n=== needle.extract (one-shot) ===")
    text = "Invoice from Acme Corp, $1,200.00, due 2026-09-01"
    result = needle.extract(text, get_invoice)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    tool_driven()
    low_level_extract()
