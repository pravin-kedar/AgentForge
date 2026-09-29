import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.llm.factory import build_llm_provider
from tests.evals.eval_runner import args_match, run_eval
from tests.fake_llm import FakeLLMProvider, final_text, tool_call

DATA_PATH = Path(__file__).parent / "data" / "tool_selection_cases.json"


def load_cases() -> list[dict]:
    return json.loads(DATA_PATH.read_text())


def test_dataset_is_well_formed() -> None:
    from app.tools.registry import TOOL_REGISTRY

    cases = load_cases()
    assert len(cases) == 20
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert case["expected_tool"] is None or case["expected_tool"] in TOOL_REGISTRY, case
    covered = {c["expected_tool"] for c in cases if c["expected_tool"]}
    assert covered == set(TOOL_REGISTRY), f"tools with no eval question: {set(TOOL_REGISTRY) - covered}"


def test_args_match_is_case_insensitive_and_allows_extras() -> None:
    assert args_match({"destination": "Goa"}, {"destination": "goa", "guests": 1})
    assert args_match({"hotel_id": 4}, {"hotel_id": "4"})
    assert not args_match({"destination": "Goa"}, {"destination": "Kerala"})
    assert not args_match({"trip_id": "abc"}, {})


async def test_tool_selection_eval_mocked() -> None:
    """CI-safe run of the scoring logic. The scripted "model" answers every
    case correctly except one wrong tool (case 1) and one wrong argument
    (case 10), so the assertions prove the metrics actually discriminate
    rather than trivially reporting 100%.
    """
    cases = load_cases()
    responses = []
    for case in cases:
        if case["expected_tool"] is None:
            responses.append(final_text("Happy to help - where would you like to go?"))
        elif case["id"] == 1:
            responses.append(tool_call("c1", "get_weather", {"destination": "Jaipur"}))
        elif case["id"] == 10:
            responses.append(tool_call("c10", "get_weather", {"destination": "Kerala"}))
        else:
            responses.append(tool_call(f"c{case['id']}", case["expected_tool"], case["expected_args"]))

    report = await run_eval(cases, FakeLLMProvider(responses=responses))

    assert report.tool_selection_accuracy == pytest.approx(19 / 20)
    # 17 tool-correct cases with expected args; case 10 has the wrong destination.
    assert report.argument_accuracy == pytest.approx(16 / 17)
    assert report.invalid_tool_rate == 0.0


@pytest.mark.skipif(
    get_settings().groq_api_key in ("", "test-groq-key", "your-groq-api-key"),
    reason="No real GROQ_API_KEY configured - run with a real key and --live-llm to evaluate live model behavior.",
)
async def test_tool_selection_eval_live(request: pytest.FixtureRequest) -> None:
    if not request.config.getoption("--live-llm"):
        pytest.skip("Pass --live-llm to run this against the real Groq API.")

    report = await run_eval(
        load_cases(), build_llm_provider(get_settings()), pause_seconds=3, max_retries=5, backoff_seconds=20
    )

    print(f"\n\n{report.table()}\n\n{report.summary()}\n")
    assert report.tool_selection_accuracy > 0.0
