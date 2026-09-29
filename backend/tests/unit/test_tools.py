from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ToolAuthorizationError, ToolValidationError
from app.db.models import Activity, Hotel, User
from app.db.seed import seed
from app.tools import activity_tools, hotel_tools, trip_tools, weather_tools
from app.tools.schemas import (
    CheckHotelAvailabilityInput,
    CreateTripInput,
    DeleteTripInput,
    GetDestinationInfoInput,
    GetHotelDetailsInput,
    GetMyTripsInput,
    GetTripInput,
    GetWeatherInput,
    SearchActivitiesInput,
    SearchHotelsInput,
    UpdateTripInput,
)


@pytest_asyncio.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    await seed()
    return db_session


async def _user(db: AsyncSession, email: str) -> User:
    user = User(email=email, hashed_password="x")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _hotel_id(db: AsyncSession, name: str) -> int:
    return (await db.execute(select(Hotel.id).where(Hotel.name == name))).scalar_one()


# --- hotels ---------------------------------------------------------------

async def test_search_hotels_filters_by_guest_capacity(seeded: AsyncSession) -> None:
    user = await _user(seeded, "h1@example.com")
    result = await hotel_tools.search_hotels(SearchHotelsInput(destination="goa", guests=4), seeded, user)
    # Only Sunset Sands has a room (its Suite) that fits 4 guests.
    assert [h["name"] for h in result["hotels"]] == ["Sunset Sands Resort"]
    assert result["destination"] == "Goa"


async def test_search_hotels_unknown_destination_returns_empty(seeded: AsyncSession) -> None:
    user = await _user(seeded, "h2@example.com")
    result = await hotel_tools.search_hotels(SearchHotelsInput(destination="Atlantis"), seeded, user)
    assert result["hotels"] == []
    assert "No destination" in result["message"]


async def test_get_hotel_details_and_not_found(seeded: AsyncSession) -> None:
    user = await _user(seeded, "h3@example.com")
    hotel_id = await _hotel_id(seeded, "Marine Drive Grand")

    found = await hotel_tools.get_hotel_details(GetHotelDetailsInput(hotel_id=hotel_id), seeded, user)
    assert found["destination"] == "Mumbai"
    assert len(found["rooms"]) == 2

    missing = await hotel_tools.get_hotel_details(GetHotelDetailsInput(hotel_id=99999), seeded, user)
    assert missing["error"] == "not_found"


async def test_check_availability_computes_nights_and_total(seeded: AsyncSession) -> None:
    user = await _user(seeded, "h4@example.com")
    hotel_id = await _hotel_id(seeded, "Palm Grove Inn")
    args = CheckHotelAvailabilityInput(
        hotel_id=hotel_id, check_in=date(2026, 12, 1), check_out=date(2026, 12, 4), guests=2
    )
    result = await hotel_tools.check_hotel_availability(args, seeded, user)
    assert result["nights"] == 3
    assert result["available_rooms"][0]["estimated_total"] == 3200 * 3


# --- destinations / activities / weather ---------------------------------

async def test_get_destination_info(seeded: AsyncSession) -> None:
    user = await _user(seeded, "d1@example.com")
    result = await activity_tools.get_destination_info(GetDestinationInfoInput(destination="Kerala"), seeded, user)
    assert result["best_season"] == "September to March"


async def test_search_activities_with_category_filter(seeded: AsyncSession) -> None:
    user = await _user(seeded, "a1@example.com")
    result = await activity_tools.search_activities(
        SearchActivitiesInput(destination="Goa", category="adventure"), seeded, user
    )
    assert [a["name"] for a in result["activities"]] == ["Scuba Diving at Grande Island"]


async def test_weather_is_deterministic_per_destination_and_date(seeded: AsyncSession) -> None:
    user = await _user(seeded, "w1@example.com")
    args = GetWeatherInput(destination="Goa", for_date=date(2026, 12, 25))
    first = await weather_tools.get_weather(args, seeded, user)
    second = await weather_tools.get_weather(args, seeded, user)
    assert first == second
    assert "simulated" in first["source"]


