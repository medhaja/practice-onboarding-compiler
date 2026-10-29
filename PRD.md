# Practice Onboarding Compiler: from intake packet to reviewed agent config

**One-liner:** Drop in a practice's intake documents. Fixed rules build an agent configuration, a checker flags problems and suggests repairs, and a person reviews only the exceptions before export.

## Problem (outside-in)

From the outside, Asha's bottleneck looks like going live, not selling. The YC posts say "We can't keep up with sales, and we have contracted ARR piling up" and "more demand than we can onboard," and they call engineering "the #1 lever" ([job](https://www.ycombinator.com/companies/asha-health/jobs/Qd1IZWf-head-of-product-ai), [company](https://www.ycombinator.com/companies/asha-health)). The [partner terms](https://www.asha.health/partners-tos) mention a separate agreement and BAA for each End Client, EHR/PMS integration fees, custom development fees and a reseller channel. The [launch post](https://www.ycombinator.com/launches/MEh-asha-health-launch-your-ai-clinic) describes practices that configure AI clinics for internal medicine, cardiology, pulmonology and urgent care.

My guess is that every practice needs someone to turn its scripts, hours, provider lists and protocols into agent settings by hand. If so, revenue can only grow as fast as about five engineers can do that work. I don't know how Asha onboards practices today. This prototype is a guess to test with the CTO.

All of this is independent work. It uses only public information and synthetic data. It assumes no access to Asha's systems, data or users.

## Users and the job to be done

- **Onboarding engineer or ops person:** "Get this practice's agent configured correctly today, and only make me look at what's actually unclear."
- **Practice admin (later):** "Confirm the agent says what our front desk would say."

## Goals / Non-goals

**Goals**
- Show the pattern from my Bizmetric ADF-to-PySpark accelerator, applied to practice setup: deterministic translation, then validation, then automatic repair. At Bizmetric that pattern cut manual effort by 90%.
- Bring human review down to a short list of exceptions.
- Measure the checker against defects with known answers.

**Non-goals**
- Real EHR/PMS integration, voice, PHI or production security.

## Prototype scope

The repo will contain:
- A synthetic packet generator with a ground-truth manifest of the defects it plants.
- A compiler that turns a packet into `agent_config.json` (hours, providers, visit types, FAQs, escalation rules).
- A validator with deterministic rules plus an optional LLM semantic check.
- A repair step that proposes fixes, each with its source citation.
- A review UI, then export.
- A scripted smoke test that runs sample patient messages against the approved config.
- An evaluation script.

## Functional requirements

1. FR1: Load any practice packet from `data/practices/<id>/`.
2. FR2: The compiler produces a config that passes the JSON schema. Every field records where it came from (`file:line`).
3. FR3: Deterministic rules flag at least these: hours that conflict across files, a provider who is referenced but not on the roster, a missing after-hours path, a red-flag symptom with no escalation, an invalid phone number, duplicate visit types and a missing timezone.
4. FR4: The semantic checker flags contradictions between the FAQ and the call script. It runs through LiteLLM if an API key is set. Otherwise a deterministic mock returns the same output shape.
5. FR5: Each issue has a severity, evidence and a proposed repair. Repairs below a set confidence level always go to a human.
6. FR6: The reviewer can accept, edit or reject each exception. Export is blocked while any high-severity issue is still open.
7. FR7: The smoke test runs 10 scripted messages per practice and reports the routed intent and any escalation against expected values.
8. FR8: `make eval` prints detection precision and recall, repair accuracy and the share of fields auto-approved, across all practices.
9. FR9: The app runs with no keys and no network.

## Demo UI

A founder can click through it in about two minutes.

1. **Practices:** six cards showing specialty, status (draft / needs review / ready) and the number of open exceptions.
2. **Packet → Config:** the source files on the left. The generated config on the right. Clicking a field highlights its source line.
3. **Exceptions:** only the flagged items. Each shows evidence, the proposed fix, and buttons to accept, edit or reject. A counter reads, for example, "41 fields auto-approved, 4 need you."
4. **Smoke test:** a table of message, expected route, actual route, pass/fail. Then an "Export config" button.

