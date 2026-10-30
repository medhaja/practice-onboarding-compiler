"""Propose a repair for each issue, decide whether it can be applied without a person, and apply it.

Every proposal carries a confidence and the source lines it was drawn from. A repair is routed
to "auto" only when its confidence clears AUTO_THRESHOLD and its defect type is not escalation
related; escalation repairs always go to a human, whatever the confidence.
"""
from __future__ import annotations

import re
from typing import Optional

from .compiler import PHONE_RE, Packet
from .generator import HOLIDAY_DATES, hours_sentence
from .schema import (AfterHours, AgentConfig, EscalationRule, Holiday, PhoneField, TextField, normalize_phone)
from .taxonomy import DEFECT_TYPES, RED_FLAG_LIBRARY, STATE_TIMEZONES
from .validator import Issue, Repair, span_text

AUTO_THRESHOLD = 0.8
REVIEW = "review"


def _route(issue: Issue, confidence: float) -> str:
    if DEFECT_TYPES[issue.type].always_human or confidence < AUTO_THRESHOLD:
        return "human"
    return "auto"


def _repair(issue: Issue, value: str, confidence: float, rationale: str, citations: list[str]) -> Repair:
    return Repair(value=value, confidence=confidence, rationale=rationale, citations=citations,
                  route=_route(issue, confidence))


# ------------------------------------------------------------------ proposals

def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _is_subsequence(short: str, long: str) -> bool:
    it = iter(long)
    return all(ch in it for ch in short)


def _phone_candidates(packet: Packet, raw: str) -> dict[str, list[str]]:
    """Valid numbers anywhere in the packet that the malformed one could be a typo of."""
    want = _digits(raw)
    found: dict[str, list[str]] = {}
    for name, lines in packet.files.items():
        for i, line in enumerate(lines, start=1):
            for m in PHONE_RE.finditer(line):
                value = normalize_phone(m.group(0))
                if value and len(want) >= 7 and _is_subsequence(want, _digits(value)):
                    found.setdefault(value, []).append(f"{name}:{i}")
    return found


def propose_invalid_phone(issue, config, packet):
    candidates = _phone_candidates(packet, issue.key)
    if len(candidates) == 1:
        value, sources = next(iter(candidates.items()))
        return _repair(issue, value, 0.85,
                       f"The only valid number in the packet that matches these digits is {value}.", sources)
    if candidates:
        return _repair(issue, "", 0.2, f"{len(candidates)} numbers in the packet could match; ask the practice.",
                       sorted(s for v in candidates.values() for s in v))
    return _repair(issue, "", 0.0, "No matching number anywhere in the packet; ask the practice.", [])


HOLIDAY_ALIASES = {"the friday after": "day after thanksgiving", "friday after thanksgiving": "day after thanksgiving"}
PARTIAL_DAY_RE = re.compile(r"afternoon|morning|close early|half day", re.I)


def parse_holidays(text: str) -> list[str]:
    lower = text.lower()
    names = {alias for phrase, alias in HOLIDAY_ALIASES.items() if phrase in lower}
    names |= {name for name in HOLIDAY_DATES if name in lower}
    return sorted(HOLIDAY_DATES[n][0] for n in names)


def propose_holiday_free_text(issue, config, packet):
    raw = " ".join(h.raw for h in config.holidays if h.date is None)
    dates = parse_holidays(raw)
    if not dates:
        return _repair(issue, "", 0.0, "No known holiday names found in the text.", [issue.evidence[0].source])
    partial = PARTIAL_DAY_RE.search(raw)
    confidence = 0.6 if partial else 0.9
    note = (f" The text mentions a partial day ('{partial.group(0)}'), which a date list cannot express."
            if partial else "")
    return _repair(issue, ", ".join(dates), confidence, f"Matched holiday names to dates.{note}",
                   [e.source for e in issue.evidence])


def propose_hours_conflict(issue, config, packet):
    h = next(h for h in config.hours if h.day == issue.key)
    value = "closed" if h.closed else span_text(h.open, h.close)
    return _repair(issue, value, 0.9, "hours.txt is the structured hours source; align the other mentions to it.",
                   [h.source])