# --- trips ----------------------------------------------------------------

async def test_create_trip_estimates_cost_from_hotel_and_activities(seeded: AsyncSession) -> None:
    user = await _user(seeded, "t1@example.com")
    hotel_id = await _hotel_id(seeded, "Palm Grove Inn")
    activity_ids = list(
        (await seeded.execute(select(Activity.id).where(Activity.name.like("Sunset Cruise%")))).scalars()
    )

    result = await trip_tools.create_trip(
        CreateTripInput(
            destination="Goa",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 5),
            hotel_id=hotel_id,
            activity_ids=activity_ids,
        ),
        seeded,
        user,
    )

    # 4 nights at 3200 + one 900 cruise.
    assert result["itinerary"]["estimated_total_cost"] == 4 * 3200 + 900
    assert result["status"] == "planned"


async def test_create_trip_rejects_hotel_from_another_destination(seeded: AsyncSession) -> None:
    user = await _user(seeded, "t2@example.com")
    mumbai_hotel = await _hotel_id(seeded, "Marine Drive Grand")
    with pytest.raises(ToolValidationError):
        await trip_tools.create_trip(
            CreateTripInput(
                destination="Goa", start_date=date(2026, 12, 1), end_date=date(2026, 12, 5), hotel_id=mumbai_hotel
            ),
            seeded,
            user,
        )


async def test_get_my_trips_only_returns_own_trips(seeded: AsyncSession) -> None:
    alice = await _user(seeded, "alice@example.com")
    bob = await _user(seeded, "bob@example.com")
    trip_args = CreateTripInput(destination="Goa", start_date=date(2026, 12, 1), end_date=date(2026, 12, 5))
    await trip_tools.create_trip(trip_args, seeded, alice)

    assert len((await trip_tools.get_my_trips(GetMyTripsInput(), seeded, alice))["trips"]) == 1
    assert (await trip_tools.get_my_trips(GetMyTripsInput(), seeded, bob))["trips"] == []


async def test_update_trip_status_and_validation(seeded: AsyncSession) -> None:
    user = await _user(seeded, "t3@example.com")
    created = await trip_tools.create_trip(
        CreateTripInput(destination="Goa", start_date=date(2026, 12, 1), end_date=date(2026, 12, 5)), seeded, user
    )
    trip_id = created["trip_id"]

    updated = await trip_tools.update_trip(UpdateTripInput(trip_id=trip_id, status="confirmed"), seeded, user)
    assert updated["status"] == "confirmed"

    with pytest.raises(ToolValidationError):
        await trip_tools.update_trip(UpdateTripInput(trip_id=trip_id, status="teleported"), seeded, user)

    with pytest.raises(ToolValidationError):
        await trip_tools.update_trip(UpdateTripInput(trip_id=trip_id, end_date=date(2026, 11, 1)), seeded, user)


async def test_trip_ownership_enforced_on_read_update_delete(seeded: AsyncSession) -> None:
    owner = await _user(seeded, "owner@example.com")
    intruder = await _user(seeded, "intruder@example.com")
    created = await trip_tools.create_trip(
        CreateTripInput(destination="Goa", start_date=date(2026, 12, 1), end_date=date(2026, 12, 5)), seeded, owner
    )
    trip_id = created["trip_id"]

    with pytest.raises(ToolAuthorizationError):
        await trip_tools.get_trip(GetTripInput(trip_id=trip_id), seeded, intruder)
    with pytest.raises(ToolAuthorizationError):
        await trip_tools.update_trip(UpdateTripInput(trip_id=trip_id, notes="mine now"), seeded, intruder)
    with pytest.raises(ToolAuthorizationError):
        await trip_tools.delete_trip(DeleteTripInput(trip_id=trip_id), seeded, intruder)

    # Owner can still delete it afterward, and then it's gone.
    assert (await trip_tools.delete_trip(DeleteTripInput(trip_id=trip_id), seeded, owner))["deleted"] is True
    assert (await trip_tools.get_trip(GetTripInput(trip_id=trip_id), seeded, owner))["error"] == "not_found"
