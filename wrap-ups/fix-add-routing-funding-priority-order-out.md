# Fix: fund ADD rows in a fixed priority order, not generation order

**Commit `0021bcc`, pushed to `origin/dev`.** One file:
`server/routes/moves.js`.

Your order is implemented and verified against live data. Three things
worth your attention: the conviction signal I used (item 1), a bug I hit
and fixed mid-implementation, and a structural nuance about *when*
funding priority actually decides anything.

## Item 1 — the conviction signal, named and cited

**`scoreCandidate(analysis, tickerType)` — `server/routes/moves.js:245`.**

```js
function scoreCandidate(a, type) {
  return (TRAJ_SCORE[a?.trajectory] ?? 0)
       + (HEALTH_SCORE[a?.thesisHealth] ?? 0)
       + (ACTION_SCORE[a?.finalAction ?? a?.recommendation] ?? 0)
       + (type === 'B' ? 2 : 1);
}
```

This is the engine's existing ranking — already used to pick *which*
tickers become candidates in the first place, at four sites: the
freshStart universe build (lines 1370, 1386) and the normal-path
watchlist candidate ranking (1626, 1674, sorted `b.rankScore -
a.rankScore`). I reused it rather than inventing a parallel ranking, as
instructed. Established-vs-Speculative comes from the existing
`barbellSide(ticker, analysis)` (line 76).

## Item 2 — separability: separable, and I did not have to force it

The prompt asked me to trace whether sizing and routing are cleanly
separable or tangled. **They're separable**, and cleanly, because of one
fact worth recording: every ADD move already carries everything routing
needs. `makeAddMove` stores `dollarAmount` (the exact `addValue`) and
`pricePerShare`, and the `positions` array is reachable from `byTicker`
in `computeMovesPayload` scope. So routing can be re-derived *after*
generation without stashing anything on the move, without closures, and
without restructuring the ~1000-line generation flow.

That meant the change is:

1. Generation no longer claims cash — the 10 ledger arguments now pass
   `null`, so each row still sizes exactly as before but commits nothing.
2. A new `routeAddsInFundingOrder(moves, accounts, tickerMeta, committed)`
   post-pass sorts all ADD moves by the decided priority and assigns
   `move.accounts`, committing to the ledger in that order.
3. It runs immediately before `annotateAddFunding`, which consumes its
   `fromCash` — same post-pass shape the prompt pointed at as a template.

Sizing, dollar amounts, and which tickers get recommended are untouched.

## ⚠ Bug I hit and fixed: new positions had no rank

My first implementation built `tickerMeta` from `byTicker` — which only
contains **currently-held** tickers. Every ADD for a *new* position
(freshStart opens, watchlist candidates) therefore had no side and no
score, hit `FUND_RANK[undefined] ?? 9`, and **sorted last** — the exact
inverse of intent for a new high-conviction Established position.

It was visible in the data, not just in theory: Eduardo's MSFT, AVGO,
GOOGL and AMD aren't held in his Custodial account, so the first version
funded Speculative ENVX/AMPX ahead of them.

Fixed by capturing `side` + `rankScore` from the candidate records
themselves — `fsOpenCandidates` (line 1452) and `candidates` (line 1727)
both already carry both fields — into a `newPositionMeta` map, merged
into `tickerMeta` before routing (held data wins where both exist).

## Nuance: priority only arbitrates *within* an account

Worth understanding before reading the results, because one case looks
like the order didn't apply.

`buildAddRouting` routes an existing-position ADD only to accounts that
already hold that ticker (the "consolidate rather than fragment" rule,
unchanged here). So a top-priority row scoped to an empty account does
**not** block a lower-priority row that can reach a funded account —
correctly, since they were never competing for the same dollars.

Andrea's freshStart shows this. `QS` (Speculative, rank 1) sorts ahead of
`ETF (unallocated)` (rank 2), yet ETF still takes her $1,479.28:

```
Andrea ROTH IRA    cash $   0.03   holds: QQQ, AVGO, NVDA, QS
Andrea Custodial   cash $1479.28   holds: SIVR, AMZN, BTC, GOOGL, ... (no QS)
```

QS is held only in the ROTH, so its routing can only reach $0.03. The ETF
bucket row uses `buildNewPositionRouting`, which spans all managed
accounts, so it reaches the Custodial cash. The ordering is applied; the
two rows simply aren't competing.

