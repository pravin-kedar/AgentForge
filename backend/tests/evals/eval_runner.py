from dataclasses import dataclass
from typing import Any

from app.agent.state import new_conversation_seed
from app.llm.base import LLMProvider
from app.tools.registry import TOOL_REGISTRY, get_llm_tool_schemas


@dataclass
class EvalCaseResult:
    input: str
    expected_tool: str | None
    actual_tool: str | None
    correct: bool
    invalid_tool: bool


@dataclass
class EvalReport:
    results: list[EvalCaseResult]

    @property
    def tool_selection_accuracy(self) -> float:
        return sum(r.correct for r in self.results) / len(self.results)

    @property
    def invalid_tool_rate(self) -> float:
        return sum(r.invalid_tool for r in self.results) / len(self.results)

    def summary(self) -> str:
        return (
            f"Tool Selection Accuracy: {self.tool_selection_accuracy:.1%}\n"
            f"Invalid Tool Rate: {self.invalid_tool_rate:.1%}"
        )


async def run_eval(cases: list[dict[str, Any]], provider: LLMProvider) -> EvalReport:
    """Sends each case's input through the same tool schema the real agent
    uses and records whether the model's (or scripted) tool pick matches the
    expected one. This is the same harness for both the mocked CI run and an
    optional live-LLM run - only the provider differs.
    """
    tools = get_llm_tool_schemas()
    results: list[EvalCaseResult] = []

    for case in cases:
        messages = [*new_conversation_seed(), {"role": "user", "content": case["input"]}]
        response = await provider.chat(messages, tools=tools)
        actual_tool = response.tool_calls[0].name if response.tool_calls else None
        invalid = actual_tool is not None and actual_tool not in TOOL_REGISTRY
        correct = actual_tool == case["expected_tool"]
        results.append(
            EvalCaseResult(
                input=case["input"],
                expected_tool=case["expected_tool"],
                actual_tool=actual_tool,
                correct=correct,
                invalid_tool=invalid,
            )
        )

    return EvalReport(results=results)
