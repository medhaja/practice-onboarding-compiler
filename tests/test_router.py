"""Smoke-test router: intents, red-flag escalation, and failure on unrepaired escalation defects."""
import pytest

from onboarding.compiler import list_practices
from onboarding.pipeline import analyze
from onboarding.review import build_state
from onboarding.router import load_smoke_tests, route, run_smoke


@pytest.mark.parametrize("message,intent", [
    ("Can I book a checkup?", "book_appointment"),
    ("I need to reschedule my appointment on Thursday.", "reschedule"),
    ("What are your hours on Saturday?", "hours"),
    ("Who do I call after hours if the office is closed?", "after_hours"),
    ("Is Dr. Bennett taking new patients?", "provider_info"),
    ("Do you accept walk-ins?", "faq"),
    ("Necesito una cita, por favor.", "book_appointment"),
    ("Tell me a joke", "unknown"),
])
def test_intents(clean, message, intent):
    _, config = clean
    assert route(message, config).intent == intent


def test_red_flag_wins_over_other_intents(clean):
    _, config = clean
    r = route("I want to book an appointment, I have chest pain", config)
    assert (r.intent, r.escalation) == ("red_flag", "emergency")


def test_hours_reply_reads_config(clean):
    _, config = clean
    assert route("What are your hours on Saturday?", config).reply == "Our Saturday hours are 9 AM to 1 PM."


@pytest.mark.parametrize("pid", list_practices())
def test_ten_scripted_messages_per_practice(pid):
    assert len(load_smoke_tests(pid)) == 10


@pytest.mark.parametrize("pid", list_practices())
def test_smoke_passes_once_every_proposal_is_accepted(pid):
    a = analyze(pid, "mock")
    accepted = {i.id: ("accept", "") for i in a.issues if i.repair.value}
    results = run_smoke(build_state(a, accepted).approved, load_smoke_tests(pid))
    assert all(r["passed"] for r in results), [r for r in results if not r["passed"]]


@pytest.mark.parametrize("pid,symptom_msg", [("p02", "face is drooping"), ("p03", "chest pain"),
                                             ("p04", "coughing up blood")])
def test_unreviewed_escalation_defect_fails_smoke(pid, symptom_msg):
    a = analyze(pid, "mock")
    results = run_smoke(build_state(a, {}).approved, load_smoke_tests(pid))
    failed = [r["message"] for r in results if not r["passed"]]
    assert len(failed) == 1 and symptom_msg in failed[0]