def propose_duplicate_visit_type(issue, config, packet):
    canon_id, dup_id = (t.split(":", 1)[1] for t in issue.targets[:2])
    canon = next(v for v in config.visit_types if v.id == canon_id)
    dup = next(v for v in config.visit_types if v.id == dup_id)
    same_length = canon.minutes == dup.minutes
    return _repair(issue, canon.name, 0.9 if same_length else 0.6,
                   f"Merge '{dup.name}' into '{canon.name}'"
                   + (" (same length)." if same_length else f" ({dup.minutes} vs {canon.minutes} min; check which)."),
                   [canon.source, dup.source])


def propose_missing_timezone(issue, config, packet):
    m = re.search(r",\s*([A-Z]{2})\s*$", config.address.value if config.address else "")
    tz = STATE_TIMEZONES.get(m.group(1)) if m else None
    if not tz:
        return _repair(issue, "", 0.0, "Could not infer a timezone from the address.", [])
    return _repair(issue, tz, 0.9, f"The address is in {m.group(1)}, which uses {tz}.", [config.address.source])


def propose_missing_after_hours(issue, config, packet):
    nurse = next((t for t in config.transfers if re.search(r"nurse|on-call", t.reason, re.I)), None)
    if nurse and nurse.phone.value:
        return _repair(issue, f"Calls forward to the {nurse.reason.lower()} at {nurse.phone.value}.", 0.5,
                       f"The script has a {nurse.reason} transfer that could take after-hours calls.", [nurse.source])
    return _repair(issue, "", 0.0, "No on-call or nurse number in the packet; ask the practice where calls go.", [])


def _library_rule(symptom: str) -> Optional[dict]:
    return RED_FLAG_LIBRARY.get(symptom)


def propose_red_flag_no_escalation(issue, config, packet):
    rule = _library_rule(issue.key)
    if not rule:
        return _repair(issue, "", 0.0, "Symptom is not in the red-flag library; a clinician must set the level.", [])
    return _repair(issue, rule["level"], 0.8,
                   f"The default library escalates '{issue.key}' as {rule['level']}: \"{rule['say']}\" "
                   "Escalation changes always need a person.", [e.source for e in issue.evidence])


def propose_missing_red_flag(issue, config, packet):
    rule = _library_rule(issue.key)
    if not rule:
        return _repair(issue, "", 0.0, "Symptom is not in the red-flag library.", [])
    return _repair(issue, rule["level"], 0.8,
                   f"Add a '{issue.key}' rule (keywords: {', '.join(rule['keywords'])}) that escalates as "
                   f"{rule['level']}: \"{rule['say']}\" Escalation changes always need a person.", [])


def propose_faq_script_contradiction(issue, config, packet):
    script_ev = issue.evidence[1]
    return _repair(issue, script_ev.text, 0.6,
                   "Use the call script's wording. Which policy is current is the practice's call.",
                   [script_ev.source])


def propose_unknown_provider(issue, config, packet):
    return _repair(issue, "", 0.3,
                   f"Remove the mention (leave the value empty), or add {issue.key.title()} to providers.csv "
                   "if they still practice here.", [e.source for e in issue.evidence])


PROPOSERS = {
    "invalid_phone": propose_invalid_phone,
    "holiday_free_text": propose_holiday_free_text,
    "hours_conflict": propose_hours_conflict,
    "duplicate_visit_type": propose_duplicate_visit_type,
    "missing_timezone": propose_missing_timezone,
    "missing_after_hours": propose_missing_after_hours,
    "red_flag_no_escalation": propose_red_flag_no_escalation,
    "missing_red_flag": propose_missing_red_flag,
    "faq_script_contradiction": propose_faq_script_contradiction,
    "unknown_provider": propose_unknown_provider,
}


def propose(issues: list[Issue], config: AgentConfig, packet: Packet) -> list[Issue]:
    return [i.model_copy(update={"repair": PROPOSERS[i.type](i, config, packet)}) for i in issues]


