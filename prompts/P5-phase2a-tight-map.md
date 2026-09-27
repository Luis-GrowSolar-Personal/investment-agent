# P5 phase 2a — tighten the peer map, check that news passes from peer to target, count what phase 2 would cost. $0

**Revised after review** (`docs/handoffs/2026-09-27-p5-phase2a-review.md`): Step 2's control is drawn from the peer's sector; Step 2's gate is lead-lag, not co-movement; the scorer's cache is named; the C2 mutual-competitor rule is added. Two Cowork additions are marked in Step 2.

**Run ID:** `p5-phase2a`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P5-phase2a-tight-map-out.md`
**Cost: $0 in model calls.** At most **400 SEC EDGAR requests** (industry
codes for non-corpus peers; XOM's 10-Ks). **No vendor calls. No Claude
API calls. No scoring. No digests.**

---

## Framing

Phase 1 (`wrap-ups/P5-phase1-peer-map-out.md`) built a point-in-time peer
map of 14,348 links covering 96% of train calls. Reading it
(`docs/peers/PEER_MAP_REVIEW.csv`), Luis judged it **too loose**:
- AAPL alone has about 60 links;
- some pairs are customer and competitor at once;
- many links touch one product line only, e.g. AAPL and CHTR on TV
  content.

Mention counts alone don't fix that. A company can be named ten times
for something trivial.

**Decided 2026-09-27 (Luis).** Tighten by **who names the link and
where**, not only how often. Then check that a linked peer's news
actually reaches the target's price, before any money is spent on
digests.

This run does three things:
1. applies the tight rule;
2. runs a $0 lead-lag check that can **stop P5**;
3. counts the digests phase 2b would need and projects their cost, **then
   stops for Luis's approval**.

**Read first:** the design doc and its review; the phase 1 wrap-up (all);
`analysis/p5p1_build_map.py`, `p5p1_coverage.py` (extend; do not fork);
`analysis/data/run_state/p5-phase1/peer_links.csv`, `filings_index.json`;
`docs/peers/SECTOR_MAP.csv`.

## Ground rules

1. **$0 in model calls.** No digests, no scoring, no tune or holdout
   returns.
2. **Price data of other companies is used here to check the map rule,
   never given to the analyst.** The firewall amendment (design §2) bars
   price data about other tickers from the analyst's input. This run
   only measures whether a fixed rule's links carry price information
   from peer to target. It never selects or drops an individual link on price.
3. **The tight rule below is fixed before any price number is
   computed.** Do not tune it after seeing the check.
4. Report, do not decide.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/p5-phase2a/`. `progress.json` first.
Commit, each as its own commit:
1. this prompt;
2. `docs/peers/PEER_MAP_REVIEW.csv`, if untracked (a review aid made in
   Cowork from `peer_links.csv`).
3. `docs/handoffs/2026-09-27-p5-phase2a-review-brief.md` and
   `docs/handoffs/2026-09-27-p5-phase2a-review.md`, if present. **If the
   review file exists and asks for changes that are not reflected in this
   prompt, stop and report. Do not apply review changes yourself.**

Any other modified or untracked file → stop and report. Clean tree.
Scripts committed before output.

---

## Step 1 — the tight rule (fixed now)

**Who named it.** For each link, determine the **source owner**, meaning
the company whose document or call it came from:
- a `CALL` link's `source_id` is `TICKER_date`;
- a `FILING` link's owner comes from `filings_index.json`, by accession.

Normalise tickers through `TICKER_ALIASES.json`.

**Peer industry codes.** `SECTOR_MAP.csv` covers corpus companies only.
For every **non-corpus peer** that survives the other rules, fetch its
EDGAR SIC code (submissions JSON, one request each, 1 per second,
`SEC_USER_AGENT` from `.env`). Map it with the same SIC-to-group table.
Peers with no EDGAR entry (foreign, private) get group `unknown`.

**A link enters the tight map only if it meets one of these:**

- **S1, supply chain from a filing.** Relation CUSTOMER or SUPPLIER, and
  at least one `FILING` source. Either company's filing counts. Any
  sector.
