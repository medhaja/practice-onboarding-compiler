# KT video script: practice-onboarding-compiler

Scope: the video covers the repo as it is now: compiler, rules, semantic check, repairer, review state, smoke-test
router, gated export, the review UI (`make demo`) and the evaluation script (`make eval`). Scenes 1 and 3-5 are
unchanged from the first version; scenes 2 and 6 were updated, and scenes 7-10 are new.

Pronunciation respellings used in the narration: "F-A-Q" (FAQ), "Jason" (JSON), "Lite L-L-M" (LiteLLM),
"pie-test" (pytest), "pie-dantic" (Pydantic), "L-L-M" (LLM),
"Ahsha's" (Asha's), "konfig" (config), "back ends" (backends), "ee-val" (eval).

---

## Scene 1 — The onboarding bottleneck  (chapter "01 / The problem")

**Narration**

From the outside, Ahsha's bottleneck looks like going live, not selling. Public posts mention contracted revenue
piling up, and more demand than the team can onboard. My guess is that every new practice needs someone to turn
its scripts, hours, provider lists and protocols into agent settings by hand. This prototype tests that guess. It
compiles a practice's intake packet into an agent konfig, checks it, and leaves a person only the exceptions.

**On screen**
- Start: title "Practice Onboarding Compiler", subtitle "from intake packet to reviewed agent config".
- At "contracted revenue piling up": two quote cards fade in, each with a small source label (YC job post, YC company page).
- At "by hand": a row of practice cards queues at a narrow "manual setup" gate; one card passes at a time.
- At "This prototype tests that guess": the gate is replaced by a pipeline bar: packet → config → exceptions.
- Footer note throughout: "Independent prototype · public information + synthetic data".

**Sources**
- Bottleneck framing, quotes: PRD.md:7
- Hand-configuration guess, "a guess to test": PRD.md:9
- One-liner (packet → config → checker → human reviews exceptions): PRD.md:3

---

## Scene 2 — Architecture  (chapter "02 / Architecture")

**Narration**

Plain code handles anything that must be exact and repeatable. The compiler parses five packet files into a
typed konfig. The validator runs nine deterministic rules. A semantic check looks for an F-A-Q
answer that contradicts the call script. That is the only place a language model is allowed. Each issue then gets
a proposed fix. After that come review, a smoke test, and a gated export.

**On screen**
- Boxes appear left to right: `packet files` → `compile_packet` → `AgentConfig` → `run_rules` + `semantic_check` → `Issue[]`.
- Color meaning: blue = packet data, green = compiled config, amber = issues, violet = optional model.
- At "five packet files": five file chips stack inside the packet box (hours.txt, providers.csv, call_script.md, faq.md, protocols.md).
- At "nine deterministic rules": the run_rules box shows a "9" badge.
- At "only place a language model is allowed": the semantic_check box gets a violet "optional model" tag.
- At "Each issue then gets": the `list[Issue]` box appears.
- At "After that come": a second row appears below, solid boxes: `propose` (repairer) → `build_state` (review, SQLite) → `run_smoke` → `export`, labelled "then".

**Sources**
- Plain code vs model split: PRD.md:86
- Five packet files: onboarding/compiler.py:19
- compile_packet returns AgentConfig: onboarding/compiler.py:76, 170
- Nine rules: onboarding/validator.py:215-217
- Semantic check, FAQ vs script: onboarding/semantic.py:1-8
- Each issue gets a proposed fix: onboarding/pipeline.py:22-27; onboarding/repairer.py:176-177
- Review, smoke test, gated export: onboarding/review.py:1-9, 104-126; onboarding/router.py:217-224; onboarding/app.py:145-153

---

## Scene 3 — Synthetic packets with an answer key  (chapter "03 / Sample data")

**Narration**

There's no real practice data anywhere. A seeded generator writes six fake practices: internal medicine,
cardiology, pulmonology, urgent care and a multispecialty group. Each packet ships a defects file, the answer key
for the mistakes planted in it. Thirty in total, and one practice is deliberately clean, to catch false alarms. A
test regenerates everything and fails if the committed data has drifted.

**On screen**
- Directory map of `data/practices/p03/` with one-line purposes:
  - hours.txt — hours, timezone, phones, holidays
  - providers.csv — roster
  - call_script.md — what the agent says
  - faq.md — answers to common questions
  - protocols.md — red-flag symptoms and escalation
  - defects.json — ground truth (highlighted amber)
- At "six fake practices": six small cards p01–p06 with specialty labels.
- At "one practice is deliberately clean": p06 card gets a "0 defects" badge.
- At "a test regenerates everything": a chip `test_regenerating_matches_committed_data` with a check mark.

**Sources**
- Seeded generator, all invented data: onboarding/generator.py:1-9, 465-466
- Six practices and specialties: onboarding/generator.py:45 (PRACTICES), 167; PRD.md:62
- Packet files and defects.json: onboarding/compiler.py:19; data/practices/p03/
- 30 defects total, one clean practice: tests/test_generator.py:15-22
- Regeneration test: tests/test_generator.py:6-11

---

## Scene 4 — Trace: compiling practice three  (chapter "04 / Compile")

**Narration**

Let's follow one practice, Harborview Heart Clinic, a cardiology packet. Load packet reads the five files as
lines, and compile packet walks them. Line twelve of the hours file says Friday, eight to three. A pattern match
finds the day, parse time converts the times to twenty-four hour form, and the result is a day-hours object with
the source hours dot T-X-T, colon twelve. Pie-dantic requires a source on every item, and checks its format.

**On screen**
- Trace token: the text `Friday: 8:00 AM - 3:00 PM` (label `hours.txt:12`) travels through three labelled stations:
  `load_packet` → `DAY_LINE_RE` → `parse_time` → lands as a green card
  `DayHours(day="friday", open="08:00", close="15:00", source="hours.txt:12")`.
- Then code focus: `onboarding/compiler.py` lines 83–93; highlight 84 at "pattern match", 91–92 at "parse time", 92 `source=src` at "source recorded".
- At "pie-dantic requires": small code card `onboarding/schema.py` lines 27 and 34–35, highlight `SOURCE_PATTERN`.

**Sources**
- load_packet reads files as lines: onboarding/compiler.py:38-46
- hours.txt line 12 content: data/practices/p03/hours.txt:12
- Day regex and parse_time: onboarding/compiler.py:22-23, 53-64, 84-92
- Source recorded as "hours.txt:12": onboarding/compiler.py:71-73, 83; tests/test_compiler.py:39-41 (same mechanism for p01)
- Source required on every item, format checked (file:line, or "review" for reviewer edits): onboarding/schema.py:3-5, 27, 34-35; tests/test_schema.py:20-24

---

## Scene 5 — Trace: checking practice three  (chapter "05 / Validate")

**Narration**

Now the compiled konfig goes to run rules. Take the hours conflict rule. It scans every line the agent might say,
script lines and F-A-Q answers, for phrases like "our Friday hours are". Line nine of the script says eight to
five. The official hours say eight to three. So it raises a high-severity issue, and cites both lines as evidence.
For this practice the checks raise seven issues, matching its seven planted defects.

**On screen**
- Code focus: `onboarding/validator.py` lines 88–101; highlight 91 at "every line the agent might say", 92–93 at "our Friday hours are", 100–101 at "raises".
- At "cites both lines": an amber issue card:
  `hours_conflict · friday · high` with evidence rows `hours.txt:12  Friday: 8:00 AM - 3:00 PM` and `call_script.md:9  Our Friday hours are 8 AM to 5 PM.`
- At "seven issues": a list of seven amber rows with severity chips:
  hours conflict (high), missing chest-pain rule (high), invalid phone (high), unknown provider Whitcombe (medium),
  duplicate visit type (medium), F-A-Q contradiction (medium), holidays as free text (low). A "7 / 7 planted" badge.

**Sources**
- run_rules over RULES: onboarding/validator.py:215-224
- Spoken lines = script + FAQ answers: onboarding/validator.py:61-66
- Hours phrase regex: onboarding/validator.py:71-74
- Conflict logic and evidence: onboarding/validator.py:88-111
- Severity from taxonomy (hours_conflict = high): onboarding/taxonomy.py:27
- p03 lines: data/practices/p03/hours.txt:12, data/practices/p03/call_script.md:9
- Seven issues = seven planted defects: data/practices/p03/defects.json; verified by running run_rules + semantic_check(mode="mock") on p03

---

## Scene 6 — The semantic check and its fallback  (chapter "06 / Semantic check")

**Narration**

The contradiction check has two back ends with the same output. If an L-L-M model is configured and Lite L-L-M is
installed, it asks the model for contradictions as Jason. That reply is validated, and every cited line must
exist. If anything fails, it falls back to a keyword mock. The mock runs whenever no model is set, so nothing
needs a key or a network.

**On screen**
- Split screen. Left lane "model configured" (violet): `LLM_MODEL=<model-name>` → `llm_check` → `LLMResult.model_validate`.
  Right lane "no key" (grey): `mock_check` → keyword stance patterns.
- Both lanes converge on the same amber Issue card.
- At "every cited line must exist": a red "unknown id" stamp on the left lane redirects its arrow into `mock_check`.
- Then code focus: `onboarding/semantic.py` lines 148–159; highlight 153–159 at "falls back", 150–152 at "runs whenever".

**Sources**
- Two backends, same Issue shape: onboarding/semantic.py:1-8
- Model only when LLM_MODEL set and litellm importable: onboarding/semantic.py:109-118
- JSON validated, unknown ids rejected: onboarding/semantic.py:130-139
- Fallback on validation or call failure: onboarding/semantic.py:153-159
- Mock runs whenever no model is set (LLM_MODEL unset or litellm missing): onboarding/semantic.py:109-118, 150-152
- litellm is an optional dependency: requirements-llm.txt:1-2

---

## Scene 7 — Repair with confidence gating  (chapter "07 / Repair")

**Narration**

Next, the repairer proposes a fix for every issue, with a confidence score and the lines it was drawn from. A fix
is applied automatically only when confidence is at least zero point eight, and never for escalation. For
Harborview, the Friday hours and the duplicate visit type are fixed automatically. The missing chest-pain rule
scores exactly zero point eight, but it's escalation, so it waits for a person, along with four others.

**On screen**
- Code focus: `onboarding/repairer.py` lines 18–25; highlight 18 and 23 at "at least zero point eight", 23 again at "never for escalation".
- At "For Harborview": a table of p03's seven issues, each with a confidence bar and a route chip:
  hours conflict 0.90 auto · duplicate visit type 0.90 auto · chest-pain rule 0.80 person (escalation) ·
  FAQ contradiction 0.60 person · holidays 0.60 person · unknown provider 0.30 person · invalid phone 0.20 person.
- At "fixed automatically": the two auto rows turn green. At "it's escalation": the chest-pain row gets an "escalation" tag;
  at "four others": a "5 need a person" badge.

**Sources**
- Proposal with confidence and cited source lines: onboarding/repairer.py:1-5, 28-30
- Auto only at confidence >= 0.8 and never escalation: onboarding/repairer.py:18, 22-25; onboarding/taxonomy.py:29-32
- p03 confidences: hours 0.9 (repairer.py:93-97), duplicate of the same length 0.9 (repairer.py:100-108), chest pain 0.8
  (repairer.py:140-146), FAQ 0.6 (repairer.py:149-153), holidays with a partial day 0.6 (repairer.py:80-90), unknown provider
  0.3 (repairer.py:156-159), phone with 3 candidate numbers 0.2 (repairer.py:57-66)
- p03 result (2 auto, 5 to a person): build_state(analyze("p03"), {}) run on the current code; README.md:26 ("54 fields auto-approved, 5 need you")

---

## Scene 8 — Review, smoke test and gated export  (chapter "08 / Review & export")

**Narration**

Reviewer decisions, accept, edit or reject, are stored in SQLite, and replayed on top of the compiled konfig. Then a
smoke test sends ten scripted patient messages through a keyword router that reads only that konfig. Harborview
passes nine. The chest-pain message finds no rule, so nothing escalates. And export stays blocked while any
high-severity issue is open. Here, that's the chest-pain rule and a broken phone number.

**On screen**
- Top row: chips `accept` `edit` `reject` → `decisions` table card (`var/review.sqlite`) → `build_state` → green "approved config" card.
- At "smoke test": a table of five of the ten p03 messages with expected vs actual route; all pass except
  "I'm having chest pain and it won't go away." expected `red_flag · emergency`, actual `unknown · none` (red). Counter "9 / 10 passed".
- At "export stays blocked": a disabled "Export config" button and the API response
  `409 · Export is blocked by 2 open high-severity issue(s): invalid phone number, required red-flag rule missing.`

**Sources**
- Decisions in SQLite, accept/edit/reject: onboarding/review.py:25-47
- Replayed on the compiled config (auto repairs and decisions applied in order): onboarding/review.py:104-126
- Ten scripted messages per practice: tests/test_generator.py:31; data/practices/p03/smoke_tests.json
- Keyword router reads only the config: onboarding/router.py:1-4, 166-183
- p03 smoke result 9/10, chest pain routes to "unknown": run_smoke(build_state(analyze("p03"), {}).approved, …) on the current code
- Export blocked while a high-severity issue is open: onboarding/review.py:79-85; onboarding/app.py:145-150; tests/test_api.py:36-37
- p03 blocking issues = invalid phone + missing chest-pain rule (both high): onboarding/taxonomy.py:32-33; build_state run as above

---

## Scene 9 — Run the demo  (chapter "09 / Run the demo")

**Narration**

To try it, run make demo, and open localhost, port eight thousand. It needs no keys, no Node, and no network.
There are four screens. Practices, with status and open exceptions. Packet to konfig, where clicking a field
highlights its source line. Exceptions, with evidence, the proposed fix, and its confidence. And the smoke test,
with the export button.

**On screen**
- Terminal card: `$ make demo` then `Practice Onboarding Compiler running at http://127.0.0.1:8000`.
- At "four screens": the four screen names listed on the left; the matching screenshot from `docs/screenshots/` shows large
  on the right and switches as each screen is named (1-practices, 2-packet-to-config, 3-exceptions, 4-smoke-test).

**Sources**
- make demo: Makefile (demo target); README.md:3-6
- Port 8000 (next free port if taken): onboarding/app.py:161-185; README.md:6
- No keys, no Node, no network: README.md:6
- Four screens and what they show: README.md:22-27; onboarding/static/index.html:174, 230, 252, 272, 312-315, 372

---

## Scene 10 — Evaluation and limits  (chapter "10 / Eval & limits")

**Narration**

Make ee-val scores everything against the answer key. In mock mode, the checks find all thirty planted defects,
with no false alarms. All twenty-four scored fixes match the known answer, and ninety-five percent of fields need
no review. Before review, fifty-seven of sixty smoke tests pass. The three failures are escalation fixes it won't
apply alone. These numbers are optimistic, because the defects and the checks were written together. Other
limits: the packet format is a guess, the red-flag lists need a physician's review, and the router matches
keywords; it isn't a live agent.

**On screen**
- Terminal card with the real `make eval` output lines, each highlighted as it's spoken: precision 1.00 (30 true, 0 false
  alarms) · recall 1.00 · repair accuracy 100% (24/24) · fields auto-approved 95% (330/346) · smoke tests, auto repairs only 57/60.
