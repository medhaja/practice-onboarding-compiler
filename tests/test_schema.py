import pytest
from pydantic import ValidationError

from onboarding.schema import AgentConfig, normalize_phone


def _minimal(**extra):
    return {
        "practice_id": "p01",
        "practice_name": {"value": "Test Clinic", "source": "hours.txt:1"},
        "specialty": {"value": "cardiology", "source": "hours.txt:2"},
        **extra,
    }


def test_minimal_config_validates():
    AgentConfig.model_validate(_minimal())


def test_source_must_be_file_line():
    bad = _minimal()
    bad["practice_name"]["source"] = "somewhere"
    with pytest.raises(ValidationError):
        AgentConfig.model_validate(bad)


def test_unknown_timezone_rejected():
    with pytest.raises(ValidationError):
        AgentConfig.model_validate(_minimal(timezone={"value": "Mars/Olympus", "source": "review"}))


@pytest.mark.parametrize("raw,expected", [
    ("(555) 555-0123", "(555) 555-0123"),
    ("555.555.0123", "(555) 555-0123"),
    ("1-555-555-0123", "(555) 555-0123"),
    ("(555) 01-23", None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected
