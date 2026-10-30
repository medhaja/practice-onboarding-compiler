"""Repair proposals, confidence gating, applying repairs, and SQLite review state."""
import json

import pytest

from onboarding.compiler import DATA_ROOT, list_practices
from onboarding.pipeline import analyze
from onboarding.repairer import AUTO_THRESHOLD, apply_repair, parse_holidays
from onboarding.review import ReviewStore, build_state
from onboarding.taxonomy import ESCALATION_TYPES


def truth(pid):
    data = json.loads((DATA_ROOT / pid / "defects.json").read_text(encoding="utf-8"))
    return {(d["type"], d["key"]): d for d in data["defects"]}


def issue(analysis, dtype):
    return next(i for i in analysis.issues if i.type == dtype)


@pytest.fixture
def store(tmp_path):
    return ReviewStore(tmp_path / "review.sqlite")


@pytest.mark.parametrize("pid", list_practices())
def test_every_issue_has_evidence_and_repair(pid):
    for i in analyze(pid, "mock").issues:
        assert i.evidence and i.severity in ("high", "medium", "low")
        assert i.repair is not None and 0 <= i.repair.confidence <= 1


@pytest.mark.parametrize("pid", list_practices())
def test_proposals_match_ground_truth_where_known(pid):
    expected = truth(pid)
    for i in analyze(pid, "mock").issues:
        fix = expected[(i.type, i.key)]["expected_fix"]
        if fix:
            assert i.repair.value == fix, i.id


@pytest.mark.parametrize("pid", list_practices())
def test_gating(pid):
    for i in analyze(pid, "mock").issues:
        if i.type in ESCALATION_TYPES or i.repair.confidence < AUTO_THRESHOLD:
            assert i.repair.route == "human", i.id
        else:
            assert i.repair.route == "auto", i.id


def test_escalation_repairs_never_auto_even_when_confident():
    i = issue(analyze("p02", "mock"), "red_flag_no_escalation")
    assert i.repair.confidence >= AUTO_THRESHOLD and i.repair.route == "human"


def test_ambiguous_phone_goes_to_human():
    i = issue(analyze("p03", "mock"), "invalid_phone")
    assert i.repair.value == "" and i.repair.route == "human" and len(i.repair.citations) > 1


def test_holiday_parsing_handles_relative_phrases():
    assert parse_holidays("We close for Thanksgiving and the Friday after.") == ["2026-11-26", "2026-11-27"]


def test_apply_hours_conflict_rewrites_script_line():
    a = analyze("p01", "mock")
    i = issue(a, "hours_conflict")
    config = apply_repair(a.config, i, i.repair.value)
    line = next(l for l in config.script if l.id == i.targets[1].split(":")[1])
    assert line.text == "Our Saturday hours are 9 AM to 12 PM." and line.source == "review"


def test_apply_requires_value_except_provider_removal():
    a = analyze("p03", "mock")
    with pytest.raises(ValueError):
        apply_repair(a.config, issue(a, "invalid_phone"), "")
    removed = apply_repair(a.config, issue(a, "unknown_provider"), "")
    assert not any("Whitcombe" in l.text for l in removed.script)


def test_auto_repairs_apply_without_review(store):
    a = analyze("p01", "mock")
    state = build_state(a, store.decisions("p01"))
    assert state.approved.main_phone.value == "(555) 555-0123"
    assert not any(v.name == "New Pt Visit" for v in state.approved.visit_types)
    assert state.status == "draft" and state.can_export  # only medium/low items are open


def test_export_blocked_until_high_issues_resolved(store):
    a = analyze("p02", "mock")
    state = build_state(a, store.decisions("p02"))
    assert not state.can_export
    assert {i.issue.type for i in state.blocking} == {"missing_after_hours", "red_flag_no_escalation"}

    store.decide("p02", issue(a, "red_flag_no_escalation").id, "accept")
    store.decide("p02", issue(a, "missing_after_hours").id, "edit",
                 "Calls forward to the on-call line at (555) 555-0158.")
    state = build_state(a, store.decisions("p02"))
    assert state.can_export and state.status == "needs review"
    assert state.approved.after_hours.phone.value == "(555) 555-0158"
    assert next(r for r in state.approved.escalation_rules if r.symptom == "stroke symptoms").level == "emergency"

    store.decide("p02", issue(a, "faq_script_contradiction").id, "reject")
    assert build_state(a, store.decisions("p02")).status == "ready"


def test_bad_edit_stays_open_with_error(store):
    a = analyze("p02", "mock")
    store.decide("p02", issue(a, "red_flag_no_escalation").id, "edit", "panic")
    item = next(i for i in build_state(a, store.decisions("p02")).items if i.issue.type == "red_flag_no_escalation")
    assert item.status == "open" and item.error


def test_reset_and_invalid_action(store):
    store.decide("p01", "x", "reject")
    store.reset("p01")
    assert store.decisions("p01") == {}
    with pytest.raises(ValueError):
        store.decide("p01", "x", "approve")


def test_clean_practice_is_ready_with_everything_auto_approved(store):
    state = build_state(analyze("p06", "mock"), {})
    counts = state.counts()
    assert state.status == "ready" and counts["exceptions"] == 0
    assert counts["auto_approved"] == counts["total_fields"]
