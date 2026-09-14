# Opening prompt — next session

Paste the block below into a new Cowork session titled
**"Analyst value attribution — contribution vs headroom"**.

---

Read `docs/handoffs/2026-09-13-analyst-value-question.md` first, then
`docs/handoffs/2026-09-07-state-of-play.md` for the broader state. Branch is
`sweep/db-corpus-baseline`.

The short version: Test 2's wrap-up was filed "inconclusive by design" as a
look-ahead probe, but its unread `lift` column is the promotion gate's §3.1
metric already computed — and it says v6 underperforms its baseline by roughly
−5.8pp across 359 calls, with bearish-call accuracy of 8.3%–24.0% every year.
Test 1 separately says the analyst is worth ~$59k over a zero-information arm.
Reconciling those two is the open question.

`prompts/value-attribution-and-headroom.md` is written and ready to run ($0
Anthropic API spend). I have not run it yet. Its Step 0 is a hard gate on two
unverified premises — what `baseline` actually means in
`analysis/analyst_direct_scorer.py`, and whether those 359 rows were v6-scored.
Treat −5.8pp as provisional until Step 0 clears; a clean stop at Step 0 is a
successful run.

What I want from you:

1. Read the prompt critically before I run it. Challenge the design — the
   permutation test's within-ticker constraint, the P&L attribution convention
   in Step 1, and whether the oracle arm in Step 4 actually bounds what I think
   it bounds. Tell me what it gets wrong.
2. Once it runs, read `wrap-ups/value-attribution-and-headroom-out.md` and
   interpret it.

I don't need softening or reassurance. Challenge my framework, and hold your
positions under pushback unless I give you specific new evidence. Track the
token budget and tell me at ~85% so I can hand off cleanly.

Two open corrections carried in from the last session, both in the handoff:
v10+auto1 was tested more thoroughly than that session initially claimed, and
v6 scores 37.5% — not 60% — on the current full-history basis. Don't repeat the
older framing.
