"""Parse a practice packet and compile it into an AgentConfig.

The compiler is deterministic: the same packet always gives the same config.
It does not judge whether the content is right; that is the validator's job.
It only records what each file says and where (file:line).
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .schema import (AfterHours, AgentConfig, DayHours, EscalationRule, FAQ, Holiday, PhoneField, Provider,
                     ScriptLine, TextField, Transfer, VisitType, normalize_phone)

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "practices"
PACKET_FILES = ["hours.txt", "providers.csv", "call_script.md", "faq.md", "protocols.md"]

PHONE_RE = re.compile(r"\(?\d{3}\)?[ .-]?\d[\d .-]*\d")
DAY_LINE_RE = re.compile(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday):\s*(.+)$")
TIME_RANGE_RE = re.compile(r"(\d{1,2}(?::\d{2})?\s*[AP]M)\s*[-–]\s*(\d{1,2}(?::\d{2})?\s*[AP]M)", re.I)
VISIT_RE = re.compile(r"^-\s*(.+?)\s*\((\d+)\s*min\)\s*$")
TRANSFER_RE = re.compile(r"^-\s*([^:]+):\s*(.+)$")


@dataclass
class Packet:
    practice_id: str
    files: dict[str, list[str]]

    def line(self, ref: str) -> str:
        name, _, number = ref.partition(":")
        return self.files[name][int(number) - 1]


def load_packet(practice_id: str, root: Path = DATA_ROOT) -> Packet:
    folder = root / practice_id
    if not folder.is_dir():
        raise FileNotFoundError(f"no packet at {folder}")
    files = {}
    for name in PACKET_FILES:
        path = folder / name
        files[name] = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return Packet(practice_id, files)


def list_practices(root: Path = DATA_ROOT) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "hours.txt").exists())


def parse_time(text: str) -> str:
    """'9 AM' / '9:30 pm' / 'noon' -> 'HH:MM'."""
    text = text.strip().lower()
    if text == "noon":
        return "12:00"
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*([ap])m", text)
    if not m:
        raise ValueError(f"cannot parse time {text!r}")
    hour, minute = int(m.group(1)) % 12, int(m.group(2) or 0)
    if m.group(3) == "p":
        hour += 12
    return f"{hour:02d}:{minute:02d}"


def phone_field(raw: str, source: str) -> PhoneField:
    return PhoneField(raw=raw, value=normalize_phone(raw), source=source)


def _numbered(lines: list[str], name: str):
    for i, line in enumerate(lines, start=1):
        yield f"{name}:{i}", line.strip()


def compile_packet(packet: Packet) -> AgentConfig:
    fields: dict[str, Optional[object]] = {}
    hours: list[DayHours] = []
    holidays: list[Holiday] = []
    after_hours = None

    # hours.txt: "Key: value" lines plus one line per weekday.
    for src, line in _numbered(packet.files["hours.txt"], "hours.txt"):
        day = DAY_LINE_RE.match(line)
        if day:
            name, rest = day.group(1).lower(), day.group(2)
            rng = TIME_RANGE_RE.search(rest)
            if rest.lower().startswith("closed"):
                hours.append(DayHours(id=f"h-{name}", day=name, closed=True, source=src))
            elif rng:
                hours.append(DayHours(id=f"h-{name}", day=name, open=parse_time(rng.group(1)),
                                      close=parse_time(rng.group(2)), source=src))
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key, value = key.strip().lower(), value.strip()
        if key in ("practice", "specialty", "address", "timezone"):
            fields[key] = TextField(value=value.lower() if key == "specialty" else value, source=src)
        elif key == "main phone":
            fields["main_phone"] = phone_field(value, src)
        elif key == "after-hours":
            m = PHONE_RE.search(value)
            after_hours = AfterHours(action=value, phone=phone_field(m.group(0), src) if m else None, source=src)
        elif key == "holidays":
            parts = [p.strip() for p in value.split(";") if p.strip()]
            structured = [re.match(r"^(\d{4}-\d{2}-\d{2})\s+(.+)$", p) for p in parts]
            if parts and all(structured):
                holidays = [Holiday(id=f"hol{i}", raw=p, date=m.group(1), name=m.group(2), source=src)
                            for i, (p, m) in enumerate(zip(parts, structured), start=1)]
            else:
                holidays = [Holiday(id="hol1", raw=value, source=src)]

    # providers.csv: header row is line 1, so data row i sits on line i + 1.
    providers = []
    rows = list(csv.DictReader(packet.files["providers.csv"]))
    for i, row in enumerate(rows, start=2):
        providers.append(Provider(
            id=row["provider_id"], name=row["name"].strip(), credentials=row["credentials"].strip(),
            specialty=row["specialty"].strip(), accepting_new_patients=row["accepting_new_patients"].strip() == "yes",
            source=f"providers.csv:{i}"))

    # call_script.md: sections become visit types, transfers or spoken lines.
    script, visit_types, transfers = [], [], []
    languages = [TextField(value="en", source="call_script.md:1")]
    section = ""
    for src, line in _numbered(packet.files["call_script.md"], "call_script.md"):
        if not line or line.startswith("# "):
            continue
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section == "visit types" and (m := VISIT_RE.match(line)):
            visit_types.append(VisitType(id=f"vt{len(visit_types) + 1}", name=m.group(1), minutes=int(m.group(2)),
                                         source=src))
        elif section == "transfers" and (m := TRANSFER_RE.match(line)):
            transfers.append(Transfer(id=f"t{len(transfers) + 1}", reason=m.group(1).strip(),
                                      phone=phone_field(m.group(2).strip(), src), source=src))
        else:
            script.append(ScriptLine(id=f"s{len(script) + 1}", section=section, text=line, source=src))
            if "español" in line.lower() and not any(l.value == "es" for l in languages):
                languages.append(TextField(value="es", source=src))

    # faq.md: "## question" followed by the answer. The answer line is the source.
    faqs = []
    question = None
    for src, line in _numbered(packet.files["faq.md"], "faq.md"):
        if line.startswith("## "):
            question = line[3:].strip()
        elif line and question and not line.startswith("#"):
            faqs.append(FAQ(id=f"faq{len(faqs) + 1}", question=question, answer=line, source=src))
            question = None

    # protocols.md: "- symptom | keywords: a, b | escalation: level | say: text"
    rules = []
    for src, line in _numbered(packet.files["protocols.md"], "protocols.md"):
        if not line.startswith("- "):
            continue
        parts = [p.strip() for p in line[2:].split("|")]
        attrs = {}
        for p in parts[1:]:
            k, _, v = p.partition(":")
            attrs[k.strip().lower()] = v.strip()
        level = attrs.get("escalation", "").lower()
        rules.append(EscalationRule(
            id=f"rf{len(rules) + 1}", symptom=parts[0].lower(),
            keywords=[k.strip().lower() for k in attrs.get("keywords", "").split(",") if k.strip()],
            level=level if level in ("emergency", "urgent") else "none", say=attrs.get("say", ""), source=src))

    return AgentConfig(
        practice_id=packet.practice_id,
        practice_name=fields["practice"], specialty=fields["specialty"], address=fields.get("address"),
        timezone=fields.get("timezone"), main_phone=fields.get("main_phone"), languages=languages,
        hours=hours, holidays=holidays, after_hours=after_hours, providers=providers, visit_types=visit_types,
        faqs=faqs, script=script, transfers=transfers, escalation_rules=rules,
    )
