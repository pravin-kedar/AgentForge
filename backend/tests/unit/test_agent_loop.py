from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import run_agent_loop
from app.agent.state import get_or_create_conversation
from app.db.models import Destination, ToolExecution, User
from tests.fake_llm import FakeLLMProvider, final_text, tool_call


async def _make_user(db: AsyncSession) -> User:
    user = User(email="agent-loop@example.com", hashed_password="x")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_final_response_without_any_tool_call(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    conversation = await get_or_create_conversation(db_session, None, user.id)
    await db_session.commit()

    llm = FakeLLMProvider(responses=[final_text("Hi! How can I help you plan a trip?")])

    result = await run_agent_loop(db_session, llm, conversation, user, "hello", max_tool_retries=2)

    assert result.message == "Hi! How can I help you plan a trip?"
    assert result.tool_activity == []


async def test_multi_step_tool_calls_then_final_response(db_session: AsyncSession) -> None:
    db_session.add(Destination(name="Goa", description="Beach state"))
    await db_session.commit()

    user = await _make_user(db_session)
    conversation = await get_or_create_conversation(db_session, None, user.id)
    await db_session.commit()

    llm = FakeLLMProvider(
        responses=[
            tool_call("call_1", "get_weather", {"destination": "Goa"}),
            tool_call("call_2", "search_activities", {"destination": "Goa"}),
            final_text("Goa looks sunny - here are some beach activities to consider."),
        ]
    )

    result = await run_agent_loop(db_session, llm, conversation, user, "Plan a trip to Goa", max_tool_retries=2)

    assert result.tool_activity == ["get_weather", "search_activities"]
    assert "sunny" in result.message.lower() or "Goa" in result.message

    count = await db_session.scalar(select(func.count()).select_from(ToolExecution))
    assert count == 2


async def test_invalid_tool_call_recovers_on_retry(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    conversation = await get_or_create_conversation(db_session, None, user.id)
    await db_session.commit()
    db_session.add(Destination(name="Goa", description="Beach state"))
    await db_session.commit()

    llm = FakeLLMProvider(
        responses=[
            tool_call("call_bad", "fetch_hotel_information", {"destination": "Goa"}),
            tool_call("call_good", "get_weather", {"destination": "Goa"}),
            final_text("Here's the forecast for Goa."),
        ]
    )

    result = await run_agent_loop(db_session, llm, conversation, user, "weather in Goa?", max_tool_retries=2)

    assert result.tool_activity == ["get_weather"]
    assert result.message == "Here's the forecast for Goa."


async def test_invalid_tool_calls_exhaust_retries_and_fail_gracefully(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    conversation = await get_or_create_conversation(db_session, None, user.id)
    await db_session.commit()

    llm = FakeLLMProvider(
        responses=[
            tool_call("call_1", "fetch_hotel_information", {}),
            tool_call("call_2", "fetch_hotel_information", {}),
            tool_call("call_3", "fetch_hotel_information", {}),
        ]
    )

    result = await run_agent_loop(db_session, llm, conversation, user, "book me something", max_tool_retries=2)

    assert result.tool_activity == []
    assert "wasn't able to complete" in result.message.lower()
