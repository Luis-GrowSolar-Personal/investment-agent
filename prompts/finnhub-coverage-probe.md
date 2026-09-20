# Finnhub probe — is the consensus data free?

**Run ID:** `finnhub-coverage-probe`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/finnhub-coverage-probe-out.md`
**Cost: $0 in model calls. Free-tier vendor key, rate-limited not call-capped.**

**Why you and not Cowork.** Both the Cowork sandbox and the cloud container
refuse `finnhub.io` with a 403 at CONNECT — a network policy, not a vendor
limit. You run in Luis's own terminal. **If you also get a 403 or a connection
refusal, stop and report; do not work around it.**

**Read first:** `wrap-ups/eodhd-coverage-probe-out.md` (the same probe against
a different vendor, including its 403 on the paid endpoint) and
`docs/handoffs/2026-09-20-state-of-play.md` §6.

---

## 1. What this run is for

The guidance-ledger work established that comparing a company to **its own
prior guidance** carries no forward signal: a mechanically graded miss was
followed by underperformance 47.4% of the time against a 46.6% base rate. The
untested hypothesis is that comparing it to **what professional analysts
expected** does. A company can beat its own conservative guide and still miss
what the street wanted, and the stock falls. That gap is invisible in a
transcript.

The other vendor's free tier refused the earnings endpoint outright ("Only EOD
data allowed for free users"), which is why the state of play recommends a $60
subscription. **Finnhub's free tier may already carry this data. If it does,
that recommendation is withdrawn and the consensus test can run for nothing.**

### The constraint that decides what this run can be

**The free tier is reported to serve about 60 calls per minute and roughly
one year of history.** If that is right, it settles something before you
start:

| free-tier window | corpus calls inside it | **of which bearish** |
|---|---|---|
| 1 year (since 2025-09-20) | 106 | **6** |
| 2 years | 516 | 53 |
| the whole corpus | 2,385 | 177 |

The corpus's last call is 2025-12-18, so a one-year window overlaps it by
**89 days** and contains **six bearish calls**.

> **Therefore: do NOT attempt the consensus hypothesis test on the free tier.
> Six bearish calls cannot support any conclusion.** If you find yourself
> computing whether a consensus miss predicts underperformance, stop — that is
> not this run.

**So this run answers a purchase question, not a research question:** *is the
paid tier worth buying?* And the good news is that the thing which decides
that — **coverage** — is perfectly answerable inside a one-year window.
Whether analysts publish estimates for Eos Energy does not change from year to
year. If the field is populated for a company in 2026, it was populated in
2022.

**Verify the one-year cap rather than assuming it.** It is reported, not
confirmed, and it may differ by endpoint. Establish it empirically and say
what you found.

**What this run is NOT.** It does not build a ledger, score anything, test the
hypothesis, or recommend a purchase. It establishes what the free key reaches,
how deep the history goes, and how good the coverage is — so the purchase
decision is informed.

## 2. Ground rules

1. **No Anthropic API calls. No model spend. No DB writes.**
2. **Do not modify** the scorer, the price cache, or anything under
   `docs/architecture/`.
3. **Holdout untouched.** Train and tune companies only.
4. The key is `FINNHUB_API_KEY` in the repo root `.env`. **Never print it,
   never write it to an output file, never commit it inside a URL.** Read it
   from the environment.
5. **Rate limit is about 60 calls per minute.** Sleep between calls; do not
   burst. There is no published daily cap, but **stop at 600 calls** and
   report if you somehow reach it.
6. **Cache every raw response to `raw/` and commit it.** We should never pay
   for or re-request the same call.
7. **`PARA` is excluded from this project** (corrupt price series, decided
   2026-09-20). `WOLF` and `SPWR` remain excluded.
8. **Resolve symbols through `analysis/data/corpus_v2/TICKER_ALIASES.json`**
   (`ANTM`→`ELV`, `GOOGL`→`GOOG`).
9. **`python3`, zsh, macOS Tahoe.** No `--break-system-packages`. No `apt`.
10. **A result that contradicts an expectation here is a finding.**

## 3. Steps −1 and 0

State in `analysis/data/run_state/finnhub-coverage-probe/`. `progress.json`
first, with a running `calls_used`. `findings.md` append-only. Clean tree,
hard stop on `git_dirty`. Driver `analysis/finnhub_probe.py` committed before
it produces output. No version guard needed — record that it was skipped and
why.

## 4. Step 1 — which endpoints does this key reach? (about 6 calls)

Call each of these once for a large, well-covered company (`MSFT`) and record
the HTTP status and whether the body is populated or an access error:

| endpoint | what it would give us |
|---|---|
| `/stock/earnings` | **the main event** — historical EPS actual vs estimate and the surprise |
| `/stock/eps-estimate` | forward earnings estimates by quarter |
| `/stock/revenue-estimate` | **forward revenue estimates** — the field the $99 competitor was going to be bought for |
| `/stock/recommendation` | analyst recommendation trend |
| `/stock/price-target` | consensus price target |
| `/stock/metric` | basic fundamentals |

**Report the access status of each in a table. This table is the run's most
important output** — it decides whether anything else is worth doing and
whether a subscription is needed at all.

**If `/stock/earnings` is not reachable, stop after this step and report.**
Everything below depends on it.

## 5. Step 2 — coverage across the corpus (about 60–120 calls)

For every train and tune company after exclusions, call `/stock/earnings` and
record:

- number of quarters returned, and the **earliest and latest period** — the
  corpus starts February 2020, so anything shallower than that is a finding;
- how many have a **populated `estimate`**, and how many a populated `actual`;
- whether a `surprise` or `surprisePercent` field is present and populated.

**Then group by corpus stratum** (S1 large cap, S2 in-scope mixed cap, S3
out-of-scope, S4 failures, S5 continuity) and report the share of quarters
with a populated estimate in each. **This is the number that decides the
purchase.**

**Coverage is measurable whatever the history depth.** If the key returns only
the last four quarters per company, that is still enough to say whether a
company is covered at all. Report coverage on whatever window you get, and
state the window.

**Call these out individually, whatever the group figures say:**

- **INTC, VZ, KHC, SBUX, UPS, SEDG** — large, well-covered names that produced
  most of the catastrophic calls. If coverage is thin here, the hypothesis is
  dead whatever happens elsewhere.
- **EOSE, ENVX, BLDP, AMPX, QS, SUNW** — the speculative and pre-revenue
  names. Report whether the estimate field is populated at all. **For a
  company with no profits an earnings estimate measures an expected loss,
  which says much less than an expected revenue figure** — so if
  `/stock/revenue-estimate` is reachable, probe these names there too and say
  whether it is populated.

**Also check, because it is free and it matters:** do the reported `period`
dates line up with the call dates in our corpus, on the quarters that overlap?
A consensus figure we cannot join to a transcript is not usable. Report the
share that match within a few days and the shape of any mismatch. **A handful
of overlapping quarters is enough to establish whether the join works** — this
is a plumbing check, not a sample-size question.

**And establish the actual history depth per endpoint.** Ask for a long range
and report what comes back: the earliest period returned, whether a `from`/`to`
or `limit` parameter extends it, and whether the response carries any warning
about the free plan. **If any endpoint returns more than about a year, say so
prominently** — it changes the arithmetic above.

## 6. Step 3 — the look-ahead question, and it is decisive

A consensus figure is only usable if it is **the estimate as it stood before
the company reported**, not a value restated afterwards.

`/stock/earnings` returns the estimate recorded against a past quarter, which
should be point-in-time by construction — but **verify rather than assume**.
State plainly in the wrap-up which of these is true, and how you established
it:

- the estimate is fixed at the announcement and does not change when re-fetched;
- or the field is a current view that could have been revised since.

**If you cannot establish which, say so.** Using a restated consensus would
hand the analyst the future, which is exactly the class of error the
entry-price test caught in our own scorer.

## 7. Report step

**Scope boundary: report, do not decide.** Do not build a ledger, do not
recommend a subscription, do not amend the state of play.

Write `wrap-ups/finnhub-coverage-probe-out.md`, three forms (`.md`, `.docx`
with real Word tables, published artifact page). **Open with §0, defined
terms** — at minimum: consensus estimate, earnings surprise, point-in-time,
coverage, stratum, pre-revenue.

Open the body with this sentence, filled in:

> Of the six endpoints tested, ___ are reachable on the free key, including
> ___ [the earnings history / not the earnings history]. History reached back
> to ___, which is ___ [about a year, as reported / deeper than reported /
> shallower]. Across ___ companies and ___ quarters, a consensus estimate was
> populated on ___% of quarters. For the large companies that produced most of
> our worst calls it was ___%, and for the speculative and pre-revenue names it
> was ___%. Forward revenue estimates ___ [are / are not] reachable. The
> estimates ___ [are / are not / could not be confirmed to be] point-in-time.
> This run used ___ calls. **It did not test the hypothesis, and could not:
> the free window holds six bearish calls.**

Then the endpoint table, the per-company coverage table, the by-stratum
summary, the date-alignment check, and one plain paragraph per finding.

**Close with what it means for the purchase decision, four ways:**

- **Endpoints free, coverage good, history deeper than a year** — the best
  case. Say how deep, and what a full test would cost in calls.
- **Endpoints free, coverage good, history one year** — the expected case.
  Coverage is established, the hypothesis is not testable here, and the
  question becomes which paid tier. Say what Finnhub's paid tiers give against
  the $60 alternative already named in the state of play.
- **Endpoints free, coverage thin on the speculative names** — say which
  companies are uncovered and what a reduced-universe test would look like.
  Note that an earnings estimate for a pre-revenue company measures an
  expected loss, so thin coverage there may matter less than it appears if
  revenue estimates are available.
- **Earnings history is premium** — say so plainly; the $60 recommendation in
  the state of play stands unchanged, and this run cost nothing to confirm it.

**Plain-language discipline is binding.** Anchor every percentage to what it
is a percentage of. Write "points," never "pp." Short sentences. Lead with the
finding. **Luis is an experienced investor and not a statistician; an
explanation that needs a statistics background is a failed explanation.**

## 8. Standing rules

`python3`, zsh, macOS Tahoe. Work on `sweep/db-corpus-baseline`. Provenance for
every figure — endpoint, parameters, and the cached raw file. Never log the
key. One prompt in, one wrap-up out. Commit the driver and `raw/`. If the rate
limit bites, sleep and continue; if you stop, mark the rest `pending` with a
precise `next_action` and say it is a partial run.
