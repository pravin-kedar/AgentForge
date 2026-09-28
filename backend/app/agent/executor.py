import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ToolAuthorizationError, ToolExecutionFailedError, ToolValidationError
from app.core.logging import log_event, redact
from app.db.models import ToolExecution, ToolExecutionStatus, User
from app.tools.validator import ValidatedToolCall

logger = logging.getLogger("agentforge.executor")


@dataclass
class ExecutionOutcome:
    tool_call_id: str
    tool_name: str
    status: ToolExecutionStatus
    result: dict[str, Any] | None
    error_message: str | None

    @property
    def succeeded(self) -> bool:
        return self.status == ToolExecutionStatus.SUCCESS


def _outcome_from_row(row: ToolExecution) -> ExecutionOutcome:
    return ExecutionOutcome(
        tool_call_id=row.tool_call_id,
        tool_name=row.tool_name,
        status=row.status,
        result=row.result,
        error_message=row.error_message,
    )


async def _find_existing_execution(
    db: AsyncSession, conversation_id: str, tool_call_id: str
) -> ToolExecution | None:
    result = await db.execute(
        select(ToolExecution).where(
            ToolExecution.conversation_id == conversation_id,
            ToolExecution.tool_call_id == tool_call_id,
        )
    )
    return result.scalar_one_or_none()


async def execute_tool_call(
    db: AsyncSession,
    conversation_id: str,
    current_user: User,
    validated: ValidatedToolCall,
) -> ExecutionOutcome:
    """Execute one already-validated tool call, with idempotency protection
    for state-mutating tools and full failure containment for everything
    else. This function never lets an exception escape to the agent loop as
    a "success" - every path returns an ExecutionOutcome with an honest
    status, and every attempt is persisted to `tool_executions` for
    observability.
    """
    spec = validated.spec
    existing_row: ToolExecution | None = None

    if spec.mutates_state:
        existing_row = await _find_existing_execution(db, conversation_id, validated.tool_call_id)
        if existing_row is not None and existing_row.status == ToolExecutionStatus.SUCCESS:
            # A prior attempt with this exact tool_call_id already succeeded
            # (network retry, duplicate client request, etc.) - replay the
            # cached result instead of mutating state a second time.
            log_event(
                logger, logging.INFO, "tool_idempotent_replay",
                tool_name=spec.name, tool_call_id=validated.tool_call_id, conversation_id=conversation_id,
            )
            return _outcome_from_row(existing_row)
        # A prior FAILED attempt (e.g. transient DB error) does not poison
        # the idempotency key forever - fall through and retry, updating the
        # existing row in place rather than inserting a duplicate.

    start = time.perf_counter()
    status: ToolExecutionStatus
    result: dict[str, Any] | None = None
    error_message: str | None = None

    try:
        result = await spec.handler(validated.args, db, current_user)
        status = ToolExecutionStatus.SUCCESS
    except (ToolAuthorizationError, ToolValidationError, ToolExecutionFailedError) as exc:
        status = ToolExecutionStatus.FAILED
        error_message = str(exc)
    except SQLAlchemyError:
        logger.exception("Database error while executing tool '%s'", spec.name)
        status = ToolExecutionStatus.FAILED
        error_message = "A database error occurred while running this tool."
    except Exception:
        logger.exception("Unexpected error while executing tool '%s'", spec.name)
        status = ToolExecutionStatus.FAILED
        error_message = "An unexpected error occurred while running this tool."

    if status == ToolExecutionStatus.FAILED:
        # A failing handler may have left a flush/commit half-done, which
        # puts the session's transaction in a state that must be rolled back
        # before it can be used again - otherwise persisting the failure
        # record below would itself raise PendingRollbackError. A no-op if
        # the handler raised before touching the session.
        await db.rollback()
        # Rollback expires every object the session is tracking, including
        # `current_user` - which a later tool call in the same multi-step
        # turn (e.g. get_my_trips after a failed create_trip) will read
        # attributes off of again. Refresh it now so that read doesn't hit
        # an implicit lazy-reload outside of an active async context.
        await db.refresh(current_user)

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    args_redacted = redact(validated.args.model_dump(mode="json"))

    if existing_row is not None:
        # Re-fetch rather than reuse the in-memory object: a rollback above
        # would have expired it, and refreshing a stale reference is not
        # worth relying on here.
        existing_row = await _find_existing_execution(db, conversation_id, validated.tool_call_id)
        assert existing_row is not None
        existing_row.arguments = args_redacted
        existing_row.status = status
        existing_row.result = result
        existing_row.error_message = error_message
        existing_row.latency_ms = latency_ms
        await db.commit()
    else:
        execution_row = ToolExecution(
            conversation_id=conversation_id,
            tool_call_id=validated.tool_call_id,
            tool_name=spec.name,
            arguments=args_redacted,
            status=status,
            result=result,
            error_message=error_message,
            latency_ms=latency_ms,
        )
        db.add(execution_row)
        try:
            await db.commit()
        except IntegrityError:
            # A concurrent request already recorded this exact
            # (conversation_id, tool_call_id) pair - fall back to whatever it
            # committed rather than erroring out or double-applying a mutation.
            await db.rollback()
            existing = await _find_existing_execution(db, conversation_id, validated.tool_call_id)
            if existing is not None:
                return _outcome_from_row(existing)
            raise

    log_event(
        logger, logging.INFO, "tool_executed",
        tool_name=spec.name, tool_call_id=validated.tool_call_id, conversation_id=conversation_id,
        status=status.value, latency_ms=latency_ms,
    )

    return ExecutionOutcome(
        tool_call_id=validated.tool_call_id,
        tool_name=spec.name,
        status=status,
        result=result,
        error_message=error_message,
    )
