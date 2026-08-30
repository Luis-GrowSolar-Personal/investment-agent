# Fix 1 of 2: Schwab sync matcher doesn't sum multiple same-symbol fills

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-schwab-sync-multifill-matching-out.md`. State the fix up
front, then walk through the dry-run verification against Andrea's real
BTC/SIVR case (details below) — do NOT run a real sync against Andrea's
account as part of this task; prove correctness via a read-only dry run
first, per the constraints section. Write for someone reading cold
later.

## Context

Root cause fully diagnosed and confirmed in
`wrap-ups/recon-btc-sivr-schwab-sync-stuck-out.md`: `server/lib/schwabSync.js`'s
transaction matcher (`ensureRecentTrades()` + the `candidates.find(...)`
check around line 378-380) only ever checks whether a SINGLE Schwab
transaction leg matches a position's diff exactly. When a broker splits
one logical buy into multiple separate fills — common for lower-volume
tickers, large orders, or orders that fill over hours — no single leg
matches the full diff, the match fails, and (for positions that already
carry pre-existing `manual`/`import` lots, which have no fallback) the
diff parks in `positionDiffs` for manual entry forever, surviving every
subsequent sync unchanged.

Confirmed concretely on Andrea Morales's Custodial account (id 7):
- **BTC**: Schwab shows two OPENING fills on 2026-08-17 — 71 sh @
  $28.335 and 0.9957 sh @ $28.335 — summing to exactly 71.9957, the
  missing diff (Schwab 109.9957 − local 38).
- **SIVR**: same pattern — 9 sh @ $63.0555 and 0.876 sh @ $63.0555,
  summing to exactly 9.876, the missing diff (Schwab 21.876 − local 12).

Luis's framing, worth keeping in mind while designing the fix: this
isn't a one-off — large orders against lower-liquidity tickers commonly
fill as multiple partial executions, sometimes over hours, sometimes
with a fill that never completes. The fix should handle the general
case, not just today's two-fill example.

## The fix

In the diff-resolution logic (`server/lib/schwabSync.js`, the
`hasManualOrImportLots` branch, currently ~lines 372-408):

1. Keep the existing single-leg match as the first, cheapest check
   (no behavior change when a single trade already matches exactly).
2. When no single leg matches, before falling through to
   `positionDiffs`, try summing the candidate legs for that symbol
   (already fetched by `ensureRecentTrades()` — same 60-day window,
   OPENING legs only) and check whether the **sum of some subset**
   equals the diff within the existing tolerance
   (`Math.abs(sum - diff) / diff < 0.0001`).
   - Start with the simple, common case: sum ALL same-symbol OPENING
     legs in the window and check if the total matches the diff. This
     covers "one order, split into N fills" cleanly without needing
     general subset-sum search.
   - If that doesn't match (e.g., some legs belong to an earlier,
     already-resolved diff), that's a genuinely ambiguous case — don't
     guess which legs belong together. Fall through to the existing
     manual-entry path (`positionDiffs`) rather than attempting
     combinatorial subset matching. Note this limitation clearly in the
     wrap-up rather than over-building.
3. **When a multi-leg sum matches**: create ONE `Lot` row PER matched
   leg (not one merged/averaged lot) — each fill has its own real price
   and trade date, and collapsing them loses tax-lot accuracy
   (different acquisition dates matter for LTCG/STCG holding period,
   even same-day fills at different prices matter for cost basis). Tag
   each with `source: 'schwab'` and a `notes` string that's honest about
   what happened, e.g. `"Auto-resolved from Schwab transaction history
   (1 of 2 fills): X shares @ $Y on <date>."`
4. **Idempotency — important.** Once a sync creates lots from matched
   transaction legs, a LATER sync must not re-match those same legs
   again and double-create lots. Read the surrounding code to see what
   guard (if any) already exists for the single-leg match case
   (`autoResolvedAdds`) and extend the same protection to the new
   multi-leg case — e.g., before creating new lots, check whether a
   `Lot` already exists for this position with a matching
   `acquiredDate`+`shares`+`source: 'schwab'` combination, or whatever
   mechanism the existing single-leg path relies on to avoid
   duplicating on every sync. If the single-leg path doesn't actually
   guard against this either (worth checking — it may rely on the diff
   naturally becoming zero after the first successful match, which
   would also protect the multi-leg case the same way), confirm that
   and explain why it's sufficient, or fix both if it's genuinely
   missing.

Read the actual current source in full before editing — confirm exact
line numbers and surrounding logic, this describes intent based on the
recon's findings.

## Verify — read-only dry run first, no real sync

Luis wants proof the fix works, but does NOT want a real sync run
against Andrea's account yet as part of this task — the current
BTC/SIVR mismatch is deliberately preserved.

1. Write a **temporary, throwaway** dry-run script (delete it before
   finishing, same convention as the recon) that: loads Andrea's
   Custodial account's real Schwab transaction history (same
   `getTransactions` call `debug_transactions.js` uses — read-only) and
   her real current `Lot` rows for BTC/SIVR (read-only Prisma query),
   then runs the NEW matching logic against that real data **without
   calling `prisma.lot.create`** — just log what it WOULD create (shares,
   price, date, per leg) and confirm the resulting sum exactly closes
   the diff (71.9957 for BTC, 9.876 for SIVR).
2. Paste that dry-run output in the wrap-up as the verification
   evidence.
3. Also confirm, by re-reading the diff, that the code fix does not
   change behavior for the cases that already worked (single-leg exact
   match, and the lenient schwab-only-lots branch — which this fix
   doesn't touch at all, that's Fix 2).

## Constraints

- **Do not call `syncAccount`, `/api/schwab/reconcile`, `/api/schwab/match`,
  Force Sync, or any route that would write to `Lot`/`Position`/`Account`
  for Andrea's account (or any account) as part of this task.** The dry
  run must not create/update/delete any real rows. Luis will trigger the
  real sync himself once he's seen the dry-run proof.
- Delete any throwaway verification scripts before finishing — don't
  leave debug scripts littering the repo.

## Commit and push

```bash
git add -A
git commit -m "Fix Schwab sync matcher to sum multiple same-symbol fills instead of only checking single legs"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-schwab-sync-multifill-matching-out.md` existing, with the
dry-run output proving the fix resolves Andrea's actual BTC/SIVR diffs,
and explicit confirmation that no real sync was run and no live
Lot/Position/Account rows were touched.
