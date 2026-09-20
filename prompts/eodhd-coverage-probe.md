# EODHD probe — is this vendor good enough, and does consensus exist for our companies?

**Run ID:** `eodhd-coverage-probe`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/eodhd-coverage-probe-out.md`
**Cost: $0 in model calls. Uses a FREE-TIER vendor key with a hard call budget.**

**Why you and not Cowork.** The Cowork sandbox's network proxy refuses
`eodhd.com` with a 403 at CONNECT. You run in Luis's own terminal on his
normal connection, so the API should be reachable. **If you also get a 403 or
a connection refusal, stop and report — do not work around it.**

**Read first:** `wrap-ups/confirmation-rule-test-out.md` §"Read this first"
(the Paramount price defect), `wrap-ups/disaster-profile-test-out.md`
§1, and `docs/handoffs/2026-09-19-state-of-play.md` §0.

---

## 1. What this run is for

Two questions, in priority order.

**Question 1 — can we trust this vendor's prices?** The project's price cache
has one corrupt series (Paramount: a flat ~$100,000 decaying to ~$1, against a
stock that never left a $10–$100 range). Before using any vendor data we need
to know whether this vendor agrees with our existing cache on companies we
believe are correct.

**Question 2 — does analyst consensus exist for our companies?** The
guidance-ledger work established that comparing a company to *its own prior
guidance* carries no forward signal. The untested hypothesis is that comparing
it to *what the market expected* does. That needs consensus estimates. **Before
anyone pays for a subscription, we need to know whether the estimate field is
actually populated for our universe — especially the small and pre-revenue
names, where analyst coverage thins out.**

**What this run is NOT.** It does not build a ledger, score anything, change
the scorer, or recommend a purchase. It probes and reports.

## 2. The call budget — this is a hard constraint

The key is a **free tier: 20 API calls per day, plus a one-time 500-call
welcome bonus.** Treat **300 calls** as this run's ceiling and leave the rest
as headroom.

- **Count every call and write the running total to `progress.json`.**
- **Stop at 300 and report**, even mid-step.
- **The earnings calendar endpoint accepts multiple symbols in one request.
  Use that.** Fetching 55 companies one at a time is the difference between 5
  calls and 55.
- Free-tier documentation states a "past year" data range limit. **Find out
  empirically whether that applies to the earnings calendar endpoint**, which
  is the one that matters, and report what you find. If history is capped at a
  year, say so plainly — it changes the buy decision.

The key is `EODHD_API_TOKEN` in the repo root `.env`. **Never print it, never
write it to any output file, never include it in a committed URL.** Read it
from the environment.

## 3. Ground rules

1. **No Anthropic API calls. No model spend. No DB writes.**
2. **Do not modify** `analysis/analyst_direct_scorer.py`,
   `analysis/data/corpus_v2/scorer_price_cache_v1.json`, or anything under
   `docs/architecture/`. This run only reads and writes its own outputs.
3. **Holdout untouched.** Probe train and tune companies only.
4. **`PARA` is excluded from this project as of 2026-09-20** — corrupt price
   series, decision recorded by Luis. Do not probe it. **`WOLF` and `SPWR`
   remain excluded.**
5. **Resolve symbols through `analysis/data/corpus_v2/TICKER_ALIASES.json`
   before building any request** (`ANTM`→`ELV`, `VIAC`→`PARA` — now dropped,
   `GOOGL`→`GOOG`). EODHD uses a `TICKER.US` suffix for US listings; note in
   the wrap-up whether the vendor prefers the old or new symbol for renamed
   companies.
6. **`python3`, zsh, macOS Tahoe.** No `--break-system-packages`. No `apt`.
7. **A result that contradicts an expectation here is a finding.**

## 4. Steps −1 and 0

State in `analysis/data/run_state/eodhd-coverage-probe/`. `progress.json`
written first, carrying `calls_used` from call one. Raw responses cached to
`raw/` so a re-run costs nothing. `findings.md` append-only. Clean tree, hard
stop on `git_dirty`. Driver `analysis/eodhd_probe.py` committed before it
produces output. **Commit `raw/` — the whole point is that we never pay for
the same call twice.**

## 5. Step 1 — price validation (do this first, ~8 calls)

Fetch daily prices for **six companies we believe are correct** and compare
against `analysis/data/corpus_v2/scorer_price_cache_v1.json` over the overlap
period: **MSFT, INTC, DUK, ENPH, EOSE, JKS** — two large, one utility, three
solar/storage including a volatile small cap.

For each: the share of shared dates where the two sources agree within 1%, the
largest disagreement and its date, and whether the vendor's series is
split-adjusted the same way ours is.

**Then fetch Paramount** (`PARA.US`) for 2020-01-01 to 2026-09-14 and record
what the vendor actually shows, so the corruption is documented against an
independent source rather than against my memory of the stock.

**Hard stop:** if the six known-good companies do not agree within 1% on the
overwhelming majority of dates, **this vendor's prices are not compatible with
ours and Question 2 is not worth asking yet.** Report and stop.

## 6. Step 2 — the consensus coverage probe (the main event)

Use the **earnings calendar** endpoint, batched by symbol, over
**2020-01-01 to 2026-01-01**, for every train and tune company after
exclusions.

For each company report:

| | |
|---|---|
| earnings events returned | count |
| events with a **populated** `estimate` field | count and share |
| events with a populated `actual` | count and share |
| events with `before_after_market` populated | count and share |
| earliest and latest event date returned | tests the free-tier range limit |

**Then group the results** by corpus stratum (S1 large cap, S2 in-scope mixed,
S3 out-of-scope, S4 failures, S5 continuity) and report the share of events
with a populated estimate in each. **This is the number that decides
everything** — if consensus is populated for the large caps and empty for the
speculative names, that is the answer to the pre-revenue question and it needs
to be stated in one plain sentence.

**Call these out individually, whatever the group figures say:**

- **INTC, VZ, KHC, SBUX, UPS, SEDG** — large, well-covered names that produced
  most of the catastrophic calls. If consensus is thin here, the hypothesis is
  dead.
- **EOSE, ENVX, BLDP, AMPX, QS, SUNW** — the speculative and pre-revenue
  names. **Report whether the estimate field is populated at all, and whether
  the estimates are of earnings only or revenue as well.** For a company with
  no profits, an earnings estimate measures expected loss, which is a much
  weaker signal than expected revenue.

**Also report whether the endpoint returns any revenue estimate field.** Our
vendor comparison assumed it is earnings-per-share only. Confirm or correct
that — it is the difference between this vendor at $60 a month and a
competitor at $99.

## 7. Report step

**Scope boundary: report, do not decide.** Do not recommend a subscription, do
not build a ledger, do not amend the state of play or the candidate queue.

Write `wrap-ups/eodhd-coverage-probe-out.md`, three forms (`.md`, `.docx` with
real Word tables, published artifact page). **Open with §0, defined terms** —
at minimum: consensus estimate, earnings surprise, point-in-time, coverage,
stratum, pre-revenue, before/after market.

Open the body with this sentence, filled in:

> Across ___ companies and ___ earnings events from 2020 onward, the vendor
> returned a populated consensus estimate on ___% of events. For the large
> companies that produced most of our worst calls it was ___%, and for the
> speculative and pre-revenue names it was ___%. Revenue estimates ___ [are /
> are not] available. On six companies we believe our own prices are correct,
> the vendor agreed within 1% on ___% of shared dates. Free-tier history
> reached back to ___. This run used ___ of its 300-call budget.

Then the per-company table, the by-stratum summary, the price comparison, and
one plain paragraph per finding.

**Close with what it means for a decision, three ways:** if coverage is good
across both groups, what the next run would be and what it would cost; if
coverage is good for large caps only, what that means for testing the
hypothesis on a reduced universe; if coverage is poor or the free tier caps
history at a year, say plainly that this vendor cannot answer the question and
what would.

**Plain-language discipline is binding.** Anchor every percentage to what it
is a percentage of. Write "points," never "pp." Short sentences. Lead with the
finding. **Luis is an experienced investor and not a statistician — an
explanation needing a statistics background is a failed explanation.**

## 8. Standing rules

`python3`, zsh, macOS Tahoe. Work on `sweep/db-corpus-baseline`. Provenance for
every figure — endpoint, parameters, and the cached raw file it came from.
Never log the API token. One prompt in, one wrap-up out. Commit the driver and
`raw/`. **If the call budget runs out, stop cleanly, mark the rest `pending`
with a precise `next_action`, and say plainly that it is a partial run — the
budget resets daily and a resumed run costs nothing extra.**
