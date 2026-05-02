# Portfolio Analyst — Cowork Task Handoff
*Generated: April 21, 2026*

---

## Repo & Stack
- **Repo:** `Luis-GrowSolar-Personal/investment-agent`, branch: `dev`
- **Stack:** React/Vite frontend, Node/Express backend, PostgreSQL via Prisma, Clerk auth, Railway hosting
- **Key config files to read before doing anything:**
  - `CLAUDE.md` — never-do rules, architecture reminders, macOS compatibility rules
  - `DESIGN_PRINCIPLES.md` — closed architectural decisions, do not re-derive
  - `BUILD_STATE.md` — what has been built, what is next
  - `EVALUATION_PROMPT.md` — the evaluator prompt (currently v5)
  - `docs/architecture/DOMAIN.md` — investment universe, do not recommend outside it

---

## macOS Compatibility Rules (Tahoe 24.2)
- Use `python3` not `python`
- Use `pip3` or `python3 -m pip` not `pip`
- Never use `--break-system-packages`
- Shell is zsh — avoid bash-only syntax
- No `apt`, `apt-get`, or Linux package managers
- Use `brew install` if a system tool is needed

---

## Current Work Context

### What This Work Is About
The backtest runner (`analysis/backtest_runner.py`) evaluates historical earnings call
transcripts using the evaluator prompt and compares the AI's recommendations against
actual price outcomes. The goal is to optimize the evaluator prompt to maximize
signal accuracy.

### Prompt Version History
| Version | Change | ENPH | TTD | Combined |
|---------|--------|------|-----|----------|
| v1 | Original (DB baseline) | 6/9 = 67% | 2/6 = 33% | 8/15 = 53% |
| v2 | Stumble classification + mitigation capability distinction | 4/9 = 44% | 3/6 = 50% | 7/15 = 47% |
| v3 | Three-part mitigation test + recommendation decision matrix | 5/9 = 56% | 3/6 = 50% | 8/15 = 53% |
| v4 | Stumble graduation rule (1 quarter grace period) | 5/9 = 56% | 2/6 = 33% | 7/15 = 47% |
| v5 | Graduation rule clarified as lookback-only | 3/9 = 33% | 2/6 = 33% | 5/15 = 33% |

**Current file in repo: v5**
**v3 is the best-performing non-baseline version.**

### Critical Finding From Last Session
`mitigation_track_record` was flipping between `strong`, `mixed`, and `unproven` on
identical transcripts across runs with no prompt change. This was identified as model
variance caused by default temperature (1.0), not prompt logic failure.

### Fix Already Applied
`temperature=0` has been added to the API call in `analysis/backtest_runner.py` (line ~415).
Prompt versioning patch has also been applied — the runner now prints prompt version at
startup and includes `prompt_version` in every output row.

---

## Immediate Task: Variance Test

### What To Do
Three runs of the ENPH backtest have been initiated (or may still be running) from the
prior chat session. The variance files should land at:
- `analysis/data/variance_ENPH_run1.csv`
- `analysis/data/variance_ENPH_run2.csv`
- `analysis/data/variance_ENPH_run3.csv`

If these files are not present, run them:
```zsh
cd analysis && \
  python3 backtest_runner.py --ticker ENPH --save-evals && \
  mv data/backtest_2026-04-21_ENPH.csv data/variance_ENPH_run1.csv && \
  python3 backtest_runner.py --ticker ENPH --save-evals && \
  mv data/backtest_2026-04-21_ENPH.csv data/variance_ENPH_run2.csv && \
  python3 backtest_runner.py --ticker ENPH --save-evals && \
  mv data/backtest_2026-04-21_ENPH.csv data/variance_ENPH_run3.csv
```

### What To Analyze
Write `analysis/variance_check.py` that:
1. Loads all three variance CSVs
2. For each of the 9 ENPH transcripts, compares these four fields across the three runs:
   - `thesis_health`
   - `recommendation`
   - `stumble_type`
   - `mitigation_track_record`
3. Flags any field that differs across runs for the same transcript
4. Prints a summary: how many of the 36 field-transcript combinations were stable vs. variable
5. Prints the specific instabilities so Luis can review them

### Decision Tree After Variance Test

**If variance is low (fields stable across all 3 runs):**
- Temperature fix worked
- Revert prompt to v3 (best non-baseline version)
- Diagnose the two remaining problem calls specifically:
  - ENPH Q3 2023 (2023-10-26) — should be Trim, was scoring Intact on v3
  - ENPH Q1 2024 (2024-04-23) — should be Trim, still scoring Hold on v3
- Inspect eval narratives: `analysis/data/evals/ENPH_2023-10-26.txt` and `ENPH_2024-04-23.txt`
- Write v6 only to fix these two specific calls without regressing others

**If variance is still high (fields unstable despite temperature=0):**
- Options in priority order:
  A) Run each transcript N=3 and take majority vote on structured fields
  B) Remove `mitigation_track_record` from signal accuracy measurement entirely —
     it is inherently subjective and may not be reliably scoreable
  C) Focus signal accuracy measurement only on `recommendation` and `thesis_health`

---

## Key Files in `analysis/`
- `backtest_runner.py` — main runner (v1.3.0, temperature=0, prompt versioning patched)
- `backtest_diff.py` — diffs two backtest CSVs
- `read_eval.py` — reads saved eval narratives by ticker and date
- `data/evals/` — saved full evaluator narratives per transcript
- `data/variance_ENPH_run*.csv` — variance test outputs (target)
- `data/backtest_2026-04-*.csv` — historical backtest runs by date

---

## What Luis Evaluates (Not Cowork)
- Whether a signal accuracy change represents real improvement or noise
- Which prompt direction to try next — this is strategic judgment
- Whether a stumble classification is correct given solar industry domain knowledge
- Final approval of any prompt changes before they become the active evaluator

---

## Architecture Rules (Never Re-Derive)
- Analyst/Allocator firewall is sacred — analyst never sees portfolio data
- Layer ordering: 3→2→1 (find → classify → enforce)
- Tax: 20% federal LTCG, Florida (no state tax)
- Type A cap 35%, Type B variable 40-60%
- Graduated exit ratchet: Weakening → trim → no improvement → trim more → exit
- 48-hour waiting period for positions above 30%
- Enough number: $6M threshold for active management
- Never store credentials in any committed file
- Never recommend outside the circle of competence (see DOMAIN.md)
