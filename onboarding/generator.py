"""Synthetic practice packet generator.

Writes six fake practice packets to data/practices/<id>/ together with:
  defects.json      ground truth for every defect planted in the packet
  smoke_tests.json  ten scripted patient messages with the expected route

All names, addresses and phone numbers are invented. Phone numbers use the
fictional 555-01xx range. Run: python -m onboarding.generator
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .taxonomy import DEFECT_TYPES, RED_FLAG_LIBRARY

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "practices"
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Next occurrence of each holiday after 2026-11-01. Shared with the repairer.
HOLIDAY_DATES = {
    "thanksgiving": ("2026-11-26", "Thanksgiving Day"),
    "day after thanksgiving": ("2026-11-27", "Day after Thanksgiving"),
    "christmas eve": ("2026-12-24", "Christmas Eve"),
    "christmas day": ("2026-12-25", "Christmas Day"),
    "new year's eve": ("2026-12-31", "New Year's Eve"),
    "new year's day": ("2027-01-01", "New Year's Day"),
    "memorial day": ("2027-05-31", "Memorial Day"),
    "independence day": ("2027-07-04", "Independence Day"),
    "labor day": ("2027-09-06", "Labor Day"),
}

SYMPTOM_MESSAGES = {
    "chest pain": "I'm having chest pain and it won't go away.",
    "stroke symptoms": "My husband's face is drooping and he has slurred speech.",
    "shortness of breath": "I have shortness of breath even sitting down.",
    "fainting": "My mother fainted twice this morning.",
    "coughing up blood": "I've been coughing up blood since this morning.",
    "confusion": "My dad seems confused and doesn't know where he is.",
    "deep cut": "I have a deep cut on my hand that won't stop bleeding.",
}

PRACTICES = [
    {
        "id": "p01", "name": "Maple Grove Internal Medicine", "specialty": "internal medicine",
        "address": "410 Example Avenue, Springfield, IL", "timezone": "America/Chicago",
        "main_phone": "(555) 555-0123", "after_hours_phone": "(555) 555-0188",
        "hours": {**{d: ("08:00", "17:00") for d in DAY_NAMES[:5]}, "Saturday": ("09:00", "12:00"), "Sunday": None},
        "providers": [("Ana Ruiz", "MD", True), ("Samuel Okafor", "MD", False), ("Jordan Lee", "NP", True),
                      ("Priya Natarajan", "DO", True)],
        "visit_types": [("New Patient Visit", 40), ("Follow-up Visit", 20), ("Annual Physical", 30), ("Sick Visit", 20)],
        "transfers": [("Billing", "(555) 555-0130"), ("Nurse line", "(555) 555-0140")],
        "policies": {"walk_ins": False, "telehealth": True, "new_patients": True, "refill_days": 2},
        "red_flags": ["chest pain", "stroke symptoms", "shortness of breath", "high fever", "severe allergic reaction",
                      "confusion"],
        "smoke_symptoms": ["chest pain", "confusion"],
        "holidays_free_text": "We close for Thanksgiving and the Friday after, Christmas Eve afternoon, and New Year's Day.",
        "holidays_expected": ["thanksgiving", "day after thanksgiving", "christmas eve", "new year's day"],
        "defects": [
            {"type": "hours_conflict", "day": "Saturday", "where": "script", "wrong": ("09:00", "13:00")},
            {"type": "unknown_provider", "name": "Halvorsen", "line": "Dr. Halvorsen sees patients on Tuesdays and Thursdays."},
            {"type": "duplicate_visit_type", "canonical": "New Patient Visit", "duplicate": "New Pt Visit"},
            {"type": "invalid_phone", "field": "main_phone", "raw": "(555) 01-23"},
            {"type": "holiday_free_text"},
            {"type": "faq_script_contradiction", "topic": "walk_ins"},
        ],
    },
    {
        "id": "p02", "name": "Riverbend Internal Medicine", "specialty": "internal medicine",
        "address": "88 Placeholder Road, Mesa, AZ", "timezone": "America/Phoenix",
        "main_phone": "(555) 555-0150", "after_hours_phone": "(555) 555-0158", "spanish": True,
        "hours": {**{d: ("07:30", "16:30") for d in DAY_NAMES[:5]}, "Saturday": None, "Sunday": None},
        "providers": [("Elena Vargas", "MD", True), ("Marcus Bell", "MD", True), ("Tessa Moreno", "PA-C", True)],
        "visit_types": [("New Patient Visit", 45), ("Follow-up Visit", 20), ("Medicare Wellness Visit", 40)],
        "transfers": [("Billing", "(555) 555-0152"), ("Referrals", "(555) 555-0154")],
        "policies": {"walk_ins": False, "telehealth": True, "new_patients": True, "refill_days": 3},
        "red_flags": ["chest pain", "stroke symptoms", "shortness of breath", "high fever", "severe headache",
                      "leg swelling"],
        "smoke_symptoms": ["chest pain", "stroke symptoms"],
        "defects": [
            {"type": "missing_timezone"},
            {"type": "missing_after_hours"},
            {"type": "red_flag_no_escalation", "symptom": "stroke symptoms"},
            {"type": "faq_script_contradiction", "topic": "telehealth"},
            {"type": "hours_conflict", "day": "Saturday", "where": "faq", "wrong": ("09:00", "13:00")},
        ],
    },
    {
        "id": "p03", "name": "Harborview Heart Clinic", "specialty": "cardiology",
        "address": "12 Sample Wharf, Salem, MA", "timezone": "America/New_York",
        "main_phone": "(555) 555-0160", "after_hours_phone": "(555) 555-0168",
        "hours": {**{d: ("08:00", "17:00") for d in DAY_NAMES[:4]}, "Friday": ("08:00", "15:00"),
                  "Saturday": None, "Sunday": None},
        "providers": [("Grace Abernathy", "MD", True), ("Daniel Osei", "MD", False), ("Mei Tanaka", "MD", True),
                      ("Rafael Duarte", "MD", True), ("Hannah Kowalski", "MD", False), ("Leon Fischer", "NP", True)],
        "visit_types": [("New Cardiology Consult", 60), ("Follow-up Visit", 30), ("Echocardiogram", 45),
                        ("Stress Test", 90), ("Device Check", 30)],
        "transfers": [("Billing", "(555) 555-0162"), ("Device clinic", "(555) 555-0164")],
        "policies": {"walk_ins": False, "telehealth": True, "new_patients": True, "refill_days": 2},
        "red_flags": ["chest pain", "fainting", "shortness of breath", "palpitations", "leg swelling",
                      "severe headache", "confusion"],
        "extra_script_days": ["Friday"],
        "smoke_symptoms": ["chest pain", "fainting"],
        "holidays_free_text": "Closed Christmas Day and New Year's Day, and we close early on Christmas Eve.",
        "holidays_expected": ["christmas eve", "christmas day", "new year's day"],
        "defects": [
            {"type": "missing_red_flag", "symptom": "chest pain"},
            {"type": "hours_conflict", "day": "Friday", "where": "script", "wrong": ("08:00", "17:00")},
            {"type": "unknown_provider", "name": "Whitcombe", "line": "Dr. Whitcombe reads all echocardiograms."},
            {"type": "invalid_phone", "field": "transfer:Billing", "raw": "(555) 555-01"},
            {"type": "duplicate_visit_type", "canonical": "Follow-up Visit", "duplicate": "Follow Up Visit"},
            {"type": "holiday_free_text"},
            {"type": "faq_script_contradiction", "topic": "new_patients"},
        ],
    },
    {
        "id": "p04", "name": "Cedar Ridge Pulmonology", "specialty": "pulmonology",
        "address": "301 Fictional Street, Boulder, CO", "timezone": "America/Denver",
        "main_phone": "(555) 555-0170", "after_hours_phone": "(555) 555-0177",
        "hours": {**{d: ("08:00", "16:30") for d in DAY_NAMES[:5]}, "Saturday": ("08:00", "12:00"), "Sunday": None},
        "providers": [("Owen Gallagher", "MD", True), ("Sofia Lindqvist", "MD", True), ("Ibrahim Haddad", "MD", False),
                      ("Carmen Ortiz", "NP", True), ("Wesley Park", "PA-C", True)],
        "visit_types": [("New Patient Consult", 60), ("Follow-up Visit", 30), ("Pulmonary Function Test", 60),
                        ("Sleep Study Consult", 45)],
        "transfers": [("Billing", "(555) 555-0172"), ("On-call physician", "(555) 555-0177")],
        "policies": {"walk_ins": False, "telehealth": True, "new_patients": True, "refill_days": 2},
        "red_flags": ["shortness of breath", "coughing up blood", "blue lips", "oxygen alarm", "chest pain",
                      "high fever", "confusion"],
        "smoke_symptoms": ["coughing up blood", "shortness of breath"],
        "holidays_free_text": "Closed on Thanksgiving, Christmas Day, New Year's Day and Memorial Day.",
        "holidays_expected": ["thanksgiving", "christmas day", "new year's day", "memorial day"],
        "defects": [
            {"type": "missing_timezone"},
            {"type": "red_flag_no_escalation", "symptom": "coughing up blood"},
            {"type": "hours_conflict", "day": "Saturday", "where": "script", "wrong": ("08:00", "10:00")},
            {"type": "invalid_phone", "field": "after_hours", "raw": "(555) 55-0177"},
            {"type": "unknown_provider", "name": "Brandt", "line": "Dr. Brandt runs the Thursday sleep clinic."},
            {"type": "duplicate_visit_type", "canonical": "New Patient Consult", "duplicate": "New Pt Consult"},
            {"type": "faq_script_contradiction", "topic": "refill_days", "faq_value": 5},
            {"type": "holiday_free_text"},
        ],
    },
    {
        "id": "p05", "name": "Lakeside QuickCare", "specialty": "urgent care",
        "address": "5 Imaginary Pier, Tacoma, WA", "timezone": "America/Los_Angeles",
        "main_phone": "(555) 555-0180", "after_hours_phone": "(555) 555-0189",
        "hours": {d: ("08:00", "20:00") for d in DAY_NAMES},
        "providers": [("Nadia Farouk", "MD", True), ("Chris Albright", "PA-C", True), ("Yuki Sato", "NP", True)],
        "visit_types": [("Urgent Visit", 20), ("Sports Physical", 20), ("Flu Shot", 10), ("X-Ray", 20)],
        "transfers": [("Billing", "(555) 555-0182"), ("Occupational health", "(555) 555-0184")],
        "policies": {"walk_ins": True, "telehealth": False, "new_patients": True, "refill_days": 1},
        "red_flags": ["chest pain", "shortness of breath", "stroke symptoms", "deep cut", "head injury",
                      "severe allergic reaction", "high fever"],
        "smoke_symptoms": ["chest pain", "deep cut"],
        "holidays_free_text": "We are open every day except Thanksgiving and Christmas Day.",
        "holidays_expected": ["thanksgiving", "christmas day"],
        "defects": [
            {"type": "duplicate_visit_type", "canonical": "Flu Shot", "duplicate": "Flu Shot Visit"},
            {"type": "holiday_free_text"},
            {"type": "unknown_provider", "name": "Castellano", "line": "Dr. Castellano covers weekend shifts."},
            {"type": "faq_script_contradiction", "topic": "walk_ins"},
        ],
    },
    {
        "id": "p06", "name": "Summit Multispecialty Group", "specialty": "multispecialty",
        "address": "900 Demo Boulevard, Minneapolis, MN", "timezone": "America/Chicago",
        "main_phone": "(555) 555-0190", "after_hours_phone": "(555) 555-0198", "spanish": True,
        "hours": {**{d: ("08:00", "18:00") for d in DAY_NAMES[:5]}, "Saturday": ("09:00", "13:00"), "Sunday": None},
        "providers": [("Laura Bennett", "MD", True), ("Kwame Mensah", "MD", True), ("Isabel Cruz", "MD", False),
                      ("Thomas Reilly", "MD", True), ("Anika Sharma", "MD", True), ("Victor Petrov", "DO", True),
                      ("Ruth Adeyemi", "MD", False), ("Paolo Ricci", "MD", True), ("Hye-jin Kim", "NP", True),
                      ("Sean Murphy", "PA-C", True), ("Fatima Khan", "NP", True), ("Erik Johansson", "MD", True)],
        "visit_types": [("New Patient Visit", 40), ("Follow-up Visit", 20), ("Cardiology Consult", 60),
                        ("Pulmonary Function Test", 60), ("Annual Physical", 30)],
        "transfers": [("Billing", "(555) 555-0192"), ("Nurse line", "(555) 555-0194"), ("Referrals", "(555) 555-0196")],
        "policies": {"walk_ins": False, "telehealth": True, "new_patients": True, "refill_days": 2},
        "red_flags": ["chest pain", "stroke symptoms", "shortness of breath", "fainting", "coughing up blood",
                      "palpitations", "high fever", "severe allergic reaction", "blue lips", "confusion"],
        "smoke_symptoms": ["chest pain", "coughing up blood"],
        "defects": [],
    },
]


class Doc:
    """Builds a text file line by line and remembers where things were written."""

    def __init__(self, name: str):
        self.name = name
        self.lines: list[str] = []

    def add(self, text: str = "") -> str:
        self.lines.append(text)
        return f"{self.name}:{len(self.lines)}"

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def fmt_time(hhmm: str) -> str:
    h, m = map(int, hhmm.split(":"))
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def fmt_time_short(hhmm: str) -> str:
    h, m = map(int, hhmm.split(":"))
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12} {suffix}" if m == 0 else f"{h12}:{m:02d} {suffix}"


def hours_sentence(day: str, span) -> str:
    if span is None:
        return f"We are closed on {day}s."
    return f"Our {day} hours are {fmt_time_short(span[0])} to {fmt_time_short(span[1])}."


def span_value(span) -> str:
    return "closed" if span is None else f"{span[0]}-{span[1]}"


POLICY_LINES = {
    "walk_ins": {True: "We welcome walk-ins any time we are open.", False: "We see patients by appointment only."},
    "telehealth": {True: "We offer telehealth video visits for follow-ups.",
                   False: "We do not offer telehealth visits."},
    "new_patients": {True: "We are accepting new patients.", False: "We are not accepting new patients right now."},
}
FAQ_POLICY = {
    "walk_ins": ("Do you accept walk-ins?", {True: "Yes. We welcome walk-ins any time we are open.",
                                             False: "No. We see patients by appointment only."}),
    "telehealth": ("Do you offer telehealth?", {True: "Yes. We offer telehealth video visits for follow-ups.",
                                                False: "No. We do not offer telehealth visits."}),
    "new_patients": ("Are you accepting new patients?", {True: "Yes, we are accepting new patients.",
                                                         False: "No, we are not accepting new patients right now."}),
}


def refill_line(days: int) -> str:
    unit = "business day" if days == 1 else "business days"
    return f"Prescription refills are processed within {days} {unit}."


def surname(name: str) -> str:
    return name.split()[-1]


def provider_mention(name: str, cred: str) -> str:
    return f"Dr. {surname(name)}" if cred in ("MD", "DO") else f"{name}, {cred},"


def build_practice(spec: dict, rng: random.Random) -> dict[str, str]:
    defects = {d["type"]: d for d in spec["defects"]}
    truth: list[dict] = []

    def plant(dtype: str, key: str, location: str, description: str, expected_fix):
        truth.append({
            "id": f"{spec['id']}-d{len(truth) + 1}", "type": dtype, "key": key,
            "severity": DEFECT_TYPES[dtype].severity, "location": location,
            "description": description, "expected_fix": expected_fix,
        })

    def phone_raw(field: str, good: str) -> str:
        d = defects.get("invalid_phone")
        return d["raw"] if d and d["field"] == field else good

    # ---------------------------------------------------------------- hours.txt
    hours = Doc("hours.txt")
    hours.add("# Office hours and contact details")
    hours.add(f"Practice: {spec['name']}")
    hours.add(f"Specialty: {spec['specialty'].title()}")
    hours.add(f"Address: {spec['address']}")
    if "missing_timezone" in defects:
        plant("missing_timezone", "timezone", "hours.txt", "No timezone line in hours.txt.", spec["timezone"])
    else:
        hours.add(f"Timezone: {spec['timezone']}")
    main_raw = phone_raw("main_phone", spec["main_phone"])
    loc = hours.add(f"Main phone: {main_raw}")
    if main_raw != spec["main_phone"]:
        plant("invalid_phone", main_raw, loc, f"Main phone '{main_raw}' is not a valid 10-digit number.",
              spec["main_phone"])
    hours.add()
    for day in DAY_NAMES:
        span = spec["hours"][day]
        hours.add(f"{day}: Closed" if span is None else f"{day}: {fmt_time(span[0])} - {fmt_time(span[1])}")
    hours.add()
    if "missing_after_hours" in defects:
        plant("missing_after_hours", "after_hours", "hours.txt",
              "No after-hours instructions in any file.", None)
    else:
        ah_raw = phone_raw("after_hours", spec["after_hours_phone"])
        loc = hours.add(f"After-hours: Calls forward to the on-call line at {ah_raw}.")
        if ah_raw != spec["after_hours_phone"]:
            plant("invalid_phone", ah_raw, loc, f"After-hours phone '{ah_raw}' is not a valid 10-digit number.",
                  spec["after_hours_phone"])
    if "holiday_free_text" in defects:
        loc = hours.add(f"Holidays: {spec['holidays_free_text']}")
        expected = sorted(HOLIDAY_DATES[h][0] for h in spec["holidays_expected"])
        plant("holiday_free_text", "holidays", loc, "Holiday closures are free text, not dates.", ", ".join(expected))
    else:
        hours.add("Holidays: 2026-11-26 Thanksgiving Day; 2026-12-25 Christmas Day; 2027-01-01 New Year's Day")

    # ----------------------------------------------------------- providers.csv
    prov_lines = ["provider_id,name,credentials,specialty,accepting_new_patients"]
    for i, (name, cred, accepting) in enumerate(spec["providers"], start=1):
        prov_lines.append(f"{spec['id']}-prov{i:02d},{name},{cred},{spec['specialty']},{'yes' if accepting else 'no'}")

    # ---------------------------------------------------------- call_script.md
    script = Doc("call_script.md")
    script.add(f"# Call script: {spec['name']}")
    script.add()
    script.add("## Greeting")
    script.add(f"Thank you for calling {spec['name']}. This is the virtual front desk.")
    if spec.get("spanish"):
        script.add('Para español, diga "español" en cualquier momento.')
    script.add("How can I help you today?")
    script.add()
    script.add("## Hours")
    for day in ["Saturday", *spec.get("extra_script_days", [])]:
        d = defects.get("hours_conflict")
        if d and d["day"] == day and d["where"] == "script":
            loc = script.add(hours_sentence(day, d["wrong"]))
            plant("hours_conflict", day.lower(), loc,
                  f"Script gives {day} hours as {span_value(d['wrong'])}; hours.txt says {span_value(spec['hours'][day])}.",
                  span_value(spec["hours"][day]))
        else:
            script.add(hours_sentence(day, spec["hours"][day]))
    script.add()
    script.add("## Visit types")
    dup = defects.get("duplicate_visit_type")
    for name, minutes in spec["visit_types"]:
        script.add(f"- {name} ({minutes} min)")
        if dup and dup["canonical"] == name:
            dup_minutes = minutes
    if dup:
        loc = script.add(f"- {dup['duplicate']} ({dup_minutes} min)")
        plant("duplicate_visit_type", dup["duplicate"].lower(), loc,
              f"'{dup['duplicate']}' duplicates '{dup['canonical']}'.", dup["canonical"])
    script.add()
    script.add("## Providers")
    for name, cred, accepting in spec["providers"]:
        mention = provider_mention(name, cred)
        script.add(f"{mention} has openings for new patients." if accepting else f"{mention} has a full panel.")
    if "unknown_provider" in defects:
        d = defects["unknown_provider"]
        loc = script.add(d["line"])
        plant("unknown_provider", d["name"].lower(), loc, f"Dr. {d['name']} is named in the script but not on the roster.", "")
    script.add()
    script.add("## Policies")
    policy_locs = {}
    for topic in ["walk_ins", "telehealth", "new_patients"]:
        policy_locs[topic] = script.add(POLICY_LINES[topic][spec["policies"][topic]])
    policy_locs["refill_days"] = script.add(refill_line(spec["policies"]["refill_days"]))
    script.add()
    script.add("## Transfers")
    for reason, number in spec["transfers"]:
        raw = phone_raw(f"transfer:{reason}", number)
        loc = script.add(f"- {reason}: {raw}")
        if raw != number:
            plant("invalid_phone", raw, loc, f"{reason} transfer number '{raw}' is not a valid 10-digit number.", None)
    script.add()
    script.add("## Closing")
    script.add("Is there anything else I can help you with?")

    # ------------------------------------------------------------------ faq.md
    faq = Doc("faq.md")
    faq.add("# Frequently asked questions")
    contra = defects.get("faq_script_contradiction")
    entries = []
    for topic in ["walk_ins", "telehealth", "new_patients"]:
        question, answers = FAQ_POLICY[topic]
        value = spec["policies"][topic]
        if contra and contra["topic"] == topic:
            entries.append((question, answers[not value], topic))
        else:
            entries.append((question, answers[value], None))
    refill_days = spec["policies"]["refill_days"]
    if contra and contra["topic"] == "refill_days":
        entries.append(("How long do prescription refills take?", refill_line(contra["faq_value"]), "refill_days"))
    else:
        entries.append(("How long do prescription refills take?", refill_line(refill_days), None))
    hc = defects.get("hours_conflict")
    if hc and hc["where"] == "faq":
        entries.append(("Are you open on Saturdays?", hours_sentence(hc["day"], hc["wrong"]), "hours"))
    else:
        entries.append(("Are you open on Saturdays?", hours_sentence("Saturday", spec["hours"]["Saturday"]), None))
    tail = [
        ("What should I bring to my first visit?", "Please bring a photo ID, your insurance card and a list of your medications."),
        ("How do I reach you?", f"Call our main line at {spec['main_phone']}."),
        ("Where do I park?", "Free parking is available in the lot next to the building."),
    ]
    rng.shuffle(tail)
    entries += [(q, a, None) for q, a in tail]
    for question, answer, planted in entries:
        faq.add()
        faq.add(f"## {question}")
        loc = faq.add(answer)
        if planted == "hours":
            plant("hours_conflict", hc["day"].lower(), loc,
                  f"FAQ gives {hc['day']} hours as {span_value(hc['wrong'])}; hours.txt says {span_value(spec['hours'][hc['day']])}.",
                  span_value(spec["hours"][hc["day"]]))
        elif planted:
            script_line = (refill_line(refill_days) if planted == "refill_days"
                           else POLICY_LINES[planted][spec["policies"][planted]])
            plant("faq_script_contradiction", planted, loc,
                  f"FAQ answer contradicts the call script ({policy_locs[planted]}).", script_line)

    # ------------------------------------------------------------- protocols.md
    proto = Doc("protocols.md")
    proto.add("# Red-flag protocols")
    proto.add("Each rule: symptom | keywords | escalation | what to say")
    proto.add()
    flags = [s for s in spec["red_flags"] if s != defects.get("missing_red_flag", {}).get("symptom")]
    if "missing_red_flag" in defects:
        s = defects["missing_red_flag"]["symptom"]
        plant("missing_red_flag", s, "protocols.md",
              f"No '{s}' rule, which {spec['specialty']} requires.", RED_FLAG_LIBRARY[s]["level"])
    for s in flags:
        rule = RED_FLAG_LIBRARY[s]
        no_esc = defects.get("red_flag_no_escalation", {}).get("symptom") == s
        level = "TBD" if no_esc else rule["level"]
        say = "" if no_esc else rule["say"]
        loc = proto.add(f"- {s} | keywords: {', '.join(rule['keywords'])} | escalation: {level} | say: {say}".rstrip())
        if no_esc:
            plant("red_flag_no_escalation", s, loc, f"The '{s}' rule has no escalation.", rule["level"])

    # ------------------------------------------------------------ smoke tests
    first_md = next(n for n, c, _ in spec["providers"] if c in ("MD", "DO"))
    smoke = [
        {"message": "Hi, I'd like to book an appointment for next week.", "expected_intent": "book_appointment"},
        {"message": "What are your hours on Saturday?", "expected_intent": "hours"},
        {"message": "I need a refill on my blood pressure medication.", "expected_intent": "prescription_refill"},
        {"message": "I have a question about a charge on my bill.", "expected_intent": "billing"},
    ]
    for s in spec["smoke_symptoms"]:
        smoke.append({"message": SYMPTOM_MESSAGES[s], "expected_intent": "red_flag",
                      "expected_escalation": RED_FLAG_LIBRARY[s]["level"]})
    smoke += [
        {"message": f"Is Dr. {surname(first_md)} taking new patients?", "expected_intent": "provider_info"},
        {"message": "Do you accept walk-ins?", "expected_intent": "faq"},
        {"message": "Who do I call after hours if the office is closed?", "expected_intent": "after_hours"},
    ]
    if spec.get("spanish"):
        smoke.append({"message": "Necesito una cita, por favor.", "expected_intent": "book_appointment"})
    else:
        smoke.append({"message": "I need to reschedule my appointment on Thursday.", "expected_intent": "reschedule"})
    for item in smoke:
        item.setdefault("expected_escalation", None)

    assert len(truth) == len(spec["defects"]), (spec["id"], len(truth), len(spec["defects"]))
    return {
        "hours.txt": hours.text(),
        "providers.csv": "\n".join(prov_lines) + "\n",
        "call_script.md": script.text(),
        "faq.md": faq.text(),
        "protocols.md": proto.text(),
        "defects.json": json.dumps({"practice_id": spec["id"], "defects": truth}, indent=2) + "\n",
        "smoke_tests.json": json.dumps(smoke, indent=2, ensure_ascii=False) + "\n",
    }


def generate(out_dir: Path = DATA_DIR, seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    ids = []
    for spec in PRACTICES:
        target = out_dir / spec["id"]
        target.mkdir(parents=True, exist_ok=True)
        for filename, content in build_practice(spec, rng).items():
            (target / filename).write_text(content, encoding="utf-8", newline="\n")
        ids.append(spec["id"])
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DATA_DIR)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    ids = generate(args.out, args.seed)
    total = sum(len(json.loads((args.out / i / "defects.json").read_text(encoding="utf-8"))["defects"]) for i in ids)
    print(f"Wrote {len(ids)} practices with {total} planted defects to {args.out}")


if __name__ == "__main__":
    main()
