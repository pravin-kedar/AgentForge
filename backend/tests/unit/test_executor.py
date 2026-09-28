from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.executor import execute_tool_call
from app.core.exceptions import ToolExecutionFailedError
from app.db.models import Conversation, Destination, Trip, User
from app.llm.base import ToolCallRequest
from app.tools.registry import ToolSpec
from app.tools.validator import ValidatedToolCall, validate_tool_call


async def _make_user_and_conversation(db: AsyncSession) -> tuple[User, Conversation]:
    user = User(email="idempotency@example.com", hashed_password="x")
    db.add(user)
    await db.flush()
    conversation = Conversation(user_id=user.id)
    db.add(conversation)
    await db.flush()
    await db.commit()
    await db.refresh(user)
    await db.refresh(conversation)
    return user, conversation


async def test_mutating_tool_replay_does_not_duplicate_state(db_session: AsyncSession) -> None:
    db_session.add(Destination(name="Goa", description="Beach state"))
    await db_session.commit()

    user, conversation = await _make_user_and_conversation(db_session)

    call = ToolCallRequest(
        id="call_create_trip_1",
        name="create_trip",
        arguments_json='{"destination": "Goa", "start_date": "2026-02-01", "end_date": "2026-02-05"}',
    )
    validated = validate_tool_call(call)

    first = await execute_tool_call(db_session, conversation.id, user, validated)
    second = await execute_tool_call(db_session, conversation.id, user, validated)

    assert first.succeeded
    assert second.succeeded
    assert first.result == second.result

    count = await db_session.scalar(select(func.count()).select_from(Trip))
    assert count == 1


class _AlwaysBlowsUpInput(BaseModel):
    pass


async def _blows_up(args, db, current_user):
    raise RuntimeError("boom")


async def test_unexpected_handler_exception_is_contained(db_session: AsyncSession) -> None:
    user, conversation = await _make_user_and_conversation(db_session)

    spec = ToolSpec(
        name="_test_blows_up",
        description="test-only tool that always raises",
        input_model=_AlwaysBlowsUpInput,
        handler=_blows_up,
    )
    validated = ValidatedToolCall(tool_call_id="call_boom", spec=spec, args=_AlwaysBlowsUpInput())

    outcome = await execute_tool_call(db_session, conversation.id, user, validated)

    assert not outcome.succeeded
    assert outcome.result is None
    assert outcome.error_message == "An unexpected error occurred while running this tool."


async def test_tool_execution_failed_error_message_is_preserved(db_session: AsyncSession) -> None:
    user, conversation = await _make_user_and_conversation(db_session)

    async def _fails_cleanly(args, db, current_user):
        raise ToolExecutionFailedError("Downstream booking service unavailable.")

    spec = ToolSpec(
        name="_test_fails_cleanly",
        description="test-only tool that raises a known failure",
        input_model=_AlwaysBlowsUpInput,
        handler=_fails_cleanly,
    )
    validated = ValidatedToolCall(tool_call_id="call_fail", spec=spec, args=_AlwaysBlowsUpInput())

    outcome = await execute_tool_call(db_session, conversation.id, user, validated)

    assert not outcome.succeeded
    assert outcome.error_message == "Downstream booking service unavailable."
