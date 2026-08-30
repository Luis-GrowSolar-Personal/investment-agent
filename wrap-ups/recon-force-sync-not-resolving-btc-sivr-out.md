# Recon: Force Sync didn't resolve BTC/SIVR even after Fix 1 landed

**Answer up front: (a) deployment lag, not a code defect.** Fix 1
(commit `b5a93f1`) is confirmed live on the Railway service Luis's
browser actually hits (`investment-agent-DEV`), and live Schwab data
still supports an exact multi-fill match for both BTC and SIVR. But
Luis's earlier Force Sync attempt almost certainly landed on the
still-running pre-fix container, before the new deploy finished
rolling out — Railway builds/deploys take real time after a `git
push`, and no evidence (old logs, old Lot rows) survives from that
specific click to prove otherwise. **No code change was made.**
Recommend: Luis retry Force Sync now — the fix is live and the data
supports it resolving cleanly.

No `Lot`/`Position`/`Account` rows were written during this recon.
`previewAccounts()` was called once (a genuine live Schwab API read —
same call `syncAccount()` itself makes to fetch positions — it may
refresh an OAuth token internally but performs no writes to
`Lot`/`Position`/`Account`), plus read-only Prisma queries and the
existing read-only `debug_transactions.js` script. No sync was
triggered.

## Step 1 — Is the deployed code actually the fixed version?

There is no `railway.json`/`railway.toml` in this repo. Checked via
the Railway CLI (`railway link`, `railway status --json`) instead.

