from app.agent.prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION


def test_system_prompt_is_versioned() -> None:
    assert SYSTEM_PROMPT_VERSION
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT) > 0


def test_system_prompt_forbids_inventing_data() -> None:
    assert "never invent" in SYSTEM_PROMPT.lower()


def test_system_prompt_never_reveals_internals() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert "do not reveal" in lowered or "do not expose" in lowered
