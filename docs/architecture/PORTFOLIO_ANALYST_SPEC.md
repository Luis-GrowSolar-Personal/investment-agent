# Portfolio Analyst — MVP Specification

**Status:** Design (pre-implementation), with Type A/B classification mechanism validated and committed
**Owner:** Luis
**Last updated:** 2026-05-17 (Type A/B section added)
**Supersedes:** N/A (new module)
**Related docs:** `CLAUDE.md`, `DESIGN_PRINCIPLES.md`, `DOMAIN.md`, `BACKTEST_SIMULATOR.md`

---

## Purpose

The Portfolio Analyst is the productionization of the v3 allocator. It transforms v3's research-stage capability into a working decision-support tool for managing a real personal investment portfolio.

It is **decision support, not auto-execution**. The system produces recommendations with full rationale; the human pulls the trigger on actual trades. This is a deliberate design choice — the agent's job is to raise the quality of decisions, not make them.

## Scope

**In scope (MVP):**
- Equity positions across taxable, IRA, and Roth IRA accounts
- v3 allocator recommendations with tax-aware routing and concentration awareness
- Recommendation lifecycle tracking with user response capture
- Investing journal for every position change (recommended or user-initiated)
- Notification system for material changes
- Scenario comparison charts (actual vs followed-every-rec vs passive baselines)
- Retrospective queries and self-monitoring

**Out of scope (deferred to future modules):**
- Bonds and fixed income (separate project — different risk dynamics)
- Commodities and crypto ETF scoring (deferred backlog — needs role-based framework)
- Auto-execution against broker APIs
- Tax-loss harvesting optimization
- Multi-strategy variant selection in UI (premature until variants validated)
- Suggesting new tickers to add to the universe (deferred — needs separate design)

## Foundational principles

### 1. Disagreements are data, not commands
User overrides of v3 recommendations are captured, logged, and analyzed retrospectively. They never silently modify v3 in real time. Algorithm transitions (v3 → v4) happen intentionally, only when (a) there is enough data to justify the change and (b) there is a structured way to ingest the new signal into the model.

### 2. Universe selection is upstream of the algorithm
v3's value is in managing a given cohort, not in selecting it. The system operates on a human-curated universe and does not attempt to pick names ex ante. Out-of-universe positions (legacy holdings) are surfaced separately and excluded from v3's sizing math.

### 3. Process and outcome are separate questions
Retrospective analyses distinguish "was the decision well-formed given the data we had?" from "what happened to the price afterward?" Both questions are answerable; the system never blurs them.

### 4. Friction is a feature
The recommendation review flow is designed to be read carefully and acted on deliberately. Mobile is a status surface only; trades are executed from laptop after thoughtful review.

### 5. Ticker classification is part of the universe contract
Each ticker carries a Type A or Type B classification (see *Type A/B classification* below). Classification is treated as part of the universe definition — slow-changing, human-reviewed, and material to allocator behavior. Misclassification can swing backtest results by 15-60% on a single universe; the system must therefore make classifications visible, editable, and persistent.

---

## Thesis Drivers (Type A/B classification)

This section is load-bearing. The Phase D regression test (2026-05-17) showed that consistent ticker-level classification meaningfully improves v3 results on universes containing monster compounders (original 17-ticker universe: full-window CAGR +23.1% → +27.5%, return-per-DD 0.50 → 0.63, max DD 46.1% → 43.5%). It has neutral effect on universes without monster compounders (top-20-2021: full-window unchanged at +9.9%). On no tested universe did it hurt aggregate performance. Decision: committed as production allocator behavior.

> **Naming note.** Internal/code terminology is "Type A" and "Type B" (preserved for backward compatibility with `data/type_classifications.json`, allocator code, and DB schema). User-facing terminology is **"Thesis Drivers"** with values **"Pure-play"** (Type A) and **"Platform"** (Type B), as displayed in the RADAR UI. The two vocabularies refer to the same concept; the UI exists to make the concept legible to humans, the internal terms exist to keep the code stable.

> **Correction to prior framing (2026-05-17).** Earlier versions of this spec said this section made the system "introduce Type A/B" for the first time. That was wrong. The v6 evaluation prompt already outputs `typeClassification` per call, but those per-call classifications proved highly inconsistent — e.g., TTD labeled "B" in 100% of calls when the user classifies it as Pure-play; RUN labeled "B" in 75% of calls; V and MA labeled "B" in 100% of calls. The actual mechanism is **enforcement of consistent ticker-level classification**, replacing the analyst's noisy per-call output. The improvement comes from removing classification noise, not from introducing A/B as a new dimension.

### Definitions

- **Type A (single-driver thesis)** — the company's revenue, valuation, or both depend predominantly on one product, market, or technology. Hard cap: **35%** of in-scope portfolio.
- **Type B (multi-driver platform)** — the company has multiple independent revenue drivers in distinct end markets, OR its valuation reflects multi-driver optionality even when current revenue is concentrated. Hard cap: **50%** (flat across all Type B tickers regardless of driver count — see "Variable cap experiment, retired" below).

The "or its valuation reflects multi-driver optionality" clause is the *Tesla rule* — Tesla is currently 90%+ auto revenue, but the stock's premium prices in FSD/Robotaxi/Energy/Optimus optionality. By revenue alone it's Type A; by valuation it's Type B. The system uses the valuation framing.

### Classification source of truth

`analysis/data/type_classifications.json` is the canonical store. Schema:

```json
{
  "_meta": {
    "created": "2026-05-16",
    "updated": "2026-05-16 — user overrides for TSLA, META",
    "method": "Claude-generated initial classification + user overrides",
    "decision_rule": "Type B if 4+ drivers OR valuation reflects multi-driver optionality",
    "confidence_values": "high | medium | low",
    "user_overrides": ["TSLA: A→B", "META: A→B"],
    "review_status": "REVIEWED"
  },
  "classifications": {
    "AAPL": { "type": "B", "drivers": 6, "rationale": "...", "confidence": "high" },
    "AMPX": { "type": "A", "drivers": 1, "rationale": "...", "confidence": "high" }
  }
}
```

