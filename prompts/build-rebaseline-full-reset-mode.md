# Build: "Full reset" mode for the re-baseline modal

## Report your findings

Write a wrap-up to
`./wrap-ups/build-rebaseline-full-reset-mode-out.md`. State up front what
was built and where. Include: the exact new option flag name and how it
flows from the UI toggle through the PATCH/confirm call to
`computeMovesPayload`; a sample of the generated moves for one owner
(pick whichever of Andrea/Eduardo/Luis produces the most interesting
diff — ideally one with several held equities that get replaced) showing
SELL rows for tickers dropped from the fresh build, ADD/TRIM rows for
tickers that make the cut at a new size, and confirmation that ETF/
Crypto/Commodities/Cash math is completely unaffected by the mode. Read
the full current source of `server/routes/moves.js` and
`client/src/pages/PortfolioManager.jsx` before writing any code — this
prompt describes intent and constraints, not exact variable names; this
file has grown across many sessions and the real current shape may not
match what's assumed below. Write for someone reading cold later.

## Context — what exists today

Re-baseline (`bypassWinnerProtection: true`) is an incremental reset:
existing equity holdings are kept and sized to model weight, watchlist
candidates only fill genuine underweight gaps, exactly the same
Layer-3→2→1 candidate-ranking/funding logic used in normal (non-
re-baseline) move generation — see `docs/architecture/DESIGN_PRINCIPLES.md`
Principle 2 (find → classify → enforce, trim proceeds must have a
destination before the trim executes) and Principle 9 (existing
positions before new — `buildCapitalFlow`'s `addUses` before `promUses`).

Luis wants a second, distinct mode on the same modal: **"Full reset"** —
assume every currently-held position is sold to cash, then rebuild the
equity side of the portfolio purely from the highest-conviction eligible
watchlist/portfolio candidates, with **zero preference for what happens
to already be held**. Confirmed explicitly by Luis: "No preference to
what's currently held" — this is a deliberate, one-time override of
Principle 9, scoped to this mode only. Normal (non-full-reset) moves
generation and normal re-baseline must be completely unaffected.

**Scope: this only changes equity (Established/Speculative) funding.**
ETF, Crypto, Commodities, and Cash are fixed-target pinned tickers
(SPY/QQQ/GLD/SLV/IBIT-style, sized via `fixedTargetMap`/
`splitBucketTarget`), not a competitive candidate pool — there is no
"best idea" to rank among them, so full-reset mode must leave their
funding logic completely untouched. Confirm this in the wrap-up with a
reconciliation-script run showing those buckets unchanged.

## Behavior — no new execution risk

Full reset does **not** need a new execution/trade path. Today,
`RebaselineModal`'s "Confirm & generate moves" already just computes a
move set and writes it to `MovesCache` (optionally with `persist: true`)
— nothing is sold until the user individually accepts each row in the
Moves tab's existing Accept/Decline flow. Full reset reuses exactly that
architecture: it's a different move-generation algorithm feeding the
same confirm → cache → Accept/Decline pipeline. If the user opens the
modal, reviews the full-reset preview, and closes without confirming (or
confirms but then declines every row), nothing changes — the next time
the modal opens it reads current actual holdings, same as always. Luis
was explicit about this and it should hold with zero extra work, since
it falls out of the existing architecture — just don't accidentally wire
confirm to anything that skips the per-row accept/decline step.

## The algorithm change

For Established and Speculative equities only, when full-reset mode is
active:

1. **Determine the candidate universe** the same way normal ADD-gap
   funding already does today (same domain filter per
   `docs/architecture/DOMAIN.md`, same Type A/B cap classification, same
   `recommendation === 'buy'`-type eligibility gate, same conviction/
   thesis-health ranking) — reuse whatever ranking function currently
   selects new-open candidates for underweight gaps (likely inside
   `sizeSide` / `computeIndividualModelWeights` or wherever
   `computeMovesPayload` currently sources ADD candidates for a side).
   **Do not invent a new ranking scheme** — the only change is that this
   ranking gets applied against the FULL bucket-side target dollar
   amount, not just the leftover gap after crediting existing holdings.
2. Greedily fill each side's full target dollar amount from that ranked
   list (same greedy-array-order mechanism `buildCapitalFlow` already
   uses elsewhere), respecting each candidate's own Type A/B cap and
   `minPositionDollar` floor, completely ignoring whether a given ticker
   is currently held.
3. For every currently-held equity ticker that is **not** part of the
   resulting fresh-build selection: generate a full-liquidation SELL
   move (100% of the position, not a partial trim) tagged
   `isFreshStartSell: true`. This still needs its own explicit tax cost
   calculation (Principle 5 — "every trim recommendation includes
   explicit tax cost calculation"; this is the case where that matters
   *most*, not an exception to it) and should still respect
   tax-advantaged-account-first sequencing for which account's shares
   are cited in the move, consistent with how existing trim moves cite
   accounts today.
4. For every currently-held equity ticker that **is** part of the
   fresh-build selection: generate the normal ADD/TRIM/HOLD move sizing
   it to its new target weight — same as today's re-baseline sizing
   logic, just fed by the full-reset candidate list instead of the
   existing-holdings-first list.
5. Tickers that make the fresh-build cut but aren't currently held at
   all: normal new-open ADD move, same as today's watchlist-promotion
   path.

## Frontend — `client/src/pages/PortfolioManager.jsx`, `RebaselineModal`

Add a two-option segmented control (not a checkbox — it's a mode, not an
add-on flag) directly under the modal's subtitle, above the "TARGET
MODEL" section:

```
[ Rebalance existing ]   [ Full reset — sell all, rebuild from best ideas ]
```

- Default to "Rebalance existing" every time the modal opens — not
  sticky/remembered across sessions, given how consequential the other
  option is.
- When "Full reset" is selected, show a warning banner above the Current
  vs Target table: something like *"This will generate a SELL for every
  currently held equity position not selected in the fresh build, and
  rebuild your equity holdings from your highest-conviction watchlist
  names. All gains and losses on sold positions will be realized. ETF,
  Crypto, Commodities, and Cash are unaffected."*
- Gate the confirm button behind a second explicit checkbox in this mode
  — "I understand this liquidates equity holdings not selected in the
  fresh build" — unchecked by default, confirm button disabled until
  checked.
- Relabel the confirm button when in this mode (e.g. "Confirm & generate
  full reset") so it's unmistakable which mode is about to run.
- The Current vs Target bucket-level table itself doesn't need
  mode-specific math — bucket targets are identical in both modes, only
  the underlying per-ticker move set differs once confirmed. Don't
  overbuild this; the table can stay as-is.

Wire the selected mode through the confirm call to the backend as an
explicit option (pick a clear flag name, e.g. `freshStart: true`,
distinct from `bypassWinnerProtection` which should remain `true` in
both modes — full reset still needs winner-protection bypassed, plus
this new behavior on top).

## Backend — `server/routes/moves.js` / `computeMovesPayload`

Read the current signature and the `bypassWinnerProtection`-gated logic
before adding anything. Add a new option (e.g. `freshStart`) that,
when true, switches on the algorithm above for the equity funding path
only, leaving every other code path (fixed buckets, cash, ETF/Crypto/
Commodities) exactly as it runs today regardless of this flag.

## Verify

Run `./server/scripts/verify-allocation-math.sh` before and after, on an
owner exercised with `freshStart: true` (you'll need to either add a
temporary way to invoke it directly the way the script already calls
`computeMovesPayload`, or extend the script's owner loop to also run a
`freshStart` pass — your call on the cleanest way to do this without
permanently bloating the script). Expect:
- ETF/Crypto/Commodities/Cash: identical PASS/FAIL pattern to normal
  re-baseline for the same owner — this mode must not touch that logic.
- Established/Speculative: the reconstructed bucket totals should still
  reconcile against `targetValue` the same way normal re-baseline does
  (same tolerance-band caveats as always) — the point of full-reset is a
  different *selection* of tickers, not different bucket math.

Also manually sanity-check one owner's full move list: every currently-
held equity ticker should appear exactly once, either as a normal
resize move or as an `isFreshStartSell`, never both, never omitted.

## Commit and push

You have real local git access — commit and push this yourself, Luis
doesn't want to hand-run git commands:

```bash
git add -A
git commit -m "Add full-reset mode to re-baseline: rebuild equities from scratch by conviction, no preference to currently held"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

## Reminder: write the wrap-up

Don't finish without `./wrap-ups/build-rebaseline-full-reset-mode-out.md`
existing, with the sample move list and script output included.
