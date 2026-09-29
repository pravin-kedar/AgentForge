from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Destination, Hotel, HotelRoom, User
from app.tools.registry import ToolSpec
from app.tools.schemas import CheckHotelAvailabilityInput, GetHotelDetailsInput, SearchHotelsInput


async def _find_destination(db: AsyncSession, name: str) -> Destination | None:
    result = await db.execute(select(Destination).where(Destination.name.ilike(name.strip())))
    return result.scalar_one_or_none()


def _hotel_summary(hotel: Hotel) -> dict[str, Any]:
    cheapest = min((room.price_per_night for room in hotel.rooms), default=None)
    return {
        "hotel_id": hotel.id,
        "name": hotel.name,
        "star_rating": hotel.star_rating,
        "address": hotel.address,
        "amenities": hotel.amenities or [],
        "from_price_per_night": cheapest,
    }


async def search_hotels(args: SearchHotelsInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    destination = await _find_destination(db, args.destination)
    if destination is None:
        return {"destination": args.destination, "hotels": [], "message": f"No destination found matching '{args.destination}'."}

    result = await db.execute(
        select(Hotel).where(Hotel.destination_id == destination.id).options(selectinload(Hotel.rooms))
    )
    hotels = result.scalars().unique().all()

    matching = [h for h in hotels if any(room.capacity >= args.guests for room in h.rooms)]

    return {
        "destination": destination.name,
        "check_in": str(args.check_in) if args.check_in else None,
        "check_out": str(args.check_out) if args.check_out else None,
        "guests": args.guests,
        "hotels": [_hotel_summary(h) for h in matching],
    }


async def get_hotel_details(args: GetHotelDetailsInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    result = await db.execute(
        select(Hotel)
        .where(Hotel.id == args.hotel_id)
        .options(selectinload(Hotel.rooms), selectinload(Hotel.destination))
    )
    hotel = result.scalar_one_or_none()
    if hotel is None:
        return {"error": "not_found", "message": f"No hotel with id {args.hotel_id}."}

    return {
        "hotel_id": hotel.id,
        "name": hotel.name,
        "destination": hotel.destination.name,
        "star_rating": hotel.star_rating,
        "address": hotel.address,
        "amenities": hotel.amenities or [],
        "rooms": [
            {
                "room_id": room.id,
                "room_type": room.room_type,
                "capacity": room.capacity,
                "price_per_night": room.price_per_night,
                "total_rooms": room.total_rooms,
            }
            for room in hotel.rooms
        ],
    }


async def check_hotel_availability(
    args: CheckHotelAvailabilityInput, db: AsyncSession, current_user: User
) -> dict[str, Any]:
    result = await db.execute(
        select(Hotel).where(Hotel.id == args.hotel_id).options(selectinload(Hotel.rooms))
    )
    hotel = result.scalar_one_or_none()
    if hotel is None:
        return {"error": "not_found", "message": f"No hotel with id {args.hotel_id}."}

    nights = (args.check_out - args.check_in).days
    matching_rooms: list[HotelRoom] = [
        room
        for room in hotel.rooms
        if room.capacity >= args.guests
        and (args.room_type is None or room.room_type.lower() == args.room_type.lower())
    ]

    return {
        "hotel_id": hotel.id,
        "hotel_name": hotel.name,
        "check_in": str(args.check_in),
        "check_out": str(args.check_out),
        "nights": nights,
        "available_rooms": [
            {
                "room_type": room.room_type,
                "capacity": room.capacity,
                "price_per_night": room.price_per_night,
                "available_count": room.total_rooms,
                "estimated_total": round(room.price_per_night * nights, 2),
            }
            for room in matching_rooms
        ],
    }


HOTEL_TOOLS = [
    ToolSpec(
        name="search_hotels",
        description=(
            "Search hotels in a destination, optionally filtered by check-in/check-out dates and guest count. "
            "Use this when the user wants hotel options for a trip. Requires a destination name; dates and "
            "guests are optional and default to a single guest with no date filter."
        ),
        input_model=SearchHotelsInput,
        handler=search_hotels,
    ),
    ToolSpec(
        name="get_hotel_details",
        description=(
            "Get full details (rooms, prices, amenities) for one specific hotel by its numeric hotel_id. "
            "Use this after search_hotels has returned a hotel_id the user wants to know more about."
        ),
        input_model=GetHotelDetailsInput,
        handler=get_hotel_details,
    ),
    ToolSpec(
        name="check_hotel_availability",
        description=(
            "Check room availability and estimated total price for a specific hotel over a date range. "
            "Requires hotel_id, check_in and check_out dates. Use this before recommending a hotel booking."
        ),
        input_model=CheckHotelAvailabilityInput,
        handler=check_hotel_availability,
    ),
]
