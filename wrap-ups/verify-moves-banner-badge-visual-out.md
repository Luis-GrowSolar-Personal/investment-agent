# Verify: Moves banner, mandatory decline reason, pending-execution badge — OUT

**Task type:** verification only. No code changed, nothing committed.
**Date:** 2026-08-23
**Commit under test:** `02c7c78` (HEAD; includes `9ac0c20`)
**Environment:** `https://investment-agent-dev-production.up.railway.app`

---

## Verdict summary

| # | Check | Verdict |
|---|---|---|
| 1 | Banner (everyday mode) | **PASS** — negative case source-verified only |
| 2 | Pending-execution badge | **COULD NOT TEST** — no accepted move exists anywhere |
| 3 | Radar `StaleTranscriptBadge` no-op | **PASS** |
| 4 | No suppression of resolved moves | **PASS** |
| 5 | Mandatory decline reason | **PASS** |

No defects found. One cosmetic observation on the badge tooltip (§2) worth
a look before it ships in front of a real accepted move.

---

## Pre-flight — deploy gate PASSED

```
investment-agent-cron-keep-alive  02c7c78c  SUCCESS
investment-agent-db-dev                     SUCCESS
investment-agent-DEV             02c7c78c  SUCCESS
```

Local HEAD is `02c7c78`; `git merge-base --is-ancestor 02c7c78 HEAD` → true.

**Cache-busting:** navigated to `/?_=20260823banner`. Bundle went from
`index-g8YkzKfp.js` (the `67c91b4` build verified earlier this session) to
`index-Cx58Rm0W.js`. Different content hash ⇒ new code. Corroborated by the
new `snapshotAmount` field appearing in the live API payload (see §2), which
did not exist before this commit.

**Mode confirmed:** all three owners return `isFreshStart: false`
(`isRebaseline: true`), so every observation below is the everyday-mode path.

---

## Check 1 — Banner — **PASS**

Renders above the move list, below the ACTION REQUIRED heading. Copy matches
the specified string **character-for-character** (compared programmatically
against the expected literal, `exactMatch: true`):

> These are today's recommended trades to bring your allocation back toward
> target, based on current prices. Declining any trade requires a logged reason.

Computed style matches `MovesBanner`'s spec exactly:

| Property | Value |
|---|---|
| background | `rgb(13, 16, 24)` (`C.card`) |
| border-left | `3px rgb(96, 165, 250)` (`C.blue`) |
| border-radius | `6px` |
| padding | `9px 12px` |
| font-size | `12px` |
| color | `rgb(148, 163, 184)` (`C.muted`) |

Confirmed present for all three owners: Andrea (13 moves), Eduardo (18),
Luis (7).

**Zero-moves negative case — not reproducible live.** All three owners
currently have open moves, and both bucket filters on every owner are
non-empty, so no zero-move view exists to navigate to. The prompt anticipated
this ("if one exists"). Source is unambiguous — the banner sits inside
`displayMoves.length > 0 && <MovesBanner …>` (`PortfolioManager.jsx:1854`),
and the "✓ No action required" empty state is the else-branch of a ternary on
that *same* expression, so the two are mutually exclusive by construction.
Not independently observed.

## Check 2 — Pending-execution badge — **COULD NOT TEST**

**No accepted move exists on any owner.** Queried the live payload for all
three: `withPriorDecision` is empty for Andrea and Eduardo; Luis has exactly
one prior decision, SPWR `TRIM_CAP`, and its `decision` is **`declined`**.
Zero `✓ Accepted` spans render anywhere in the app.

Producing one would mean accepting a real move against live account data,
which this prompt's "What NOT to do" forbids. The capture-phase-detector
trick used earlier this session doesn't help here: it proves a click *reaches*
a handler while suppressing the effect, but the badge requires the accepted
state to actually **persist and re-render**, which is precisely the mutation
being avoided. So this is a genuine gap, not a shortcut I declined to take.

**Compensating evidence gathered (does not substitute for seeing it):**

- **The visual is verified.** The badge is `CircledBangBadge`, the same
  component Radar renders — confirmed live in §3 with the exact spec'd
  geometry (14×14, 50% radius, amber, `cursor: help`). The Moves usage passes
  `color={C.amber}`, the same token Radar's non-overdue branch uses.
- **The server half is verified.** `snapshotAmount` is present and populated
  in the live payload — SPWR carries `snapshotAmount: 11938.22` with
  `acceptedAmount: null`, exactly the case the commit added it for.
- **Negative case confirmed.** SPWR's declined row renders `✗ Declined` with
  **no** badge, so the badge is correctly scoped to `status === 'accepted'`.
- **Exact tooltip computed** by replaying the template
  (`PortfolioManager.jsx:494–502`) against SPWR's real `priorDecision`:

  > Accepted on 6/27/2026 at $11,938 — still pending execution. It is still
  > listed because the position has not reached target yet; if you have
  > already placed this trade it will drop off once a broker sync reflects it.

  Wording is sensible and non-alarmist, and matches what the prompt expected.

### Observation worth acting on before this ships