- At "optimistic": an amber note "synthetic defects · defects and checks written together".
- At "Other limits": three rows: packet format is a guess · red-flag lists need physician review (`taxonomy.py:43`) ·
  router is keywords, not a live agent (`router.py:1-4`).

**Sources**
- make eval and what it scores: onboarding/eval.py:1-4, 50-86; Makefile (eval target)
- Numbers: `python -m onboarding.eval` output on the current code (also README.md:57-66)
- Repair accuracy counts only defects with a known fix (24 of 30): onboarding/eval.py:60-63
- The three smoke failures are escalation defects (p02 stroke, p03 chest pain, p04 coughing up blood): smoke run on the current code; README.md:68
- Optimistic, defects and checks written together: README.md:68; PRD.md:111
- Packet format is a guess: README.md:91; PRD.md:107
- Red-flag placeholders: onboarding/taxonomy.py:43; README.md:93
- Router is keyword based, not a live agent: onboarding/router.py:1-4; README.md:94

---

## Scene 11 — Recap  (chapter "11 / Recap")

**Narration**

So, to recap. The compiler is deterministic, and every value points back to a file and a line. Nine rules and one
semantic check turn mistakes into issues with evidence. Confident fixes apply themselves; escalation always waits
for a person. And the answer key lets make ee-val score all of it.

