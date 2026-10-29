"""Defect taxonomy shared by the generator (ground truth) and the validator (detections).

A defect is identified by (type, key). The key names the thing that is wrong, so a
detection can be matched to the planted defect without depending on line numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class DefectType:
    name: str
    severity: Severity
    title: str
    key_meaning: str
    # Escalation-related repairs are never applied without a person, whatever the confidence.
    always_human: bool = False


DEFECT_TYPES: dict[str, DefectType] = {
    d.name: d
    for d in [
        DefectType("hours_conflict", "high", "Hours conflict across files", "day name, e.g. 'saturday'"),
        DefectType("unknown_provider", "medium", "Provider not on roster", "surname, lowercase"),
        DefectType("missing_after_hours", "high", "No after-hours path", "'after_hours'", always_human=True),
        DefectType("red_flag_no_escalation", "high", "Red-flag rule has no escalation", "symptom",
                   always_human=True),
        DefectType("missing_red_flag", "high", "Required red-flag rule missing", "symptom", always_human=True),
        DefectType("invalid_phone", "high", "Invalid phone number", "raw phone text as written"),
        DefectType("duplicate_visit_type", "medium", "Duplicate visit types", "duplicate (non-canonical) name, lowercase"),
        DefectType("missing_timezone", "high", "Missing timezone", "'timezone'"),
        DefectType("holiday_free_text", "low", "Holiday closures written as free text", "'holidays'"),
        DefectType("faq_script_contradiction", "medium", "FAQ contradicts call script", "topic, e.g. 'walk_ins'"),
    ]
}

ESCALATION_TYPES = {name for name, d in DEFECT_TYPES.items() if d.always_human}

# Red-flag symptoms each specialty must cover. Placeholders that need physician review.
REQUIRED_RED_FLAGS: dict[str, list[str]] = {
    "internal medicine": ["chest pain", "stroke symptoms", "shortness of breath"],
    "cardiology": ["chest pain", "fainting", "shortness of breath"],
    "pulmonology": ["shortness of breath", "coughing up blood"],
    "urgent care": ["chest pain", "shortness of breath", "stroke symptoms"],
    "multispecialty": ["chest pain", "stroke symptoms", "shortness of breath", "fainting"],
}

# Default wording for red-flag rules, used by the generator and proposed by the repairer.
RED_FLAG_LIBRARY: dict[str, dict] = {
    "chest pain": {"keywords": ["chest pain", "chest pressure", "chest tightness"], "level": "emergency",
                   "say": "Please hang up and call 911 now."},
    "stroke symptoms": {"keywords": ["face drooping", "slurred speech", "sudden weakness", "stroke"],
                        "level": "emergency", "say": "Please hang up and call 911 now."},
    "shortness of breath": {"keywords": ["shortness of breath", "can't breathe", "cannot breathe",
                                         "trouble breathing"], "level": "emergency",
                            "say": "Please hang up and call 911 now."},
    "fainting": {"keywords": ["fainted", "passed out", "fainting"], "level": "emergency",
                 "say": "Please hang up and call 911 now."},
    "coughing up blood": {"keywords": ["coughing up blood", "coughing blood"], "level": "emergency",
                          "say": "Please hang up and call 911 now."},
    "high fever": {"keywords": ["fever of 104", "very high fever"], "level": "urgent",
                   "say": "I'm connecting you to the nurse line now."},
    "severe allergic reaction": {"keywords": ["throat swelling", "allergic reaction", "hives and swelling"],
                                 "level": "emergency", "say": "Please hang up and call 911 now."},
    "leg swelling": {"keywords": ["swollen leg", "leg swelling"], "level": "urgent",
                     "say": "I'm connecting you to the nurse line now."},
    "palpitations": {"keywords": ["racing heart", "palpitations", "heart racing"], "level": "urgent",
                     "say": "I'm connecting you to the nurse line now."},
    "severe headache": {"keywords": ["worst headache", "severe headache"], "level": "emergency",
                        "say": "Please hang up and call 911 now."},
    "blue lips": {"keywords": ["blue lips", "lips turning blue"], "level": "emergency",
                  "say": "Please hang up and call 911 now."},
    "oxygen alarm": {"keywords": ["oxygen level", "oxygen below"], "level": "urgent",
                     "say": "I'm connecting you to the nurse line now."},
    "deep cut": {"keywords": ["deep cut", "won't stop bleeding"], "level": "urgent",
                 "say": "Please come in now or go to the nearest ER."},
    "head injury": {"keywords": ["hit my head", "head injury"], "level": "urgent",
                    "say": "Please come in now or go to the nearest ER."},
    "confusion": {"keywords": ["confused", "confusion"], "level": "emergency",
                  "say": "Please hang up and call 911 now."},
}

# State to timezone, used to propose a timezone when the packet has none.
STATE_TIMEZONES = {
    "IL": "America/Chicago", "AZ": "America/Phoenix", "MA": "America/New_York",
    "CO": "America/Denver", "WA": "America/Los_Angeles", "OR": "America/Los_Angeles",
    "NY": "America/New_York", "TX": "America/Chicago", "MN": "America/Chicago",
}
