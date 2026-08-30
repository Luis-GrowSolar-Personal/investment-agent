# Verify: Moves grid chrome + swallowed-click fixes — OUT

**Task type:** verification only. No code changed, nothing committed.
**Date:** 2026-08-23
**Commit under test:** `67c91b4` ("Fix Moves grid overflow chrome,
swallowed post-drag click, and stale Schwab reconnect message")
**Environment:** `https://investment-agent-dev-production.up.railway.app`

---

## Verdict summary

| # | Check | Verdict |
|---|---|---|
| 1 | Moves grid card chrome covers overflow | **PASS** |
| 2 | Swallowed click after outside-drag-end | **PASS** |
| 3 | Schwab message text changed (source-only) | **PASS** |

All three defects from `wrap-ups/verify-drag-scroll-standardization-out.md`
are fixed. No regressions found. No new defects found.

---

## Pre-flight — deploy gate PASSED

Read `wrap-ups/fix-moves-chrome-swallowed-click-schwab-message-out.md`
first for the commit hash, as instructed (it is `67c91b4`, not `af48727`).

```
investment-agent-cron-keep-alive  67c91b4b  SUCCESS
investment-agent-db-dev                     SUCCESS
investment-agent-DEV             67c91b4b  SUCCESS
```

Matches. Local `git log` confirms `67c91b4` is HEAD on `dev`.

### Cache-busting — method used, and proof the new bundle loaded

**Method:** navigated to the URL with a cache-busting query param
appended — `/?_=20260823verify2` — rather than a plain reload.

**Proof the new code is actually running**, not assumed: Vite emits
content-hashed asset filenames, so the bundle name changes whenever the
code changes. The prior verification session (pre-fix, commit `af48727`)
loaded:

```
/assets/index-CX5EV50s.js
```

This session loads:

```
/assets/index-g8YkzKfp.js
```

Different hash ⇒ different bundle ⇒ new code. Independently corroborated
by behavior: the Check 2 click that was reproducibly swallowed before now
reaches its handler, and the Check 1 grid now carries an inline
`min-width: max-content` that did not exist pre-fix.

---

## Check 1 — Moves grid card chrome — **PASS**

The grid at `PortfolioManager.jsx:1816` now carries
`minWidth: 'max-content'`; confirmed live as
`style.minWidth === "max-content"` on the element with the card border.

Measured the same way as the prior verification (bounding box of the
painted card vs. the union of its children), scrolled fully right to the
Decision column:

| Viewport | Card box width | Content outside card — **before** | Content outside card — **now** |
|---|---|---|---|
| 800px | 995px | 68px | **−13px** (inside) |
| 500px | 995px | 368px | **−13px** (inside) |

Negative means the content sits *inside* the painted box. −13px on both
edges is exactly the card's 12px padding + 1px border, i.e. correct.

The card box is now 995px — the full content width — instead of
collapsing to the container width (437px at the 500px viewport). Visually
confirmed at 500px: background, border, and rounded corner all extend past
the Decision column, with Accept/Decline fully inside the card. Nothing
renders on bare page background any more.

Grid still scrolls and drag-pans (container 437px visible / 995px content,
`cursor: grab`), so the fix did not trade scrolling away for chrome.

## Check 2 — Swallowed click after outside-drag-end — **PASS**

Tested on Eduardo Custodial (10 equity rows, 879px visible / 1181px
content). Used the same capture-phase detector as the prior verification:
a listener on the ✎ button that records the click reached it and then
stops propagation, so `onEdit` never actually runs against live data.

| Sub-check | Result |
|---|---|
| Drag inside, release inside — still pans, no row toggle | **PASS** — `scrollLeft` 0 → 302, rows stayed 10 |
| Drag released **outside** the table, then click ✎ | **PASS** — `REACHED` (this is the click that did nothing before) |
| The very next click after that one | **PASS** — `REACHED` again; the fix didn't just shift which click gets eaten |
| Plain row click, no preceding drag | **PASS** — 10 → 27 rows (lot detail expands) |
| Row did not toggle when clicking the action icon | **PASS** — rows stayed 10 across both ✎ clicks |

The drag for the outside-release case went from (700,500) to (300,770);
the container's bottom edge is y=718, so the release genuinely landed
outside it and `onMouseLeave` terminated the drag with no click to clear
the flag — the exact pre-fix repro.

**Behavior change worth recording:** the fix also swapped the
interactive-target guard from a bare `tagName` check to
`e.target.closest('button, a, input, select, textarea')`. That closes the
`<svg>`-inside-`<button>` hole I flagged last time (Portfolio's rename
icon). Side effect: pressing on the rename icon no longer initiates a
drag-pan, where it used to. That is the intended behavior for an
interactive control, and it makes rename consistent with ✎ and ×, but it
is a real change to what a press on that icon does.

## Check 3 — Schwab message — **PASS** (source-only, as instructed)

Read `server/routes/schwab.js` from the repo. Both the comment and the
user-facing string were changed. Not browser-tested — that would require
manufacturing a real `SCHWAB_TOKEN_EXPIRED`, which the prompt explicitly
ruled out.

**Comment — before:** asserted Schwab's refresh_token has "a hard 7-day
expiration from the original authorization" that rotation does not reset,
framing the error as "an expected recurring state."

**Comment — now:** states that claim is wrong, citing the 2026-08-22
measurement (a token from the 2026-06-13 authorization still refreshing
~70 days later, with the refresh_token value not rotating across four
refreshes). It explicitly labels the 7-day-*inactivity* theory a
hypothesis rather than a measurement, says not to quote a number, and
notes a broker-side outage can surface as the same error with a perfectly
good stored token. Cross-references
`wrap-ups/fix-keepalive-unconditional-refresh-out.md`.

**User-facing message — before:**
> Broker connection needs reconnecting — Schwab requires manual
> reconnection at least every 7 days. Use "Reconnect" in Admin > Broker
> Connections.

**User-facing message — now:**
> Schwab rejected the stored credentials. If Schwab is reachable and you
> can log in there normally, reconnect via "Reconnect" in Admin > Broker
> Connections; if Schwab itself is down or erroring, this usually clears
> on its own once their service recovers.

`client/src/pages/Admin.jsx:1553` had the matching claim removed too —
the expired-token line now ends at "will auto-refresh on next use."

### Residual, out of scope — not a failure

`grep` for lingering 7-day claims turned up
`server/lib/schwabAuth.js:228`:

> `// Well inside the ~7-day refresh_token lifetime.`

That restates the unverified number without a caveat. It is the rationale
comment for the keep-alive interval, and the same file's header
(lines 25–36) already documents the contradicting 70-day measurement at
length, so the file is not self-contradictory in a misleading way. It was
also outside this fix's stated scope (which named `schwab.js` and
`Admin.jsx` only). Flagging it as a tidy-up candidate, not a defect.
The other hit, `server/routes/users.js:208`, is a Clerk invitation TTL —
unrelated.

