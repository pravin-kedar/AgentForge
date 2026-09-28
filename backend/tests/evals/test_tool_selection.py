import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.llm.factory import build_llm_provider
from tests.evals.eval_runner import run_eval
from tests.fake_llm import FakeLLMProvider, final_text, tool_call

DATA_PATH = Path(__file__).parent / "data" / "tool_selection_cases.json"


def load_cases() -> list[dict]:
    return json.loads(DATA_PATH.read_text())


async def test_tool_selection_eval_mocked() -> None:
    """CI-safe run: scripts the mock to answer correctly for every case
    except one deliberately-wrong pick, so the assertions prove the scoring
    math actually discriminates right from wrong - not just a tautological
    100% because the mock always agrees with itself.
    """
    cases = load_cases()
    responses = []
    for i, case in enumerate(cases):
        if case["expected_tool"] is None:
            responses.append(final_text("Hello! How can I help you plan your trip?"))
        elif i == 2:  # "Find me hotels in Jaipur..." -> deliberately answer with the wrong tool
            responses.append(tool_call("call_wrong", "get_weather", {"destination": "Jaipur"}))
        else:
            responses.append(tool_call(f"call_{i}", case["expected_tool"], {}))

    provider = FakeLLMProvider(responses=responses)
    report = await run_eval(cases, provider)

    assert report.tool_selection_accuracy == pytest.approx(0.9, abs=0.001)
    assert report.invalid_tool_rate == 0.0


@pytest.mark.skipif(
    get_settings().groq_api_key in ("", "test-groq-key", "your-groq-api-key"),
    reason="No real GROQ_API_KEY configured - run with a real key and --live-llm to evaluate live model behavior.",
)
async def test_tool_selection_eval_live(request: pytest.FixtureRequest) -> None:
    if not request.config.getoption("--live-llm"):
        pytest.skip("Pass --live-llm to run this against the real Groq API.")

    cases = load_cases()
    provider = build_llm_provider(get_settings())
    report = await run_eval(cases, provider)

    print(f"\n{report.summary()}")
    assert report.tool_selection_accuracy > 0.0
