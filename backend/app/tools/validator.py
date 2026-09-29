import json
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.core.exceptions import ToolNotFoundError, ToolValidationError
from app.llm.base import ToolCallRequest
from app.tools.registry import TOOL_REGISTRY, ToolSpec


@dataclass
class ValidatedToolCall:
    tool_call_id: str
    spec: ToolSpec
    args: BaseModel


def validate_tool_call(call: ToolCallRequest) -> ValidatedToolCall:
    """Never trust the LLM's tool call at face value: confirm the tool name
    is real and that the arguments satisfy the tool's own Pydantic schema
    before anything is executed. Authorization (does this user own the
    target resource) is checked separately, inside each tool handler, once
    we're past this structural validation.
    """
    spec = TOOL_REGISTRY.get(call.name)
    if spec is None:
        known = ", ".join(sorted(TOOL_REGISTRY))
        raise ToolNotFoundError(f"Unknown tool '{call.name}'. Available tools: {known}.")

    try:
        raw_args = json.loads(call.arguments_json) if call.arguments_json.strip() else {}
    except json.JSONDecodeError as exc:
        raise ToolValidationError(f"Arguments for '{call.name}' are not valid JSON: {exc}") from exc

    try:
        args = spec.input_model.model_validate(raw_args)
    except ValidationError as exc:
        raise ToolValidationError(f"Arguments for '{call.name}' failed validation: {exc}") from exc

    return ValidatedToolCall(tool_call_id=call.id, spec=spec, args=args)