## Data

Six synthetic practices: two internal medicine, one cardiology, one pulmonology, one urgent care and one mixed. Each packet has:
- `hours.txt`, `providers.csv` (3–12 rows), `call_script.md`, `faq.md`, `protocols.md` (5–15 red-flag rules)
- `defects.json` (ground truth)

Each practice gets 3–8 planted defects, about 30 in total. Edge cases:
- Saturday hours that conflict between files
- A provider who left but is still named in the script
- Holiday closures written as free text
- A Spanish-language line
- A "chest pain" rule missing from cardiology
- A phone number written as `(555) 01-23`
- "New patient" and "New Pt Visit" as duplicate visit types
- One clean practice, to test false positives

All names and numbers are fake.

## Architecture

```
packet files → Parser → Compiler (rules) → Config + provenance
            → Validator (rules → optional LLM) → Repairer → Review queue
            → Approved config → Smoke-test router → Export
```

Plain code handles parsing, schema mapping, cross-file consistency and routing, because those need to be exact and repeatable. The LLM is used only where text meaning matters: spotting that an FAQ answer contradicts the script, and drafting repair wording. Its output is checked against the schema. If it fails the check, the item goes to a human instead of being auto-applied. The mock checker uses keyword and pattern rules, so the demo always works.

## Tech choices

- **Python + FastAPI backend, React (Vite) frontend.** This is my strongest full-stack combination. I used it for my resume RAG chatbot and exam evaluation projects. The role also asks for strong UX, so I want a real UI rather than a notebook.
- **LiteLLM** for optional model calls, so Claude and OpenAI models can be swapped freely. I built LiteLLM routing at Bizmetric.
- **Pydantic** for the config schema.
- **pytest** for tests.
- **SQLite** for review state.
- **`make demo`** builds the frontend and serves everything from one uvicorn process.

## How we'd know it works

- **Checker quality:** recall of at least 0.9 and precision of at least 0.8 against `defects.json` in mock mode. These are targets, not results. If an LLM is enabled, its numbers are reported separately, so we can see whether it actually helps.
- **Repair accuracy:** the share of accepted repairs that match the ground-truth fix.
- **Review load:** the share of fields auto-approved, and the number of exceptions per practice.
- **Safety:** zero false negatives on red-flag escalation defects. The test fails otherwise.
- **Tests:** unit tests per rule, a golden config for the clean practice, and the smoke-test pass rate.

## Risks and open questions

- My packet format is a guess. I don't know what material practices actually hand over, or which config fields Asha's agents use.
- I have not worked in US healthcare. The clinical red-flag rules here are placeholders and need physician review.
- Auto-repair in a clinical setting is risky. Escalation logic should probably never be auto-applied.
- Is setup actually the bottleneck, or is it EHR integration? I'd want to ask the CTO.
- Synthetic defects are easier to catch than real ones, so these metrics will be optimistic.

## Build plan

1. Write the Pydantic config schema and the defect taxonomy.
2. Write the synthetic packet generator with a seed. Write `defects.json`.
3. Build the parser and the compiler with provenance.
4. Add the deterministic validator rules, with a unit test for each.
5. Add the mock semantic checker, then the optional LiteLLM path.
6. Build the repairer, confidence gating and review state in SQLite.
7. Add FastAPI endpoints.
8. Build the four React screens.
9. Add the smoke-test router and the 10 scripted messages per practice.
10. Add `make eval`, `make demo` and a README with screenshots and the honest limits.

## Out of scope for the prototype

- Real practice data, PHI, a BAA or HIPAA controls
- EHR/PMS connectors
- Voice or SMS
- Multi-tenant auth
- Deployment
- Fine-tuning or distilling the checker
- A self-serve portal for practice admins

---
*Medhaja H L, Bengaluru. Remote India works for me, so no visa is needed for this role. [GitHub](https://github.com/medhaja) · [Portfolio](https://medhaja.me)*
