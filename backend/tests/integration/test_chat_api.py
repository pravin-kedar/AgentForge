from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ToolExecution, Trip, User
from tests.fake_llm import FakeLLMProvider, final_text, tool_call


async def test_chat_happy_path_no_tool_needed(
    client: AsyncClient, fake_llm: FakeLLMProvider, auth_headers: dict[str, str]
) -> None:
    fake_llm.responses.append(final_text("Hi! Where would you like to travel?"))

    response = await client.post("/api/v1/chat", json={"message": "hi"}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Hi! Where would you like to travel?"
    assert body["tool_activity"] == []
    assert body["conversation_id"]


async def test_chat_executes_tool_and_reports_activity(
    client: AsyncClient, fake_llm: FakeLLMProvider, auth_headers: dict[str, str]
) -> None:
    fake_llm.responses.extend(
        [
            tool_call("call_1", "get_weather", {"destination": "Goa"}),
            final_text("It looks sunny in Goa - great for the beach!"),
        ]
    )

    response = await client.post(
        "/api/v1/chat", json={"message": "What's the weather in Goa?"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_activity"] == ["get_weather"]
    assert "goa" in body["message"].lower()


async def test_chat_continues_existing_conversation(
    client: AsyncClient, fake_llm: FakeLLMProvider, auth_headers: dict[str, str]
) -> None:
    fake_llm.responses.append(final_text("Sure, tell me the destination."))
    first = await client.post("/api/v1/chat", json={"message": "I want to plan a trip"}, headers=auth_headers)
    conversation_id = first.json()["conversation_id"]

    fake_llm.responses.append(final_text("Got it, Goa it is."))
    second = await client.post(
        "/api/v1/chat",
        json={"conversation_id": conversation_id, "message": "Goa"},
        headers=auth_headers,
    )

    assert second.json()["conversation_id"] == conversation_id
    # The second LLM call should have seen the full prior history (system + 2 user + 1 assistant turns).
    assert len(fake_llm.calls[-1]) == 4


async def test_chat_rejects_unknown_conversation_id(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/chat", json={"conversation_id": "does-not-exist", "message": "hi"}, headers=auth_headers
    )
    assert response.status_code == 404


async def test_agent_cannot_read_another_users_trip(
    client: AsyncClient, fake_llm: FakeLLMProvider, auth_headers: dict[str, str], db_session: AsyncSession
) -> None:
    victim = User(email="victim@example.com", hashed_password="x")
    db_session.add(victim)
    await db_session.commit()
    await db_session.refresh(victim)

    trip = Trip(user_id=victim.id, destination="Goa", start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
    db_session.add(trip)
    await db_session.commit()
    await db_session.refresh(trip)

    fake_llm.responses.extend(
        [
            tool_call("call_1", "get_trip", {"trip_id": trip.id}),
            final_text("Here's what I found."),
        ]
    )

    # auth_headers belongs to a *different* registered user than `victim`.
    response = await client.post(
        "/api/v1/chat", json={"message": f"show me trip {trip.id}"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["tool_activity"] == ["get_trip"]

    result = await db_session.execute(select(ToolExecution).where(ToolExecution.tool_name == "get_trip"))
    execution = result.scalar_one()
    assert execution.status.value == "failed"
    assert execution.result is None


async def test_tool_failure_is_never_reported_as_success(
    client: AsyncClient, fake_llm: FakeLLMProvider, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tools.registry import TOOL_REGISTRY

    async def _broken_create_trip(args, db, current_user):
        raise RuntimeError("simulated database outage")

    monkeypatch.setattr(TOOL_REGISTRY["create_trip"], "handler", _broken_create_trip)

    fake_llm.responses.extend(
        [
            tool_call(
                "call_1",
                "create_trip",
                {"destination": "Goa", "start_date": "2026-03-01", "end_date": "2026-03-05"},
            ),
            final_text("I wasn't able to save that trip - please try again shortly."),
        ]
    )

    response = await client.post(
        "/api/v1/chat", json={"message": "Book my Goa trip"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert "wasn't able" in body["message"].lower() or "sorry" in body["message"].lower()

    result = await client.get("/api/v1/conversations", headers=auth_headers)
    assert result.status_code == 200
