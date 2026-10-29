"""Pydantic schema for the agent configuration a practice packet compiles into.

Every item carries a `source` string ("file:line") so a reviewer can trace any
value back to the line of the packet it came from. Values changed during review
get the source "review".
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# US time zones the prototype accepts. A fixed list keeps validation offline.
US_TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
]

SOURCE_PATTERN = r"^([\w.-]+:\d+|review)$"
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
PHONE_PATTERN = r"^\(\d{3}\) \d{3}-\d{4}$"

EscalationLevel = Literal["emergency", "urgent", "none"]


class Sourced(BaseModel):
    source: str = Field(pattern=SOURCE_PATTERN)


class TextField(Sourced):
    value: str


class PhoneField(Sourced):
    raw: str
    # Normalized "(555) 555-0123" form, or None when the raw text is not a valid number.
    value: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)


class DayHours(Sourced):
    id: str
    day: Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    closed: bool = False
    open: Optional[str] = Field(default=None, pattern=TIME_PATTERN)
    close: Optional[str] = Field(default=None, pattern=TIME_PATTERN)


class Holiday(Sourced):
    id: str
    raw: str
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    name: str = ""


class AfterHours(Sourced):
    action: str
    phone: Optional[PhoneField] = None


class Provider(Sourced):
    id: str
    name: str
    credentials: str
    specialty: str
    accepting_new_patients: bool


class VisitType(Sourced):
    id: str
    name: str
    minutes: int = Field(gt=0, le=240)


class FAQ(Sourced):
    id: str
    question: str
    answer: str


class ScriptLine(Sourced):
    id: str
    section: str
    text: str


class Transfer(Sourced):
    id: str
    reason: str
    phone: PhoneField


class EscalationRule(Sourced):
    id: str
    symptom: str
    keywords: list[str]
    level: EscalationLevel
    say: str = ""


class AgentConfig(BaseModel):
    practice_id: str = Field(pattern=r"^p\d{2}$")
    practice_name: TextField
    specialty: TextField
    address: Optional[TextField] = None
    timezone: Optional[TextField] = None
    main_phone: Optional[PhoneField] = None
    languages: list[TextField] = Field(default_factory=list)
    hours: list[DayHours] = Field(default_factory=list)
    holidays: list[Holiday] = Field(default_factory=list)
    after_hours: Optional[AfterHours] = None
    providers: list[Provider] = Field(default_factory=list)
    visit_types: list[VisitType] = Field(default_factory=list)
    faqs: list[FAQ] = Field(default_factory=list)
    script: list[ScriptLine] = Field(default_factory=list)
    transfers: list[Transfer] = Field(default_factory=list)
    escalation_rules: list[EscalationRule] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, v: Optional[TextField]) -> Optional[TextField]:
        if v is not None and v.value not in US_TIMEZONES:
            raise ValueError(f"unknown timezone {v.value!r}")
        return v


def json_schema() -> dict:
    return AgentConfig.model_json_schema()


def normalize_phone(raw: str) -> Optional[str]:
    """Return "(AAA) EEE-NNNN" for a 10-digit US number (optional leading 1), else None."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def count_fields(config: AgentConfig) -> int:
    """Number of reviewable items in a config: scalar fields plus list entries."""
    scalars = [config.practice_name, config.specialty, config.address, config.timezone,
               config.main_phone, config.after_hours]
    lists = [config.languages, config.hours, config.holidays, config.providers, config.visit_types,
             config.faqs, config.script, config.transfers, config.escalation_rules]
    return sum(1 for s in scalars if s is not None) + sum(len(items) for items in lists)
