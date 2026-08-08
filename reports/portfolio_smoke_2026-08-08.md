# Portfolio smoke test — 2026-08-08T21:41:22+00:00

**Verdict: PASS** — 15/15 personas passed, frontend ok.

- Backend: `https://upmyrank-poc.onrender.com`
- Frontend: `https://upmyrank-poc.vercel.app`
- First `/health` (cold-start indicator): **0.38s** (warm)

## Frontend

| Route | Status | Time | Note |
|---|---|---|---|
| frontend / | ok 200 | 0.13s |  |
| frontend /auth/login | ok 200 | 0.05s |  |
| frontend /auth/signup | ok 200 | 0.05s |  |

## Personas

| # | Persona | Class | Exam | Subject | Result | Total |
|---|---|---|---|---|---|---|
| 1 | Aarav Sharma | 12th | JEE_MAINS | Physics | PASS | 40.4s |
| 2 | Diya Patel | 11th | NEET | Chemistry | PASS | 39.0s |
| 3 | Rohan Verma | dropper | JEE_ADVANCED | Maths | PASS | 31.2s |
| 4 | Ananya Iyer | 12th | JEE_MAINS | Physics | PASS | 34.1s |
| 5 | Kabir Nair | 12th | NEET | Chemistry | PASS | 44.6s |
| 6 | Meera Joshi | 11th | JEE_MAINS | Maths | PASS | 50.2s |
| 7 | Arjun Reddy | dropper | JEE_ADVANCED | Physics | PASS | 37.8s |
| 8 | Sanya Gupta | 11th | NEET | Chemistry | PASS | 70.8s |
| 9 | Vihaan Kulkarni | 12th | JEE_ADVANCED | Maths | PASS | 33.2s |
| 10 | Ishita Bose | 12th | JEE_MAINS | Maths | PASS | 42.2s |
| 11 | Aditya Menon | dropper | NEET | Chemistry | PASS | 35.0s |
| 12 | Nisha Rao | 11th | JEE_MAINS | Physics | PASS | 31.9s |
| 13 | Karthik Pillai | dropper | JEE_ADVANCED | Physics | PASS | 41.4s |
| 14 | Tanvi Desai | 12th | NEET | Chemistry | PASS | 36.1s |
| 15 | Yash Chauhan | 12th | JEE_MAINS | Maths | PASS | 42.5s |

## Latency by step

| Step | n | min | median | max |
|---|---|---|---|---|
| signup | 15 | 0.79s | 1.23s | 1.85s |
| onboarding_status | 15 | 0.40s | 0.60s | 1.09s |
| onboarding_submit | 15 | 3.96s | 5.07s | 7.10s |
| session_start | 15 | 0.64s | 0.75s | 1.14s |
| doubt_ask | 15 | 11.36s | 15.20s | 42.83s |
| doubt_followup | 15 | 8.61s | 11.62s | 24.89s |
| session_end | 15 | 1.10s | 1.48s | 3.24s |

## Cleanup

Accounts created use the `smoke-20260808-213904-NN@upmyrank.test` pattern. Purge with:

```bash
python3 scripts/diag_cleanup_test_accounts.py --dry-run
python3 scripts/diag_cleanup_test_accounts.py --execute
```