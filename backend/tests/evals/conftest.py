import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-llm",
        action="store_true",
        default=False,
        help="Run evals against the real configured LLM provider instead of a scripted mock.",
    )
