"""Drive the loop by hand instead of letting `run()` do it.

This is how you integrate Needle into an existing agent that already has
its own tool-execution layer.
"""
import json

import needle


@needle.tool
def get_weather(city: str):
    """Look up the current weather for a city."""
    return {"city": city, "temp_c": 18, "sky": "rain"}


def main() -> None:
    agent = needle.Needle(tools=[get_weather])

    step = 0
    text = "what's it like in Lagos right now?"
    while step < 4:
        step += 1
        res = agent.complete(text)
        print(f"step {step}: {res}")
        if res["type"] != "call" or not res["function_calls"]:
            break
        # Execute the call ourselves.
        fn = res["function_calls"][0]
        # In real code dispatch into the matching function instead of eval.
        tool_map = {f.name: globals()[f.name] for f in [
            type("F", (), {"name": n}) for n in ("get_weather",)
        ]}
        result = get_weather(**fn["arguments"])
        text = json.dumps(result)


if __name__ == "__main__":
    main()
