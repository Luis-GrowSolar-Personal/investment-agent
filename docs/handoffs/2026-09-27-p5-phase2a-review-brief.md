# Review brief — P5 phase 2a (tight peer map + co-movement check)

**For:** architect review. **Date:** 2026-09-27.
**Under review:** `prompts/P5-phase2a-tight-map.md` (not yet run, $0 in
model calls).
**Wanted back:** go / change, as `docs/handoffs/2026-09-27-p5-phase2a-review.md`.

---

## What happened since your design review

Phase 1 ran (`wrap-ups/P5-phase1-peer-map-out.md`; $19.24):

- **The map is huge.** 14,348 directional links (7,132 from 10-Ks, 7,216
  from calls). They cover 1,168 of 1,217 train calls (96%). By pair and
  relation: partner 1,784, competitor 1,288, supplier/customer 1,195 each
  way. 2,310 of 5,462 pairs rest on a single mention. Review file:
  `docs/peers/PEER_MAP_REVIEW.csv`, one row per company, peer and
  relation, with counts and the earliest quote.
- **Luis's read: too loose.**
  - AAPL has about 60 links.
  - Some pairs are customer and competitor at once.
  - Many links touch one product line only (AAPL–CHTR on TV content), so
    "CHTR beat, therefore AAPL grows" is a weak read.
  - Mislabels exist too. RUN–Dominion is labelled "competitor" from a
    regulatory dispute.
  - Mention counts alone won't fix it.
- **Your change 3 ran** (phase 1 Step 1). B's ranking **within sector and
  year** is **0.070 and 0.046** on its two runs (both ranges include
  zero), against 0.130 and 0.099 overall. The pre-registered reading is
  "mostly across sectors", so phase 3 gates on the overall comparison and
  only reports within sector-year. Winners cluster in a few sector-years
  (e.g. solar/storage 2025: 8 of 14 calls were big winners). B's
  call-over-call score change ranks at 0.075 and 0.020.

## What the phase 2a prompt does

1. **Tight rule, fixed before any check.** A link enters only as one of:
   - **S1:** a customer or supplier named in a 10-K, any sector;
   - **S2:** a customer or supplier named in 3 or more calls;
   - **C1:** a competitor that is **same sector group**, named **by the
     target itself** or by both sides, with 2 or more sources.

   Partners, "other" and hand links are out. At most 3 peers per target,
   ordered S1, then C1, then S2. Validity starts when a count threshold
   is first met. The coverage stop stays at 300.
2. **Co-movement check ($0, can stop P5).** Weekly-return correlation over
   the 52 weeks before each tight link's qualifying date. Tight pairs are
   compared with random **same-sector** pairs and random pairs. P5
   continues only if tight minus same-sector has its range above zero.
   Price data is used to judge the rule, never to select links, and never
   reaches the analyst.
3. **Cost count.** Distinct peer calls to digest at 3 and at 5 peers,
   split into on disk and to fetch, with projected cost. **It stops for
   Luis's approval.**
4. **Two phase 1 gaps:** a count of anonymised customers, and XOM's
   10-Ks.

## Questions for you

1. **Is the tight rule right?** In particular:
   - Is **C1's same-sector requirement** too blunt? It uses the SIC-based
     group in `docs/peers/SECTOR_MAP.csv`. It drops AAPL–CHTR, but may
     also drop real cross-sector rivals.
   - Is **S2's 3-call threshold** enough, given call mentions include
     things like "Walmart uses Cosmos DB"?
2. **Is the co-movement check sound as a gate?**
   - Its window ends before the link's qualifying date, so it should be
     hindsight-free for the returns themselves.
   - But links named more often may simply be between companies that
     already co-move. Does that bias the check in P5's favour?
   - Is "tight minus random same-sector, range above zero" the right bar?
3. **Does the within-sector result change P5's phase 3 gate?** Your change
   3 said to fix the comparator from it, and the fixed reading gates
   overall. But Luis's portfolio is concentrated in a few sectors, and
   within-sector is where he'd use peer information (ENPH vs SEDG).
   Should P5 be **gated** within sector-year as well? Or is the sample
   too thin for that (cells of 12–40 calls)?
4. **Peer cap: 3 or 5?** The design said 5. The prompt selects 3 and
   reports 5.

## Read

- `prompts/P5-phase2a-tight-map.md` (the prompt under review)
- `wrap-ups/P5-phase1-peer-map-out.md`
- `docs/peers/PEER_MAP_REVIEW.csv` (look at AAPL, MSFT, RUN, ENPH/SEDG, NVDA)
- `docs/handoffs/2026-09-26-p5-peer-readthrough-design.md` (with Addendum A)
- `docs/handoffs/2026-09-26-p5-design-review.md` (your previous review)
- Background, if needed: `docs/handoffs/2026-09-26-state-of-play.md`
