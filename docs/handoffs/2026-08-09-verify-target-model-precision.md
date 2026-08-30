# Handoff: verify target-model precision drift (Andrea Morales)

## Context

Cowork (this session) has been chasing why the Allocation tab's bucket
targets for Andrea Morales don't match what the re-baseline modal computes
live from the same inputs, even after a forced recompute (which rules out
stale cache):

| Bucket      | Allocation tab (server, forced recompute) | Re-baseline modal (client live calc, assumes clean 55/25/10/10) |
|-------------|--------------------------------------------|-------------------------------------------------------------------|
| Established | $8,210 (26.1%)                              | $8,217 (26.1%)                                                     |
| ETF         | $7,486 (23.8%)                              | $7,470 (23.8%)                                                     |
| Crypto      | $2,988 (9.5%)                               | $2,988 (9.5%) — matches                                            |
| Commodities | $2,988 (9.5%)                               | $2,988 (9.5%) — matches                                            |

Working theory: Admin's target-model input fields display
`Math.round(value * 100)` (see `client/src/pages/Admin.jsx`, `toUI()`), so
the UI shows clean integers ("55", "25") even if the actual stored
`OwnerProfile.equitiesTargetPct` / `etfTargetPct` values in Postgres are
slightly off (e.g. `0.5496` instead of `0.55`). Reverse-engineering the
numbers above (against total portfolio value ~$31,454) implies the real
stored values are approximately:

- `equitiesTargetPct` ≈ 0.54955 (displays as "55")
- `etfTargetPct` ≈ 0.25054 (displays as "25")
- `cryptoTargetPct` = 0.10 exactly (matches, no drift)
- `commoditiesTargetPct` = 0.10 exactly (matches, no drift)

Cowork could not confirm this directly — the sandbox has no network path
to Railway's Postgres proxy (`interchange.proxy.rlwy.net`), and works off
a Dropbox-synced mount of this repo that can lag behind the real local
filesystem. You're running this from the actual machine, so both problems
go away here.

## What to do

1. Confirm you're in the real working directory (not a stale Dropbox
   sync artifact) — `pwd` should resolve to the actual local
   `investment-agent` checkout, and `git status` / `git log -1` should
   match what's on GitHub (`origin/dev`, currently expects the commit
   titled "Refresh MovesCache when Admin edits target-model fields
   directly...").

2. Query the actual current value of Andrea Morales' `OwnerProfile` row
   in production Postgres, at full precision (not rounded):

   ```bash
   DATABASE_URL=$(grep '^DATABASE_URL' .env | cut -d '=' -f2-) node -e "
   const { PrismaClient } = require('./server/node_modules/@prisma/client');
   const prisma = new PrismaClient();
   (async () => {
     const p = await prisma.ownerProfile.findFirst({ where: { displayName: 'Andrea Morales' } });
     console.log({
       owner: p.owner,
       equitiesTargetPct: p.equitiesTargetPct,
       etfTargetPct: p.etfTargetPct,
       cryptoTargetPct: p.cryptoTargetPct,
       commoditiesTargetPct: p.commoditiesTargetPct,
       estSpecRatio: p.estSpecRatio,
       cashReservePct: p.cashReservePct,
     });
     await prisma.\$disconnect();
   })();
   "
   ```

   (If the Prisma client complains about a missing query engine binary,
   run `cd server && npx prisma generate` first — that regenerates it for
   your actual OS/arch, which the Dropbox-synced `node_modules` may not
   have if it was last generated somewhere else.)

3. **If the values show drift** (anything other than exactly `0.55`,
   `0.25`, `0.1`, `0.1`): that confirms the theory. Two things to fix:

   a. **Clean up this specific row** — either resave through the Admin UI
      (open Andrea's card, click Edit, click Save without necessarily
      changing anything — `fromUI()` will write back the clean rounded
      integer you see displayed) and re-verify with the same query above
      that it now reads exactly `0.55`/`0.25`; or do it directly via
      Prisma `update` if you'd rather not go through the UI.

   b. **Find how it got there in the first place**, so it doesn't
      recur. Worth checking: `git log -p -- server/routes/users.js
      server/prisma/schema.prisma` around when the 4-bucket target model
      was first added (search commit messages for "target model" /
      "4-bucket"), and whether any script under `server/scripts/` ever
      wrote to these fields directly (bypassing the UI's integer-only
      inputs). Also worth adding a defensive fix regardless of root
      cause: round `equitiesTargetPct`/`etfTargetPct`/`cryptoTargetPct`/
      `commoditiesTargetPct` to, say, 4 decimal places server-side in
      `PATCH /api/users/:owner` (`server/routes/users.js`) before writing,
      so no future write path (UI or script) can introduce silent
      long-tail float drift again.

4. **If the values come back exactly `0.55`/`0.25`/`0.1`/`0.1`** (no
   drift): the precision theory is wrong, and the ~$16/$7 gap is a real
   bug somewhere in the computation path, not a data-precision issue.
   In that case, next step is comparing `computeMovesPayload`'s
   `bucketEntry()` calls (`server/routes/moves.js`, search for
   `bucketEntry(` and the `estPoolPct`/`etfTargetPct` variables feeding
   it) against the client's `liveTargets()` reimplementation in
   `client/src/pages/PortfolioManager.jsx` line-by-line for a genuine
   formula mismatch, rather than assuming stored-value drift.

## Report back

Whichever branch above applies, report: the exact raw values found, which
fix path was taken, and confirmation (re-run the Allocation tab / a fresh
re-baseline modal open) that Established now shows $8,217 and ETF shows
$7,470 for Andrea, matching the modal exactly.
