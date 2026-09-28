import pytest
from pydantic import BaseModel

from app.tools.registry import TOOL_REGISTRY, ToolSpec, build_registry, get_llm_tool_schemas


class _DummyInput(BaseModel):
    x: int


async def _dummy_handler(args, db, current_user):  # pragma: no cover - never invoked
    return {}


def test_duplicate_tool_names_rejected_at_build_time() -> None:
    specs = [
        ToolSpec(name="dup", description="a", input_model=_DummyInput, handler=_dummy_handler),
        ToolSpec(name="dup", description="b", input_model=_DummyInput, handler=_dummy_handler),
    ]
    with pytest.raises(ValueError, match="Duplicate tool name"):
        build_registry(specs)


def test_all_spec_tools_are_registered() -> None:
    expected = {
        "search_hotels",
        "get_hotel_details",
        "check_hotel_availability",
        "get_destination_info",
        "search_activities",
        "get_weather",
        "create_trip",
        "get_my_trips",
        "get_trip",
        "update_trip",
        "delete_trip",
    }
    assert expected == set(TOOL_REGISTRY)


def test_llm_tool_schema_shape() -> None:
    schemas = get_llm_tool_schemas()
    assert len(schemas) == len(TOOL_REGISTRY)
    for schema in schemas:
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


def test_mutating_tools_flagged_for_idempotency() -> None:
    mutating = {name for name, spec in TOOL_REGISTRY.items() if spec.mutates_state}
    assert mutating == {"create_trip", "update_trip", "delete_trip"}
