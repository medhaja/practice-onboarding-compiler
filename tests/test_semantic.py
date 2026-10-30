"""Semantic checker: the mock finds FAQ/script contradictions, and a bad LLM reply falls back to the mock."""
import json
import sys
import types

import pytest

from onboarding import semantic
from onboarding.compiler import compile_packet, load_packet


def test_stance_reads_negation_before_affirmation():
    assert semantic.stance("walk_ins", "We do not accept walk-ins.") == "no"
    assert semantic.stance("walk_ins", "Yes. We welcome walk-ins any time we are open.") == "yes"
    assert semantic.stance("new_patients", "We are not accepting new patients right now.") == "no"
    assert semantic.stance("refill_days", "Prescription refills are processed within 5 business days.") == "5"
    assert semantic.stance("telehealth", "Free parking is available.") is None


def test_clean_practice_has_no_contradictions(clean):
    packet, config = clean
    assert semantic.mock_check(config, packet) == []


def test_mock_flags_flipped_faq(clean):
    packet, config = clean
    faq = next(f for f in config.faqs if "walk-ins" in f.question)
    faq.answer = "Yes. We welcome walk-ins any time we are open."
    issues = semantic.mock_check(config, packet)
    assert [(i.type, i.key) for i in issues] == [("faq_script_contradiction", "walk_ins")]
    assert issues[0].targets == [f"faqs:{faq.id}"]
    assert len(issues[0].evidence) == 2


@pytest.mark.parametrize("pid,topic", [("p01", "walk_ins"), ("p02", "telehealth"), ("p03", "new_patients"),
                                       ("p04", "refill_days"), ("p05", "walk_ins")])
def test_mock_finds_planted_contradiction(pid, topic):
    packet = load_packet(pid)
    issues = semantic.semantic_check(compile_packet(packet), packet, mode="mock")
    assert [i.key for i in issues] == [topic]


def fake_litellm(monkeypatch, content: str):
    reply = types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])
    module = types.SimpleNamespace(completion=lambda **kwargs: reply)
    monkeypatch.setitem(sys.modules, "litellm", module)
    monkeypatch.setenv("LLM_MODEL", "test-model")


def test_auto_mode_without_model_uses_mock(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    packet = load_packet("p01")
    issues = semantic.semantic_check(compile_packet(packet), packet)
    assert [i.detector for i in issues] == ["mock"]


def test_llm_result_is_used_when_valid(monkeypatch):
    packet = load_packet("p01")
    config = compile_packet(packet)
    faq = next(f for f in config.faqs if "walk-ins" in f.question)
    line = next(l for l in config.script if "appointment only" in l.text)
    fake_litellm(monkeypatch, json.dumps({"contradictions": [
        {"topic": "Walk-ins", "faq_id": faq.id, "script_id": line.id, "explanation": "Opposite policies."}]}))
    issues = semantic.semantic_check(config, packet)
    assert [(i.key, i.detector) for i in issues] == [("walk_ins", "llm:test-model")]


@pytest.mark.parametrize("content", ["not json at all", '{"contradictions": [{"topic": "x"}]}',
                                     '{"contradictions": [{"topic": "x", "faq_id": "faq99", "script_id": "s1", '
                                     '"explanation": "made up"}]}'])
def test_malformed_llm_reply_falls_back_to_mock(monkeypatch, content):
    packet = load_packet("p01")
    fake_litellm(monkeypatch, content)
    issues = semantic.semantic_check(compile_packet(packet), packet)
    assert [(i.key, i.detector) for i in issues] == [("walk_ins", "mock")]
