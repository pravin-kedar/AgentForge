from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Activity, Destination, User
from app.tools.registry import ToolSpec
from app.tools.schemas import GetDestinationInfoInput, SearchActivitiesInput


async def _find_destination(db: AsyncSession, name: str) -> Destination | None:
    result = await db.execute(select(Destination).where(Destination.name.ilike(name.strip())))
    return result.scalar_one_or_none()


async def get_destination_info(args: GetDestinationInfoInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    destination = await _find_destination(db, args.destination)
    if destination is None:
        return {"error": "not_found", "message": f"No destination found matching '{args.destination}'."}

    return {
        "name": destination.name,
        "country": destination.country,
        "description": destination.description,
        "best_season": destination.best_season,
    }


async def search_activities(args: SearchActivitiesInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    destination = await _find_destination(db, args.destination)
    if destination is None:
        return {"destination": args.destination, "activities": [], "message": f"No destination found matching '{args.destination}'."}

    query = select(Activity).where(Activity.destination_id == destination.id)
    if args.category:
        query = query.where(Activity.category.ilike(f"%{args.category.strip()}%"))
    result = await db.execute(query)
    activities = result.scalars().all()

    return {
        "destination": destination.name,
        "category_filter": args.category,
        "activities": [
            {
                "activity_id": a.id,
                "name": a.name,
                "category": a.category,
                "description": a.description,
                "price": a.price,
                "duration_hours": a.duration_hours,
            }
            for a in activities
        ],
    }


ACTIVITY_TOOLS = [
    ToolSpec(
        name="get_destination_info",
        description=(
            "Get general information about a travel destination (description, country, best season to visit). "
            "Use this when the user asks what a destination is like or when to visit."
        ),
        input_model=GetDestinationInfoInput,
        handler=get_destination_info,
    ),
    ToolSpec(
        name="search_activities",
        description=(
            "Search things to do in a destination, optionally filtered by category "
            "(e.g. beach, adventure, culture, food, nightlife, shopping, wellness, leisure). "
            "Use this when the user wants activity or itinerary suggestions."
        ),
        input_model=SearchActivitiesInput,
        handler=search_activities,
    ),
]
