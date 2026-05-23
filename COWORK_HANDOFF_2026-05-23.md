# Cowork Handoff — 2026-05-23

**How to use this doc:** Load it at the start of a fresh chat. It's an *index*, not a
re-dump — read the source-of-truth files below rather than re-deriving anything. This
supersedes `COWORK_HANDOFF_2026-04-21.md`.

---

## Read first (source of truth — in this order)
1. `CLAUDE.md` — never-do rules, key design decisions, current state. **Authoritative.**
2. `docs/architecture/DESIGN_PRINCIPLES.md` — closed architectural decisions; do not re-derive.
3. `docs/architecture/DOMAIN.md` — investment universe; never recommend outside it.
4. `docs/architecture/PORTFOLIO_ANALYST_SPEC.md` — Portfolio Analyst MVP spec (design phase).
5. `docs/architecture/PROMOTION_GATE.md` — change-control / evaluation methodology (NEW this session).

**Stale — do not trust numbers in:** `docs/architecture/BUILD_STATE.md` and
`COWORK_HANDOFF_2026-04-21.md`. They predate several decisions (they still say Type B
40–60%, 20% LTCG, $6M enough-number, watchlist cap 6, prompt v5). `CLAUDE.md` is current.

---

## Where the project is (one paragraph)
The earnings-call **Evaluator** (v6 prompt) and **RADAR** are live on Railway. The
**backtest simulator** (allocator v1→v4) is built and validated. The **Type A/B
classification engine** ("Thesis Drivers": Pure-play=A/35% cap, Platform=B/50% cap) is
built — curated `analysis/data/type_classifications.json` + `analysis/type_classifier.py`
wired into the simulator. The variable Type B cap was tested and **retired** (flat 50%;
profit-take at 25% binds first). The **Portfolio Analyst** and the **Promotion Gate** are
specced but **not yet built** (design phase).

## Repo / stack
- `Luis-GrowSolar-Personal/investment-agent`, branch `dev`. Railway dev service watches `dev`.
- React/Vite · Node/Express · PostgreSQL/Prisma · Clerk · Anthropic API · Railway.

---

## This session's deltas (2026-05-23)
- Committed this session's work to `dev` in 3 commits (spec+engine, analysis scripts,
  model-bump). `type_classifications.json` is now git-tracked via a `.gitignore`
  exception (it's curated work, not a regenerable cache).
- Locked the **Promotion Gate** methodology and wrote `PROMOTION_GATE.md`:
  manual/on-demand; analyst-direct metric = benchmark-relative 2Q hit-rate (±5% dead-band,
  lift over always-hold, by call type); portfolio metric = return per unit max drawdown;
  recent-holdout + scaled-rigor OOS; metric→change mapping (analyst metric gates
  prompt/model changes, portfolio metric gates parameter changes).

## Open decisions (need Luis)
- **Model pin:** `evaluate.js` was accidentally bumped `claude-sonnet-4-20250514` →
  `claude-sonnet-4-6` (drift over the multi-week project, not requested). Decide: revert
  to the pinned old snapshot (freeze) **or** adopt 4-6 deliberately via a first gate run.
  `CLAUDE.md` line ~24 still lists the old string — reconcile once decided.
- **Railway cap=50 deploy:** the watchlist transcript cap was raised to 50 in code/commits
  but the ENPH-won't-load-past-~17 symptom suggests Railway may still run an older build.
  Worked around by promoting tickers to portfolio status; real fix (verify Railway deploy)
  deferred.

---

## Next tasks (live list)
**Promotion Gate build** (see `PROMOTION_GATE.md` §9): 1) version plumbing
(`promptVersion`/`modelVersion` on `Analysis`, pin model, version-key eval cache) →
2) analyst-direct scorer → 3) end-to-end scorer → 4) holdout+robustness harness →
5) gate runner + experiment ledger → 6) (deferred) CI automation.

**Maturity (tier) classification** — sequential follow-on to Thesis Drivers UI:
1) `data/tier_classifications.json` + override-aware `tier_for_ticker` (mirrors the
type work; small, terminal-friendly) → 2) Prisma tier-override columns → 3) RADAR
"Maturity" column + drawer → 4) recompute monitoring + notification.

**Portfolio Analyst** (see `PORTFOLIO_ANALYST_SPEC.md` build sequence): Phase 1 =
Position/Lot/CashBalance schema + Ticker schema additions + manual position-entry UI
(gateway to the rest).

**Smaller:** v6 prompt — emit `typeClassificationRationale` per call (needed for the
Thesis Drivers drawer); model-pin A/B diff script.

---

## Environment gotchas (carry these into the new chat)
- **Git must run on Luis's laptop, not the Cowork sandbox.** The Dropbox mount lets the
  sandbox *create* files but not *delete* them, so any sandbox git command strands
  `.git/index.lock` and breaks the next op. Prep git work (edit files, choose commit
  grouping) then hand Luis a copy-pasteable command block. If a lock got stranded,
  prefix with `rm -f .git/index.lock`.
- **Laptop is macOS (zsh):** use `python3`/`pip3`, no `--break-system-packages`, no
  `apt`. The Cowork *sandbox* is Linux and differs — keep laptop commands macOS-clean.
- **Secrets stay on the laptop:** `.env` (ANTHROPIC_API_KEY, DATABASE_URL, Clerk keys)
  is unreadable from the sandbox. Pipeline steps that hit the DB / yfinance / Anthropic
  API run on Luis's laptop. Never paste `.env` contents or commit credentials.
- **Backtests are file-based:** `dump_transcripts.py` → file cache → `backtest_from_files.py`;
  no live DB dependency once the cache is warmed.

## Working style
Iterative co-work, one build item at a time — ship, accumulate real usage, apply lessons
to the next. Luis makes the strategic/judgment calls (what's real improvement vs noise,
domain correctness); the agent prepares, tests, and proposes.