## Check 4 (not asked, but recorded) — console

One message across the whole session, from the new bundle:

```
[priceRefresh] updated=37 schwab=17 polygon=0 errors=1
```

An application data-fetch counter, unrelated to these fixes and present
pre-fix too. **No JS exceptions, no React warnings** during any drag,
click, or resize.

---

## Deviations from the prompt

1. **375px still not testable** — Chrome clamps its window to a ~500px
   minimum viewport, so 500px remains the narrow case, exactly as the
   prompt anticipated.
2. **Nothing fixed** — verification only, per the constraint.
3. Never clicked Accept, Decline, Remove, or a real Edit. The ✎ clicks
   were intercepted by the capture-phase detector so `onEdit` never fired.
   No Force Sync, no Schwab API call, no attempt to break the stored token.

## Left for Luis

Nothing blocking. Both browser-testable fixes verified working, and the
Schwab text is corrected in both the API response and the Admin UI.

One optional tidy-up: `server/lib/schwabAuth.js:228` still says "well
inside the ~7-day refresh_token lifetime," which is the same unverified
number the rest of this commit set out to stop quoting. One-line comment
edit if you want the codebase fully consistent.

Deploy gate for any future run (it will move past `67c91b4`):

```
railway status --json | python3 -c "import json,sys; d=json.load(sys.stdin); [print(n['node']['serviceName'], (((n['node'].get('latestDeployment') or {}).get('meta') or {}).get('commitHash') or '')[:8]) for e in d['environments']['edges'] for n in e['node']['serviceInstances']['edges']]"
curl -sI https://investment-agent-dev-production.up.railway.app | head -1
```

And to re-confirm a fresh bundle rather than a cached one, load
`/?_=<timestamp>` and check the hashed asset name changed:

```
# in the browser console
[...document.querySelectorAll('script[src]')].map(s => s.src)
```
