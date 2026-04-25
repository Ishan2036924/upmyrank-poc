# UpMyRank — Diagnostic-100 Quality Report (diag-post-v0.21)

**Generated:** 2026-04-25 05:40:56 IST
**Backend:** http://localhost:8000
**Persona:** Diag Persona (email `diag-diag-post-v0.21-9cb136@upmyrank.test`, student `f8e9529b`)
**Prompts run:** 100 across 68 flows, 9 scenario classes.

---

## TL;DR

| Pillar | Headline metric | Value |
|---|---|---|
| **1. Quality communication** | Socratic adherence (ped ≥ 1) | 97.1% (68 judge rows) |
| **2. Knowledge Genome** | Mastery rows written / blocks ended | 0 / 68 (0.0%) |
| **3. Personalized response** | Response length stdev / avg | 0.444 |
| **4. Easy learning** | Hint ladder monotonic + P95 latency | ✅ / 39191 ms |

---

## Pillar 1 — Quality communication / response

Backed by `judge_evaluations` (Judge LLM 4-dim, fired async on every response) + `conversation_turn_quality` (per-turn).

- `socratic_adherence_pct_peda_ge_1`: **97.1**
- `avg_pedagogical_0_2`: **1.824**
- `avg_factual_0_1`: **1**
- `avg_context_rel_0_1`: **0.824**
- `avg_hint_app_0_1`: **0.971**
- `avg_overall_0_1`: **0.934**
- `n_judge_rows`: **68**
- `ctq_validation_avg`: **1.611**
- `ctq_appropriateness_avg`: **1.611**
- `ctq_single_question_pct`: **100.0**

## Pillar 2 — Knowledge Genome correctness

Did EMA actually fire? Is attempt_count non-zero where blocks ended? This is the direct regression guard for v0.20.5 autoclose-idle.

- `mastery_rows_written`: **0**
- `blocks_opened`: **68**
- `blocks_resolved`: **0**
- `blocks_ended`: **68**
- `genome_update_rate_pct`: **0.0**
- `n_concepts_touched`: **0**

## Pillar 3 — Personalized response

Heuristic — a personalised engine should produce responses with varied length/structure across different contexts (easy topic vs hard topic, subject_doubt vs misconception vs forced-attempt). Low variance = one-size-fits-all.

- `response_len_avg`: **428.96**
- `response_len_stdev`: **190.6**
- `len_stdev_over_avg`: **0.444**
- `note`: **Heuristic: higher stdev/avg ratio = responses varied in structure/length per context (signal, not proof).**

## Pillar 4 — Easy learning

- `hint_ladder_progression_monotonic`: **✅**
- `median_latency_ms`: **31689**
- `p95_latency_ms`: **39191**
- `forced_attempt_triggered_count`: **2**
- `full_solution_triggered_count`: **0**

---

## Scenario-class rollups

| Class | Prompts | HTTP OK | Intents | Avg latency (ms) |
|---|---|---|---|---|
| canonical | 30 | 100.0% | {'subject_doubt': 30} | 33612.633 |
| followup | 15 | 100.0% | {'subject_doubt': 5, 'continuation': 10} | 26327.267 |
| sudden_pivot | 12 | 100.0% | {'subject_doubt': 8, 'continuation': 3, 'out_of_scope': 1} | 29643.333 |
| short_pivot | 6 | 100.0% | {'subject_doubt': 5, 'continuation': 1} | 33876.667 |
| misconception | 10 | 100.0% | {'subject_doubt': 10} | 33714.9 |
| emotional | 8 | 100.0% | {'subject_doubt': 4, 'emotional': 4} | 18892.875 |
| out_of_scope | 6 | 100.0% | {'greeting': 1, 'conversational': 1, 'subject_doubt': 1, 'out_of_scope': 3} | 8742.667 |
| vague | 5 | 100.0% | {'conversational': 1, 'subject_doubt': 3, 'out_of_scope': 1} | 23274.8 |
| hint_ladder | 8 | 100.0% | {'subject_doubt': 2, 'null': 6} | 21790.875 |

## Expected-intent match rate (per class)

| Class | Checked | Matched | Match % |
|---|---|---|---|
| canonical | 30 | 30 | 100.0% |
| followup | 15 | 15 | 100.0% |
| sudden_pivot | 12 | 8 | 66.7% |
| short_pivot | 6 | 5 | 83.3% |
| misconception | 10 | 10 | 100.0% |
| emotional | 8 | 8 | 100.0% |
| out_of_scope | 6 | 4 | 66.7% |
| vague | 1 | 1 | 100.0% |

## Scenario-specific checks

- **Topic-shift (new block opens on pivot):** 58.3% (12 checks)
- **Misconception detection rate:** 0.0% (expected > 60% — library-matching is literal)
- **Emotional → COUNSELOR mode:** 0.0%
- **Vague-prompt robustness (HTTP OK):** 100.0%
- **Out-of-scope routing correctness:** 83.3%
- **Follow-up → continuation intent:** 100.0%

## Errors

None — all 100 prompts completed HTTP 200.

## Render logs (filtered)

- ERROR/CRITICAL lines: 0
- topic_shift hits:     0
- autoclose hits:       0

## Prioritized bug / regression list

| Priority | Bug | Fix direction |
|---|---|---|
| **P0** | Genome not writing despite ended blocks | 68 blocks ended but 0 mastery rows. Inspect app/api/doubt.py _genome_update_task. |
| **P0** | Topic-shift detection regression | 58.3% of 12 pivots opened a new doubt_block (expected ≥80%). Inspect _detect_topic_shift + _looks_like_new_question in app/api/doubt.py. |
| **P1** | Misconception library under-firing | 0.0% of 10 misconception prompts matched. Review app/services/doubt/misconceptions.py MISCONCEPTION_LIBRARY patterns. |
| **P2** | COUNSELOR switch unreliable | Emotional cue → COUNSELOR fired 0.0% of 4 emotional turns. |
| **P1** | Latency P95 > 15s | p95 = 39191 ms. Cold-start (Render free tier) or agentic-RAG loop pathology. |

---

## Raw counts

- Judge rows: 68
- session_events rows (all-time, persona): 0
- concept_mastery rows: 0
- doubt_blocks opened: 68, resolved: 0, ended: 68