## Verification — all 6 items

**1. New order confirmed on live data, with before/after.** Eduardo's
freshStart is the clean demonstration — idle cash claimed per row:

```
                                      before        after
ETF (unallocated)                  $1,530.48  ->    $0.00
Crypto (unallocated)               $1,530.48  ->    $0.00
Commodities (below minimum)          $177.37  ->    $0.00
MSFT   (established)                   $0.00  -> $1,408.00
AVGO   (established)                   $0.00  -> $1,408.00
GOOGL  (established)                   $0.00  ->   $422.33
```

The full $3,238.33 moves from bucket-level rows to conviction-scored
Established tickers. Eduardo's normal mode shows the Established-over-
Speculative rule directly: `QS` (spec) $446.76 → $0, `GOOGL` (est)
$159.57 → $606.33.

**Strong sanity check:** total idle cash claimed across all rows is
**identical before and after — $9,022.94**. Reordering redistributes;
it doesn't create or destroy funding. 12 rows unchanged.

**2. Within-bucket conviction ordering** ✔ — Eduardo freshStart, after
the fix, funds all four Established rows (MSFT, AVGO, GOOGL, then AMD
which gets $0 once cash runs out) before any Speculative row (QS, ENVX,
AMPX all $0) and before all three bucket rows. Established and
Speculative are cleanly separated by `barbellSide`, and MSFT/AVGO/GOOGL
tie on `scoreCandidate` (all `Strengthening` / `Add`, same type), so the
deterministic dollar-amount tiebreak orders them — no arbitrary DB order
remains.

**3. Ledger invariant still holds** ✔ — re-verified, not assumed: **0
violations** across all three owners in both modes; no account's routed
total exceeds its real balance.

**4. `annotateAddFunding` split still correct** ✔ — rerun as instructed:
**26 ADD rows, 0 sum mismatches** (`fromCash + expectedFromTrims +
unbacked == requested`). It consumes whatever `fromCash` the ledger
produced, so reordering flows through cleanly.

**5.** `node --check server/routes/moves.js` ✔ · `npx vite build` clean
at 112 modules ✔.

**6. `verify-allocation-math.sh`** ✔ — same 7 failures as the tracked
task-#50 baseline, unchanged. **No writes** — `computeMovesPayload` is
pure compute; no `upsert` in any verification script.

## Deviations from the prompt

**None on scope.** One judgment call to flag: Established/Speculative
*scarcity-gap* rows are bucket-level (no ticker, so no conviction score),
but they belong to the est/spec sides rather than to ETF/Commodities/
Crypto. I ranked them with their own side but sorted them **last within
that side** (score `-Infinity`), so scored tickers always outrank an
unscored gap row on the same side. Your stated order didn't cover this
case; say the word if you'd rather they sit elsewhere.

## What was deliberately NOT done

- **No change to which tickers/buckets get ADDs, or their dollar
  amounts** — routing order only.
- **No change to the payload's display sort** — it remains
  priority-sorted at the end, independent of funding order. (Worth
  knowing: display order and funding order are now deliberately
  different things.)
- **No gating or disabled buttons.**
- **No touch to `annotateAddFunding`'s trim-proceeds limitation** (one
  row's `expectedFromTrims` can still be cited by another) — separate,
  documented, out of scope.
- **No visual verification** — Chrome tools still not connected (eighth
  session). All evidence above is live-data and source verification.

## Follow-up for Luis

1. **Check the reordering where it's most visible:** Eduardo →
   Recommended Moves → Full Reset. MSFT/AVGO/GOOGL should now show real
   "available now" dollars, and the ETF/Crypto/Commodities rows should
   show $0 available with their amounts under "expected from trims".
2. **Andrea will look unchanged** — that's the account-scoping nuance
   above, not a failure. If you'd rather a held-ticker ADD be able to
   draw on an account that doesn't yet hold it, that's a change to
   `buildAddRouting`'s consolidate rule and a separate decision.
3. **Decide on scarcity-gap placement** (the judgment call above) if you
   disagree with sorting them last within their side.
4. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect 0021bcc...
   ```

## Note on the commit trailer

Unchanged: `Co-Authored-By: Claude Opus 4.8 (1M context)` per your
`/execute-prompt` workflow, though this session runs **Opus 5**.
