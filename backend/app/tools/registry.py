from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

# First arg is `Any` rather than `BaseModel`: each handler takes its own
# specific input model, and Callable parameters are contravariant.
ToolHandler = Callable[[Any, AsyncSession, User], Awaitable[dict[str, Any]]]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler
    """Whether this tool changes state and must be idempotency-protected by
    the executor (see app/agent/executor.py)."""
    mutates_state: bool = False

    def to_llm_schema(self) -> dict[str, Any]:
        parameters = self.input_model.model_json_schema()
        parameters.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


def build_registry(specs: list[ToolSpec]) -> dict[str, ToolSpec]:
    registry: dict[str, ToolSpec] = {}
    for spec in specs:
        if spec.name in registry:
            raise ValueError(f"Duplicate tool name registered: '{spec.name}'")
        registry[spec.name] = spec
    return registry


def _load_specs() -> list[ToolSpec]:
    # Imported lazily (inside the function) to avoid a circular import at
    # module load time: the tool implementation modules import ToolSpec from
    # this module.
    from app.tools.activity_tools import ACTIVITY_TOOLS
    from app.tools.hotel_tools import HOTEL_TOOLS
    from app.tools.trip_tools import TRIP_TOOLS
    from app.tools.weather_tools import WEATHER_TOOLS

    return [*HOTEL_TOOLS, *ACTIVITY_TOOLS, *WEATHER_TOOLS, *TRIP_TOOLS]


TOOL_REGISTRY: dict[str, ToolSpec] = build_registry(_load_specs())


def get_llm_tool_schemas() -> list[dict[str, Any]]:
    return [spec.to_llm_schema() for spec in TOOL_REGISTRY.values()]
