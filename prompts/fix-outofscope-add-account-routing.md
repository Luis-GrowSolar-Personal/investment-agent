# Fix: show account routing for out-of-scope bucket-level ADD rows

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-outofscope-add-account-routing-out.md`.

## Context

Three bucket-level `ADD` rows in Recommended Moves — "ETF (unallocated)",
"Crypto (unallocated)", and "Commodities (below minimum)" — represent
dollar gaps where the specific ticker is intentionally outside the
agent's Circle of Competence (see `docs/architecture/DOMAIN.md` /
`CLAUDE.md`). The agent correctly never picks a specific ETF/crypto/
commodity ticker. But today these rows also show **no account routing
at all** ("Outside agent scope", no accounts), even though the dollar
amount to add is fully known and account cash balances are already
loaded in the same request.

This caused a real problem: during a manual Full Reset execution
(2026-08-24), the user didn't know which account(s) these unallocated
adds were meant to draw from, made an account choice for a *held-ticker*
add (AVGO, which the agent DID specify → ROTH IRA) without realizing an
unplanned extra purchase upstream had drained that account's cash, and
ended up unable to fund the recommended AVGO buy in ROTH. Showing
routing on the unallocated rows won't fully prevent that class of
mistake (manual execution ordering is the deeper cause, tracked
separately — see `memory/accept_triggers_trade_ticket_backlog.md`), but
it closes a real information gap: the user should always be able to see
which account(s) an ADD is expected to draw from, ticker-scoped or not.

## Recon already done — read before starting

A recon pass already traced this precisely (not re-summarized fully
here — verify it against current code, since it may have drifted):

- **Bucket-level ADD rows generated in `server/routes/moves.js`**,
  three near-identical blocks: ~line 1084-1163 (fixed ETF/Crypto/
  Commodity buckets under `bypassWinnerProtection`), ~1305-1345, and
  ~1580-1670 (Established/Speculative scarcity-gap variant). Each
  pushes an `ADD` move with `accounts: [], isBucketLevel: true` and a
  `reason` string ending "...outside agent scope." The dollar gap
  (`shortfall` or equivalent variable — confirm exact name at each
  site) is already fully computed at push time.
- **A function already exists for exactly this shape of problem**:
  `buildNewPositionRouting(accounts, dollarAmount)` (~line 402). It
  takes the raw `accounts` array (already fetched with `.id, .name,
  .type, .managed, .cashBalance` at ~line 928, in scope before all
  three bucket-row blocks) and a dollar amount — no ticker/price
  required (`sharesToBuy: null`). It sorts Roth → IRA → taxable →
  custodial and splits by available `cashBalance`, with a fallback
  (`insufficientCash: true`) if no account has room. It's **already
  used for the same kind of ticker-less row** at ~line 1392 and ~1706
  (freshStart/watchlist candidate rows) — confirm those call sites to
  see the established calling convention before writing the new ones.
- **Frontend**: `client/src/pages/PortfolioManager.jsx`. The routing
  detail panel (`AddRoutingDetail`, ~line 193) is generic and purely
  data-driven off `move.accounts` — should need no changes. The
  collapsed-row summary at ~line 583 currently shows "Outside agent
  scope" whenever `move.isBucketLevel` is true, **unconditionally** —
  this needs to check `move.accounts?.length` and fall through to the
  normal routing-summary rendering when accounts are populated, keeping
  "Outside agent scope" language folded into the reason text rather
  than replacing the routing display.

## What to build

1. At each of the three bucket-level `ADD` push sites in `moves.js`,
   replace `accounts: []` with `accounts: buildNewPositionRouting(accounts, <shortfall var>)`
   using whatever the actual local variable name is for the dollar gap
   at that site (confirm — don't assume it's literally `shortfall` in
   all three).
2. Update the frontend collapsed-row logic (~line 583) so a
   `isBucketLevel` row with populated `accounts` renders the normal
   routing summary, not the "Outside agent scope" placeholder. The
   ticker-selection caveat ("pick a specific ETF/crypto ticker — outside
   agent scope") should stay visible somewhere (it's still true and
   important), just not suppress the routing info.
3. **Judgment call, already decided — implement as follows unless you
   find a reason not to:** apply this to all three rows, *including*
   "Commodities (below minimum)". Even though the agent's advice there
   is "not worth a new position, don't act on this," showing where the
   money *would* come from if the user chose to act anyway is still
   useful information and costs nothing extra to compute. Don't hide
   routing specifically on that row.

## What NOT to do

- Do not have the agent pick a specific ETF/crypto/commodity ticker —
  ticker selection for these three buckets stays explicitly out of
  scope, unchanged. This fix only adds *account* routing for a known
  dollar amount, not ticker selection.
- Do not touch `buildAddRouting` (the held-ticker version) or any
  ticker-specific ADD/TRIM row's routing logic.
- Do not touch the manual-trade-sequencing/insufficient-funds problem
  itself — that's a separate, already-backlogged future feature
  (trade-ticket execution from the app). This fix only closes the
  visibility gap.

## Verify

1. Confirm all three bucket-level ADD rows now show account routing
   (account name, tax treatment, dollar amount per account) instead of
   "Outside agent scope" with no accounts — check against live data for
   at least one owner where these rows currently appear (Andrea's
   account had all three as of 2026-08-23/24, though her Full Reset
   window may have expired by the time this runs — check any owner with
   open bucket-level gaps).
2. Confirm the routing splits sensibly across accounts by tax
   treatment/cash availability, consistent with how `buildNewPositionRouting`
   already behaves at its two existing call sites.
3. Confirm the ticker-out-of-scope language is still shown somewhere on
   these rows — this fix must not make it look like the agent picked a
   ticker.
4. Confirm no regression on the two existing `buildNewPositionRouting`
   call sites (freshStart/watchlist candidate rows) — same function,
   more call sites now, should behave identically at the original two.
5. `node --check server/routes/moves.js` and `npx vite build` clean.
6. Run `./server/scripts/verify-allocation-math.sh` after any real
   writes (there shouldn't be any — this is a read/display-only
   change, no `OwnerDecision` or position writes). Confirm output
   unchanged from the pre-existing baseline failures already tracked
   (task #50).

## Commit and push

```bash
git add -A
git commit -m "Show account routing on out-of-scope bucket-level ADD rows (ETF/Crypto/Commodities)"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-outofscope-add-account-routing-out.md` existing, with
each of the 6 verify items addressed.
