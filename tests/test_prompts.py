from app.services.prompts import (
    CBT_SYSTEM_PROMPT,
    DISTORTIONS,
    TASK_GENERATOR_SYSTEM_PROMPT,
)


def test_distortions_present_in_cbt_prompt():
    for d in DISTORTIONS:
        assert d in CBT_SYSTEM_PROMPT


def test_distortions_present_in_generator_prompt():
    for d in DISTORTIONS:
        assert d in TASK_GENERATOR_SYSTEM_PROMPT


def test_distortions_count():
    assert len(DISTORTIONS) == 17
    assert len(set(DISTORTIONS)) == 17
