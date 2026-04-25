# UpMyRank — Multi-User Personalization Diagnostic (mu-post-v0.21)

**Generated:** 2026-04-25 04:54:22 IST
**Backend:** http://localhost:8000
**Personas:** HIGH / MEDIUM / LOW scaffolding, 20 shared prompts each = 60 responses total

## TL;DR — Is personalization firing?

**Avg response-length stdev / mean across personas:** **0.231** (threshold ≥ 0.15 = personalization observable)
**Verdict:** ✅ personalization firing

## Style-keyword totals (per persona × 20 prompts)

| Persona | example-style | formula-style | analogy-style | Expected lean |
|---|---|---|---|---|
| HIGH    | 4 | **28** | 4 | formula |
| MEDIUM  | **6** | 25 | 3 | example |
| LOW     | 15 | 23 | **13** | analogy |

_Bold = expected winner for that persona's `learning_preference`. Reads left-to-right: a well-tuned engine shows the diagonal ≥ the off-diagonal._

## Judge LLM quality per persona

| Persona | Judge rows | Avg pedagogical (0-2) | Avg factual (0-1) | Avg overall (0-1) |
|---|---|---|---|---|
| HIGH | 10 | 1.6 | 1 | 0.86 |
| MEDIUM | 11 | 1.455 | 1 | 0.823 |
| LOW | 11 | 1.636 | 1 | 0.859 |

Quality should be consistent across all three — if LOW's overall is markedly below HIGH's, the engine is giving weaker students weaker pedagogy (the opposite of the intent).

## Per-prompt divergence detail

| # | Subject | Prompt (trunc) | HIGH len | MEDIUM len | LOW len | σ/μ |
|---|---|---|---|---|---|---|
| 0 | Physics | A ball is thrown upward with 20 m/s. How high does it go? g=10. | 417 | 290 | 395 | 0.185 |
| 1 | Physics | A 5 kg block on a 30 degree frictionless incline. Find the acceleration. | 432 | 419 | 648 | 0.257 |
| 2 | Physics | State Newton's second law in one line. | 372 | 339 | 411 | 0.096 |
| 3 | Physics | Moment of inertia of a uniform rod of length L, mass M, about its center? | 329 | 406 | 448 | 0.153 |
| 4 | Physics | Electric field due to a point charge 2 microcoulombs at 10 cm. | 691 | 794 | 938 | 0.154 |
| 5 | Physics | A stone of mass 1 kg whirled in a horizontal circle of radius 0.5 m at 4 m/s. Te | 224 | 203 | 243 | 0.09 |
| 6 | Physics | Escape velocity from Earth's surface? | 2940 | 2867 | 2261 | 0.139 |
| 7 | Chemistry | Why is BF3 planar but NH3 pyramidal? | 0 | 277 | 304 | 0.869 |
| 8 | Chemistry | Calculate pH of 0.01 M HCl. | 279 | 390 | 366 | 0.169 |
| 9 | Chemistry | Difference between SN1 and SN2 with examples. | 409 | 363 | 411 | 0.069 |
| 10 | Chemistry | Half-life of first-order reaction with k=0.1 /min? | 525 | 540 | 517 | 0.022 |
| 11 | Chemistry | IUPAC of [Co(NH3)4Cl2]Cl? | 176 | 168 | 233 | 0.184 |
| 12 | Chemistry | 5 g NaCl (M=58.5) in 500 mL water — molarity? | 1823 | 1500 | 1815 | 0.108 |
| 13 | Maths | If sin(theta)=3/5 and theta is acute, find cos(2*theta). | 199 | 453 | 405 | 0.383 |
| 14 | Maths | Evaluate lim x->0 of sin(3x)/x. | 231 | 266 | 576 | 0.531 |
| 15 | Maths | Derivative of x^3 * ln(x)? | 189 | 227 | 400 | 0.413 |
| 16 | Maths | Evaluate integral of x*e^x dx. | 388 | 488 | 690 | 0.295 |
| 17 | Maths | Determinant of [[2,3],[1,4]]? | 314 | 358 | 368 | 0.083 |
| 18 | Maths | P(sum=7) for two fair dice? | 390 | 474 | 507 | 0.132 |
| 19 | Maths | If z = 3 + 4i, find |z| and arg(z). | 300 | 272 | 449 | 0.28 |
