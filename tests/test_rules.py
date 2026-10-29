"""One test per deterministic rule: the clean practice passes, a targeted mutation is caught."""
from onboarding.schema import EscalationRule, PhoneField, ScriptLine, VisitType
from onboarding.validator import (normalize_visit_type, rule_duplicate_visit_type, rule_holiday_free_text,
                                  rule_hours_conflict, rule_invalid_phone, rule_missing_after_hours,
                                  rule_missing_red_flag, rule_missing_timezone, rule_red_flag_no_escalation,
                                  rule_unknown_provider, run_rules)


def keys(issues):
    return [(i.type, i.key) for i in issues]


def test_clean_practice_has_no_rule_issues(clean):
    packet, config = clean
    assert run_rules(config, packet) == []


def test_hours_conflict(clean):
    packet, config = clean
    config.script.append(ScriptLine(id="sx", section="hours", text="Our Saturday hours are 9 AM to 5 PM.",
                                    source="call_script.md:9"))
    config.faqs[0].answer = "We are closed on Saturdays."
    issues = rule_hours_conflict(config, packet)
    assert keys(issues) == [("hours_conflict", "saturday")]
    assert {"script:sx", f"faqs:{config.faqs[0].id}"} <= set(issues[0].targets)


def test_unknown_provider(clean):
    packet, config = clean
    config.script.append(ScriptLine(id="sx", section="providers", text="Dr. Nobody covers Fridays.",
                                    source="call_script.md:20"))
    assert keys(rule_unknown_provider(config, packet)) == [("unknown_provider", "nobody")]


def test_known_provider_with_first_name_is_fine(clean):
    packet, config = clean
    config.script.append(ScriptLine(id="sx", section="providers", text="Dr. Laura Bennett is in on Mondays.",
                                    source="call_script.md:20"))
    assert rule_unknown_provider(config, packet) == []


def test_missing_after_hours(clean):
    packet, config = clean
    config.after_hours = None
    assert keys(rule_missing_after_hours(config, packet)) == [("missing_after_hours", "after_hours")]


def test_on_call_transfer_counts_as_after_hours_path(clean):
    packet, config = clean
    config.after_hours = None
    config.transfers[0].reason = "On-call physician"
    assert rule_missing_after_hours(config, packet) == []


def test_red_flag_no_escalation(clean):
    packet, config = clean
    config.escalation_rules[1].level = "none"
    assert keys(rule_red_flag_no_escalation(config, packet)) == [("red_flag_no_escalation", "stroke symptoms")]


def test_missing_red_flag(clean):
    packet, config = clean
    config.escalation_rules = [r for r in config.escalation_rules if r.symptom != "fainting"]
    assert keys(rule_missing_red_flag(config, packet)) == [("missing_red_flag", "fainting")]


def test_cardiology_requires_chest_pain(clean):
    packet, config = clean
    config.specialty.value = "cardiology"
    config.escalation_rules = [r for r in config.escalation_rules if r.symptom != "chest pain"]
    assert ("missing_red_flag", "chest pain") in keys(rule_missing_red_flag(config, packet))


def test_invalid_phone(clean):
    packet, config = clean
    config.transfers[0].phone = PhoneField(raw="(555) 01-23", value=None, source="call_script.md:30")
    issues = rule_invalid_phone(config, packet)
    assert keys(issues) == [("invalid_phone", "(555) 01-23")]
    assert issues[0].targets == [f"transfers:{config.transfers[0].id}"]


def test_duplicate_visit_type(clean):
    packet, config = clean
    config.visit_types.append(VisitType(id="vtx", name="New Pt Visit", minutes=40, source="call_script.md:16"))
    assert keys(rule_duplicate_visit_type(config, packet)) == [("duplicate_visit_type", "new pt visit")]


def test_visit_type_normalization():
    assert normalize_visit_type("New Pt Visit") == normalize_visit_type("New Patient Visit")
    assert normalize_visit_type("Follow Up Visit") == normalize_visit_type("Follow-up Visit")
    assert normalize_visit_type("Flu Shot Visit") == normalize_visit_type("Flu Shot")
    assert normalize_visit_type("New Patient Visit") != normalize_visit_type("Follow-up Visit")


def test_missing_timezone(clean):
    packet, config = clean
    config.timezone = None
    assert keys(rule_missing_timezone(config, packet)) == [("missing_timezone", "timezone")]


def test_holiday_free_text(clean):
    packet, config = clean
    config.holidays[0].date = None
    assert keys(rule_holiday_free_text(config, packet)) == [("holiday_free_text", "holidays")]
