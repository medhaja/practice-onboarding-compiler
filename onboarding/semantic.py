"""Semantic check: does an FAQ answer contradict the call script?

Two backends return the same Issue shape:
  mock  keyword and pattern rules per topic. Always available, no network.
  llm   a model called through LiteLLM. Used only when LLM_MODEL is set and
        litellm is installed. Its JSON is validated; anything malformed falls
        back to the mock result so the demo never breaks.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from pydantic import BaseModel, ValidationError

from .compiler import Packet
from .schema import AgentConfig
from .validator import Evidence, Issue, make_issue

log = logging.getLogger(__name__)

TOPICS = ["walk_ins", "telehealth", "new_patients", "refill_days"]

# Checked in order; the first matching pattern sets the stance, so negations come first.
STANCE_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "walk_ins": [("no", r"by appointment only|do not accept walk-ins|no walk-ins"),
                 ("yes", r"welcome walk-ins|walk-ins are welcome|accept walk-ins")],
    "telehealth": [("no", r"do not offer telehealth|no telehealth|in-person only"),
                   ("yes", r"offer telehealth|telehealth visits are available")],
    "new_patients": [("no", r"not accepting new patients"),
                     ("yes", r"\b(?:we are|we're|the practice is) accepting new patients")],
}
REFILL_RE = re.compile(r"refills? (?:are )?processed within (\d+) business days?", re.I)


def stance(topic: str, text: str) -> Optional[str]:
    if topic == "refill_days":
        m = REFILL_RE.search(text)
        return m.group(1) if m else None
    for value, pattern in STANCE_PATTERNS[topic]:
        if re.search(pattern, text, re.I):
            return value
    return None


def _contradiction(faq, script_line, topic: str, why: str, detector: str) -> Issue:
    return make_issue(
        "faq_script_contradiction", topic,
        f"FAQ '{faq.question}' contradicts the call script. {why}",
        [Evidence(source=faq.source, text=faq.answer), Evidence(source=script_line.source, text=script_line.text)],
        [f"faqs:{faq.id}"], detector=detector)


def mock_check(config: AgentConfig, packet: Packet) -> list[Issue]:
    issues = []
    for topic in TOPICS:
        script_hits = [(l, s) for l in config.script if (s := stance(topic, l.text))]
        if not script_hits:
            continue
        line, script_stance = script_hits[0]
        for faq in config.faqs:
            faq_stance = stance(topic, faq.answer)
            if faq_stance and faq_stance != script_stance:
                why = f"Script says '{line.text}' but the FAQ says '{faq.answer}'."
                issues.append(_contradiction(faq, line, topic, why, "mock"))
                break
    return issues


class LLMFinding(BaseModel):
    topic: str
    faq_id: str
    script_id: str
    explanation: str


class LLMResult(BaseModel):
    contradictions: list[LLMFinding]


PROMPT = """You check a medical practice's front-desk material for contradictions.
Compare each FAQ answer with the call script lines. Report only real contradictions of fact or policy
(hours, walk-ins, telehealth, accepting new patients, refill turnaround and similar).
Use one of these topic names when it fits: {topics}; otherwise a short snake_case name.
Reply with JSON only: {{"contradictions": [{{"topic": "...", "faq_id": "...", "script_id": "...", "explanation": "..."}}]}}

FAQ answers:
{faqs}

Call script lines:
{script}
"""


def llm_model() -> Optional[str]:
    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        return None
    try:
        import litellm  # noqa: F401
    except ImportError:
        log.warning("LLM_MODEL is set but litellm is not installed; using the mock checker")
        return None
    return model


def llm_check(config: AgentConfig, packet: Packet, model: str) -> list[Issue]:
    import litellm

    faqs = "\n".join(f"[{f.id}] Q: {f.question} A: {f.answer}" for f in config.faqs)
    script = "\n".join(f"[{l.id}] {l.text}" for l in config.script)
    response = litellm.completion(
        model=model, temperature=0, timeout=60,
        messages=[{"role": "user", "content": PROMPT.format(topics=", ".join(TOPICS), faqs=faqs, script=script)}])
    text = response.choices[0].message.content or ""
    match = re.search(r"\{.*\}", text, re.S)
    result = LLMResult.model_validate(json.loads(match.group(0) if match else text))

    faq_by_id = {f.id: f for f in config.faqs}
    line_by_id = {l.id: l for l in config.script}
    issues, seen = [], set()
    for finding in result.contradictions:
        faq, line = faq_by_id.get(finding.faq_id), line_by_id.get(finding.script_id)
        if not faq or not line:
            raise ValueError(f"model cited unknown ids {finding.faq_id!r}/{finding.script_id!r}")
        topic = re.sub(r"[^a-z0-9_]+", "_", finding.topic.lower()).strip("_")
        if topic in seen:
            continue
        seen.add(topic)
        issues.append(_contradiction(faq, line, topic, finding.explanation, f"llm:{model}"))
    return issues


def semantic_check(config: AgentConfig, packet: Packet, mode: str = "auto") -> list[Issue]:
    """mode: 'mock', 'llm' or 'auto' (llm when configured, else mock)."""
    model = llm_model() if mode in ("auto", "llm") else None
    if model is None:
        return mock_check(config, packet)
    try:
        return llm_check(config, packet, model)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        log.warning("LLM output failed validation (%s); using the mock checker", exc)
    except Exception as exc:  # network, auth, rate limits
        log.warning("LLM call failed (%s); using the mock checker", exc)
    return mock_check(config, packet)
