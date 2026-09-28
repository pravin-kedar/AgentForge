import pytest

from app.core.exceptions import ToolNotFoundError, ToolValidationError
from app.llm.base import ToolCallRequest
from app.tools.validator import validate_tool_call


def test_unknown_tool_name_rejected() -> None:
    call = ToolCallRequest(id="call_1", name="fetch_hotel_information", arguments_json="{}")
    with pytest.raises(ToolNotFoundError):
        validate_tool_call(call)


def test_malformed_json_arguments_rejected() -> None:
    call = ToolCallRequest(id="call_1", name="get_weather", arguments_json="{not valid json")
    with pytest.raises(ToolValidationError):
        validate_tool_call(call)


def test_missing_required_argument_rejected() -> None:
    call = ToolCallRequest(id="call_1", name="get_hotel_details", arguments_json="{}")
    with pytest.raises(ToolValidationError):
        validate_tool_call(call)


def test_valid_call_parses_into_typed_args() -> None:
    call = ToolCallRequest(id="call_1", name="get_weather", arguments_json='{"destination": "Goa"}')
    validated = validate_tool_call(call)
    assert validated.spec.name == "get_weather"
    assert validated.args.destination == "Goa"
    assert validated.tool_call_id == "call_1"


def test_date_ordering_validation_on_create_trip() -> None:
    call = ToolCallRequest(
        id="call_1",
        name="create_trip",
        arguments_json='{"destination": "Goa", "start_date": "2026-01-10", "end_date": "2026-01-05"}',
    )
    with pytest.raises(ToolValidationError):
        validate_tool_call(call)
