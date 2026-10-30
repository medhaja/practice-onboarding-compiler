"""Smoke-test router: send scripted patient messages through a config and check where they land.

Routing is keyword based and reads only the config, so a config that is missing a red-flag rule
or has a rule with no escalation fails the smoke test the same way a live agent would.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Optional

from .compiler import DATA_ROOT
from .generator import hours_sentence
from .schema import AgentConfig

INTENT_PATTERNS = [
    ("after_hours", r"after hours|after-hours|office is closed|on-call"),
    ("reschedule", r"reschedul|cancel my|move my appointment"),
    ("prescription_refill", r"refill|prescription|medication"),
    ("billing", r"\bbill|charge|payment|insurance|copay"),
    ("provider_info", r"\bdr\.|doctor|provider"),
    ("hours", r"\bhours\b|\bopen\b|\bclose[ds]?\b"),
    ("book_appointment", r"\bbook|appointment|schedule|\bcita\b"),
]
STOPWORDS = {"do", "you", "we", "are", "is", "the", "a", "i", "my", "your", "on", "to", "of", "for", "can", "what", "how"}


@dataclass
class Route:
    intent: str
    escalation: Optional[str]
    reply: str


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z'-]+", text.lower()) if w not in STOPWORDS}


def route(message: str, config: AgentConfig) -> Route:
    text = message.lower()

    for rule in config.escalation_rules:
        if any(k in text for k in rule.keywords):
            escalation = None if rule.level == "none" else rule.level
            reply = rule.say or "I'll pass this on to the care team."
            return Route("red_flag", escalation, reply)

    for intent, pattern in INTENT_PATTERNS:
        if re.search(pattern, text):
            return Route(intent, None, _reply(intent, message, config))

    words = _words(message)
    best = max(config.faqs, key=lambda f: len(words & _words(f.question)), default=None)
    if best and len(words & _words(best.question)) >= 2:
        return Route("faq", None, best.answer)
    return Route("unknown", None, "Let me connect you with someone at the front desk.")


def _reply(intent: str, message: str, config: AgentConfig) -> str:
    if intent == "after_hours":
        return config.after_hours.action if config.after_hours else "I don't have after-hours instructions."
    if intent == "hours":
        day = next((h for h in config.hours if h.day in message.lower()), None)
        if day:
            return hours_sentence(day.day.title(), None if day.closed else (day.open, day.close))
        return "; ".join(f"{h.day.title()}: {'closed' if h.closed else f'{h.open}-{h.close}'}" for h in config.hours)
    if intent == "provider_info":
        for p in config.providers:
            if p.name.split()[-1].lower() in message.lower():
                status = "is accepting new patients" if p.accepting_new_patients else "has a full panel right now"
                return f"{p.name}, {p.credentials}, {status}."
        return "I can tell you about any of our providers. Who would you like to see?"
    if intent == "billing":
        billing = next((t for t in config.transfers if "billing" in t.reason.lower()), None)
        return f"I'll transfer you to billing at {billing.phone.value or billing.phone.raw}." if billing \
            else "I'll take a message for our billing team."
    if intent == "prescription_refill":
        faq = next((f for f in config.faqs if "refill" in f.question.lower()), None)
        return faq.answer if faq else "I'll send your refill request to the care team."
    names = ", ".join(v.name for v in config.visit_types)
    if intent == "reschedule":
        return "I can help move your appointment. What day works better?"
    return f"I can book that. We offer: {names}."


def load_smoke_tests(practice_id: str) -> list[dict]:
    return json.loads((DATA_ROOT / practice_id / "smoke_tests.json").read_text(encoding="utf-8"))


def run_smoke(config: AgentConfig, tests: list[dict]) -> list[dict]:
    results = []
    for t in tests:
        r = route(t["message"], config)
        passed = r.intent == t["expected_intent"] and r.escalation == t.get("expected_escalation")
        results.append({**t, **{f"actual_{k}": v for k, v in asdict(r).items() if k != "reply"},
                        "reply": r.reply, "passed": passed})
    return results
