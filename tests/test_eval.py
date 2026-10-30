"""End-to-end quality bars from the PRD, measured against defects.json in mock mode."""
from onboarding.eval import evaluate


def test_quality_targets_and_zero_escalation_misses():
    r = evaluate("mock")
    assert r.escalation_missed == []
    assert r.recall >= 0.9 and r.precision >= 0.8
    assert r.repair_accuracy >= 0.9
    assert r.smoke_reviewed[0] == r.smoke_reviewed[1]
