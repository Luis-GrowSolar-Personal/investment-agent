# Cowork Handoff — 2026-05-23b

**How to use this doc:** Load it at the start of a fresh chat. It's an *index*, not a
re-dump — read the source-of-truth files below rather than re-deriving anything.
This supersedes `COWORK_HANDOFF_2026-05-23.md`.

---

## Read first (source of truth — in this order)
1. `CLAUDE.md` — never-do rules, key design decisions, current state. **Authoritative.**
2. `docs/architecture/DESIGN_PRINCIPLES.md` — closed architectural decisions.
3. `docs/architecture/DOMAIN.md` — investment universe.
4. `docs/architecture/PORTFOLIO_ANALYST_SPEC.md` — Portfolio Analyst MVP spec.
5. `docs/architecture/PROMOTION_GATE.md` — change-control methodology (locked).

---

## Where the project is

Same as `COWORK_HANDOFF_2026-05-23.md` plus the work below. The **Promotion Gate**
is now fully built and ready to run. The **model-pin decision** (sonnet-4-20250514
vs sonnet-4-6) is the immediate next action — the challenger eval cache is being
generated right now and the gate run is the first task next session.

---

## This session's deltas (2026-05-23b)

### typeClassificationRationale — shipped
- Added to `docs/EVALUATION_PROMPT.md` STRUCTURED block + field definition.
- Also fixed stale Type B cap description in prompt (was "Variable cap 40-60%",
  now "Fixed cap 50%; profit-take rule at 25% gain binds first").
- Added `typeClassificationRationale String?` to `server/prisma/schema.prisma`.
- Wired through `server/routes/save.js`.
- **Migration applied:** `20260523183341_add_type_classification_rationale` ✅

### Version plumbing — built, migration pending
- `server/lib/versions.js` created: single source of truth for `PROMPT_VERSION = "v6"`
  and `MODEL_VERSION = "claude-sonnet-4-6"`. Both routes import it.
- `server/routes/evaluate.js`: uses `MODEL_VERSION` constant (was hardcoded string),
  returns `promptVersion` + `modelVersion` in API response.
- `server/routes/save.js`: stamps every `Analysis` row with `PROMPT_VERSION` /
  `MODEL_VERSION` from `versions.js` — never from client input.
- `server/prisma/schema.prisma`: added `promptVersion String?` and `modelVersion String?`
  to `Analysis` model.
- **Migration NOT yet run.** Luis must run:
  ```
  cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) npx prisma migrate dev --name add_version_columns
  ```

### Promotion Gate — fully built
Five scripts in `analysis/`:

| Script | Role |
|---|---|
| `analyst_direct_scorer.py` | §3.1 analyst-direct hit-rate: benchmark-relative 2Q, ±5% dead-band, lift-over-always-bullish, by call type. |
| `e2e_scorer.py` | §3.2 end-to-end metric: return / max-drawdown from file-based simulator (no DB). |
| `gate_runner.py` | Champion-vs-challenger driver: applies §5 promotion rule, bootstrap noise threshold, robustness slicing, writes to `gate_ledger.json`. |
| `analysis/data/gate_ledger.json` | Experiment ledger (empty array, ready for first entry). |

**Also updated:**
- `analysis/simulator/data_from_cache.py`: `EVALS_DIR` now auto-selects
  `v6_sonnet-4-20250514/` (with fallback to `v6/` until rename is done); 
  `load_events_from_cache()` accepts optional `eval_dir` override.
- `analysis/backtest_from_files.py`: cache subdir is now `{prompt_version}_{MODEL_SLUG}`
  (e.g. `v6_sonnet-4-20250514`); redundant flat-write removed; `MODEL_SLUG` auto-derived
  from `MODEL` constant.

### Baseline result (7-ticker, v6_sonnet-4-20250514, training window)
Champion analyst-direct metric on ENPH/TTD/AMPX/ENVX/EOSE/QS/SPWR,
pre-2024-11-01 training window (n=81 scoreable calls):
- **Hit-rate: 30.9% | Always-bullish baseline: 26.0% | Lift: +4.9pp**
- Noise threshold (bootstrap 1 SD across tickers): **4.35pp**
- Bearish calls are the strength: 63.6% hit, +31.8pp lift.
- Bullish calls: no lift over baseline. Neutral calls: −3.8pp.
- **Holdout split: 2024-11-01** (472 training / 187 holdout events in full corpus).

---

## What Luis did manually (or is doing now)

- [ ] Rename eval cache dir on laptop:
  ```bash
  cd analysis
  mv "data/evals/v6" "data/evals/v6_sonnet-4-20250514"
  mv data/evals/*.txt "data/evals/v6_sonnet-4-20250514/" 2>/dev/null; true
  rmdir "data/evals/v6 (stable best after v5→v8 iteration)" 2>/dev/null; true
  ```
- [ ] Run DB migration for version columns (command above).
- [~] Generate challenger eval cache — running now:
  ```bash
  # MODEL = "claude-sonnet-4-6" in backtest_from_files.py (already changed)
  for ticker in ENPH TTD AMPX ENVX EOSE QS SPWR; do
      python3 backtest_from_files.py --save-evals --ticker $ticker
  done
  ```
  Output lands in `analysis/data/evals/v6_sonnet-4-6/`.

---

## Next tasks (in order)

### Immediate (first thing next session)
**Run the model-pin gate:**
```bash
cd analysis
python3 gate_runner.py analyst \
    --champion  data/evals/v6_sonnet-4-20250514 \
    --challenger data/evals/v6_sonnet-4-6 \
    --tickers ENPH TTD AMPX ENVX EOSE QS SPWR \
    --holdout-start 2024-11-01 \
    --label "model_pin: sonnet-4-20250514 vs sonnet-4-6"
```
**If PROMOTE:** update `CLAUDE.md` line ~24 to `claude-sonnet-4-6`. Done.
**If HOLD:** revert `MODEL_VERSION` in `server/lib/versions.js` to
`claude-sonnet-4-20250514`. Update `CLAUDE.md` accordingly.

### After model-pin decision
- **Portfolio Analyst Phase 1** (see `PORTFOLIO_ANALYST_SPEC.md` build sequence):
  Position/Lot/CashBalance schema + Ticker schema additions + manual position-entry UI.
- **Maturity (tier) classification** — `data/tier_classifications.json` + override-aware
  `tier_for_ticker` → Prisma tier-override columns → RADAR "Maturity" column + drawer.
- **Thesis Drivers drawer** — now has `typeClassificationRationale` data in DB; needs
  the RADAR UI component to surface it.

### Backlog (not urgent)
- Railway cap=50 deploy: verify Railway picked up the watchlist transcript cap change
  (ENPH-won't-load-past-~17 symptom). Worked around by promoting tickers to portfolio.

---

## Environment gotchas (carry forward)
- **Git on Luis's laptop only** — Dropbox mount strands `.git/index.lock` in sandbox.
  Prep commit blocks and hand them to Luis. If a lock is stranded: `rm -f .git/index.lock`.
- **Laptop is macOS (zsh):** `python3`/`pip3`, no `--break-system-packages`, no `apt`.
  Sandbox is Linux — keep commands OS-clean.
- **Secrets on laptop:** `.env` unreadable from sandbox. API/DB steps run on Luis's laptop.
- **Backtests are file-based:** `dump_transcripts.py` → file cache → `backtest_from_files.py`;
  no live DB dependency once warmed.
- **Analyst gate needs challenger cache first:** `backtest_from_files.py --save-evals`
  must be run on the laptop (needs `ANTHROPIC_API_KEY`) before `gate_runner.py`.
