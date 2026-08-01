# Per-Account Portfolio Construction — Design Spec

**Status:** Approved design, not yet implemented.
**Prerequisite:** Read DESIGN_PRINCIPLES.md and DOMAIN.md before implementing.

---

## Problem statement

The current moves engine computes model weights at the total-portfolio level, then routes
the resulting buy/sell amounts to specific accounts. This breaks for small accounts
(ROTH IRA, IRA) where:

- Annual contribution limits (~$7K) mean the account grows slowly
- Minimum position size ($1,500) means only 3–5 positions can be funded at current value
- The engine recommends positions at whole-portfolio weight (e.g. "add $2,316 of AVGO")
  but the account has $0 cash — surfacing unfundable recommendations
- The portfolio stays perpetually under-diversified because every position is "behind"
  simultaneously and contributions are too small to close all gaps at once

---

## Three-tier architecture

### Tier 1 — Global conviction list (unchanged)

The analyst and allocator continue to operate on the whole portfolio. Output: a ranked
list of positions by conviction, with thesis health, trajectory, and recommended sizing.
The analyst/allocator firewall is preserved. No per-account logic here.

### Tier 2 — Per-account position target

Each account is assigned a target number of positions based on its current value:

```
targetPositions(account) = min(M, max(N, floor(accountValue / minPositionDollar)))
```

Where:
- `minPositionDollar` — minimum meaningful position size (default $1,500, per OwnerProfile)
- `N` — minimum positions floor (prevents 1–2 position accounts; suggested default: 3)
- `M` — maximum positions ceiling (prevents index-like dilution; suggested default: 10–12
  for tax-advantaged accounts, 15 for taxable)

**Scaling examples** (minPositionDollar=$1,500, N=3, M=10):

| Account value | floor(value/1500) | targetPositions |
|---|---|---|
| $5,000  | 3  | 3  |
| $10,000 | 6  | 6  |
| $30,000 | 20 | 10 (capped at M) |
| $1M     | 666| 10 (capped at M) |

**Account share modifier**: N and M should also account for the account's share of the
total portfolio. A ROTH that is 60% of total portfolio value needs more diversification
than a ROTH that is 10%. Suggested: if `accountValue / totalPortfolioValue > 0.40`,
raise the effective N by 2 and surface a warning (see §Warnings below).

### Tier 3 — Per-account model weights

Each account holds the top-N positions from the global conviction list, ranked by
analyst signal quality (trajectory + health + type + finalAction score).

Within the account, positions are weighted by conviction — NOT derived from whole-portfolio
percentage targets. Example: ROTH with targetPositions=3 holds AVGO/NVDA/ORCL at
roughly 33% each within the ROTH.

The whole-portfolio hard caps (Type A: 35%, Type B: 50%) continue to apply at the
aggregate portfolio level as a concentration check — not as per-account targets.

---

## Warnings (implement first — Task #20)

Two new warning types added to the existing `warnings[]` array in `computeMovesPayload`.

### Warning 1: Too few positions for account size

**Fires when:** `currentPositionCount < floor(accountValue / minPositionDollar)`
and `currentPositionCount < M`

**Severity:** amber

**Message:** "{AccountName} has {X} positions but could support up to {Y} at its current
value (${accountValue}). Consider adding {Z} more from the conviction list."

**Accept action:** One-click accept updates `minPositions` on the owner's OwnerProfile
(or a new per-account field). Must not require navigating to the Admin tab.

**Warning payload** must include:
```json
{
  "type": "too_few_positions",
  "accountName": "Andrea ROTH IRA",
  "accountType": "roth",
  "currentCount": 2,
  "supportedCount": 5,
  "suggestedTarget": 5,
  "actionType": "update_position_target",
  "actionPayload": { "owner": "Andrea Morales", "accountId": 3, "suggestedTarget": 5 }
}
```

### Warning 2: Account over-concentrated in portfolio

**Fires when:** `accountValue / totalPortfolioValue > 0.40` AND `positionCount < M`

**Severity:** amber

**Message:** "{AccountName} represents {X}% of your total portfolio with only {Y}
positions. Consider raising its position target to reduce concentration risk."

**Accept action:** Same as Warning 1 — updates the position target without going to Admin.

---

## Build sequence

1. **Warnings (Task #20)** — backend only, slots into existing warnings[] array.
   Frontend: add Accept button to warning cards that PATCHes OwnerProfile.
   Self-contained, no engine refactor needed.

2. **Per-account model weights (Task #21)** — engine refactor in `computeMovesPayload`.
   - Compute targetPositions per account using the formula above
   - Select top-N tickers from global conviction ranking for each account
   - Compute within-account weights (equal or conviction-weighted)
   - Replace current "aggregate weight → route to accounts" logic
   - Preserve whole-portfolio cap enforcement as a post-computation check

---

## Schema changes needed (Task #21)

Per-account position targets may need storage if users accept warning recommendations:

```prisma
// Option A: add to OwnerProfile (applies to all accounts for that owner)
minPositions  Int?   // floor N (default 3)
maxPositions  Int?   // ceiling M — already exists at portfolio level; extend per-account

// Option B: new per-account override table
model AccountPositionConfig {
  id           Int     @id @default(autoincrement())
  accountId    Int     @unique
  minPositions Int?
  maxPositions Int?
  account      Account @relation(fields: [accountId], references: [id])
}
```

Option B is preferred — it allows ROTH and Taxable to have different M values without
polluting OwnerProfile with per-account fields.

---

## Open questions (resolve before Task #21 implementation)

1. Should accounts hold the **same** top-N positions (each account is a scaled copy of
   the global list) or **different** positions (sleeve approach, no overlap)?
   → Lean toward same positions, different scales. Simpler, avoids fragmentation.

2. When an account grows from N=3 to N=4 (new contribution arrives), which position
   gets added — strictly rank 4 from conviction list, or does the agent re-optimize?
   → Strictly rank 4. Re-optimization on every contribution adds complexity without
   meaningful benefit at small account sizes.

3. How does the per-account weight interact with the whole-portfolio hard cap check?
   → Run the per-account engine first, then do a whole-portfolio cap check as a
   post-pass. If any position exceeds its hard cap in aggregate, generate a TRIM_CAP
   move for the account where it's easiest to trim (tax-advantaged first).
