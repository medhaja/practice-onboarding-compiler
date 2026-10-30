"""FastAPI app: JSON endpoints plus the single-page review UI.

Run: python -m onboarding.app   (then open http://127.0.0.1:8000)
"""
from __future__ import annotations

import json
import os
import socket
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from .compiler import PACKET_FILES, list_practices
from .generator import fmt_time_short
from .pipeline import Analysis, analyze
from .review import ReviewState, ReviewStore, build_state
from .router import load_smoke_tests, run_smoke
from .schema import AgentConfig
from .semantic import llm_model

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Practice Onboarding Compiler")
store = ReviewStore()


@lru_cache(maxsize=None)
def cached_analysis(practice_id: str) -> Analysis:
    return analyze(practice_id)


def _state(practice_id: str) -> ReviewState:
    if practice_id not in list_practices():
        raise HTTPException(404, f"unknown practice {practice_id}")
    return build_state(cached_analysis(practice_id), store.decisions(practice_id))


def _span(h) -> str:
    return "Closed" if h.closed else f"{fmt_time_short(h.open)} – {fmt_time_short(h.close)}"


def config_rows(config: AgentConfig) -> list[dict]:
    """Flatten a config into display rows: group, label, value, source and the target key issues refer to."""
    rows = []

    def add(group, label, value, source, key):
        rows.append({"group": group, "label": label, "value": value, "source": source, "key": key})

    add("Practice", "Name", config.practice_name.value, config.practice_name.source, "practice_name")
    add("Practice", "Specialty", config.specialty.value, config.specialty.source, "specialty")
    if config.address:
        add("Practice", "Address", config.address.value, config.address.source, "address")
    add("Practice", "Timezone", config.timezone.value if config.timezone else "— missing —",
        config.timezone.source if config.timezone else "", "timezone")
    if config.main_phone:
        add("Practice", "Main phone", config.main_phone.value or f"{config.main_phone.raw} (invalid)",
            config.main_phone.source, "main_phone")
    add("Practice", "After hours", config.after_hours.action if config.after_hours else "— missing —",
        config.after_hours.source if config.after_hours else "", "after_hours")
    add("Practice", "Languages", ", ".join(l.value for l in config.languages),
        config.languages[-1].source if config.languages else "", "languages")
    for h in config.hours:
        add("Hours", h.day.title(), _span(h), h.source, f"hours:{h.id}")
    for h in config.holidays:
        add("Holidays", h.name or "Free text", h.date or h.raw, h.source, "holidays")
    for p in config.providers:
        add("Providers", f"{p.name}, {p.credentials}",
            "accepting new patients" if p.accepting_new_patients else "full panel", p.source, f"providers:{p.id}")
    for v in config.visit_types:
        add("Visit types", v.name, f"{v.minutes} min", v.source, f"visit_types:{v.id}")
    for r in config.escalation_rules:
        add("Escalation rules", r.symptom, r.level if r.level != "none" else "— no escalation —", r.source,
            f"escalation_rules:{r.id}")
    for t in config.transfers:
        add("Transfers", t.reason, t.phone.value or f"{t.phone.raw} (invalid)", t.source, f"transfers:{t.id}")
    for f in config.faqs:
        add("FAQs", f.question, f.answer, f.source, f"faqs:{f.id}")
    for s in config.script:
        add("Call script", s.section.title(), s.text, s.source, f"script:{s.id}")
    return rows


def _summary(state: ReviewState) -> dict:
    cfg = state.original
    return {"id": state.practice_id, "name": cfg.practice_name.value, "specialty": cfg.specialty.value,
            "status": state.status, "can_export": state.can_export, "counts": state.counts()}


@app.get("/api/practices")
def practices() -> list[dict]:
    return [_summary(_state(pid)) for pid in list_practices()]


@app.get("/api/practices/{practice_id}")
def practice(practice_id: str) -> dict:
    state = _state(practice_id)
    analysis = cached_analysis(practice_id)
    issues = [{**i.issue.model_dump(), "status": i.status, "applied_value": i.applied_value, "error": i.error}
              for i in state.items]
    return {
        **_summary(state),
        "checker": llm_model() or "mock",
        "files": {name: analysis.packet.files[name] for name in PACKET_FILES},
        "rows": config_rows(state.approved),
        "issues": issues,
    }


class Decision(BaseModel):
    action: Literal["accept", "edit", "reject"]
    value: Optional[str] = ""


@app.post("/api/practices/{practice_id}/issues/{issue_id}")
def decide(practice_id: str, issue_id: str, decision: Decision) -> dict:
    state = _state(practice_id)
    item = next((i for i in state.items if i.issue.id == issue_id), None)
    if item is None:
        raise HTTPException(404, f"unknown issue {issue_id}")
    if decision.action == "accept" and not item.issue.repair.value and item.issue.type != "unknown_provider":
        raise HTTPException(422, "There is no proposed value to accept; edit it instead.")
    store.decide(practice_id, issue_id, decision.action, (decision.value or "").strip())
    return practice(practice_id)


@app.post("/api/practices/{practice_id}/reset")
def reset(practice_id: str) -> dict:
    _state(practice_id)
    store.reset(practice_id)
    return practice(practice_id)


@app.get("/api/practices/{practice_id}/smoke")
def smoke(practice_id: str) -> dict:
    state = _state(practice_id)
    results = run_smoke(state.approved, load_smoke_tests(practice_id))
    return {"results": results, "passed": sum(r["passed"] for r in results), "total": len(results)}


@app.get("/api/practices/{practice_id}/export")
def export(practice_id: str) -> Response:
    state = _state(practice_id)
    if not state.can_export:
        names = ", ".join(i.issue.title.lower() for i in state.blocking)
        raise HTTPException(409, f"Export is blocked by {len(state.blocking)} open high-severity issue(s): {names}.")
    body = json.dumps(state.approved.model_dump(), indent=2)
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{practice_id}_agent_config.json"'})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


def _free_port(preferred: int, tries: int = 20) -> int:
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit(f"No free port between {preferred} and {preferred + tries - 1}; set PORT to choose one.")


def main() -> None:
    import uvicorn

    port = int(os.environ["PORT"]) if os.getenv("PORT") else _free_port(8000)
    print(f"Practice Onboarding Compiler running at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