Two **separate Railway projects** exist (not two services in one
project, per a stale assumption in CLAUDE.md — worth updating that doc
separately, flagged here rather than fixed since it's out of scope):

- **`investment-agent-DEV`** — the service Luis's browser actually
  uses day-to-day. `railway status --json` shows its `investment-agent-DEV`
  service's `latestDeployment.meta`:
  ```
  branch: dev
  commitHash: b5a93f131a15ad95ea5812ab790412ebd2c5cda3
  commitMessage: "Fix Schwab sync matcher to sum multiple same-symbol
                  fills instead of only checking single legs..."
  ```
  This **is** the Fix 1 commit, deploying from `dev`. Deployment id
  `b917d1bc-624e-4a2b-849a-d072082c24b0`, `railway deployment list`
  shows it `SUCCESS` at `2026-08-22 12:57:33 -04:00` — 2 seconds after
  `git log dev -1` shows `b5a93f1` was pushed at `2026-08-22
  12:57:31 -0400`. `railway logs` on this deployment shows a very
  short log (only 15 lines: `Starting Container` through a handful of
  keep-alive/moves-cache refresh lines) — consistent with a
  **recently-restarted container**, i.e. this deployment replaced an
  older one not long ago.
- **`investment-agent-PROD`** — its only service's `latestDeployment`
  is **`FAILED`**, on `branch: main`, commit `2830d274...` from
  **2026-04-04** (`Add investment agent handoff brief` — predates all
  the RADAR/re-baseline/allocator work in current `dev`). `main` is
  ~19 commits behind `dev` in this repo (`git log main..dev`).
  `investment-agent-PROD` appears to have had no successful deployment
  since April and is not the service Luis is actually using — nothing
  in this session used it as the live app.

**Conclusion for step 1: the deployed code Luis's browser hits IS the
fixed version** (`investment-agent-DEV`, commit `b5a93f1`, confirmed
via the deployment's own commit-hash metadata, not just push time).

## Step 2 — Did `syncAccount()` actually attempt anything?

Read-only Prisma query against the live DB for Andrea's Custodial
account (id 7), same query as the Fix 1 dry run:

```
=== BTC (positionId 80) ===
  id=119 shares=34 costBasis=37.55  source=manual acquiredDate=2024-11-11 createdAt=2026-05-31
  id=118 shares=4  costBasis=44.16  source=manual acquiredDate=2024-11-22 createdAt=2026-05-31
  total local shares: 38

=== SIVR (positionId 74) ===
  id=105 shares=12 costBasis=72.6703 source=import acquiredDate=2026-02-02 createdAt=2026-05-31
  total local shares: 12
```

**Identical to the pre-fix state** (compare to the Fix 1 wrap-up's dry
run: BTC 38 sh across the same 2 manual lots, SIVR 12 sh in the same
import lot). No new `schwab`-source lots exist for either symbol —
`createdAt` on every existing lot predates today entirely (2026-05-31).
This confirms: whatever Force Sync run(s) Luis triggered, **none of
them ever got as far as creating a lot** for BTC or SIVR — the diff
either wasn't computed, or fell straight through to `positionDiffs`
without attempting the match logic at all. This is consistent with the
sync having run against the **pre-fix container**, where the old
single-leg-only code was still active and would behave exactly this
way (no match → `positionDiffs`, no lot created) — same outward result
as "the fix ran but failed," which is why it looked identical to
before from the UI.

## Step 3 — Check for a thrown/caught error

`railway logs` for the **current** deployment shows no sync-related
log lines at all (no `schwabSync`, no `ensureRecentTrades` warning, no
route error) — only the container-boot sequence and
keep-alive/moves-cache refresh lines. This is expected either way:
Railway's `logs` command only serves the **current** deployment's log
stream. If Luis's Force Sync click happened on the **previous**
deployment (pre-fix), those logs no longer exist — Railway doesn't
retain logs from a replaced deployment via this CLI path. **Could not
rule in or out a live-environment fetch failure (token
refresh/rate-limit) for the specific click Luis made**, because that
deployment's logs are gone. Telling Luis plainly: if he wants to
capture this evidence for a *future* click, watch `railway logs
--service investment-agent-DEV` live at the moment he clicks Force
Sync (or check the Railway dashboard's log history for the service,
which may retain more than the CLI tail does).

## Step 4 — Re-run the dry-run check, live, right now

Read-only, no writes. Confirmed the underlying data still fully
supports an exact multi-fill match — nothing changed since the Fix 1
dry run:

**Live Schwab positions** (via `previewAccounts()`, the same read-only
call `syncAccount()` itself makes — no DB writes to
`Lot`/`Position`/`Account`; may silently refresh an OAuth token
internally, same as any other read):

```json
{ "symbol": "BTC",  "longQuantity": 109.9957, "averagePrice": 31.758514196464 }
{ "symbol": "SIVR", "longQuantity": 21.876,   "averagePrice": 68.329676357652 }
```

**Live transaction feed** (`debug_transactions.js 7 90`, re-run just
now): identical BTC legs (0.9957 sh + 71 sh @ $28.335, same trade date)
and identical SIVR legs (0.876 sh + 9 sh @ $63.0555, same trade date)
as the original recon and the Fix 1 dry run — nothing fell out of the
60-day window, nothing changed on Schwab's side.

Diffs, computed the same way `syncAccount()` would:
- BTC: `109.9957 (schwab) − 38 (local) = 71.9957` — still exactly
  matches the sum of the two legs (`0.9957 + 71 = 71.9957`).
- SIVR: `21.876 (schwab) − 12 (local) = 9.876` — still exactly matches
  the sum of the two legs (`0.876 + 9 = 9.876`).

Symbol matching also re-confirmed correct at the **live positions**
level, not just the transaction-feed level checked in the original
recon: `previewAccounts()`'s `pos.instrument?.symbol` returns exactly
`'BTC'` / `'SIVR'` — identical to what the transaction feed and the
local `Ticker.symbol` use. No symbol-mismatch explanation here either.

**If Luis retries Force Sync right now, against the currently-deployed
code, the fix should create exactly the lots described in the Fix 1
wrap-up** (2 lots each, summing to 71.9957 for BTC and 9.876 for
SIVR).

## Which of (a)/(b)/(c) this is

**(a) — deployment hadn't caught up yet at the moment Luis clicked.**
Not (b): there's no log evidence of a live-environment-only failure
(though also no way to fully rule it out for that specific past click,
since the logs are gone — noted above). Not (c): the Fix 1 code itself
is confirmed correct against live data in this recon; no defect found.
No code change needed or made.

## Constraints followed

- No additional sync was triggered by this recon — `previewAccounts()`
  was called (a live Schwab read, same one `syncAccount()` uses
  internally) specifically to re-verify the underlying data per Step
  4's instruction; `syncAccount()`, `/api/schwab/sync/:id`,
  `/api/schwab/reconcile`, `/api/schwab/match`, and Force Sync itself
  were never invoked.
- No `Lot`/`Position`/`Account` row was created, updated, or deleted.
- Two throwaway read-only scripts (`server/scripts/_recon_lots2.js`,
  `server/scripts/_recon_live_positions.js`) were written for this
  recon and deleted immediately after capturing their output — nothing
  left in the repo (confirmed via `git status --short`).
- No commit, no push (nothing to fix).

## What was deliberately NOT done

- Did not re-click Force Sync myself, per the constraint not to go
  further than Luis already has without explaining first — this
  wrap-up IS that explanation. Retrying is safe and recommended (see
  below) but left for Luis to do himself.
- Did not attempt to recover the pre-fix deployment's logs from the
  Railway dashboard (may have more retention than the CLI tail) —
  flagged as an option below rather than pursued, since the live data
  already gives a definitive enough answer without it.
- Did not fix the stale `main` branch / `investment-agent-PROD`
  service (19 commits behind, last deploy `FAILED` since April) — that
  looks like a separate, pre-existing housekeeping gap unrelated to
  this recon's question, not something to touch without Luis's
  direction.
- Did not correct the CLAUDE.md line describing Railway as "dev and
  prod services" (singular project) vs. the two separate projects
  found here — noting the discrepancy, not fixing docs unprompted.

## Follow-up for Luis

1. **Retry Force Sync now** on Andrea's Custodial account — the fix is
   confirmed live (`investment-agent-DEV`, commit `b5a93f1`) and the
   underlying Schwab data still supports an exact match. Expect BTC to
   pick up 2 new `schwab` lots (0.9957 sh @ $28.335, 71 sh @ $28.335)
   and SIVR to pick up 2 new `schwab` lots (0.876 sh @ $63.0555, 9 sh
   @ $63.0555), matching Schwab's totals exactly (109.9957 / 21.876).
2. To verify from the terminal after retrying, re-run (read-only):
   ```bash
   cd server && export DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) && node -e "
   const {PrismaClient}=require('@prisma/client');const p=new PrismaClient();
   (async()=>{for (const symbol of ['BTC','SIVR']) {
     const t=await p.ticker.findUnique({where:{symbol}});
     const pos=await p.position.findUnique({where:{tickerId_accountId:{tickerId:t.id,accountId:7}}});
     const lots=await p.lot.findMany({where:{positionId:pos.id}});
     console.log(symbol, lots.map(l=>({shares:l.shares,source:l.source,notes:l.notes})));
   } await p.\$disconnect();})();"
   ```
3. If Force Sync still doesn't create the lots after this retry, that
   would rule out deployment lag definitively and point at (b) or (c)
   — at that point, watch `railway logs --service investment-agent-DEV`
   live during the click (or check the Railway dashboard's log
   history) to capture whatever `ensureRecentTrades()`'s
   `console.warn` or any thrown error says in the moment.
4. Separately, worth deciding at some point whether
   `investment-agent-PROD` (branch `main`, last successful deploy
   pre-April) is still meant to be a real environment — right now it
   looks stale/abandoned relative to the actively-used `dev`-deployed
   `investment-agent-DEV` service.
