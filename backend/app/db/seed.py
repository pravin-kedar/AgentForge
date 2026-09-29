"""Idempotent demo-data seeder for destinations, hotels, rooms and activities.

Run with: python -m app.db.seed
Safe to run repeatedly - it's a no-op once destinations already exist.
"""
import asyncio
import logging
from typing import Any

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import Activity, Destination, Hotel, HotelRoom

logger = logging.getLogger("agentforge.seed")

DESTINATIONS: list[dict[str, Any]] = [
    {
        "name": "Goa",
        "country": "India",
        "description": "Beach state on India's west coast, known for sandy coastlines, nightlife and Portuguese heritage.",
        "best_season": "November to February",
        "hotels": [
            {
                "name": "Sunset Sands Resort",
                "star_rating": 4,
                "address": "Calangute Beach Road, Goa",
                "amenities": ["pool", "beach access", "spa", "free wifi"],
                "rooms": [
                    {"room_type": "Deluxe Sea View", "capacity": 2, "price_per_night": 6500, "total_rooms": 12},
                    {"room_type": "Suite", "capacity": 4, "price_per_night": 11000, "total_rooms": 5},
                ],
            },
            {
                "name": "Palm Grove Inn",
                "star_rating": 3,
                "address": "Baga Road, Goa",
                "amenities": ["pool", "free wifi", "breakfast included"],
                "rooms": [
                    {"room_type": "Standard", "capacity": 2, "price_per_night": 3200, "total_rooms": 20},
                ],
            },
        ],
        "activities": [
            {"name": "Scuba Diving at Grande Island", "category": "adventure", "price": 3500, "duration_hours": 4,
             "description": "Guided scuba dive with equipment for beginners and certified divers."},
            {"name": "Sunset Cruise on the Mandovi River", "category": "leisure", "price": 900, "duration_hours": 2,
             "description": "Evening boat cruise with live music and river views."},
            {"name": "Old Goa Heritage Walk", "category": "culture", "price": 500, "duration_hours": 3,
             "description": "Guided walking tour of Goa's Portuguese-era churches and monuments."},
            {"name": "Anjuna Flea Market Tour", "category": "shopping", "price": 0, "duration_hours": 3,
             "description": "Self-guided visit to Goa's famous Wednesday flea market."},
        ],
    },
    {
        "name": "Mumbai",
        "country": "India",
        "description": "India's financial capital, a coastal metropolis of colonial architecture, film industry and street food.",
        "best_season": "November to February",
        "hotels": [
            {
                "name": "Marine Drive Grand",
                "star_rating": 5,
                "address": "Marine Drive, Mumbai",
                "amenities": ["pool", "gym", "sea view", "spa"],
                "rooms": [
                    {"room_type": "Deluxe", "capacity": 2, "price_per_night": 9500, "total_rooms": 15},
                    {"room_type": "Executive Suite", "capacity": 3, "price_per_night": 16000, "total_rooms": 6},
                ],
            },
            {
                "name": "Colaba Comfort Stay",
                "star_rating": 3,
                "address": "Colaba Causeway, Mumbai",
                "amenities": ["free wifi", "breakfast included"],
                "rooms": [
                    {"room_type": "Standard", "capacity": 2, "price_per_night": 4200, "total_rooms": 18},
                ],
            },
        ],
        "activities": [
            {"name": "Gateway of India & Elephanta Caves Tour", "category": "culture", "price": 1200, "duration_hours": 5,
             "description": "Ferry to Elephanta Caves with a guided heritage tour."},
            {"name": "Bollywood Studio Tour", "category": "entertainment", "price": 2500, "duration_hours": 4,
             "description": "Behind-the-scenes tour of a working Bollywood film studio."},
            {"name": "Mumbai Street Food Walk", "category": "food", "price": 800, "duration_hours": 3,
             "description": "Guided tasting tour through Mumbai's iconic street food stalls."},
        ],
    },
    {
        "name": "Delhi",
        "country": "India",
        "description": "India's capital, blending Mughal-era monuments with modern government and commercial districts.",
        "best_season": "October to March",
        "hotels": [
            {
                "name": "Lutyens Heritage Hotel",
                "star_rating": 5,
                "address": "Connaught Place, New Delhi",
                "amenities": ["pool", "gym", "spa", "free wifi"],
                "rooms": [
                    {"room_type": "Deluxe", "capacity": 2, "price_per_night": 8800, "total_rooms": 20},
                ],
            },
            {
                "name": "Paharganj Budget Stay",
                "star_rating": 2,
                "address": "Paharganj, New Delhi",
                "amenities": ["free wifi"],
                "rooms": [
                    {"room_type": "Standard", "capacity": 2, "price_per_night": 1800, "total_rooms": 25},
                ],
            },
        ],
        "activities": [
            {"name": "Red Fort & Old Delhi Walking Tour", "category": "culture", "price": 700, "duration_hours": 4,
             "description": "Guided walk through Old Delhi's markets and Mughal monuments."},
            {"name": "Humayun's Tomb & Qutub Minar Tour", "category": "culture", "price": 900, "duration_hours": 5,
             "description": "Half-day tour of two UNESCO World Heritage sites."},
            {"name": "Chandni Chowk Food Trail", "category": "food", "price": 650, "duration_hours": 3,
             "description": "Guided tasting tour of Delhi's oldest food market."},
        ],
    },
    {
        "name": "Jaipur",
        "country": "India",
        "description": "The Pink City, capital of Rajasthan, famed for palaces, forts and vibrant bazaars.",
        "best_season": "October to March",
        "hotels": [
            {
                "name": "Amber Palace Heritage Resort",
                "star_rating": 5,
                "address": "Amer Road, Jaipur",
                "amenities": ["pool", "spa", "heritage architecture"],
                "rooms": [
                    {"room_type": "Royal Suite", "capacity": 2, "price_per_night": 13500, "total_rooms": 8},
                ],
            },
            {
                "name": "Pink City Inn",
                "star_rating": 3,
                "address": "MI Road, Jaipur",
                "amenities": ["free wifi", "breakfast included"],
                "rooms": [
                    {"room_type": "Standard", "capacity": 2, "price_per_night": 2800, "total_rooms": 16},
                ],
            },
        ],
        "activities": [
            {"name": "Amber Fort Tour with Elephant Ride", "category": "culture", "price": 1500, "duration_hours": 4,
             "description": "Guided tour of Amber Fort including an optional elephant ride."},
            {"name": "Hawa Mahal & City Palace Tour", "category": "culture", "price": 800, "duration_hours": 3,
             "description": "Walking tour covering Jaipur's iconic palace landmarks."},
            {"name": "Jaipur Bazaar Shopping Tour", "category": "shopping", "price": 0, "duration_hours": 2,
             "description": "Guided visit to Jaipur's textile, gem and handicraft markets."},
        ],
    },
    {
        "name": "Bangalore",
        "country": "India",
        "description": "India's tech hub, known for its parks, craft breweries and pleasant climate.",
        "best_season": "October to February",
        "hotels": [
            {
                "name": "MG Road Business Hotel",
                "star_rating": 4,
                "address": "MG Road, Bangalore",
                "amenities": ["gym", "free wifi", "business center"],
                "rooms": [
                    {"room_type": "Deluxe", "capacity": 2, "price_per_night": 5800, "total_rooms": 22},
                ],
            },
            {
                "name": "Koramangala Stay Inn",
                "star_rating": 3,
                "address": "Koramangala, Bangalore",
                "amenities": ["free wifi", "breakfast included"],
                "rooms": [
                    {"room_type": "Standard", "capacity": 2, "price_per_night": 3000, "total_rooms": 14},
                ],
            },
        ],
        "activities": [
            {"name": "Lalbagh Botanical Garden Walk", "category": "leisure", "price": 100, "duration_hours": 2,
             "description": "Guided walk through one of India's finest botanical gardens."},
            {"name": "Craft Brewery Tasting Tour", "category": "nightlife", "price": 1800, "duration_hours": 3,
             "description": "Tasting flight tour across Bangalore's craft breweries."},
            {"name": "Nandi Hills Sunrise Trip", "category": "adventure", "price": 1200, "duration_hours": 6,
             "description": "Early-morning trip to watch sunrise from Nandi Hills."},
        ],
    },
    {
        "name": "Kerala",
        "country": "India",
        "description": "Backwater state on India's southwest coast, known for houseboats, tea plantations and beaches.",
        "best_season": "September to March",
        "hotels": [
            {
                "name": "Alleppey Backwater Houseboat Resort",
                "star_rating": 4,
                "address": "Alleppey Backwaters, Kerala",
                "amenities": ["houseboat stay", "meals included", "backwater view"],
                "rooms": [
                    {"room_type": "Deluxe Houseboat Cabin", "capacity": 2, "price_per_night": 7500, "total_rooms": 10},
                ],
            },
            {
                "name": "Munnar Tea Hills Homestay",
                "star_rating": 3,
                "address": "Munnar, Kerala",
                "amenities": ["mountain view", "free wifi", "breakfast included"],
                "rooms": [
                    {"room_type": "Standard", "capacity": 2, "price_per_night": 3500, "total_rooms": 12},
                ],
            },
        ],
        "activities": [
            {"name": "Alleppey Backwater Houseboat Cruise", "category": "leisure", "price": 4000, "duration_hours": 8,
             "description": "Full-day houseboat cruise through Kerala's backwaters."},
            {"name": "Munnar Tea Plantation Trek", "category": "adventure", "price": 1000, "duration_hours": 4,
             "description": "Guided trek through rolling tea estates with a factory visit."},
            {"name": "Kovalam Beach Ayurvedic Spa Day", "category": "wellness", "price": 2500, "duration_hours": 3,
             "description": "Traditional Ayurvedic massage and wellness treatment session."},
        ],
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Destination.id).limit(1))
        if existing.scalar_one_or_none() is not None:
            logger.info("Seed data already present, skipping.")
            return

        for dest_data in DESTINATIONS:
            destination = Destination(
                name=dest_data["name"],
                country=dest_data["country"],
                description=dest_data["description"],
                best_season=dest_data["best_season"],
            )
            db.add(destination)
            await db.flush()

            for hotel_data in dest_data["hotels"]:
                hotel = Hotel(
                    destination_id=destination.id,
                    name=hotel_data["name"],
                    star_rating=hotel_data["star_rating"],
                    address=hotel_data["address"],
                    amenities=hotel_data["amenities"],
                )
                db.add(hotel)
                await db.flush()
                for room_data in hotel_data["rooms"]:
                    db.add(HotelRoom(hotel_id=hotel.id, **room_data))

            for activity_data in dest_data["activities"]:
                db.add(Activity(destination_id=destination.id, **activity_data))

        await db.commit()
        logger.info("Seeded %d destinations.", len(DESTINATIONS))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())
