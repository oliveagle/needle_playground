"""Needle 2 — happy path with the `@needle.tool` decorator.

Run:   python examples/01_basic_decorator.py
"""
from typing import Annotated

import needle


@needle.tool
def get_weather(city: str):
    """Get the current weather for a city."""
    # Real code would call an API; here we just echo the argument.
    return {"city": city, "temp_c": 27, "sky": "clear"}


@needle.tool
def set_thermostat(
    temperature: int,
    mode: Annotated[str, needle.Field(
        enum=["heat", "cool", "auto"],
        description="heating strategy",
    )] = "auto",
):
    """Set the thermostat."""
    return {"temperature": temperature, "mode": mode}


agent = needle.Needle(tools=[get_weather, set_thermostat])

queries = [
    "what's it like in Lagos right now?",
    "make it 21 and cool the room",
]

for q in queries:
    print(">", q)
    out = agent.run(q)
    print(out)
    print()
