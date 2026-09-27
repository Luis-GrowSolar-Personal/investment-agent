# Review brief — consensus-surprise screen

**For:** architect review. **Date:** 2026-09-27.
**Under review:** `prompts/consensus-surprise-screen.md` (one day, $0),
and the full test it feeds, `prompts/consensus-surprise-test.md` (about
3 days, $0).
**Wanted back:** go / change, as `docs/handoffs/2026-09-27-consensus-screen-review.md`.

---

## Why this test, now

Every route to **finding winners** has failed:

| route | result | wrap-up |
|---|---|---|
| Prompt changes (v6 rubric, P7 three voices) | no bullish signal | `P7-three-voices-train-out.md` |
| B's own notes (beat-and-raise, balance) | not seen; beat-and-raise halves big losers, doesn't make winners | `winners-missed-v3-out.md` |
| Opus | sharper on the downside, no better on winners | `opus-screen-out.md` |
| P5 peer read-through | stopped at the map gate; the peer's reaction predicts nothing over 6 months (0.005) | `P5-phase2a-tight-map-out.md` |
| Sector average of B | no gain (0.030 vs B 0.110) | `P5-close-sector-and-drift-out.md` |
| The stock's own announcement-day move | no drift (−0.033); combining with B made B **worse** | same |

The one documented route left is **surprise against analyst consensus**.
It was historically the stronger form of post-earnings drift, though it
has faded.

## The data

- Alpha Vantage's free `EARNINGS` endpoint gives reported EPS, estimated
  EPS and surprise per quarter, back to 2019 or earlier (probe: MU, RUN,
  JPM, 30 of 30 quarters since 2019).
- **Point-in-time check, done in Cowork against coverage from the time:**
  - JPM Q1 2023: $3.41, matching Refinitiv in CNBC's preview the morning
    of the report;
  - MU fiscal Q1 2023: −$0.02, matching TipRanks;
  - MU fiscal Q2 2023: −$0.88, against previews of −$0.67 to about
    −$0.85.
- None looks revised after the fact, **but it is three quarters**.
- The free tier allows 25 requests a day. One request is a company's full
  history.

## The design

- **Surprise measure:** (reported EPS − estimated EPS) ÷ the share price
  at the last close before the call. Percentage surprise explodes near
  zero EPS (RUN shows +1,471%).
- **Outcome:** the usual 182-day return vs SPY from the tradeable entry.
  The surprise is known before entry; the run asserts no overlap.
- **Screen (today, 20 companies), Luis's design, 2026-09-27.** Choose
  the train companies with the most **big-winner** calls (+20 points or
  more; at least 2 winners and 6 other calls each). Then compare, **inside
  those companies**, winner calls against the same companies' other
  calls:
  - beat rate;
  - median price-scaled surprise, with a company-block range;
  - the share of companies where winners had bigger surprises (against
    50%).
  - **Primary reading:** "surprise separates winners" if the median
    surprise difference has its range above zero. Market-wide rates from
    this winner-rich sample are reported and labelled **inflated by
    design**.
- **Full test (57 train companies, about 3 days free):**
  - rank correlation of surprise with the 6-month return;
  - top-19% big-winner share against 12.6%;
  - combined with B (does it add?);
  - beat two quarters running;
  - by year and within sector-year;
  - how closely surprise relates to the failed announcement-day move.

  Readings are fixed in the prompt. A pass earns a pre-registered tune
  test, and promotes nothing.

## Questions for you

1. **Is the winner-rich, within-company screen valid** for "does surprise
   separate winners?" In particular:
   - Does selecting companies on outcomes bias the within-company
     comparison, e.g. through winner clustering in certain years?
   - Should the comparison be matched on **year** as well as company?
2. **Is price-scaled surprise the right single measure?** Alternatives:
   surprise ÷ the stock's own past surprise spread (the classic
   "standardised unexpected earnings"), or rank within company. Pick one
   before the run.
3. **Point-in-time:** are three verified quarters enough to proceed, with
   5 more listed by the run for manual checking? Or should the full test
   wait on those checks?
4. **Relation to the failed announcement-day move.** If surprise and the
   day-one move are strongly related, should a failed screen close the
   lead outright, rather than only "can't tell"?
5. **Scope:** EPS only, no revenue surprise. Acceptable for a screen?

## Read

- `prompts/consensus-surprise-screen.md` and `prompts/consensus-surprise-test.md`
- `wrap-ups/P5-close-sector-and-drift-out.md` (the announcement-move null
  and the Alpha Vantage probe)
- `wrap-ups/winners-missed-v3-out.md` (beat-and-raise against the
  company's **own** guidance)
- Background: `docs/handoffs/2026-09-26-state-of-play.md`
