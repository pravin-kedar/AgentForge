from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ToolAuthorizationError, ToolValidationError
from app.db.models import Activity, Destination, Hotel, Trip, TripStatus, User
from app.tools.registry import ToolSpec
from app.tools.schemas import CreateTripInput, DeleteTripInput, GetMyTripsInput, GetTripInput, UpdateTripInput

_VALID_STATUSES = {s.value for s in TripStatus}


def _trip_summary(trip: Trip) -> dict[str, Any]:
    return {
        "trip_id": trip.id,
        "destination": trip.destination,
        "start_date": trip.start_date.isoformat() if trip.start_date else None,
        "end_date": trip.end_date.isoformat() if trip.end_date else None,
        "status": trip.status.value,
        "budget": trip.budget,
        "notes": trip.notes,
        "itinerary": trip.itinerary,
    }


async def _find_destination(db: AsyncSession, name: str) -> Destination | None:
    result = await db.execute(select(Destination).where(Destination.name.ilike(name.strip())))
    return result.scalar_one_or_none()


async def _get_owned_trip(db: AsyncSession, trip_id: str, current_user: User) -> Trip | None:
    """Returns the Trip if owned by current_user, None if it doesn't exist,
    or raises ToolAuthorizationError if it belongs to someone else. The
    backend decides ownership - the LLM never supplies or influences whose
    trips are visible.
    """
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if trip is None:
        return None
    if trip.user_id != current_user.id:
        raise ToolAuthorizationError("You are not authorized to access this trip.")
    return trip


async def create_trip(args: CreateTripInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    destination = await _find_destination(db, args.destination)
    if destination is None:
        return {"error": "not_found", "message": f"No destination found matching '{args.destination}'. Ask the user to confirm the destination."}

    nights = (args.end_date - args.start_date).days
    itinerary: dict[str, Any] = {"hotel": None, "activities": []}
    hotel_cost = 0.0
    activities_cost = 0.0

    if args.hotel_id is not None:
        hotel_result = await db.execute(
            select(Hotel)
            .where(Hotel.id == args.hotel_id, Hotel.destination_id == destination.id)
            .options(selectinload(Hotel.rooms))
        )
        hotel = hotel_result.scalar_one_or_none()
        if hotel is None:
            raise ToolValidationError(f"hotel_id {args.hotel_id} does not exist in destination '{destination.name}'.")
        cheapest_room = min((r.price_per_night for r in hotel.rooms), default=0.0)
        hotel_cost = cheapest_room * nights
        itinerary["hotel"] = {"hotel_id": hotel.id, "name": hotel.name, "estimated_cost": hotel_cost}

    if args.activity_ids:
        activity_result = await db.execute(
            select(Activity).where(Activity.id.in_(args.activity_ids), Activity.destination_id == destination.id)
        )
        activities = activity_result.scalars().all()
        found_ids = {a.id for a in activities}
        missing = set(args.activity_ids) - found_ids
        if missing:
            raise ToolValidationError(
                f"activity_ids {sorted(missing)} do not exist in destination '{destination.name}'."
            )
        activities_cost = sum(a.price for a in activities)
        itinerary["activities"] = [{"activity_id": a.id, "name": a.name, "price": a.price} for a in activities]

    estimated_total_cost = round(hotel_cost + activities_cost, 2)
    itinerary["estimated_total_cost"] = estimated_total_cost

    trip = Trip(
        user_id=current_user.id,
        destination=destination.name,
        start_date=args.start_date,
        end_date=args.end_date,
        budget=args.budget,
        notes=args.notes,
        itinerary=itinerary,
        status=TripStatus.PLANNED,
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    return _trip_summary(trip)


async def get_my_trips(args: GetMyTripsInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    result = await db.execute(
        select(Trip).where(Trip.user_id == current_user.id).order_by(Trip.created_at.desc())
    )
    trips = result.scalars().all()
    return {"trips": [_trip_summary(t) for t in trips]}


async def get_trip(args: GetTripInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    trip = await _get_owned_trip(db, args.trip_id, current_user)
    if trip is None:
        return {"error": "not_found", "message": f"No trip with id {args.trip_id}."}
    return _trip_summary(trip)


async def update_trip(args: UpdateTripInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    trip = await _get_owned_trip(db, args.trip_id, current_user)
    if trip is None:
        return {"error": "not_found", "message": f"No trip with id {args.trip_id}."}

    if args.status is not None:
        if args.status not in _VALID_STATUSES:
            raise ToolValidationError(f"status must be one of {sorted(_VALID_STATUSES)}, got '{args.status}'.")
        trip.status = TripStatus(args.status)

    new_start = args.start_date or trip.start_date
    new_end = args.end_date or trip.end_date
    if new_start and new_end and new_end <= new_start:
        raise ToolValidationError("end_date must be after start_date.")

    if args.start_date is not None:
        trip.start_date = args.start_date
    if args.end_date is not None:
        trip.end_date = args.end_date
    if args.budget is not None:
        trip.budget = args.budget
    if args.notes is not None:
        trip.notes = args.notes

    await db.commit()
    await db.refresh(trip)
    return _trip_summary(trip)


async def delete_trip(args: DeleteTripInput, db: AsyncSession, current_user: User) -> dict[str, Any]:
    trip = await _get_owned_trip(db, args.trip_id, current_user)
    if trip is None:
        return {"error": "not_found", "message": f"No trip with id {args.trip_id}."}

    await db.delete(trip)
    await db.commit()
    return {"trip_id": args.trip_id, "deleted": True}


TRIP_TOOLS = [
    ToolSpec(
        name="create_trip",
        description=(
            "Save a new planned trip for the current user: destination, start_date, end_date, and optionally a "
            "hotel_id, a list of activity_ids, a budget, and notes. Only call this once the user has confirmed "
            "the destination and dates - never invent dates the user hasn't given."
        ),
        input_model=CreateTripInput,
        handler=create_trip,
        mutates_state=True,
    ),
    ToolSpec(
        name="get_my_trips",
        description="List all trips previously saved by the current user. Takes no parameters.",
        input_model=GetMyTripsInput,
        handler=get_my_trips,
    ),
    ToolSpec(
        name="get_trip",
        description="Get full details of one of the current user's saved trips by trip_id.",
        input_model=GetTripInput,
        handler=get_trip,
    ),
    ToolSpec(
        name="update_trip",
        description=(
            "Update fields on one of the current user's existing trips (dates, budget, notes, or status: "
            "planned/confirmed/cancelled). Requires trip_id; only include the fields being changed."
        ),
        input_model=UpdateTripInput,
        handler=update_trip,
        mutates_state=True,
    ),
    ToolSpec(
        name="delete_trip",
        description="Permanently delete one of the current user's saved trips by trip_id.",
        input_model=DeleteTripInput,
        handler=delete_trip,
        mutates_state=True,
    ),
]
