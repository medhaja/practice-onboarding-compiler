"""Review state: reviewer decisions stored in SQLite, merged with the analysis into an approved config.

An issue's status is one of:
  auto      repair applied without a person (confidence cleared the bar, not escalation related)
  open      waiting for a reviewer
  accepted  reviewer applied the proposed repair
  edited    reviewer applied their own value
  rejected  reviewer decided no change is needed
Export is blocked while any high-severity issue is open.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .pipeline import Analysis
from .repairer import apply_repair
from .schema import AgentConfig, count_fields
from .validator import Issue

DEFAULT_DB = Path(__file__).resolve().parent.parent / "var" / "review.sqlite"
ACTIONS = ("accept", "edit", "reject")


class ReviewStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or os.getenv("REVIEW_DB") or DEFAULT_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS decisions (
                practice_id TEXT NOT NULL, issue_id TEXT NOT NULL, action TEXT NOT NULL,
                value TEXT NOT NULL DEFAULT '', decided_at TEXT NOT NULL,
                PRIMARY KEY (practice_id, issue_id))""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def decide(self, practice_id: str, issue_id: str, action: str, value: str = "") -> None:
        if action not in ACTIONS:
            raise ValueError(f"action must be one of {ACTIONS}")
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?)",
                       (practice_id, issue_id, action, value, datetime.now(timezone.utc).isoformat()))

    def decisions(self, practice_id: str) -> dict[str, tuple[str, str]]:
        with self._connect() as db:
            rows = db.execute("SELECT issue_id, action, value FROM decisions WHERE practice_id = ?", (practice_id,))
            return {issue_id: (action, value) for issue_id, action, value in rows}

    def reset(self, practice_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM decisions WHERE practice_id = ?", (practice_id,))


@dataclass
class ReviewedIssue:
    issue: Issue
    status: str
    applied_value: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ReviewState:
    practice_id: str
    original: AgentConfig
    approved: AgentConfig
    items: list[ReviewedIssue] = field(default_factory=list)
    touched: bool = False

    @property
    def open_items(self) -> list[ReviewedIssue]:
        return [i for i in self.items if i.status == "open"]

    @property
    def blocking(self) -> list[ReviewedIssue]:
        return [i for i in self.open_items if i.issue.severity == "high"]

    @property
    def can_export(self) -> bool:
        return not self.blocking

    @property
    def status(self) -> str:
        """draft: nobody has reviewed it yet; needs review: review started; ready: nothing left open."""
        if not self.open_items:
            return "ready"
        return "needs review" if self.touched else "draft"

    def counts(self) -> dict[str, int]:
        """Fields the reviewer never has to look at vs. exceptions routed to a person."""
        human = [i for i in self.items if i.issue.repair.route == "human"]
        flagged_fields = {t for i in human for t in (i.issue.targets or [i.issue.id])}
        total = count_fields(self.original)
        return {"total_fields": total, "auto_approved": max(total - len(flagged_fields), 0),
                "exceptions": len(human), "open": len(self.open_items), "blocking": len(self.blocking),
                "auto_repaired": sum(1 for i in self.items if i.status == "auto")}


def build_state(analysis: Analysis, decisions: dict[str, tuple[str, str]]) -> ReviewState:
    config = analysis.config
    items = []
    for issue in analysis.issues:
        decision = decisions.get(issue.id)
        if decision:
            action, value = decision
            status = {"accept": "accepted", "edit": "edited", "reject": "rejected"}[action]
            value = issue.repair.value if action == "accept" else value
        elif issue.repair.route == "auto":
            status, value = "auto", issue.repair.value
        else:
            items.append(ReviewedIssue(issue, "open"))
            continue
        item = ReviewedIssue(issue, status)
        if status != "rejected":
            try:
                config = apply_repair(config, issue, value)
                item.applied_value = value
            except Exception as exc:  # a bad edit must not take the whole practice down
                item.status, item.error = "open", f"Could not apply '{value}': {exc}"
        items.append(item)
    return ReviewState(analysis.packet.practice_id, analysis.config, config, items, touched=bool(decisions))