`decidedAt` is `2026-06-28T00:11:09.592Z`, but `toLocaleDateString()` renders
it as **6/27/2026** in US Eastern — the UTC timestamp is 11 minutes past
midnight, so local time is the previous day. Any decision made late-evening
local will display a date one day earlier than the DB record. Cosmetic, and
pre-existing to this pattern rather than introduced by the commit, but the
tooltip makes an explicit factual claim about a date, which is where that
kind of drift is most likely to be noticed and doubted.

## Check 3 — Radar `StaleTranscriptBadge` no-op — **PASS**

**Source:** the diff moves the style block verbatim into
`components/CircledBangBadge.jsx` and replaces it with
`<CircledBangBadge color={color} title={tip} />`. The threshold logic and both
tooltip strings stay in `Radar.jsx` untouched. Byte-identical by inspection.

**Live:** five badges rendering on Radar, all with the spec'd geometry —
`14px × 14px`, `border-radius: 50%`, `font-size: 9px`, `font-weight: 800`,
`margin-left: 4px`, `cursor: help`, `display: flex`. Tooltip copy is the
pre-refactor text verbatim, e.g.:

> Last transcript: 95 days ago. Quarterly companies typically release every
> 85-95 days — a new one is likely available. Time to check your sources.

**Colour logic spot-checked against the thresholds.** Observed 86, 86, 94, 95
and 96 days, all amber `rgb(251, 191, 36)` = `#fbbf24`. The 96-day case looked
like a possible off-by-one, so I checked: `Radar.jsx:165` is
`daysSinceLastCall >= 100` for red. 96 is correctly amber. No off-by-one.

**Caveat:** no ticker is currently ≥100 days stale, so the red `#ef4444`
variant was not observed live. Its colour is selected by the same untouched
ternary, so risk is negligible.

## Check 4 — No suppression of resolved moves — **PASS**

For Andrea: payload `moves.length` = 13, tab label "Recommended Moves (13)",
and scanning every child of the moves grid for `display:none`,
`visibility:hidden`, or `opacity < 0.9` returned **0**. Nothing is
rendered-but-hidden and nothing is greyed — the rendered set equals the
payload set.

**Limit of this check:** I could not force a live diff to *resolve* and then
observe the move drop off, since that requires an actual position change.
What is confirmed is the weaker but still useful property: the UI does not
retain or grey out anything the server omits.

## Check 5 — Mandatory decline reason — **PASS**

Tested against Luis's existing declined SPWR move — no new decision created.

| Sub-check | Result |
|---|---|
| "change" on a declined move prefills the reason | **PASS** — 233 chars, exact match to `priorDecision.reason` |
| Empty reason blocks submit | **PASS** — `disabled: true`, `opacity: 0.5`, `cursor: not-allowed` |
| Non-empty reason re-enables submit | **PASS** — `disabled: false`, `opacity: 1`, `cursor: pointer` |

The prefilled value is editable (cleared it with a real select-all + delete,
then typed into it), confirming it is a live input and not display text.

**I did not actually submit the decline** — see Deviations.

**Post-test state verified clean:** editor closed via Cancel, and re-querying
the API shows SPWR unchanged — still `declined`, same
`decidedAt: 2026-06-28T00:11:09.592Z`, same reason text. No mutation.

---

## Deviations from the prompt

1. **Check 5 — did not complete a real submit.** The prompt says "Enter a
   reason and confirm it submits normally," but the same prompt's constraints
   forbid changing any real move. Submitting would have overwritten a genuine
   June decision (including its reason and timestamp) with the word "test".
   I verified the button transitions from disabled to enabled on non-empty
   input and then cancelled. The gate is what was under test and it is
   confirmed; the POST path itself was already source-verified in the build
   wrap-up.
2. **Check 2 — reported as COULD NOT TEST rather than manufacturing state.**
   Explained above; creating an accepted move is exactly the action ruled out.
3. **Check 1 negative case and Check 4's stronger form** could not be
   reproduced because the live data doesn't contain the required situations.
   Both stated plainly rather than glossed.

## Deliberately NOT done

No code changed. No move accepted or declined. No position edited. No Force
Sync and no Schwab API call triggered — note the header showed "Schwab synced
just now (4)" on arrival, which was the app's own scheduled sync, not
something I initiated.

## Left for Luis

Nothing blocking. Two items:

1. **The badge still has never been seen rendered.** It will first appear in
   front of a real accepted move. Cheapest way to close this properly is to
   glance at the Decision cell the next time you accept something in the
   normal course of using the app.
2. **Tooltip date drift** (§2) — a late-evening local decision displays as the
   prior day. One-line fix if it bothers you; ignorable if not.

Re-check the deploy gate and bundle freshness on any future run:

```
railway status --json | python3 -c "import json,sys; d=json.load(sys.stdin); [print(n['node']['serviceName'], (((n['node'].get('latestDeployment') or {}).get('meta') or {}).get('commitHash') or '')[:8]) for e in d['environments']['edges'] for n in e['node']['serviceInstances']['edges']]"
```

Then load `/?_=<timestamp>` and confirm the hashed bundle name changed:

```
[...document.querySelectorAll('script[src]')].map(s => s.src)
```
