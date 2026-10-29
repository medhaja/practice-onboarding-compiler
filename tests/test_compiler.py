import json
from pathlib import Path

import pytest

from onboarding.compiler import compile_packet, list_practices, load_packet, parse_time
from onboarding.schema import AgentConfig

GOLDEN = Path(__file__).parent / "golden" / "p06_agent_config.json"


def _all_sources(obj):
    if isinstance(obj, dict):
        if "source" in obj:
            yield obj["source"]
        for v in obj.values():
            yield from _all_sources(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_sources(v)


@pytest.mark.parametrize("practice_id", list_practices())
def test_config_passes_schema_and_every_source_points_at_a_real_line(practice_id):
    packet = load_packet(practice_id)
    config = compile_packet(packet)
    dumped = config.model_dump(mode="json")
    AgentConfig.model_validate(dumped)
    sources = list(_all_sources(dumped))
    assert sources
    for src in sources:
        assert packet.line(src).strip(), src


def test_clean_practice_matches_golden_config():
    config = compile_packet(load_packet("p06"))
    assert config.model_dump(mode="json") == json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_hours_and_provenance():
    config = compile_packet(load_packet("p01"))
    saturday = next(h for h in config.hours if h.day == "saturday")
    assert (saturday.open, saturday.close, saturday.source) == ("09:00", "12:00", "hours.txt:13")
    assert next(h for h in config.hours if h.day == "sunday").closed


def test_spanish_line_adds_language():
    langs = [l.value for l in compile_packet(load_packet("p02")).languages]
    assert langs == ["en", "es"]


def test_invalid_phone_is_kept_raw_with_no_normalized_value():
    phone = compile_packet(load_packet("p01")).main_phone
    assert phone.raw == "(555) 01-23" and phone.value is None


@pytest.mark.parametrize("text,expected", [("9 AM", "09:00"), ("12 PM", "12:00"), ("4:30 pm", "16:30"),
                                           ("12:00 AM", "00:00"), ("noon", "12:00")])
def test_parse_time(text, expected):
    assert parse_time(text) == expected
