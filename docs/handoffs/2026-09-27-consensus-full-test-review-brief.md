# Review brief — consensus-surprise full test (57 train companies)

**For:** architect review. **Date:** 2026-09-27.
**Under review:** `prompts/consensus-surprise-test.md` (one session, $0
marginal; premium Alpha Vantage key `AV_API_KEY_PREMIUM`).
**Wanted back:** go / change, as `docs/handoffs/2026-09-27-consensus-full-test-review.md`.

**Why it matters.** This is the **last documented route to finding
winners** we have data for. If it fails, the machine's role is settled
as downside protection, and picking winners stays with Luis. If it
passes, it is the first bullish signal in the project, and it shapes the
allocator and Layer 3.

---

## Where the screen left it

`wrap-ups/consensus-surprise-screen-out.md`: 20 winner-rich train
companies, 439 matched calls, with your three review changes applied.

| | result |
|---|---|
| Median quarter-adjusted surprise | winners +0.0097 · middle +0.0005 · losers −0.0215 (the order the mechanism predicts) |
| **Winners − middle (primary)** | **+0.0092, range −0.0236 to +0.1341** → "does not", by a hair |
| Surprise alone, ranking 6-month returns | 0.074 (−0.022 to 0.161); the sample could detect about 0.09 |
| **Surprise + B combined** | **0.138 (0.049 to 0.224), clears zero**; combined − B +0.047 (−0.034 to +0.129) |
| Within sector-year | **−0.001** |
| By year | unstable: 2024 −0.22, 2025 +0.37 |
| Relation to the failed announcement-day move | 0.203 (so the closing exception did not apply) |
| Within-company | 12 of 20 companies had bigger surprises on winner calls (50% by chance) |
| Flagged small-EPS companies | EOSE, JKS, RUN. Excluding them makes every figure slightly stronger |

**Point-in-time:** 3 quarters verified in Cowork against coverage from
the time (JPM Q1 2023, MU fiscal Q1 and Q2 2023). The screen's five
extreme rows for checking were all EOSE or JKS.

## Changes made after the screen (Cowork; reported only, readings unchanged)

- A **sector-and-quarter adjusted** surprise, reported beside the
  primary, because within sector-year was −0.001.
- Spot-checks: 3 extremes from flagged companies **plus 5 from unflagged
  companies**.
- The screen's 20 fetches are reused; about 33 new fetches; one session
  on the premium key.

## Questions for you

1. **One primary reading?** The prompt carries three separate readings
   ("drift present", "finds winners", "adds to B"), plus the three-group
   winners-vs-middle comparison. The screen already split: the primary
   failed by a hair while "combined with B" cleared zero. With four
   chances, one may pass by luck. **Should we declare now which single
   reading decides "first bullish lead"**, with the rest reported? If so,
   which one?
2. **Should the sector-and-quarter adjustment be a gate, not a report?**
   Luis's portfolio sits in a few sectors, and within sector-year the
   screen showed nothing. A signal that exists only across sectors is
   sector timing, not company picking. Should a pass require the
   sector-adjusted version to hold as well? Or should the sector-only
   case be read as "useful for the allocator, not for picking"?
3. **Does the screen contaminate the full test?** 20 of the 57 companies,
   and 439 of about 1,200 calls, were already seen, and the screen's
   result drove the decision to continue and the post-screen additions.
   Report the 37 unscreened companies separately as a clean check? Or
   accept the pooled result?
4. **Point-in-time.** The reading drops to "can't tell" if any checked
   extreme row is found revised. Are 8 hand-checks (3 flagged, 5
   unflagged) the right number, and should they be done **before** the
   verdict is written, not after?
5. **The next step if it passes.** Pre-register the tune test now, in this
   review, rather than after seeing train? The premium key makes tune a
   same-day run.
6. **Anything else** that would make a pass or a fail here misleading.

## Read

- `prompts/consensus-surprise-test.md` (its "Review amendments" section
  carries your last review plus item 6, the post-screen additions)
- `wrap-ups/consensus-surprise-screen-out.md`
- `docs/handoffs/2026-09-27-consensus-screen-review.md` (your last review)
- Background: `wrap-ups/P5-close-sector-and-drift-out.md`,
  `wrap-ups/winners-missed-v3-out.md`, `docs/handoffs/2026-09-26-state-of-play.md`
