# KT video outline: practice-onboarding-compiler

## Summary

Practice Onboarding Compiler is a prototype that turns a medical practice's intake packet (office hours, provider
roster, call script, FAQ and red-flag protocols) into a structured agent configuration, then checks and repairs it so
a person only reviews the exceptions. The compiler is deterministic and records `file:line` provenance for every
value. Nine deterministic rules and a semantic FAQ-vs-script check (keyword mock, or a model through LiteLLM) produce
issues with a severity and evidence. A repairer proposes a fix for each, applies it automatically only at confidence
>= 0.8 and never for escalation, and sends the rest to a review queue stored in SQLite. A keyword smoke-test router
runs ten scripted patient messages against the approved config, and export is blocked while any high-severity issue
is open. It is for an onboarding engineer or ops person setting up a new practice; it runs offline (`make demo`) on six
synthetic practices with 30 planted, ground-truth defects, and `make eval` scores it against them.

## Scenes (~5:20)

Scenes 1 and 3–5 are unchanged from the first version. Scenes 2 and 6 were updated for the current code, and scenes
7–10 are new (they replace the earlier "Run it & limits" scene, which described these parts as not built yet).

| # | Title | One idea | Visual | Files |
|---|-------|----------|--------|-------|
| 1 | The onboarding bottleneck | If each practice is configured by hand, revenue grows only as fast as that work; this prototype tests that guess. | Practices queueing at a "manual setup" gate; PRD quotes as cards with source labels. | PRD.md:3-9 |
| 2 | Architecture | Plain code where exactness matters, a model only where meaning matters; then repair, review, smoke test and a gated export. | Architecture diagram; arrows animate in data order; second row `propose → build_state → run_smoke → export`. | compiler.py, validator.py, semantic.py, pipeline.py, review.py, router.py, app.py |
| 3 | Synthetic packets with an answer key | Six seeded synthetic practices; each packet ships `defects.json` so the checker can be scored. | Directory map of `data/practices/p03/`; six practice cards with planted-defect counts. | generator.py, test_generator.py |
| 4 | Trace: compiling p03 (Harborview Heart Clinic) | Each line becomes a typed field with `source="hours.txt:12"`. | Trace token through `load_packet → DAY_LINE_RE → parse_time → DayHours`; code focus compiler.py:83-93, schema.py:27-35. | compiler.py, schema.py |
| 5 | Trace: validating p03 | `rule_hours_conflict` cites both lines; p03 yields 7 issues matching its 7 planted defects. | Code focus validator.py:88-101; issue card; 7-issue list. | validator.py, taxonomy.py |
| 6 | The semantic check and its fallback | Model via LiteLLM when `LLM_MODEL` is set, keyword mock otherwise; same output shape; bad model output falls back. | Two lanes converging on one Issue card; code focus semantic.py:148-159. | semantic.py |
| 7 | Repair with confidence gating | Auto-apply only at >= 0.8 and never for escalation; p03: 2 auto, 5 to a person (chest pain is 0.8 but escalation). | Code focus repairer.py:18-25; p03 table with confidence bars and route chips. | repairer.py, taxonomy.py |
| 8 | Review, smoke test, gated export | Decisions in SQLite replayed on the compiled config; the router reads only that config; p03 passes 9/10; export blocked by 2 high issues. | Decision flow; smoke table with the failing chest-pain row; disabled export + 409 message. | review.py, router.py, app.py |
| 9 | Run the demo | `make demo`, port 8000, no keys/Node/network; four screens. | Terminal card; the four committed UI screenshots switching as each screen is named. | Makefile, app.py, static/index.html, README.md, docs/screenshots |
| 10 | Evaluation and limits | `make eval` numbers, why they're optimistic, and the remaining limits. | Real `make eval` output with lines highlighted as spoken; limits list. | eval.py, README.md, taxonomy.py, router.py |
| 11 | Recap | 4 takeaways. | Recap list. | — |
| 12 | Thank you | End card. | "Thank you" / "Made by Medhaja H L". | — |

## Open questions

1. The video is now about 5:20, over the original 3–4 minute target, because the repairer, review, smoke test, UI and
   eval are new. Scenes 3 and 10 are the easiest places to cut if a shorter cut is wanted.
