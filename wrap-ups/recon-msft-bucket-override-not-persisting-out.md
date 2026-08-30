# Recon: MSFT's bucket override doesn't persist — always reverts to ETF

**Root cause found and fixed (simple, obvious, low-risk — implemented,
committed `4feea87`, pushed to `origin/dev`).** This is **not** a
persistence bug — the `PATCH /api/portfolio/tickers/:id/bucket` route
was already writing `bucketOverride` correctly and unconditionally,
confirmed by a live round-trip test. The real defect: **any UI action
that resets a ticker's bucket override to `null` (meaning "use the
smart default, i.e. equity") can never actually resolve back to
`equity`**, because the display-time fallback
(`server/routes/portfolio.js`'s `enrichPosition()`) calls
`smartDefaultBucket(pos.assetType || '', ...)` — and `pos` there is a
Prisma `Position` row, which **has no `assetType` column at all**. That
expression is always `''`, never `'Equity'`, so the fallback's only
equity-detecting branch can never fire, and every reset silently lands
on the function's final catch-all: `return 'etf';`.

There are three places in the app that write `bucketOverride: null`
intending "equity/default": `BucketPill`'s "Reset to default" link,
`BucketPill`'s toggle-off-the-currently-selected-pill behavior
(clicking "Equity" again while it's already selected), and RADAR's
ticker-edit modal (`<option value="">Equity (default...)`, which
submits `bucketOverride: '' || null` = `null`). All three hit the same
broken fallback. This fully explains "selected a different bucket for
MSFT... after making the change, MSFT reverts to (or never leaves) the
ETF bucket" — not because the PATCH failed, but because *some*
subsequent action (a re-click, a RADAR edit, "Reset to default") wrote
`null` back, which the display layer can only ever resolve to `'etf'`.

## What was checked, in order (per the prompt's steps)

**1. Does the PATCH actually persist?** Found MSFT's live `Ticker` row
first (read-only): `id=82`, single row (confirmed `Ticker.symbol` is
genuinely unique in the live data — only one MSFT row exists), single
`Position` (id 115, Andrea Custodial, account 7). At the moment this
recon started, `bucketOverride` was **already `"equity"`** in the DB —
not `"etf"` as the prompt's motivating snapshot described, meaning
whatever last touched it (a prior PATCH) had already written the
correct value.

To directly test the PATCH route's own behavior (not just infer it),
exercised it live against the real `investment-agent-DEV` Railway
deployment (`https://investment-agent-dev-production.up.railway.app`)
— confirmed this endpoint has **no auth check** (`router.patch('/tickers/:id/bucket', ...)`
in `portfolio.js` never reads `req.ownerProfile` or calls
`requireAuth()`, unlike most other routes in this file — flagging this
as a separate, pre-existing gap below, not part of this fix):

```
curl -X PATCH .../api/portfolio/tickers/82/bucket -d '{"bucket":"etf"}'   → 200
  → DB confirmed: bucketOverride = "etf"
curl -X PATCH .../api/portfolio/tickers/82/bucket -d '{"bucket":"equity"}' → 200
  → response body: {"id":82,...,"bucketOverride":"equity",...}
  → DB confirmed: bucketOverride = "equity"
```

**The PATCH route persists correctly and unconditionally, every
time.** Not a persistence bug. (End state: `bucketOverride` left as
`"equity"` — the correct value — after this round-trip test; see
"What was written" below.)

**2. Is it a display/caching issue instead?** Re-implemented the exact
server-side `effectiveBucket` computation
(`pos.ticker.bucketOverride ?? smartDefaultBucket(pos.assetType || '', symbol)`)
against the live position row: with `bucketOverride = "equity"`, it
correctly computes `effectiveBucket = "equity"` — matches what the
`GET /api/portfolio/accounts` route would actually return right now.
`GET /api/portfolio/accounts` **does** require auth
(confirmed: unauthenticated curl → `401`), so couldn't hit it directly
without a live Clerk session token, but its logic
(`server/routes/portfolio.js`'s `enrichPosition()`) was read directly
and traced by hand against the real DB row — no caching layer sits
between the DB and this route (plain Prisma query on every request, no
Redis/memoization). **Not a caching issue when the override is
non-null** — the bug only manifests when the override is `null`.

**3. Does something run AFTER the change and reset it?** This is where
the actual mechanism was found. Grepped the **entire repo** for every
`bucketOverride` write (not just `schwabSync.js`, per the prompt's
instruction):

- `schwabSync.js`'s watchlist-promotion backfill (~line 512,
  `if (ticker.bucketOverride == null)`) — confirmed this guard really
  is `== null` (catches both `null` and `undefined`, nothing looser).
  It also only fires inside the `else if (ticker.status === 'watchlist')`
  branch — **structurally unreachable for MSFT now**, since MSFT's
  `Ticker.status` is already `'portfolio'`. A resync of an
  already-portfolio-status ticker with existing lots goes straight to
  the `localPos && localPos.lotCount > 0` branch and never touches
  `bucketOverride` at all. Ruled out.
- `schwabSync.js`'s brand-new-position path (~line 495) and
  `portfolio.js`'s CSV-import / `POST /positions` auto-create paths
  (~lines 289, 581) — all three are guarded by `if (!ticker)` /
  "ticker doesn't exist yet" — cannot refire for an existing MSFT
  ticker. Ruled out.
- `radar.js`'s `PATCH /api/radar/tickers/:id` (~lines 347, 365) — only
  writes `bucketOverride` when the request body includes it
  (`bucketOverride !== undefined` guard) — so editing MSFT in RADAR for
  an unrelated reason (e.g. domains, tier) while its Asset-class
  dropdown is showing something wouldn't silently touch it *unless*
  the dropdown is submitted. **This is one of the three culprits** —
  see below.
- No other `bucketOverride` write exists anywhere in the codebase.

**Definitive mechanism, found here:** three UI-writable paths (not a
sync/backend process) can set `bucketOverride: null`, and none of them
can ever correctly resolve back to `'equity'`:

  a. `client/src/pages/Portfolio.jsx`'s `BucketPill`, "Reset to
     default" link (`onBucketChange(ticker.id, null)`, ~line 149) —
     the label implies this restores the correct default, but for any
     symbol not in the small hardcoded ETF/crypto/commodity lists
     (MSFT isn't), the "default" it actually restores is always `etf`.
  b. Same component's toggle-off behavior: clicking the
     **already-selected** bucket pill again
     (`onBucketChange(ticker.id, b === effective && ticker.bucketOverride ? null : b)`,
     ~line 132) sends `null` instead of re-sending `'equity'` — so
     re-opening the dropdown after correctly setting Equity and
     clicking "Equity" again (a very natural thing to do, e.g. to
     double-check or dismiss the menu) silently clears the override
     right back to the broken state.
  c. `client/src/pages/Radar.jsx`'s ticker-edit modal — its Asset
     class `<select>` (~line 1157) has options for `""` (labeled
     *"Equity (default — individual stock, analyst-scored)"*), `etf`,
     `commodity`, `crypto` — **no explicit `"equity"` option at all**.
     Selecting "Equity" here, or simply having it pre-selected while
     saving an unrelated edit, submits `bucketOverride: '' || null =
     null` (~line 872/347/365) — same broken fallback.

All three are plausible explanations for what Luis actually clicked;
the report doesn't specify which one, and it doesn't matter — they all
funnel into the exact same underlying defect, confirmed and fixed at
its single root cause (see below) rather than chasing each UI trigger
individually.

**4. Reproduce end-to-end via a real Force Sync?** Per the code trace
in step 3, a resync of MSFT (already `status: 'portfolio'`, with
existing `schwab`-source lots) cannot reach any `bucketOverride`-writing
branch in `schwabSync.js` at all — confirmed by re-reading the loop
structure, not by inference. Did **not** actually trigger a live Force
Sync: `POST /api/schwab/sync/:accountId` requires `requireAuth()`, and
no valid Clerk session token was available from this environment to
exercise it live. Given the code-level proof already rules out sync as
a possible cause for an already-`portfolio`-status ticker, this
live-trigger step was judged unnecessary to reach a definitive answer,
per the prompt's own allowance to rely on code-level checks when a live
path isn't reachable — flagging this as the one step not literally
executed, with the reasoning for why it wasn't needed.

## The fix

`server/routes/portfolio.js`, `enrichPosition()` (~line 66-73):

```diff
-  // Effective bucket: override wins, else smart default
+  // Effective bucket: override wins, else smart default. Position has no
+  // assetType column, so passing 'Equity' here (not pos.assetType, which
+  // never exists) makes smartDefaultBucket's known-symbol checks (crypto/
+  // commodity/well-known ETFs) still apply, while any other symbol with no
+  // override correctly defaults to 'equity' instead of silently falling
+  // through to 'etf' (see "Reset to default"/RADAR's blank "Equity (default)"
+  // option, which both write bucketOverride: null intending equity).
   const effectiveBucket = pos.ticker.bucketOverride
-    ?? smartDefaultBucket(pos.assetType || '', pos.ticker.symbol);
+    ?? smartDefaultBucket('Equity', pos.ticker.symbol);
```

One line changed. `smartDefaultBucket(schwabAssetType, symbol)`
(`server/lib/portfolioImport.js:25-32`) checks hardcoded
crypto/commodity/well-known-ETF symbol lists **first**, and only falls
to the `schwabAssetType === 'Equity'` check afterward — those symbol-list
checks are unaffected by this change and still correctly classify QQQ,
IBIT, GLD, etc. even with a `null` override. Passing the literal string
`'Equity'` (instead of the always-empty `pos.assetType || ''`) simply
makes the *last* branch — the one that's supposed to catch "yes, this
is a plain equity" — actually able to fire, since it's the only branch
that was structurally dead at this call site.

**Why this specific fix, not a UI-side patch:** all three trigger
points identified in step 3 write the same `null` value with the same
intent ("use the default, which should be equity") — patching one of
them (e.g. just "Reset to default") would leave the other two as live
traps. Fixing the shared fallback function call closes all three at
once, and only affects the ONE call site in the whole codebase where
`pos.assetType` was being read off a `Position` row that doesn't have
that field — the other two `smartDefaultBucket()` call sites in the
repo (`portfolioImport.js:116`, `portfolio.js:572`, both inside CSV-import
code) operate on parsed CSV rows that **do** carry a real `assetType`
string from the brokerage file, and are untouched by this change.

## Verification performed

- **Blast-radius check (read-only, before committing):** queried every
  currently-**active** `Position` in the whole database for a ticker
  with `bucketOverride === null` — **zero results**. Every existing
  active position already has an explicit override (consistent with
  this codebase's established, previously-fixed pattern of always
  writing `bucketOverride` explicitly at ticker-creation time — see the
  extensive comments already in `schwabSync.js` about the exact same
  class of bug for newly-created tickers). This means the fix changes
  behavior for **zero currently-displayed positions** — it only
  changes what happens the *next* time something writes
  `bucketOverride: null` for an existing ticker (i.e., closes the
  three traps above going forward).
- **Direct before/after simulation** of the exact expression, run
  outside the DB entirely (pure function calls):
  ```
  If bucketOverride were null, effectiveBucket (after fix): equity      # MSFT-style symbol
  QQQ with null override (after fix): etf                              # symbol-list check still works
  IBIT (crypto) with null override (after fix): crypto                 # symbol-list check still works
  ```
- `node --check server/routes/portfolio.js` — passes.
- Re-grepped after editing to confirm the new `smartDefaultBucket('Equity', ...)`
  call landed exactly as written, and that the other two
  `smartDefaultBucket()` call sites in the repo were correctly left
  untouched (they operate on parsed-CSV data with real `assetType`,
  not `Position` rows).
- `git diff --stat` — confirms only the intended 8-line hunk (comment +
  one changed argument) in `server/routes/portfolio.js`.

## What was written to the live database (per the constraints section)

This recon involved live writes to `Ticker` id 82 (MSFT) as part of
reproducing and confirming the PATCH route's behavior — explicitly
sanctioned by the prompt ("writing to `Ticker` rows for bucket
classification is low-risk... say clearly in the wrap-up what was
written"):

1. `bucketOverride`: `"equity"` (starting state) → `"etf"` (test write,
   to confirm the PATCH route persists a change) → `"equity"` (test
   write, restoring the correct value).
2. **End state confirmed: `Ticker.id=82` (MSFT) `bucketOverride =
   "equity"`** — the correct value, matching what Luis wants. No
   `Lot`/`Position`/`Account` row was touched at any point.

## Deviations from the prompt

1. **Did not literally trigger a live Force Sync (step 4).** The route
   requires `requireAuth()` and no session token was available in this
   environment. Substituted a full code-trace of `schwabSync.js`'s
   loop structure, which definitively shows a resync of an
   already-`portfolio`-status ticker with existing lots cannot reach
   any `bucketOverride`-writing branch — the same conclusion a live
   trigger would have confirmed, reached without needing write access
   to a real sync.
2. **Found three UI trigger points, not one.** The prompt's context
   named only the Portfolio page's `BucketPill`; investigation also
   surfaced RADAR's edit modal and `BucketPill`'s own toggle-off
   behavior as equally-broken paths sharing the identical root cause.
   Fixed the shared root cause rather than guessing which one Luis
   actually hit.
3. **Flagging, not fixing, a separate finding:** `PATCH
   /api/portfolio/tickers/:id/bucket` has no authentication check at
   all (confirmed via an unauthenticated `curl` returning `200`),
   unlike `GET /api/portfolio/accounts` (`401` unauthenticated) and the
   Schwab sync route (`requireAuth()`). This is unrelated to the
   persistence bug and out of scope for this recon — noting it for
   Luis rather than fixing it unprompted.

## What was deliberately NOT done

- Did not touch the three UI trigger points themselves
  (`BucketPill`'s "Reset to default" link/toggle behavior, RADAR's
  Asset-class dropdown) — the backend fix makes all of them resolve
  correctly now, so no UI change was necessary. Left as-is rather than
  making cosmetic changes beyond what's needed to fix the defect.
- Did not add an `assetType` column to `Position` — that would be the
  "more correct" long-term fix (letting `enrichPosition()` use a real,
  per-position asset type instead of a symbol-list heuristic), but it's
  a schema migration with a much larger footprint than this recon's
  scope — flagging as a possible future improvement, not implementing
  it.
- Did not fix the missing-auth-check finding on the bucket PATCH route
  — separate, pre-existing issue, flagged above for Luis's judgment.
- Did not trigger a real Schwab Force Sync (see deviation #1).

## Follow-up for Luis

1. Reload the Portfolio page for Andrea Custodial — MSFT should now
   show under Equities (its `bucketOverride` is currently `"equity"`
   in the DB, left there by this recon's verification writes).
2. The specific traps (re-clicking an already-selected bucket pill,
   using "Reset to default," or saving a RADAR ticker edit while its
   Asset class shows "Equity (default)") no longer cause a revert —
   they now correctly resolve to `equity` — but if you'd like the
   labels/behavior cleaned up further (e.g., an explicit "Equity"
   option in RADAR's dropdown instead of the blank default, or removing
   the now-safe-but-still-slightly-misleading toggle-off behavior),
   that's a small follow-up UI task, not required for correctness.
3. Consider (separately, no urgency) whether `PATCH
   /api/portfolio/tickers/:id/bucket` should require auth like the
   rest of the portfolio routes.
4. To verify the DB state directly at any time (read-only):
   ```bash
   cd server && export DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) && node -e "
   const {PrismaClient}=require('@prisma/client');const p=new PrismaClient();
   (async()=>{ const t = await p.ticker.findUnique({ where: { symbol: 'MSFT' } });
     console.log('bucketOverride:', t.bucketOverride);
     await p.\$disconnect(); })();"
   ```
5. To confirm the live deployment has this fix, check
   `investment-agent-DEV`'s latest deployment commit hash matches
   `4feea87` (same pattern used in the earlier Force-Sync recon):
   `railway status --json` (after `railway link -p investment-agent-DEV
   --service investment-agent-DEV`) and look for
   `latestDeployment.meta.commitHash`.
