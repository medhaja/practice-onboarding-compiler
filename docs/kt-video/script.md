# KT video script: practice-onboarding-compiler

Decisions applied (from the outline's open questions, defaulted because no answer was given):
- The video covers the core as it exists today. "How to run" shows the generator and the test suite; the review
  UI, repairer, smoke test and eval are presented as next steps, drawn dashed.
- `onboarding/semantic.py` (not yet committed) is covered as the newest piece.
- The 30-of-30 result is mentioned, labelled as measured on synthetic data with no eval script yet.

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
answer that contradicts the call script. That is the only place a language model is allowed. Everything ends up as
a list of issues. The later stages, repair, review, smoke test and export, are designed in the P-R-D but not built
yet.

**On screen**
- Boxes appear left to right: `packet files` → `compile_packet` → `AgentConfig` → `run_rules` + `semantic_check` → `Issue[]`.
- Color meaning: blue = packet data, green = compiled config, amber = issues, violet = optional model.
- At "five packet files": five file chips stack inside the packet box (hours.txt, providers.csv, call_script.md, faq.md, protocols.md).
- At "nine deterministic rules": the run_rules box shows a "9" badge.
- At "only place a language model is allowed": the semantic_check box gets a violet "optional model" tag.
- At "designed ... but not built yet": dashed grey boxes appear to the right: Repair → Review → Smoke test → Export, label "planned".

**Sources**
- Plain code vs model split: PRD.md:86
- Five packet files: onboarding/compiler.py:19
- compile_packet returns AgentConfig: onboarding/compiler.py:76, 170
- Nine rules: onboarding/validator.py:215-217
- Semantic check, FAQ vs script: onboarding/semantic.py:1-8
- Planned stages: PRD.md:81-83, 119-124 (no corresponding modules in onboarding/)

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
- Then code focus: `onboarding/semantic.py` lines 138–149; highlight 140–142 at "the default", 145–149 at "falls back".

**Sources**
- Two backends, same Issue shape: onboarding/semantic.py:1-8
- Model only when LLM_MODEL set and litellm importable: onboarding/semantic.py:99-108
- JSON validated, unknown ids rejected: onboarding/semantic.py:120-129
- Fallback on validation or call failure: onboarding/semantic.py:143-149
- Mock runs whenever no model is set (LLM_MODEL unset or litellm missing): onboarding/semantic.py:99-108, 140-142
- litellm is an optional dependency: requirements-llm.txt:1-2

---

## Scene 7 — Running it, gotchas and next steps  (chapter "07 / Run it & limits")

**Narration**

To run it today, install the requirements, run the generator, and run pie-test. The thirty-nine tests include one
per rule, and a golden konfig for the clean practice. In mock mode, on this synthetic data, the checks find all
thirty planted defects with no false alarms. But there's no ee-val script yet, and synthetic defects are easier
than real ones. Other limits: the packet format is a guess, the red-flag lists need a physician's review, and
escalation fixes are flagged to always need a person. Next come repair, review, the smoke test and the ee-val.

**On screen**
- Terminal card (monospace):
  ```
  pip install -r requirements.txt
  python -m onboarding.generator
  pytest
  → 39 passed
  ```
- At "all thirty planted defects": a stat chip "30 / 30 found · 0 false alarms" with a small label "synthetic data · mock mode · no eval script yet".
- At "A few honest limits": three gotcha rows with amber markers:
  - Packet format is a guess
  - Red-flag lists are placeholders — need physician review (`taxonomy.py:43`)
  - Escalation fixes flagged to always need a person (`always_human`)
- At "Next comes": dashed roadmap boxes: Repair → Review UI → Smoke test → Eval.

**Sources**
- Generator command: onboarding/generator.py:8, 477-488
- Requirements file: requirements.txt
- 39 tests pass: `pytest -q` output, 39 passed
- One test per rule: tests/test_rules.py:1
- Golden config for clean practice: tests/test_compiler.py:34-36; tests/golden/p06_agent_config.json
- 30/30, 0 false positives: ad-hoc run of run_rules + semantic_check(mode="mock") vs defects.json for p01–p06 (no eval script in repo)
- Synthetic defects easier: PRD.md:111
- Packet format is a guess: PRD.md:107
- Red-flag placeholders: onboarding/taxonomy.py:43; PRD.md:108
- Escalation repairs flagged always_human (a flag only; no repair step consumes it yet): onboarding/taxonomy.py:20-21, 29-32
- Remaining build steps: PRD.md:119-124

---

## Scene 8 — Recap  (chapter "08 / Recap")

**Narration**

So, to recap. The compiler is deterministic, and every value points back to a file and a line. Nine rules and one
semantic check turn mistakes into issues with evidence. A model is optional, validated, and never required. And
the sample data carries its own answer key, so the checker can be scored.

**On screen**
- Four takeaways appear one per sentence:
  1. Deterministic compile, `file:line` on every value
  2. 9 rules + 1 semantic check → issues with evidence
  3. Model optional, validated, never required
  4. Synthetic data with an answer key
- Footer: "Independent prototype built from public information and synthetic data. Not affiliated with Asha Health."

**Sources**
- Deterministic compiler: onboarding/compiler.py:3-5
- Provenance on every item: onboarding/schema.py:3-5
- Nine rules: onboarding/validator.py:215-217; semantic check: onboarding/semantic.py:138
- Optional model with fallback: onboarding/semantic.py:99-108, 138-149
- Answer key: onboarding/generator.py:4-5

---

## Scene 9 — Thank you  (chapter "09 / Thank you", hold 3)

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
| 2 | 75 |
| 3 | 63 |
| 4 | 75 |
| 5 | 74 |
| 6 | 66 |
| 7 | 95 |
| 8 | 53 |
| 9 | 4 |
| **Total** | **578** |

Measured from the generated audio (timing.json); see the total there.
