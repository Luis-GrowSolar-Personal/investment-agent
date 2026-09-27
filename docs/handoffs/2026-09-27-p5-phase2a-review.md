# P5 phase 2a — review

**Reviews:** `docs/handoffs/2026-09-27-p5-phase2a-review-brief.md` and
`prompts/P5-phase2a-tight-map.md`. **Verdict: change.** Two changes to
Step 2, one small fix. The tight rule (Step 1), the cost count (Step 3)
and the gaps pass (Step 4) go as written.

---

## Change 1 — the control group is mismatched for cross-sector links (error)

Step 2 compares a tight pair against a random company from the
**target's** sector. S1 and S2 links are allowed across sectors. So an
AAPL–chip-supplier pair is compared with AAPL against a random consumer
hardware name. Two companies in the same industry co-move because of the
industry, so the control pair will usually co-move **more** than a real
cross-sector link. The gate would then read "sector noise" on exactly the
links that bring information a sector label does not, and stop P5 for
the wrong reason.

**Fix.** For each tight pair (target T, peer P), draw the control from
**P's** sector group, not T's: a random company in the peer's industry
that is not linked to T in the loose phase 1 map either. The question
the control answers is then the right one: "is this named company more
tied to T than any other company in the same line of business?" For C1
the two sectors coincide, so nothing changes there.

Same fix for the exclusion list: exclude **every** phase 1 peer of T from
the control draw, not only its tight peers, or the control will contain
real links.

## Change 2 — co-movement is not the hypothesis P5 tests (material)

Weekly-return correlation says whether two stocks move **together**. P5
needs something else: that the peer's call, reported **earlier**, says
something about the target's **later** return. Two stocks can share a
beta and tell each other nothing in advance. And the reverse: a
supplier's numbers can lead its customer by a quarter while the two
stocks barely co-move week to week. A gate on co-movement can pass a map
that carries no lead information, and fail one that does.

The lead-lag version costs the same $0 and uses the same price caches.

**For each (target call, selected peer call) pair in `target_peers.csv`:**
- **x** = the peer's return against SPY over the three trading days
  from the peer's tradeable entry (first close after its call).
- **y1** = the target's return against SPY from that same entry to the
  close before the **target's** call. This is the window in which the
  peer's news can reach the target's price.
- **y2** = the target's 182-day return against SPY after its own call,
  tradeable entry. This is P5's grading window.

Report the rank correlation of x with y1 and with y2, with a
ticker-block bootstrap (2,000 draws, seed 11), split by rule (S1, S2,
C1). Control: the same x from the matched control peer's call (change
1), same dates.

**Reading, fixed now.**
- **Gate:** x→y1, tight minus control, range above zero → "links
  transmit". Continue to Step 3. Otherwise P5 stops: nothing observable
  passes from peer to target, and a digest will not find what the price
  did not.
- **Reported, not gated:** x→y2. If it is positive, the peer's price
  reaction is already a $0 signal for the allocator, and P5's gain in
  phase 3 must be read against it.

Keep the contemporaneous correlation (Step 2 as written, with change 1
applied) as a **reported** line, not the gate. It is useful for the
allocator's correlated-positions question, which the prompt already asks
in the close.

Non-corpus peers have no prices in the caches. Report how many pairs the
check could not score for that reason, and the coverage of the pairs it
did score. A pass on 40% of pairs is not a pass on the map.

## Small fix

Step 2 uses `analysis/data/corpus_v2/corpus_v2_price_cache.json`. The
scorer's frozen cache is `scorer_price_cache_v1.json` in the same folder.
Name which one the returns come from and use the same one for x, y1, y2
and the co-movement line.

---

## Answers to the brief's questions

1. **Tight rule.** Right as written. C1's same-sector test is blunt, but
   the "target named it" condition is doing the real work. One
   exception worth adding: two companies that **each** name the other as
   a competitor, in two or more sources each, enter regardless of sector
   group. Mutual naming is stronger evidence than a SIC table. S2's
   3-call threshold: accept. "Walmart uses Cosmos DB" is a customer named
   by the seller; three separate calls naming the same customer is a
   reasonable stand-in for the 10% rule filings apply. If it lets
   trivia through, the lead-lag split by rule will show S2 at zero, and
   the cap ordering already puts S2 last.
2. **Co-movement as a gate.** Not sound as written, for the two reasons
   above. The hindsight point is fine: windows end before
   `qualified_from`. The "links named often already co-move" worry is
   real for co-movement and mostly disappears under the lead-lag form,
   because a shared beta does not produce lead-lag.
3. **Within sector-year.** Do not gate there. B's within-group ranking
   (0.070 and 0.046, both ranges include zero) is below the 0.10 bar the
   state of play §4a set, so the comparator stays B's overall ranking.
   Cells of 12–40 calls cannot carry a gate. Report P5 within
   sector-year, pooled across cells, as the phase 1 script already
   does. If P5 passes overall and the within-sector line is also
   positive, that is the result that matters for a concentrated
   portfolio; if it passes overall and within-sector is flat, say so
   plainly in the wrap-up.
4. **Cap.** 3 selected, 5 costed is right. Digests are ~200 words, so 5
   is not a token problem; decide the cap on the Step 3 count and on
   how many targets actually have a fourth or fifth eligible peer.

## What it means

If the lead-lag gate passes, phase 2b spends on digests for links that
are shown to carry information forward in time, and phase 3 has a $0
price-only reference (x→y2) to beat. If it fails, the tight map goes to
the allocator as a correlation input and no more prompt money is spent
on P5.
