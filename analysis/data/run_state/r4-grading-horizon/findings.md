# R4 findings (append-only)

## PRE-REGISTRATION -- written and committed before any cell was computed (2026-09-19)

Copied from prompts/R4-grading-horizon.md section 5.

- Primary: v6's bearish-call edge over the base rate is largest at a SHORTER horizon than 182 days, most likely 60-90 days.
- Secondary: the neutral-call edge stays approximately zero at every horizon.
- Falsified if: bearish edge is flat across all six horizons, OR largest at 182 days or longer.
- A result where the edge peaks at a short horizon on train and not on tune is a NEGATIVE result.
- Rules: report every horizon; train discovers, tune confirms; base rate always at the same horizon.
- Horizons 30, 60, 90, 182, 270, 365. Dead band +-5%, benchmark SPY, price cache scorer_price_cache_v1.json.
- 182-day cell must reproduce pooled train+tune: bearish 59.9% vs 46.6% (+13.3), bullish 37.2% vs 32.8% (+4.4), neutral 20.6% vs 20.6% (0.0); otherwise STOP.
- "Materially varies" for the 6c gate is defined here, before computing: the bearish edge range across horizons (max minus min) exceeds 10 points on train AND the ordering of the best horizon agrees on tune. Otherwise 6c is not run.
- Version guard skipped: no scoring (API) calls are made.

- 2026-09-19: 182d pooled reproduction exact. Train bearish edge falls monotonically 23.2 (30d) to 10.1 (365d); tune peaks at 182d (+11.2), all tune bearish ranges span 0 -> NEGATIVE result per pre-registration. Neutral edge +4.0 (30d) / +2.8 (60d) on train contradicts 'zero at every horizon' (small, not replicated on tune). 6c not run (best horizon disagrees across splits). 90d also used by extract_db_baseline.py (missed in prompt table).
