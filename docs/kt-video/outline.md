# KT video outline: practice-onboarding-compiler

## Summary

Practice Onboarding Compiler is a prototype that turns a medical practice's intake packet (office hours, provider
roster, call script, FAQ and red-flag protocols) into a structured agent configuration, then checks that
configuration for the mistakes a person would otherwise catch by hand. The compiler is deterministic and records
`file:line` provenance for every value. Nine deterministic rules and a semantic FAQ-vs-script check produce issues
with a severity and evidence, so a reviewer only looks at exceptions. It is for an onboarding engineer or ops
person setting up a new practice. It runs offline on six synthetic practices with 30 planted, ground-truth defects.

**Build state today (important):** the repo implements build-plan steps 1–4 of PRD.md (schema, taxonomy,
generator, compiler, rules, tests) plus an uncommitted `onboarding/semantic.py` (step 5). The repairer, review
state, FastAPI endpoints, React UI, smoke-test router, `make eval`, `make demo` and README do not exist yet.

## Scenes (target ~3:30)

| # | Title | One idea | Visual | Files |
|---|-------|----------|--------|-------|
| 1 | The onboarding bottleneck | If each practice is configured by hand, revenue grows only as fast as engineers can configure; this prototype tests that guess. | Stack of contracted practices queueing at a narrow "manual setup" funnel; PRD quotes as small cards with source labels. | PRD.md:5-11 |
| 2 | Architecture | Plain code where exactness matters, a model only where meaning matters. Packet → compiler → validator → issues (built), then repair → review → smoke test → export (planned, drawn dashed). | Architecture diagram; arrows animate in data order; planned stages greyed/dashed. | PRD.md:78-86, compiler.py, validator.py, semantic.py |
| 3 | The packet and the generator | Six seeded synthetic practices; each packet ships a `defects.json` answer key so the checker can be scored. | Directory map of `data/practices/p03/` with one-line purposes; defects.json card. | generator.py:1-9, 465, PRACTICES; data/practices/p03/* ; test_generator.py |
| 4 | Trace: compiling p03 (Harborview Heart Clinic) | `load_packet` → `compile_packet`: each line becomes a typed field with `source="hours.txt:12"`. | Request trace: the line "Friday: 8:00 AM - 3:00 PM" travels through `DAY_LINE_RE` → `parse_time` → `DayHours(open="08:00", close="15:00", source="hours.txt:12")`. Then code focus on compiler.py:83-93. | compiler.py:38-46, 76-93; schema.py:34-53 |
| 5 | Trace continued: validating p03 | `run_rules` runs nine rules; `rule_hours_conflict` compares what the script *says* with the official hours and cites both lines. p03 yields 7 issues matching its 7 planted defects. | Code focus validator.py:88-111; then an issue card with evidence lines; then the 7-issue list with severities. | validator.py:88-111, 215-224; taxonomy.py:24-39 |
| 6 | The semantic check and its fallback | FAQ-vs-script contradictions: LiteLLM if `LLM_MODEL` is set, otherwise a keyword mock with the same output shape; malformed model output falls back to the mock. | With/without split: "LLM_MODEL set" vs "no key"; both arrive at the same Issue card. Code focus semantic.py:138-149. | semantic.py |
| 7 | Running it, gotchas and next steps | How to run today; honest limits: packet format is a guess, red-flag lists are placeholders needing physician review, escalation repairs are always human, synthetic defects are easier than real ones; next: repairer, review UI, smoke router, eval. | Terminal card with commands; gotcha list; roadmap of remaining PRD build steps. | taxonomy.py:20-21, 43; PRD.md:105-124 |
| 8 | Recap | 5 takeaways. | Recap list. | — |

## Open questions

1. **The demo doesn't exist yet.** "How to run the demo" can't be covered truthfully: there is no UI, no `make demo`,
   no README. Options: (a) pause the video until the app is finished, (b) make the video about the current core
   (compiler + validator) and show "run it" as `python -m onboarding.generator` + `pytest` with the UI as a next
   step, (c) script the planned UI as "planned", clearly labelled. I recommend (a) if the build will continue soon,
   otherwise (b).
2. `onboarding/semantic.py` is untracked (uncommitted). Should the video cover it as if it's part of the repo?
3. An ad-hoc run I did shows the mock checker finds all 30 planted defects with 0 false positives across the six
   practices. There's no eval script in the repo yet, so this can't be cited from code. Mention it (flagged as
   "measured on synthetic data, no eval script yet") or leave it out?
