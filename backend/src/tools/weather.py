from livekit.agents import function_tool
import json

@function_tool
async def get_weather(location: str) -> str:
    """Used to look up weather information."""
    return {"weather": "snowy", "temperature": -10}