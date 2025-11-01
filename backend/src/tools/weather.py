from livekit.agents import function_tool
import json

@function_tool
async def get_weather(location: str) -> str:
    """Used to look up weather information."""
    weather_map = { "New York": {"weather": "snowy", "temperature": -10}, 
                    "London": {"weather": "rainy", "temperature": 10}, 
                    "Paris": {"weather": "sunny", "temperature": 20},
                    "Tokyo": {"weather": "cloudy", "temperature": 15},
                    }
    if location in weather_map:
        return weather_map[location]
    else:
        return {"weather": "sunny", "temperature": 20}