- **S2, supply chain from calls.** Relation CUSTOMER or SUPPLIER, named in
  at least **3 distinct calls** (either company's). Any sector.
- **C1, competitor.** Relation COMPETITOR, **and** the two companies share
  a **sector group** (`final_group`; `unknown` never matches), **and**
  either:
  - the **target company itself** named the peer (its own 10-K or its own
    call), or
  - both companies named each other,

  **and** at least **2 sources** in total.
- **C2, mutual competitors (review, 2026-09-27).** Two companies that
  **each** name the other as a competitor, in **2 or more sources each**,
  enter as competitors **regardless of sector group**. Selection order
  treats C2 like C1.

**Always excluded:** PARTNER, OTHER, and `HAND` links. Hand links stay a
separate, reported-only layer, as in phase 1.

**A pair that is both supply chain and competitor:**
- if it qualifies under S1 or S2, it enters as supply chain;
- set `dual_role = true`, so the phase 2b digest header can say so.

**Validity dates are unchanged from phase 1.** A link applies only from
its first qualifying source date. For S2 and C1 that is the date on
which the **count threshold was first met**, never earlier.

**Peer selection per target call (train), at most 3 peers:**
1. Eligible means: valid on the target's date, and with a call dated
   **strictly before** the target within **120 days**, readable per phase
   1 (on disk, or confirmed in the vendor's event list).
2. Order: **S1 first, then C1 and C2, then S2.**
3. Ties: more distinct sources first, then the most recent peer call.

Output:
- `peer_links_tight.csv` (phase 1 columns plus `rule`, `source_owner`,
  `dual_role`, `qualified_from`);
- `target_peers.csv`: one row per train target, up to 3 peers, with rule
  and dates.

**1b. Coverage under the tight rule:**
- train calls with at least 1 selected peer: total, by rule, by sector
  group;
- the mean number of peers per covered call;
- links per company, before and after, for the 10 most-linked companies.
  Show AAPL explicitly;
- AAPL's surviving peers, listed with rule and one quote each.

**Stop rule, unchanged (design §3):** fewer than **300** covered train
calls → P5 stops.

## Step 2 — does news pass from peer to target? ($0; review changes 1–2)

**Prices:** use `analysis/data/corpus_v2/scorer_price_cache_v1.json` (the
scorer's frozen cache) for every figure in this step. Do not fetch
prices. Name the cache in the wrap-up.

**Whose prices may be read (Cowork addition 2, holdout integrity):**
- **train peers:** yes;
- **tune peers:** only the short reaction window `x` below. Tune's 182-day
  windows stay unread;
- **holdout peers:** **no.** Pairs with a holdout peer are excluded from
  this step and counted;
- **non-corpus peers:** no prices in the caches. Excluded and counted.

Report how many `target_peers.csv` pairs each exclusion removes, and the
share of covered train targets the check could score. **The reviewer's
standard applies: a pass on a minority of pairs is not a pass on the
map.** State the scored share next to the verdict.

**The lead-lag check, per (target call, selected peer call) pair:**
- **x, the peer's reaction.** The peer's return against SPY from the
  **last close before the peer's call** to the **third close after it**.
  (Cowork addition 1: starting at the pre-call close captures the
  announcement-day move. Starting at the tradeable entry would miss it,
  because that first close after the call already contains the day-one
  reaction.)
- **y1, what reached the target before its call.** The target's return
  against SPY over the **same start**, the peer's pre-call close, to the
  **last close before the target's call**. Report the number of pairs
  whose y1 window is under 5 trading days.
- **y2, P5's grading window.** The target's 182-day return against SPY
  from its own tradeable entry. Train targets only.

**Control (review change 1).** For each pair, draw a control peer:
- from the **peer's** sector group, not the target's;
- **excluding every phase 1 peer of the target**, not only its tight
  peers;
- with a call dated within ±10 days of the real peer's call;
- train or tune only, with seed `p5-2a-11`.

Compute its x the same way, on its own call dates. Pair it with the same
y1 and y2.

**Report,** as rank correlations with ticker-block ranges (2,000 draws,
seed 11), overall and split by rule (S1, S2, C1):
- x→y1, tight and control, and **tight minus control**;
- x→y2, tight and control, and tight minus control.

**Pre-registered reading, fixed now:**
- **Gate: x→y1, tight minus control, range above zero → "links
  transmit".** Continue to Step 3. Otherwise **P5 stops**: nothing
  observable passes from peer to target, and a digest will not find what
  the price did not.
- **Reported, not gated: x→y2.** If it is positive, the peer's price
  reaction is already a $0 signal. Phase 3 must read P5's gain against
  it, and the allocator rebuild gets it as a candidate input.
- **Reported, not gated: co-movement.** Weekly-return correlation over
  the 52 weeks before `qualified_from`, tight against the peer-sector
  control above. For the allocator's correlated-positions question.

## Step 3 — what phase 2b would cost (only if Step 2 continues)

Count the **distinct peer calls** that `target_peers.csv` would need
digested, at the 3-peer cap, and for information at a 5-peer cap with the
same ordering:
- how many are on disk (train or tune transcripts);
- how many must be fetched from the vendor (holdout or non-corpus). Rate
  limits only: EarningsCall is flat-rate, 20 calls per minute, so give
  the fetch time;
- **the projected digest cost.** Measure the token length of 30 of the
  needed transcripts, on disk or already fetched in phase 0. Price one
  digest at `claude-sonnet-4-6` batch rates with about 300 output
  tokens, and multiply. Give a range.

**Then stop.** Write the wrap-up and let Luis approve the digest spend and
the peer cap before phase 2b is written.

## Step 4 — two small gaps from phase 1 ($0, SEC requests only)

- **Anonymised customers.** A regex pass over the saved 10-K texts: count
  filers per year disclosing "one customer" / "a single customer" /
  "Customer A" with a revenue percentage. Report the count and 5 quotes.
  No model.
- **XOM.** Fetch its 2019–2025 10-Ks under the pre-2025 CIK, at most 20
  requests. Say whether any link would change. **Do not re-run
  extraction.** Just report what the 10-Ks' competition and customer
  sections name, by heading search.

---

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/P5-phase2a-tight-map-out.md`, `.md` only. Open with:

> Under the tight rule, the peer map keeps ___ links (from ___), and ___ of
> 1,217 train calls have at least one selected peer (___ via filings
> supply chain, ___ via competitors, ___ via call supply chain); AAPL goes
> from ___ links to ___. A peer's reaction to its own call predicted the
> target's move before the target's call at ___, against ___ for matched
> control peers (difference ___, range ___ to ___), scored on ___% of
> covered targets: **[links transmit / P5 stops]**. Against the target's
> next six months the same figure is ___ (control ___). [If continuing:] Phase 2b needs ___
> distinct peer digests (___ on disk, ___ to fetch), projected at $___–___.

Then Steps 1–4 in detail, AAPL's surviving peers with quotes, and SEC
requests used.

**Close with what it means, both ways.**
- **Links transmit:** the numbers Luis needs to approve phase 2b (peer cap,
  digest spend, fetch time).
- **P5 stops:** Say whether the tight map is still worth
  keeping as an allocator input for correlated positions.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure. One prompt in, one wrap-up out. **Finish with
`git push`** after the wrap-up commit, and report the pushed hash; on
failure, say so and never force.
