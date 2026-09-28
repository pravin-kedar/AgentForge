import random
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.tools.registry import ToolSpec
from app.tools.schemas import GetWeatherInput

_CONDITIONS = ["Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Heavy Rain", "Humid"]


async def get_weather(args: GetWeatherInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    """Deterministic mock forecast: no real weather API is called.

    The same (destination, date) pair always yields the same simulated
    forecast, which keeps the demo believable across repeated calls without
    depending on a paid external service.
    """
    target_date = args.for_date or date.today()
    seed = f"{args.destination.strip().lower()}::{target_date.isoformat()}"
    rng = random.Random(seed)

    condition = rng.choice(_CONDITIONS)
    temp_c = rng.randint(18, 36)
    humidity = rng.randint(40, 95)

    return {
        "destination": args.destination,
        "date": target_date.isoformat(),
        "condition": condition,
        "temperature_celsius": temp_c,
        "humidity_percent": humidity,
        "source": "simulated forecast (demo data, not a live weather API)",
    }


WEATHER_TOOLS = [
    ToolSpec(
        name="get_weather",
        description=(
            "Get a weather forecast for a destination on a given date (defaults to today if no date given). "
            "Use this when the user asks about weather or when it's relevant to recommend indoor/outdoor "
            "activities. This is simulated demo forecast data, not a live weather feed."
        ),
        input_model=GetWeatherInput,
        handler=get_weather,
    ),
]
