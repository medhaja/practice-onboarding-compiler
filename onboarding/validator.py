"""Deterministic validator rules.

Each rule reads a compiled AgentConfig and returns Issues. Every Issue carries
evidence (the source lines that show the problem) and a `targets` list naming
the config items a repair would touch.
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from .compiler import Packet, parse_time
from .generator import fmt_time_short
from .schema import AgentConfig
from .taxonomy import DEFECT_TYPES, REQUIRED_RED_FLAGS


class Evidence(BaseModel):
    source: str
    text: str


class Repair(BaseModel):
    value: str
    confidence: float = Field(ge=0, le=1)
    rationale: str
    citations: list[str] = Field(default_factory=list)
    route: str = "human"  # "auto" or "human"


class Issue(BaseModel):
    id: str
    type: str
    key: str
    severity: str
    title: str
    message: str
    evidence: list[Evidence]
    targets: list[str] = Field(default_factory=list)  # "collection:id" or a top-level field name
    detector: str = "rules"
    repair: Optional[Repair] = None


def make_issue(dtype: str, key: str, message: str, evidence: list[Evidence], targets: list[str] | None = None,
               detector: str = "rules") -> Issue:
    d = DEFECT_TYPES[dtype]
    slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-") or "x"
    return Issue(id=f"{dtype}:{slug}", type=dtype, key=key, severity=d.severity, title=d.title, message=message,
                 evidence=evidence, targets=targets or [], detector=detector)


def _ev(packet: Packet, source: str) -> Evidence:
    try:
        return Evidence(source=source, text=packet.line(source).strip())
    except (KeyError, IndexError, ValueError):
        return Evidence(source=source, text="")


def _spoken_lines(config: AgentConfig):
    """Lines the agent may say: call script lines and FAQ answers."""
    for line in config.script:
        yield f"script:{line.id}", line.source, line.text
    for faq in config.faqs:
        yield f"faqs:{faq.id}", faq.source, faq.answer


# ------------------------------------------------------------------ rules

HOURS_MENTION_RE = re.compile(
    r"Our (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) hours are "
    r"(\d{1,2}(?::\d{2})? ?[AP]M|noon) to (\d{1,2}(?::\d{2})? ?[AP]M|noon)", re.I)
CLOSED_MENTION_RE = re.compile(r"closed on (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)s?", re.I)


def span_text(open_: Optional[str], close: Optional[str]) -> str:
    return "closed" if open_ is None else f"{open_}-{close}"


def human_span(value: str) -> str:
    if value == "closed":
        return "closed"
    a, b = value.split("-")
    return f"{fmt_time_short(a)} to {fmt_time_short(b)}"


def rule_hours_conflict(config: AgentConfig, packet: Packet) -> list[Issue]:
    official = {h.day: h for h in config.hours}
    conflicts: dict[str, list[tuple[str, str, str]]] = {}
    for target, source, text in _spoken_lines(config):
        mentions = [(m.group(1).lower(), f"{parse_time(m.group(2))}-{parse_time(m.group(3))}")
                    for m in HOURS_MENTION_RE.finditer(text)]
        mentions += [(m.group(1).lower(), "closed") for m in CLOSED_MENTION_RE.finditer(text)]
        for day, said in mentions:
            h = official.get(day)
            if h is None:
                continue
            truth = "closed" if h.closed else span_text(h.open, h.close)
            if said != truth:
                conflicts.setdefault(day, []).append((target, source, said))
    issues = []
    for day, items in conflicts.items():
        h = official[day]
        truth = "closed" if h.closed else span_text(h.open, h.close)
        said = ", ".join(f"{src} says {human_span(v)}" for _, src, v in items)
        issues.append(make_issue(
            "hours_conflict", day, f"{day.title()} hours disagree: {h.source} says {human_span(truth)}; {said}.",
            [_ev(packet, h.source)] + [_ev(packet, src) for _, src, _ in items],
            [f"hours:{h.id}"] + [t for t, _, _ in items]))
    return issues


DR_RE = re.compile(r"\bDr\.\s+([A-Z][A-Za-z'-]+)(?:\s+([A-Z][A-Za-z'-]+))?")
CRED_RE = re.compile(r"\b([A-Z][a-z]+) ([A-Z][A-Za-z'-]+), (?:NP|PA-C|MD|DO)\b")


def rule_unknown_provider(config: AgentConfig, packet: Packet) -> list[Issue]:
    roster = {p.name.split()[-1].lower() for p in config.providers}
    found: dict[str, list[tuple[str, str]]] = {}
    for target, source, text in _spoken_lines(config):
        names = [(m.group(2) or m.group(1)) for m in DR_RE.finditer(text)]
        names += [m.group(2) for m in CRED_RE.finditer(text)]
        for name in names:
            if name.lower() not in roster:
                found.setdefault(name.lower(), []).append((target, source))
    return [make_issue("unknown_provider", name,
                       f"{name.title()} is named in {', '.join(s for _, s in refs)} but is not on providers.csv.",
                       [_ev(packet, s) for _, s in refs], [t for t, _ in refs])
            for name, refs in found.items()]


def rule_missing_after_hours(config: AgentConfig, packet: Packet) -> list[Issue]:
    if config.after_hours is not None:
        return []
    if any(re.search(r"on-call|after.hours", t.reason, re.I) for t in config.transfers):
        return []
    return [make_issue("missing_after_hours", "after_hours",
                       "No file says what happens to calls outside office hours.",
                       [Evidence(source="hours.txt", text="(no After-hours line)")], ["after_hours"])]


def rule_red_flag_no_escalation(config: AgentConfig, packet: Packet) -> list[Issue]:
    return [make_issue("red_flag_no_escalation", r.symptom,
                       f"The '{r.symptom}' red-flag rule has no escalation level, so the agent would not escalate it.",
                       [_ev(packet, r.source)], [f"escalation_rules:{r.id}"])
            for r in config.escalation_rules if r.level == "none"]


def rule_missing_red_flag(config: AgentConfig, packet: Packet) -> list[Issue]:
    present = {r.symptom for r in config.escalation_rules}
    required = REQUIRED_RED_FLAGS.get(config.specialty.value, [])
    return [make_issue("missing_red_flag", s,
                       f"{config.specialty.value.title()} practices need a '{s}' rule; protocols.md has none.",
                       [Evidence(source="protocols.md", text=f"(no rule for '{s}')")], ["escalation_rules"])
            for s in required if s not in present]


def _phone_slots(config: AgentConfig):
    if config.main_phone:
        yield "main_phone", config.main_phone
    if config.after_hours and config.after_hours.phone:
        yield "after_hours", config.after_hours.phone
    for t in config.transfers:
        yield f"transfers:{t.id}", t.phone


def rule_invalid_phone(config: AgentConfig, packet: Packet) -> list[Issue]:
    return [make_issue("invalid_phone", phone.raw,
                       f"'{phone.raw}' at {phone.source} is not a valid 10-digit US number.",
                       [_ev(packet, phone.source)], [target])
            for target, phone in _phone_slots(config) if phone.value is None]


VISIT_ABBREV = {"pt": "patient", "f/u": "follow up", "fu": "follow up", "appt": "", "visit": "", "appointment": ""}


def normalize_visit_type(name: str) -> str:
    words = re.sub(r"[-_.]", " ", name.lower()).split()
    return " ".join(w for w in (VISIT_ABBREV.get(w, w) for w in words) if w)


def rule_duplicate_visit_type(config: AgentConfig, packet: Packet) -> list[Issue]:
    first: dict[str, object] = {}
    issues = []
    for vt in config.visit_types:
        norm = normalize_visit_type(vt.name)
        if norm in first:
            canon = first[norm]
            issues.append(make_issue("duplicate_visit_type", vt.name.lower(),
                                     f"'{vt.name}' looks like a duplicate of '{canon.name}'.",
                                     [_ev(packet, canon.source), _ev(packet, vt.source)],
                                     [f"visit_types:{canon.id}", f"visit_types:{vt.id}"]))
        else:
            first[norm] = vt
    return issues


def rule_missing_timezone(config: AgentConfig, packet: Packet) -> list[Issue]:
    if config.timezone is not None:
        return []
    return [make_issue("missing_timezone", "timezone",
                       "No timezone given, so the agent cannot tell whether the office is open right now.",
                       [Evidence(source="hours.txt", text="(no Timezone line)")], ["timezone"])]


def rule_holiday_free_text(config: AgentConfig, packet: Packet) -> list[Issue]:
    loose = [h for h in config.holidays if h.date is None]
    if not loose:
        return []
    return [make_issue("holiday_free_text", "holidays", "Holiday closures are written as free text, not dates.",
                       [_ev(packet, h.source) for h in loose], ["holidays"])]


RULES = [rule_missing_timezone, rule_hours_conflict, rule_missing_after_hours, rule_red_flag_no_escalation,
         rule_missing_red_flag, rule_invalid_phone, rule_unknown_provider, rule_duplicate_visit_type,
         rule_holiday_free_text]


def run_rules(config: AgentConfig, packet: Packet) -> list[Issue]:
    issues: list[Issue] = []
    for rule in RULES:
        issues.extend(rule(config, packet))
    return issues

