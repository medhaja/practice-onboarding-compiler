"""Evaluate the checker and repairer against the planted ground truth in every defects.json.

Prints detection precision and recall, repair accuracy, the share of fields auto-approved and the
smoke-test pass rate. Run: python -m onboarding.eval   (add --mode llm to score the LLM checker)
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field

from .compiler import DATA_ROOT, list_practices
from .pipeline import analyze
from .review import build_state
from .router import load_smoke_tests, run_smoke
from .semantic import llm_model, load_env_file
from .taxonomy import ESCALATION_TYPES


@dataclass
class Report:
    mode: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    missed: list[str] = field(default_factory=list)
    false_alarms: list[str] = field(default_factory=list)
    escalation_missed: list[str] = field(default_factory=list)
    repairs_scored: int = 0
    repairs_correct: int = 0
    fields_total: int = 0
    fields_auto: int = 0
    exceptions: dict[str, int] = field(default_factory=dict)
    smoke_auto: list[int] = field(default_factory=lambda: [0, 0])
    smoke_reviewed: list[int] = field(default_factory=lambda: [0, 0])

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def repair_accuracy(self) -> float:
        return self.repairs_correct / self.repairs_scored if self.repairs_scored else 1.0


def evaluate(mode: str = "mock") -> Report:
    report = Report(mode=mode if mode == "mock" else f"llm:{llm_model() or 'unavailable, mock used'}")
    for pid in list_practices():
        truth = json.loads((DATA_ROOT / pid / "defects.json").read_text(encoding="utf-8"))["defects"]
        expected = {(d["type"], d["key"]): d for d in truth}
        analysis = analyze(pid, semantic_mode=mode)
        found = {(i.type, i.key): i for i in analysis.issues}

        for key in expected.keys() & found.keys():
            report.tp += 1
            fix = expected[key]["expected_fix"]
            if fix:  # defects whose fix is "ask the practice" have nothing to score
                report.repairs_scored += 1
                report.repairs_correct += found[key].repair.value == fix
        for key in expected.keys() - found.keys():
            report.fn += 1
            report.missed.append(f"{pid} {key[0]} {key[1]}")
            if key[0] in ESCALATION_TYPES:
                report.escalation_missed.append(f"{pid} {key[1]}")
        for key in found.keys() - expected.keys():
            report.fp += 1
            report.false_alarms.append(f"{pid} {key[0]} {key[1]}")

        state = build_state(analysis, {})
        counts = state.counts()
        report.fields_total += counts["total_fields"]
        report.fields_auto += counts["auto_approved"]
        report.exceptions[pid] = counts["exceptions"]

        tests = load_smoke_tests(pid)
        accept_all = {i.id: ("accept", "") for i in analysis.issues if i.repair.value}
        for bucket, config in ((report.smoke_auto, state.approved),
                               (report.smoke_reviewed, build_state(analysis, accept_all).approved)):
            results = run_smoke(config, tests)
            bucket[0] += sum(r["passed"] for r in results)
            bucket[1] += len(results)
    return report


def render(r: Report) -> str:
    pct = lambda x: f"{x * 100:.0f}%"
    lines = [
        f"Checker mode: {r.mode}   practices: {len(r.exceptions)}   planted defects: {r.tp + r.fn}",
        "",
        f"Detection precision   {r.precision:.2f}   ({r.tp} true, {r.fp} false alarms)      target >= 0.80",
        f"Detection recall      {r.recall:.2f}   ({r.tp} found, {r.fn} missed)            target >= 0.90",
        f"Escalation misses     {len(r.escalation_missed)}                                      target = 0",
        f"Repair accuracy       {pct(r.repair_accuracy)}   ({r.repairs_correct}/{r.repairs_scored} proposals match the known fix)",
        f"Fields auto-approved  {pct(r.fields_auto / r.fields_total)}   ({r.fields_auto}/{r.fields_total})",
        "Exceptions per practice  " + ", ".join(f"{k}: {v}" for k, v in r.exceptions.items()),
        f"Smoke tests, auto repairs only       {r.smoke_auto[0]}/{r.smoke_auto[1]}",
        f"Smoke tests, all proposals accepted  {r.smoke_reviewed[0]}/{r.smoke_reviewed[1]}",
    ]
    if r.missed:
        lines += ["", "Missed: " + "; ".join(r.missed)]
    if r.false_alarms:
        lines += ["False alarms: " + "; ".join(r.false_alarms)]
    lines += ["", "Synthetic defects are easier to catch than real ones; treat these numbers as optimistic."]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["mock", "llm"], default="mock")
    args = parser.parse_args()
    load_env_file()
    print(render(evaluate(args.mode)))


if __name__ == "__main__":
    main()