This file is the *current* working state. Future enhancements (per-call classification from the analyst, prompt update, automatic refresh) feed into this file but do not replace it as the source of truth.

### How the allocator consumes it

The simulator threads a `type_for_ticker(ticker) → "A" | "B" | None` function into `run_simulation()` via the `type_for_ticker` parameter. The function is built once per session by `analysis/type_classifier.py:build_type_function()`, which loads the JSON.

When the allocator's `decide()` is called, it receives `type_classification=<value from type_for_ticker>` instead of the per-event `type_classification` from the cached eval. Order of precedence:

1. If `type_for_ticker` is passed to `run_simulation()`, its return value is authoritative
2. Otherwise, falls back to `event.type_classification` from the cached structured score (this is the analyst's per-call classification — known to be noisy; see "Correction to prior framing" above)
3. Otherwise, allocator defaults to Type A

In production, `type_for_ticker` will always be passed. The fallback path exists for backward compatibility with old test scripts but **should not be used for live decisions** because the per-call classification noise produces inflated drawdowns (60.9% vs 37.1% observed on the speculative-only scenario).

### Where the cap actually binds

The Type A vs Type B cap affects **initial Add sizing**: an Add recommendation with `recommended_size=50%` gets truncated to 35% for Type A but honored at 50% for Type B. However, the profit-take rule (trim 5pp on the next call when a position exceeds 25% of portfolio) fires regardless of type — so Type B positions still get trimmed when they grow past 25%.

Practical effect: Type B mostly matters when a winner is *compounding between calls* (price growth pushing the position past 25% without a new Add). Type A caps these at ~35%; Type B lets them reach 40-50% before the next call's profit-take catches up. This is why Type B's impact is large on universes containing monster compounders (e.g., AVGO 8x in our window) and small on universes where no single name dominates.

### Classification updates

- **Initial population:** `analysis/data/type_classifications.json` is populated by a Claude-generated first pass, reviewed and overridden by the user (Phase A + C of the Type A/B project, completed 2026-05-17).
- **User overrides:** RADAR UI (Phase B, pending) lets the user view current classifications, edit per ticker, and persist back to the JSON. User overrides take precedence over any future analyst-suggested classification.
- **Future: per-call classification from the analyst.** Task #84 adds a `typeClassification` field to the v6 prompt's structured output. Future eval re-runs would populate per-call classifications stored in the Analysis table. The Portfolio Analyst would surface persistent disagreement between the analyst's recent take and the stored ticker type ("analyst has flagged AAPL as Type A in the last 3 calls; currently classified Type B") but would not silently override.
- **Reclassification triggers:** companies can transition (Type A startup grows into Type B platform; Type B platform divests and becomes Type A). The system makes these transitions visible but always requires explicit user action.

### Variable cap experiment, retired (2026-05-17)

The original architectural intent (per `DESIGN_PRINCIPLES.md`) specified a variable Type B cap of 40-60% based on driver count: 40% for 2 drivers, scaling up to 60% for 6+ drivers. The scheme was implemented and tested against the full event corpus.

**Empirical result:** essentially zero impact on v3 aggregate returns. Full-window v3 went from $287k (flat 50%) to $266k (variable 40-60%) — a $21k loss with no compensating DD reduction. Per-year scenarios were identical or within ±$2k. Established-only, speculative-only, and Original Run 1 scenarios were all unchanged. Top-20 universe was completely unchanged.

**Mechanism:** the 25% profit-take rule (introduced in v2 as `PROFIT_TAKE_THRESHOLD_PCT`) binds long before the Type B cap binds. Positions get trimmed at 25% on every call regardless of whether the upper cap is 40%, 50%, or 60%. The variable scheme is therefore vestigial in the presence of profit-take — the two rules are partial substitutes for the same job, and profit-take dominates.

**Decision:** Type B cap is **flat 50% across all drivers** in production. Variable scheme retired. The `driver_count` parameter remains plumbed through `allocator_v2/v3/v4` and `simulator.run_simulation` for backward compatibility and possible future use (e.g., metadata for RADAR UI, or a future tier-aware Type B refinement), but it is a no-op in cap math. The `drivers` field in `data/type_classifications.json` remains useful for human judgment ("AAPL has 6 drivers vs JNJ's 2 reinforces the classification confidence") but does not feed the allocator's sizing.

### Deferred enhancements

- **Correlation-based cohort caps ("correlation solver").** Independent of single-name Type A/B; addresses the correlation problem (AVGO + AMD + ORCL is effectively one bet). **Promoted from idea to committed backlog item 2026-08-30.** Rationale sharpened while specifying `ALLOCATOR_OPERATING_MODEL.md` §6: per-position tier caps cannot see aggregate factor exposure. ENPH + SPWR + RUN + FSLR is four independent 15% Speculative caps and one bet on solar policy and rates — 60% of portfolio in a single macro exposure with every concentration rule satisfied. That is not hypothetical; it is this portfolio's own 2022-23 history. The aggregate **speculative ceiling** specified in `ALLOCATOR_OPERATING_MODEL.md` §6 is an explicitly acknowledged crude proxy for this control and is intended to be *replaced* by it, not supplemented. Scope when built: derive cohorts from realized return correlation over a trailing window (not hand-assigned sectors, which miss cross-sector single bets), cap aggregate cohort exposure, and surface the binding cohort in the Moves grid so the user can see *why* an Add was refused. Future v5 candidate.
- **Confidence-weighted sizing.** Use the `confidence` field in classifications to soften caps for medium/low-confidence classifications.
- **Tier-aware Type B refinement.** Currently both Speculative+Platform and Established+Platform map to 50%. A pre-commercial multi-product startup probably shouldn't get the same cap as a mature multi-segment mega-cap. Task #7 tracks this.

### RADAR UI: Thesis Drivers display

The Thesis Drivers classification is a foundational input to the allocator and must be visible, editable, and persistent in the RADAR UI. This section specifies the surface.

**Column header:** `Thesis Drivers` (with tooltip: "How many independent value drivers the business depends on. Determines position-size cap. Click any value to see classification rationale and analyst's recent take.")

**Cell values:**
- `Pure-play (N)` for Type A — N is the active driver count (typically 1, sometimes 2)
- `Platform (N)` for Type B — N is the active driver count (2-6+)

Cell formatting:
- Both values shown with a small confidence dot (high = solid, medium = half-filled, low = outlined)
- Cell is clickable; opens the classification drawer (see below)

**Disagreement badge:** A small amber dot appears next to the cell value when the analyst has *persistently disagreed* with the stored classification. Specifically, the badge fires when:

1. The last 3+ consecutive analyst calls have output a `typeClassification` that disagrees with the stored ticker classification, AND
2. Those classifications are consistent with each other (no flip-flopping)

This filtering rule is important. The analyst's per-call output is known to be noisy (e.g., AMPX 8 A / 5 B across history — too noisy to act on). Only persistent, consistent disagreement should fire the badge. Without filtering, the badge would fire on most tickers and lose signal value.

**Click action — Classification drawer:** Clicking the cell or the badge opens a side drawer containing:

| Section | Content |
|---|---|
| Header | "Thesis Drivers: Pure-play (1)" with confidence indicator |
| Your rationale | The text from `data/type_classifications.json[ticker].rationale` |
| Last reviewed | "By you, 2026-05-16" — tracks `typeReviewedAt` from Ticker table |
| Analyst's recent take | Summary line: "Platform in 18 of 20 recent calls — persistent disagreement" |
| Per-call detail | Scrollable list of recent calls, each with: date, analyst's classification, the analyst's rationale text for that classification |
| Suggested re-classify | If badge is firing: "Consider: Platform" with one-click apply button |
| Override controls | Dropdown to change classification; driver count input; rationale text area; "Save" button. Saving updates Ticker table, bumps `typeReviewedAt`, syncs to `data/type_classifications.json` for backtest consistency |

**Data model implications:** The per-call analyst rationale text must be captured *at evaluation time*. This requires:

- v6 evaluation prompt update to output `typeClassificationRationale` alongside `typeClassification` (free-text justification for the per-call classification)
- Analysis table schema addition: `typeClassificationRationale: String?`
- Eval cache parser update to capture the new field
- One-time eval re-run after prompt update to populate the rationale field for existing transcripts (~$15, ~2 hours, optional — can also populate forward-only for new calls and accept that existing calls show no rationale)

**Dependency:** The drawer's "Per-call detail" section requires the prompt update + rationale capture. Without it, the drawer can still display the analyst's per-call classification (already captured) but the rationale column will be empty. This is acceptable for MVP; the rationale field is a follow-on improvement.

**Example use case:** ENPH is currently Pure-play (1 driver: microinverters/storage). If they launch EV chargers and the analyst starts classifying ENPH as Platform across the next 3+ calls, the badge appears. User clicks → reads the per-call rationale ("Q3 call: EV charger now $40M/qtr, growing 40% QoQ" + "Q4 call: guided to $200M FY25") → makes informed call: reclassify to Platform (2 drivers) OR keep Pure-play and add a note explaining why ("not yet material; revisit in 4 quarters"). The system surfaces the change-in-character; the user decides.

---

## Maturity (tier classification)

This section parallels Thesis Drivers. Maturity is the *second* foundational classification that determines allocator behavior, alongside Thesis Drivers. The two combined produce a 2×2 sizing matrix (see below).

> **Naming note.** Internal/code terminology is "tier" with values `speculative` and `established` (preserved in `trend_analyst.py`, the structured score, and allocator code). User-facing terminology is **"Maturity"** with values **"Speculative"** and **"Established"** in the RADAR UI. Same concept, different vocabulary for different audiences.

> **Why this section exists.** Maturity was originally specified in `DESIGN_PRINCIPLES.md` and implemented as the 3-axis classifier in `trend_analyst.py`. But it had no UI surface, no user-override mechanism, and no visibility into the classification rationale. The 2026-05-17 conversation about Thesis Drivers surfaced that Maturity faces the same UX problem (different cause — mechanical rather than noisy) and deserves the same first-class UI treatment.

### Mechanism

The mechanical 3-axis classifier uses three inputs to produce a tier verdict:

1. **Trailing 90-day volatility** from `data/price_cache.json`
2. **Market capitalization** from `data/fundamentals_cache.json`
3. **Trailing P/E ratio** from `data/fundamentals_cache.json`

Each axis votes "speculative" or "established" based on thresholds (defined in `trend_analyst.py`). If **≥2 of 3 axes vote speculative**, the ticker is classified speculative; otherwise established. Thresholds are configurable and are themselves part of the architectural design.

Unlike Type/Thesis Drivers, this is NOT noisy per-call output from the analyst. It's a deterministic function of market data snapshots. But it has its own risks:

- **Mechanical drift.** A speculative growing past the market-cap threshold flips to established without anyone reviewing.
- **No user override today.** No human-in-the-loop. The mechanical rule decides.
- **Threshold opacity.** Why is X established and Y speculative? Currently invisible — only the rule output is exposed.
- **Update timing.** Every fundamentals refresh re-classifies. Silent shifts possible.

### Where tier binds

Maturity directly affects two pieces of allocator behavior:

1. **Type A cap, tier-aware (v2/v3):**
   - Type A Speculative: **15% cap** (Phase 2 — tighter to prevent TTD-Day-1-style blowups)
   - Type A Established: **35% cap** (Phase 2 — unchanged from v1)
2. **v3 first-call starter:**
   - Speculative: **5% starter** on first call regardless of recommendation
   - Established: **8% starter** on first call regardless of recommendation

Practical consequence: AMPX growing into established would let the allocator size into AMPX 2.3× more aggressively on Add decisions (from 15% to 35% Type A cap), AND take a larger starter on its first call (5% → 8%). Both effects can be material.

### Combined 2×2 sizing matrix

| | **Pure-play (Type A)** | **Platform (Type B)** |
|---|---|---|
| **Speculative** | 15% cap | 50% cap (rare combo; flagged for future refinement — Task #7) |
| **Established** | 35% cap | 50% cap |

Three of the four cells produce different sizing behavior. The fourth (Speculative + Platform) is a rare combination — a pre-commercial multi-product startup. The current 50% cap is likely too lenient for that combination; future refinement (Task #7) could differentiate by tier within Type B. Out of scope for MVP.

Note: the Type B cap is **flat 50%** for all Type B tickers regardless of driver count. A variable 40-60% scheme based on driver count was tested 2026-05-17 and retired — see "Variable cap experiment, retired" above.

### Classification source of truth

Mirroring the Thesis Drivers pattern, user overrides live in a structured store. Two options for storage:

**Option A: Extend `data/type_classifications.json`** — add a `tier` field alongside `type`. Pros: one canonical file for both classifications. Cons: misleading filename.

**Option B: Separate `data/tier_classifications.json`** — keep the two stores parallel. Pros: clear separation. Cons: more files to maintain.

Recommendation: **Option B**, with `data/tier_classifications.json` mirroring the JSON schema of the type file. Implementation cost is trivial; conceptual separation is cleaner.

### How the allocator consumes it

The simulator already passes `tier_for_ticker` to allocators (introduced in v2). The current implementation calls `trend_analyst.build_tier_function()` which produces purely-mechanical output. The production system should:

1. Build `tier_for_ticker` from `data/tier_classifications.json` (user overrides) as primary
2. Fall back to mechanical 3-axis classifier when no override is stored
3. The mechanical result is always computed in parallel for the disagreement-badge logic

### RADAR UI: Maturity display

Parallel to the Thesis Drivers display:

**Column header:** `Maturity` (tooltip: "Speculative or established. Affects position sizing — speculative names are capped tighter. Click to see classification rationale.")

**Cell values:**
- `Speculative` or `Established`
- Confidence indicator: derivation strength
  - "3/3 axes agree" = high confidence (solid orange dot)
  - "2/3 axes" = medium (half-filled dot)
  - User override active = blue dot replacing the confidence dot

**Disagreement badge:** Filled orange dot when the mechanical 3-axis classifier currently produces a different result than the stored ticker classification. Unlike Thesis Drivers, this badge fires *immediately* on disagreement — the underlying signal isn't noisy and there's no need to filter for multi-call persistence.

**Click action — Maturity drawer:**

| Section | Content |
|---|---|
| Header | "Maturity: Speculative" with confidence (e.g., "2/3 axes fire") |
| 3-axis breakdown | Volatility: 38% (threshold 30%) → speculative ✓ |
|  | Market cap: $1.2B (threshold $50B) → speculative ✓ |
|  | P/E: 24 (threshold spec) → established |
| Trajectory | Mini sparkline of mcap, P/E, vol over last 4 quarters with threshold lines (highlights when thresholds were last crossed) |
| Your rationale | Free-text from `data/tier_classifications.json[ticker].rationale` if user overrode |
| Last reviewed | "By you, 2026-05-17" — tracks `tierReviewedAt` from Ticker table |
| Mechanical classifier says | If stored ≠ mechanical: "Mechanical: Established (3/3 axes)" — frames the disagreement |
| Suggested re-classify | If badge is firing: "Consider: Established" with one-click apply |
| Override controls | Dropdown to change classification; rationale text area; "Save" button. Saving updates Ticker table, bumps `tierReviewedAt`, syncs to `data/tier_classifications.json` for backtest consistency |
| Sizing consequence preview | "After change: Type A cap goes from 15% to 35%. Current position would re-target from X% to Y% on next Add." |

The "Sizing consequence preview" is a Maturity-specific addition — flipping tier has direct, computable consequences on cap math. Surfacing this prevents the user from making the change blind to its effect on portfolio behavior.

### Schema additions

```
Ticker (additions for Maturity)
  tierOverride       String?    // "speculative" | "established" | null (use mechanical)
  tierMechanical     String?    // last computed mechanical result; for diff/badge
  tierReviewedAt     DateTime?  // when user last confirmed/overrode
  tierRationale      String?    // user's reasoning for override
```

### Build phasing — sequential, not parallel

**Maturity UI work follows Thesis Drivers UI work, not in parallel.** Rationale: the two surfaces are conceptually parallel and have similar implementation patterns. Shipping Thesis Drivers first, accumulating real-world usage feedback, then applying lessons to Maturity is cheaper than building both in parallel and discovering UX issues on both at once.

Practical schedule:
1. Ship Thesis Drivers UI (column + drawer + override + sync to JSON)
2. Use it for at least 2-4 weeks of real review cycles
3. Identify what's working and what isn't (badge thresholds, drawer organization, override flow)
4. Apply lessons to Maturity UI implementation
5. Ship Maturity UI

### Example use case for Maturity

AMPX is currently classified speculative (3/3 axes fire: high vol, low mcap, no P/E). Suppose AMPX commercializes aggressively over 2027-2028 and:

- Market cap grows past $50B → mechanical classifier votes "established" on that axis
- P/E becomes computable and reasonable → second axis flips to "established"
- Volatility remains elevated → third axis still says "speculative"

Mechanical result: 2/3 say established → flips to established. Disagreement badge fires.

User clicks → reviews the 3-axis breakdown. The drawer shows the *sizing consequence preview*: "If you accept Established, AMPX's Type A cap goes from 15% to 35%. Your current 12% position remains within the new cap." User decides:

- Accept → AMPX is now sized like an established ticker. Future Adds can go to 35%.
- Override to keep speculative → "Mcap is real but vol is still elevated and the platform thesis is unproven. Revisit in 2 quarters."

The system surfaces the threshold crossing; the user calls the shot.

---

## Inputs

### Per-position state
For each holding the system tracks:

| Field | Description | Source |
|---|---|---|
| Ticker | Stock symbol | User entry / CSV import |
| Account | `taxable` \| `ira` \| `roth` | User entry / CSV import |
| Lot record | Shares, cost basis per share, acquisition date | User entry / CSV import |
| Notes | Free-text per-lot annotation | User entry |

Lots are tracked individually (FIFO accounting) — not aggregated per ticker. A position of "100 shares of AAPL" might be three lots from different dates with different cost bases. This is required for accurate gain/loss and long-vs-short-term tax computation at sell time.

### Per-account state
| Field | Description |
|---|---|
| Cash balance | Available cash by account |
| YTD contributions | Roth/IRA tracking against annual limit |
| Contribution limit | $7,000 (or $8,000 if 50+) per IRA |
| Last reconciled date | When manual state was last verified against broker |

### Per-ticker reference data
| Field | Source | Refresh |
|---|---|---|
| Current price | yfinance / price cache | Daily |
| Volume, volatility | yfinance / price cache | Daily |
| Market cap, P/E | yfinance / fundamentals cache | Weekly |
| Earnings call transcripts | Manual entry via RADAR UI | On call release |
| Dividends, splits, corporate actions | yfinance | Daily check |

### Universe membership
Every held ticker is classified:
- **In-scope:** within the circle of competence (per `DOMAIN.md`); v3 operates on it
- **Legacy/out-of-scope:** held but outside the universe; v3 excludes from sizing math; system surfaces in legacy view with optional "consider exit" prompts

---

## Outputs

### Recommendation object
Every recommendation includes:

| Field | Description |
|---|---|
| Action | `Add` \| `Hold` \| `Trim` \| `Exit` |
| Ticker | Target symbol |
| Account | Suggested account for the trade |
| Target shares | After-trade share count |
| Delta shares | Shares to buy/sell |
| Price at recommendation | Immutable; for stale-detection and counterfactual scenarios |
| Rationale | Structured: per-call rec + trajectory + tier + sizing math + triggered rules |
| Tax impact estimate | For sells: realized gain, LT vs ST, federal tax cost |
| Concentration warning | If trade would push single-name or sector exposure over threshold |
| Confidence band | `confident` \| `advisory` \| `unknown` (from trend layer) |
| Priority/sequencing | Order of execution when multiple recommendations exist |

### Daily/weekly/quarterly outputs
- **On every analysis run:** ordered list of trade recommendations with full rationale
- **On daily price scan:** notification only if a tripwire is hit (no full recommendations)
- **Quarterly recap (auto-generated):** summary of N recommendations made, user response distribution, hit rates on executed vs disagreed, portfolio vs baselines

### What every recommendation must NOT do
- Recommend buys that exceed account cash balance
- Recommend Roth contributions exceeding YTD limit
- Recommend trades that violate the 48-hour waiting period (positions above 30%)
- Recommend trading out-of-scope positions silently (always flag legacy)

---

## Triggers

Three event flows, each with different work profiles:

| Trigger | Frequency | Work | Notification? |
|---|---|---|---|
| Transcript save | Per call (~5-7/week across universe) | Full pipeline: eval → trend → sync → re-recommend | Yes: "new recommendations available" |
| User opens dashboard | On-demand | Cached state + fresh prices | No (already there) |
| Daily price scan | 1×/business day | Price-based tripwire checks only, NO eval | Yes, but only if thresholds tripped |

### Daily tripwires
The daily scan does not re-run v3's full reasoning. It checks:

- Any position now exceeds **30% of in-scope portfolio** → notification
- Any sector/cohort exposure exceeds **50%** → notification
- Any held position moved **±20% in 5 business days** → notification
- Total portfolio drawdown from 60-day peak exceeds **15%** → notification
- Any pending recommendation about to expire within 1 day → notification
- New high or new 52-week low on any in-scope ticker → low-priority notification

---

## Recommendation lifecycle

Every recommendation has a state and full audit trail:

| State | Meaning | Trigger |
|---|---|---|
| `pending` | Generated, awaiting user response | At creation |
| `executed` | User marked as done | User action |
| `disagreed` | User explicitly disagreed (rationale required) | User action |
| `ignored` | User explicitly ignored (rationale optional) | User action |
| `expired` | N days passed with no action | Auto-transition after **5 business days** or after a **±7% price move** in the underlying, whichever comes first |

### Why expired ≠ deleted
Expired recommendations retain their data permanently. For the "what if I'd followed every recommendation" scenario, expired recs still count — they would have been executed in that counterfactual at the price *at recommendation time*. The live user's action window is separate from the simulation logic.

### Auto-recomputation
When a recommendation expires due to price movement, the system optionally re-runs v3 with current state and either confirms (re-issues with updated price) or supersedes (issues a different action).

---

## Journal & rationale

Every position change generates a journal entry. Three categories:

1. **v3-recommended + executed** — rationale auto-populated from v3 reasoning, user may add notes
2. **v3-recommended + disagreed/ignored** — rationale required from user (why override?)
3. **User-initiated (not v3-recommended)** — detected via CSV reconciliation; rationale required prompt

### CSV reconciliation flow
On every CSV upload:
1. Compute diff between current manual state and CSV-reported state
2. For each detected change (buy, sell, open, close, cash movement), create a journal-prompt entry
3. Display badge "rationale needed" until each prompt is answered
4. Reconcile state once all prompts resolved

This is the **discipline mechanism** that ensures every position change has a documented "why" — even those made offline and forgotten.

### Cash movements
Tracked separately from position changes. A $20k deposit followed by a $20k buy is two distinct events with two rationales. Distinguishing them matters for understanding capital deployment vs reallocation.

---

## Out-of-scope position handling

Legacy positions (held but outside the circle of competence per `DOMAIN.md`):

- v3 sizing math operates on **in-scope portfolio value only** — concentration caps are computed against the in-scope total, not the full total
- Total portfolio view shows both: e.g., "Total: $500k ($450k in-scope, $50k legacy)"
- Recommendations footnote explicitly: "Computed against in-scope portfolio. $50k in legacy positions excluded."
- Dedicated **legacy positions tab** lists out-of-scope holdings with optional "consider exit on next opportunity" prompts
- After each in-universe earnings call, the legacy view also surfaces the *delta between current real-world holding and v3's implied target* — useful for positions like TTD that may have grown beyond v3's preferred sizing

---

## Notification system

Tiered by severity, routed to channel by tier:

| Severity | Channels (Phase 1 → Phase 2) | Examples |
|---|---|---|
| **HIGH** | SMS → SMS + WhatsApp | Single-name concentration >40%, ±20% move in 3 days on held name, portfolio DD >15% |
| **MEDIUM** | SMS → WhatsApp | New recommendation available, sector concentration alert, stale rec about to expire |
| **LOW** | Email digest | Weekly summary, quarterly retrospective, low-priority tripwires |

### Implementation phases
1. **Phase 1 (MVP):** Twilio SMS for all real-time alerts. Email digest for weekly/quarterly.
2. **Phase 2:** WhatsApp via Twilio (requires Meta WhatsApp Business approval). Route HIGH/MEDIUM to WhatsApp.
3. **Phase 3 (later):** Native mobile app with push notifications. Only if SMS/WhatsApp prove insufficient.

Email is always **archive-only** — every notification BCCs an email so a searchable record exists, but the user does not rely on email for action.

---

## Scenario comparison charts

A dedicated charts tab compares portfolio value over time across four series:

1. **Actual portfolio** — derived from CSV imports
2. **Followed-every-rec hypothetical** — what the portfolio would be worth if every v3 recommendation had been executed at recommendation time, ignoring user response
3. **50/50 v3 + QQQ hedge** — matches the stated real-world strategy of running v3 on a portion and indexing the rest
4. **Passive baselines** — SPY, QQQ, TMFC buy-and-hold from portfolio start date

### Why series 3 matters
The honest comparison is not "v3 alone vs SPY alone" but "the strategy I actually intend to run vs alternatives." If 50/50 hedged v3 isn't meaningfully different from 100% QQQ, the hedge has costs worth reconsidering.

### Additional chart features
- Toggle individual series on/off
- Time range selector (1mo, YTD, 1yr, all)
- Drawdown overlay (highlight peak-to-trough periods)
- Annotation layer for major recommendations (executed, disagreed, expired)

---

## Retrospective queries

Two distinct question types, never blurred:

### Process question
*"Given the data we had at decision time, was the recommendation well-formed?"*

Reads the stored rationale at recommendation time. Shows:
- Per-call rec, trajectory, tier, sizing math
- Triggered rules
- What thresholds were crossed
- Confidence band

### Outcome question
*"What happened to the ticker after the recommendation?"*

Shows price evolution from rec date to today, with the rec marker overlaid.

### Base rate context (REQUIRED on every retrospective)
Both individual answers must be accompanied by category-level base rates:

- "Trim recommendations at Trajectory=Softening have had Y% hit rate historically"
- "Average performance of Trim recs over the next 90 days: -Z%"

Without base rates, individual retrospectives invite hindsight bias. Every event feels meaningful when statistically it may not be.

### Chat interrogation
A free-form Q&A surface where the user can ask questions like:
- "Remind me why we trimmed ENVX in March?"
- "What would happen to the recommendation if I told you I'm retiring in 2 years?"
- "How does this trim compare to historical Trim/Softening recommendations?"

Architecturally: the rationale is **persisted at recommendation time** in structured form. The chat surface reads from that store and uses Claude as the renderer/formatter. The structured data is the load-bearing piece; Claude is the friendly interface.

---

## Self-monitoring (NOT auto-tuning)

The system periodically computes recommendation performance metrics and surfaces patterns:

- Hit rate by category (per-call rec × trajectory × tier)
- Average performance of executed recs over 30/90/180-day windows
- Comparison of executed vs disagreed outcomes
- Trends in user agreement rates

### Critical constraint
**The algorithm never tunes itself based on these metrics.** Surfacing a pattern is monitoring; modifying v3 parameters in response is curve-fitting on recent noise. Any v3 → v4 transition must follow the validation discipline below.

### Algorithm version transitions
v3 → v4 happens only when:
1. There is a hypothesized improvement with explicit rationale
2. The change is validated with walk-forward optimization (tune on one window, test on another)
3. The improvement holds on out-of-sample data
4. The improvement is significant enough to justify the integration cost

Avoid the trap of fitting v3.x.y.z incrementally — small changes accumulating against backtest noise produce false confidence.

---

## UX surfaces

### Laptop (primary)
Optimized for careful reading and deliberate action:
- Recommendation page: top-to-bottom scannable, each rec with rationale, tax impact, concentration warning, confidence band
- Charts tab: full comparison views with all series and controls
- Decision history: filterable, queryable, with retrospective + base rates
- Journal: full entry capture for both v3-recommended and user-initiated changes
- Settings: account configuration, notification preferences, universe membership

### Mobile (status only, NOT interactive)
Optimized for glance:
- Counts: "3 new recommendations, 1 tripwire alert"
- Latest tripwire summary
- One chart: portfolio value vs primary baseline
- **No execute, no agree/disagree on mobile.** Anything requiring decision pushes to "Open on laptop" link.

### Why this split
Protects against the worst failure mode: glancing at the phone during a busy moment, hitting "approve" without reading rationale, executing a trade that needed more thought. The friction of switching to laptop is intentional.

---

## Schema additions

New tables (Prisma):

```
Position
  id            Int      @id
  ticker        String
  account       String   // taxable | ira | roth
  status        String   // active | closed
  createdAt     DateTime
  closedAt      DateTime?

Lot
  id            Int      @id
  positionId    Int
  shares        Float
  costBasis     Float
  acquiredDate  DateTime
  closedDate    DateTime?

CashBalance
  account       String   @id  // taxable | ira | roth
  balance       Float
  asOfDate      DateTime

Recommendation
  id            Int      @id
  ticker        String
  action        String   // Add | Hold | Trim | Exit
  account       String
  targetShares  Float
  deltaShares   Float
  priceAtRec    Float    // immutable
  rationale     Json     // structured: per-call rec, trajectory, tier, triggered rules
  taxImpact     Json?    // realized gain, LT/ST, fed tax estimate
  concentration Json?    // post-trade % of portfolio, sector exposure
  confidence    String   // confident | advisory | unknown
  state         String   // pending | executed | disagreed | ignored | expired
  generatedAt   DateTime
  resolvedAt    DateTime?
  expiresAt     DateTime

UserResponse
  recommendationId Int
  response         String   // executed | disagreed | ignored
  rationale        String?  // user free-text
  respondedAt      DateTime

JournalEntry
  id          Int      @id
  positionId  Int?
  ticker      String
  changeType  String   // buy | sell | open | close | deposit | withdrawal
  shares      Float?
  amount      Float?
  rationale   String   // required for user-initiated, auto-filled for v3-rec
  source      String   // v3_recommendation | user_manual | csv_reconciliation
  createdAt   DateTime

Notification
  id          Int      @id
  severity    String   // HIGH | MEDIUM | LOW
  channel     String   // sms | whatsapp | email
  message     String
  triggerType String   // concentration | price_move | drawdown | rec_available
  sentAt      DateTime
  readAt      DateTime?
```

Existing tables (`Ticker`, `Transcript`, `Analysis`) remain as-is, with the following additions:

```
Ticker (additions)
  inScope            Boolean  // false for legacy positions
  type               String   // "A" | "B" — production classification, source of truth
  activeDriverCount  Int?     // 1-6+, used for future variable-cap implementation
  typeReviewedAt     DateTime?  // when user last confirmed/overrode classification
```

The `type` field on `Ticker` is the authoritative classification used by the production allocator. It is initially populated from `analysis/data/type_classifications.json` (the working JSON) and synced bidirectionally with the RADAR UI Type editor. The JSON remains the canonical *backtest-side* store; the DB is the canonical *live-side* store. A small sync script ensures they stay aligned.

---

## Build sequence

Each phase produces something usable on its own:

1. **Schema + manual position entry** — Position, Lot, CashBalance tables; UI to enter starting holdings. Also: Ticker schema additions for `inScope`, `type`, `activeDriverCount`, `typeReviewedAt`, plus tier columns (`tierOverride`, `tierMechanical`, `tierReviewedAt`, `tierRationale`).
2. **Thesis Drivers (Type A/B) classification UI** — RADAR Type editor (column header "Thesis Drivers"; cell values "Pure-play (N)" / "Platform (N)"; disagreement badge with 3+ consecutive call filter; classification drawer with per-call analyst rationale, override controls, sync to JSON for backtest consistency). Backend ingests `data/type_classifications.json` as initial population.
2b. **Recommendation engine v1** — wire v3 to position state + the production `type_for_ticker` lookup + the production `tier_for_ticker` lookup (mechanical fallback OK until phase 2c ships); produce ordered recommendations with rationale.
2c. **Maturity (tier) classification UI** — Sequential follow-on to phase 2. Same pattern (column "Maturity", values "Speculative" / "Established", disagreement badge fires immediately on mechanical-vs-stored mismatch, drawer with 3-axis breakdown + sparkline + sizing-consequence preview, sync to `data/tier_classifications.json`). Builds on lessons from Phase 2 real-world usage. **Sequential, not parallel** — ship Thesis Drivers first, accumulate 2-4 weeks of real-world usage, apply lessons here.
3. **Recommendation engine v2** — refresh with `tier_for_ticker` reading user overrides from `data/tier_classifications.json` (now that classifications can be overridden, allocator must honor them).
4. **Recommendation display + lifecycle** — clean view of pending recommendations with tax impact, concentration warnings, full rationale; user response capture; state transitions
5. **Journal + CSV reconciliation** — every position change generates an entry; CSV upload prompts for rationales on diffs
6. **Daily price scan + notifications** — Twilio SMS for tripwires; severity routing
7. **Scenario charts** — four series (actual, followed-every-rec, 50/50 hedge, passive baselines)
8. **Retrospective queries + chat interrogation** — questions against persisted rationale + base rates
9. **Self-monitoring dashboards** — pattern surfacing, no auto-tuning
10. **(Phase 2) WhatsApp via Twilio** — once SMS pattern is proven
11. **(Phase 2+) Schwab CSV import** — automated state reconciliation

Each phase should ship to the user (Luis) and accumulate real-world usage before the next phase begins. Resist the temptation to build all phases in parallel.

---

## Success criteria

The Portfolio Analyst is working if, after 6 months of real use:

1. **Adoption:** Luis reviews recommendations on the cadence intended (1-2× per week)
2. **Compliance:** A meaningful fraction of recommendations are acted on (executed or explicitly disagreed); ignore-rate is low
3. **Quality:** Journal entries accumulate with substantive rationales; user revisits past entries productively
4. **Outcomes:** Real-world portfolio performance is at least as good as the followed-every-rec hypothetical (i.e., user overrides aren't systematically hurting)
5. **Trust:** Luis can articulate, six months in, what the agent is good at and where it falls short — and is willing to commit additional capital to it

The Portfolio Analyst is **not** working if:

- Notifications are routinely missed or ignored
- Recommendations expire at high rates without user engagement
- Journal entries become sparse or perfunctory
- User overrides systematically outperform v3 (means soft info is dominant and v3 is the wrong tool)
- User overrides systematically underperform v3 (means user is fighting the tool emotionally)

Both failure modes are diagnostic, not terminal. They point toward different remediation: better UX/notification cadence, better v4 design with explicit qualitative signal channels, or honest reassessment of whether the tool fits the user's situation.

---

## Open questions / deferred decisions

1. **Universe-membership boundary cases** — when does a held position graduate from "speculative" to "established"? When does an in-scope position become "legacy"? Manual flag for now; could become rule-driven later.

2. **Multi-account contribution timing** — Roth contribution timing decisions (front-load vs spread) are not addressed in MVP. Tracker only.

3. **Multi-currency** — assumed USD-only for MVP.

4. **Joint vs individual accounts** — assumed single-owner. Spouse/joint accounts not modeled.

5. **Estate considerations** — out of scope. Different problem class.

6. **Performance attribution** — beyond comparison to baselines, the system does not decompose returns into selection vs sizing vs timing. Future enhancement.

7. **Tax-lot harvesting opportunities** — the system identifies tax impact per sell but does not actively scan for harvestable losses. Future enhancement, possibly tied to a "year-end tax review" feature.

---

## Changelog

| Date | Change | Rationale |
|---|---|---|
| 2026-05-16 | Initial spec drafted | Captures inputs, outputs, triggers, lifecycle, notification system, retrospective design, schema additions, build sequence — single source of truth for Portfolio Analyst MVP |
| 2026-05-17 | Added principle #5 (ticker classification as universe contract) | Phase D regression test demonstrated 17% lift in v3 full-window return ($245k → $287k) from proper Type A/B classification; warrants top-level structural treatment |
| 2026-05-17 | Added *Type A/B classification* section | Documents JSON source of truth, simulator wiring, classification update flow, and deferred enhancements (variable cap, sector cap, confidence-weighted sizing) |
| 2026-05-17 | Updated build sequence | Added phase 2 (Type A/B classification UI) as foundational; subsequent phases renumbered |
| 2026-05-17 | Updated Schema additions | Added `inScope`, `type`, `activeDriverCount`, `typeReviewedAt` fields to Ticker table |
| 2026-05-17 | Corrected mechanism description in Type A/B section | Diagnostic on speculative-only DD anomaly (60.9% → 37.1%) revealed v6 prompt already outputs `typeClassification` per call, but those classifications are noisy (TTD 100% B vs user A; RUN 75% B vs user A; etc.). Actual improvement mechanism is *enforcement of consistent ticker-level classification*, not introduction of A/B. Previous spec framing was incorrect; corrected with prominent note plus footnote on the order-of-precedence section warning against relying on the fallback in production. |
| 2026-05-17 | Renamed section to "Thesis Drivers (Type A/B classification)" | UI vocabulary "Thesis Drivers / Pure-play / Platform" formalized as user-facing terminology; internal "Type A / Type B" preserved for code and JSON compatibility. |
| 2026-05-17 | Added RADAR UI: Thesis Drivers display subsection | Specifies column header, cell values, disagreement badge with 3+ consecutive call filter, classification drawer with per-call analyst rationale, override controls, and dependency on v6 prompt update for rationale capture. ENPH/EV-charger example included as canonical use case. |
| 2026-05-17 | Added Maturity (tier classification) section | Second foundational classification surfaced as first-class UI element. Parallel pattern to Thesis Drivers: column header "Maturity", values "Speculative" / "Established", disagreement badge fires immediately on mechanical-vs-stored mismatch (unlike Thesis Drivers which requires multi-call filtering — tier is deterministic from market data, not noisy). Drawer includes 3-axis breakdown, threshold-crossing sparkline, sizing-consequence preview. AMPX maturity transition included as canonical use case. Stored in `data/tier_classifications.json` (parallel to type classifications). |
| 2026-05-17 | Added combined 2×2 sizing matrix | Documents Type × Tier → cap mapping. Flags Speculative+Platform as future refinement candidate (currently treated identically to Established+Platform). |
| 2026-05-17 | Updated build sequence | Inserted Phase 2c (Maturity UI) as sequential follow-on to Phase 2 (Thesis Drivers UI), not parallel. Rationale: real-world usage feedback from Thesis Drivers should inform Maturity UX decisions. |
| 2026-05-17 | Retired variable Type B cap (40-60%); committed flat 50% as production | Empirical test showed variable scheme produces essentially zero impact on v3 returns/DD on either tested universe. Full-window v3 went from $287k (flat 50%) to $266k (variable 40-60%); per-year scenarios identical or within ±$2k. Mechanism: the 25% profit-take rule binds before the Type B cap binds, making the 40-60% spread vestigial. Replaced "MVP deviation: flat 50%" with formal retirement of variable scheme. The `driver_count` parameter remains plumbed in allocator/simulator for future use (UI metadata, possible tier-aware refinement) but is a no-op in cap math. |

---

*Document end. Update this spec — not memory — when design changes. Memory should reference this spec.*
