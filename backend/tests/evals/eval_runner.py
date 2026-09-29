import asyncio
import json
from dataclasses import dataclass
from typing import Any

from app.agent.state import new_conversation_seed
from app.core.exceptions import LLMProviderError
from app.llm.base import LLMProvider, LLMResponse
from app.tools.registry import TOOL_REGISTRY, get_llm_tool_schemas


@dataclass
class EvalCaseResult:
    id: int
    input: str
    expected_tool: str | None
    actual_tool: str | None
    actual_args: dict[str, Any]
    tool_correct: bool
    # None when not applicable: wrong tool picked, or a no-tool case.
    args_correct: bool | None
    invalid_tool: bool


def _values_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()
    if isinstance(expected, int | float) and isinstance(actual, str):
        try:
            return float(actual) == float(expected)
        except ValueError:
            return False
    return expected == actual


def args_match(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    """Every expected key must be present with a matching value. Extra
    arguments the model adds (e.g. guests=1) are allowed."""
    return all(key in actual and _values_match(value, actual[key]) for key, value in expected.items())


@dataclass
class EvalReport:
    results: list[EvalCaseResult]

    @property
    def tool_selection_accuracy(self) -> float:
        return sum(r.tool_correct for r in self.results) / len(self.results)

    @property
    def argument_accuracy(self) -> float:
        """Of the cases where the right tool was picked, how many also got
        the key arguments right."""
        scored = [r for r in self.results if r.args_correct is not None]
        return sum(bool(r.args_correct) for r in scored) / len(scored) if scored else 0.0

    @property
    def invalid_tool_rate(self) -> float:
        return sum(r.invalid_tool for r in self.results) / len(self.results)

    def summary(self) -> str:
        passed = sum(r.tool_correct for r in self.results)
        return (
            f"Tool Selection Accuracy: {self.tool_selection_accuracy:.1%} ({passed}/{len(self.results)})\n"
            f"Argument Accuracy:       {self.argument_accuracy:.1%}\n"
            f"Invalid Tool Rate:       {self.invalid_tool_rate:.1%}"
        )

    def table(self) -> str:
        lines = [f"{'#':>3}  {'tool':4}  {'args':4}  {'expected':26} {'actual':26} question"]
        for r in self.results:
            tool_mark = "PASS" if r.tool_correct else "FAIL"
            args_mark = {True: "ok", False: "BAD", None: "-"}[r.args_correct]
            lines.append(
                f"{r.id:>3}  {tool_mark:4}  {args_mark:4}  {str(r.expected_tool):26} "
                f"{str(r.actual_tool):26} {r.input}"
            )
            if r.args_correct is False:
                lines.append(f"{'':16}got args: {json.dumps(r.actual_args)}")
        return "\n".join(lines)


async def _chat_with_rate_limit_retry(
    provider: LLMProvider,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    max_retries: int,
    backoff_seconds: float,
) -> LLMResponse:
    for attempt in range(max_retries + 1):
        try:
            return await provider.chat(messages, tools=tools)
        except LLMProviderError as exc:
            # Free-tier Groq keys have a low tokens-per-minute limit (each
            # request carries the full prompt + 11 tool schemas), and live
            # networks drop the odd request - both are worth waiting out.
            transient = any(s in exc.message for s in ("429", "timed out", "Could not reach", ": 5"))
            if not transient or attempt == max_retries:
                raise
            await asyncio.sleep(backoff_seconds * (attempt + 1))
    raise AssertionError("unreachable")


async def run_eval(
    cases: list[dict[str, Any]],
    provider: LLMProvider,
    pause_seconds: float = 0.0,
    max_retries: int = 0,
    backoff_seconds: float = 20.0,
) -> EvalReport:
    """Sends each case's question, with the same system prompt and tool
    schemas the real agent uses, and scores the model's *first* choice:
    which tool (or none), and whether the key arguments are right. The same
    harness serves the mocked CI run and the live run; only the provider
    differs.
    """
    tools = get_llm_tool_schemas()
    results: list[EvalCaseResult] = []

    for index, case in enumerate(cases):
        if pause_seconds and index:
            await asyncio.sleep(pause_seconds)
        messages = [*new_conversation_seed(), {"role": "user", "content": case["input"]}]
        try:
            response = await _chat_with_rate_limit_retry(provider, messages, tools, max_retries, backoff_seconds)
        except LLMProviderError as exc:
            # Score an unanswerable case as a miss and keep going, so one bad
            # request doesn't throw away the rest of a live run.
            results.append(
                EvalCaseResult(
                    id=case["id"], input=case["input"], expected_tool=case["expected_tool"],
                    actual_tool=f"<error: {exc.message}>", actual_args={}, tool_correct=False,
                    args_correct=None, invalid_tool=False,
                )
            )
            continue

        first_call = response.tool_calls[0] if response.tool_calls else None
        actual_tool = first_call.name if first_call else None
        try:
            actual_args = json.loads(first_call.arguments_json or "{}") if first_call else {}
        except json.JSONDecodeError:
            actual_args = {}

        tool_correct = actual_tool == case["expected_tool"]
        expected_args = case.get("expected_args")
        args_correct = (
            args_match(expected_args, actual_args) if tool_correct and expected_args is not None else None
        )

        results.append(
            EvalCaseResult(
                id=case["id"],
                input=case["input"],
                expected_tool=case["expected_tool"],
                actual_tool=actual_tool,
                actual_args=actual_args,
                tool_correct=tool_correct,
                args_correct=args_correct,
                invalid_tool=actual_tool is not None and actual_tool not in TOOL_REGISTRY,
            )
        )

    return EvalReport(results=results)