**On screen**
- Four takeaways appear one per sentence:
  1. Deterministic compile, `file:line` on every value
  2. 9 rules + 1 semantic check → issues with evidence
  3. Confident fixes auto-apply; escalation waits for a person
  4. An answer key, so `make eval` can score it all
- Footer: "Independent prototype built from public information and synthetic data. Not affiliated with Asha Health."

**Sources**
- Deterministic compiler: onboarding/compiler.py:3-5
- Provenance on every item: onboarding/schema.py:3-5
- Nine rules: onboarding/validator.py:215-217; semantic check: onboarding/semantic.py:148
- Gating: onboarding/repairer.py:18-25
- Answer key and eval: onboarding/generator.py:4-5; onboarding/eval.py:1-4

---

## Scene 12 — Thank you  (chapter "12 / Thank you", hold 3)

**Narration**

Thank you for watching.

**On screen**
- Centered end card: "Thank you" (large), fading in at the start of the scene.
- At "watching": below it, "Made by Medhaja H L" in the muted body color.

**Sources**
- No factual claims.

---

## Totals

| Scene | Words |
|---|---|
| 1 | 73 |
| 2 | 67 |
| 3 | 63 |
| 4 | 75 |
| 5 | 74 |
| 6 | 66 |
| 7 | 73 |
| 8 | 68 |
| 9 | 59 |
| 10 | 94 |
| 11 | 51 |
| 12 | 4 |
| **Total** | **767** |

Measured from the generated audio (timing.json); see the total there.