# ------------------------------------------------------------------ applying

def _split(target: str) -> tuple[str, str]:
    collection, _, item_id = target.partition(":")
    return collection, item_id


def _set_text(config: AgentConfig, target: str, text: str) -> None:
    collection, item_id = _split(target)
    if collection == "script":
        item = next(l for l in config.script if l.id == item_id)
        item.text, item.source = text, REVIEW
    elif collection == "faqs":
        item = next(f for f in config.faqs if f.id == item_id)
        item.answer, item.source = text, REVIEW


def _drop(config: AgentConfig, target: str) -> None:
    collection, item_id = _split(target)
    if collection == "script":
        config.script = [l for l in config.script if l.id != item_id]
    elif collection == "faqs":
        config.faqs = [f for f in config.faqs if f.id != item_id]


def _phone(value: str) -> PhoneField:
    return PhoneField(raw=value, value=normalize_phone(value), source=REVIEW)


def apply_repair(config: AgentConfig, issue: Issue, value: str) -> AgentConfig:
    """Return a copy of config with the repair applied using `value` (the proposal or a reviewer's edit)."""
    config = config.model_copy(deep=True)
    value = value.strip()
    t = issue.type
    if not value and t != "unknown_provider":
        raise ValueError("a value is required for this repair")

    if t == "hours_conflict":
        h = next(h for h in config.hours if h.day == issue.key)
        before = "closed" if h.closed else span_text(h.open, h.close)
        if value == "closed":
            h.closed, h.open, h.close = True, None, None
            span = None
        else:
            h.open, h.close = value.split("-")
            h.closed, span = False, (h.open, h.close)
        if value != before:
            h.source = REVIEW
        for target in issue.targets[1:]:
            _set_text(config, target, hours_sentence(issue.key.title(), span))
    elif t == "duplicate_visit_type":
        dup_id = _split(issue.targets[1])[1]
        config.visit_types = [v for v in config.visit_types if v.id != dup_id]
        canon = next(v for v in config.visit_types if v.id == _split(issue.targets[0])[1])
        if value and value != canon.name:
            canon.name, canon.source = value, REVIEW
    elif t == "invalid_phone":
        target = issue.targets[0]
        if target == "main_phone":
            config.main_phone = _phone(value)
        elif target == "after_hours":
            config.after_hours.phone = _phone(value)
        else:
            transfer = next(x for x in config.transfers if x.id == _split(target)[1])
            transfer.phone = _phone(value)
    elif t == "holiday_free_text":
        by_date = {d: name for d, name in HOLIDAY_DATES.values()}
        dates = [d.strip() for d in value.split(",") if d.strip()]
        config.holidays = [Holiday(id=f"hol{i}", raw=d, date=d, name=by_date.get(d, ""), source=REVIEW)
                           for i, d in enumerate(dates, start=1)]
    elif t == "missing_timezone":
        config.timezone = TextField(value=value, source=REVIEW)
    elif t == "missing_after_hours":
        m = PHONE_RE.search(value)
        config.after_hours = AfterHours(action=value, phone=_phone(m.group(0)) if m else None, source=REVIEW)
    elif t == "red_flag_no_escalation":
        rule = next(r for r in config.escalation_rules if r.symptom == issue.key)
        rule.level, rule.source = value, REVIEW
        if not rule.say:
            rule.say = RED_FLAG_LIBRARY.get(issue.key, {}).get("say", "")
    elif t == "missing_red_flag":
        lib = RED_FLAG_LIBRARY[issue.key]
        config.escalation_rules.append(EscalationRule(
            id=f"rf{len(config.escalation_rules) + 1}", symptom=issue.key, keywords=lib["keywords"], level=value,
            say=lib["say"], source=REVIEW))
    elif t == "faq_script_contradiction":
        _set_text(config, issue.targets[0], value)
    elif t == "unknown_provider":
        for target in issue.targets:
            if value:
                _set_text(config, target, value)
            else:
                _drop(config, target)
    else:
        raise ValueError(f"no repair for {t}")

    return AgentConfig.model_validate(config.model_dump())
