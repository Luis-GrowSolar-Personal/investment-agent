# Conformance Fixtures — proving the app implements the validated model

**Status:** Drafted 2026-09-02. Implements `PROMOTION_GATE.md` §2.3.
**Purpose:** Make it impossible to ship production allocator code whose decisions
differ from the simulator that validated the design — and to find out on the
commit that broke it, not at release time.

Read `PROMOTION_GATE.md` §2.3 and §5d first; this document is the mechanics of
that gate. Read `ALLOCATOR_OPERATING_MODEL.md` §9 (invariants), §10b
(reproducibility contract) and §11 (known defects) before generating or changing
a fixture set.

---

## 1. The one-sentence version

The simulator dumps, for every decision point in a frozen historical window, the
exact inputs it saw and the exact trades it produced; production's test suite
feeds itself the same inputs and asserts it produces the same trades.

---

## 2. What a fixture is

One fixture is a triple:

    (event, portfolio state before, expected trade list)

- **event** — what woke the allocator: an earnings-call date with its
  transcript-derived score, or a scheduled session under cadence `K`.
- **portfolio state before** — everything the allocator is allowed to see at
  decision time: per-account positions, per-account cash, cost bases, holding
  periods, trailing peaks, type classifications, and the session bookkeeping the
  per-session limit `X` depends on.
- **expected trade list** — the ordered decisions the validated model produced.

The fixture is **self-contained**. Production must be able to satisfy it without
a database, a network call, or a price feed beyond what the fixture carries. A
fixture that requires standing up the app is not a unit test and will rot.

---

## 3. Schema

`analysis/data/fixtures/<fixture_set_id>/fixtures.jsonl` — one JSON object per
line, ordered by `session_date` then `sequence`.

```json
{
  "fixture_id": "0076",
  "session_date": "2023-08-14",
  "sequence": 76,
  "event": {
    "kind": "earnings_call",
    "ticker": "ENPH",
    "call_date": "2023-08-14",
    "analysis_id": 4412,
    "score": {
      "thesisHealth": "weakening",
      "recommendation": "trim",
      "recommendedSize": 0.15,
      "thesisDelta": -1,
      "activeDriverCount": 1,
      "ratchetTranche": 1
    }
  },
  "state_before": {
    "as_of": "2023-08-14",
    "accounts": [
      {
        "account_id": "taxable",
        "tax_advantaged": false,
        "cash": 4182.11,
        "positions": [
          {
            "ticker": "ENPH",
            "shares": 141,
            "cost_basis": 18122.44,
            "acquired": "2022-03-11",
            "trailing_peak_value": 29104.02,
            "type": "A"
          }
        ]
      }
    ],
    "prices": { "ENPH": 158.24, "TTD": 79.11 },
    "portfolio_total_value": 96411.83,
    "session": {
      "session_id": "2023-08-14",
      "position_change_used_pp": { "ENPH": 0.0 }
    }
  },
  "expected_trades": [
    {
      "session_date": "2023-08-14",
      "ticker": "ENPH",
      "side": "sell",
      "shares": 47,
      "account_id": "taxable",
      "reason": "ratchet_trim_to_cap"
    }
  ],
  "diagnostics": {
    "portfolio_total_value_after": 96411.83,
    "cash_after": { "taxable": 11618.39 },
    "realized_gain": 2913.07,
    "tax_withheld": 436.96
  }
}
```

**Gated fields** — every one must match exactly:
`session_date`, `ticker`, `side`, `shares`, `account_id`, and the **order and
length** of `expected_trades`.

**Ungated fields** — `reason` and everything under `diagnostics` are reported on
mismatch and never block. `reason` is a label whose vocabulary may legitimately
differ between implementations; it is carried because it makes a failure
readable, not because it is contractual.

An **empty** `expected_trades` is a fixture, not an omission. "The allocator was
woken and correctly did nothing" is exactly the assertion a naive implementation
fails.

---

## 4. Manifest

`analysis/data/fixtures/<fixture_set_id>/manifest.json`, written per
`ALLOCATOR_OPERATING_MODEL.md` §10b:

```json
{
  "fixture_set_id": "alloc-settled-20260902",
  "generated_at": "2026-09-02T14:02:11Z",
  "git_commit": "1f0a6b5...",
  "git_dirty": false,
  "driver_file": "analysis/dump_conformance_fixtures.py",
  "config": {
    "window": ["2022-01-01", "2024-06-12"],
    "universe": "ALL16",
    "decider": "decide_v3",
    "funding_mode": "swap_funding",
    "scope": "new_calls_only",
    "cadence_K": 30,
    "session_limit_X_pp": 2.5,
    "execution": "pooled",
    "trim_budget_scope": "per_event_date",
    "dedup": true
  },
  "config_hash": "sha256:...",
  "input_hashes": {
    "price_cache.json": "sha256:...",
    "fundamentals_cache.json": "sha256:...",
    "type_classifications.json": "sha256:...",
    "analysis_corpus_20260830.sql": "sha256:..."
  },
  "fixture_count": 312,
  "expected_final_value": 184819.00
}
```

The same §10b rules apply without exception: `git_dirty: true` voids the set; the
recorded commit must contain the recorded driver; the driver is committed
**before** the manifest, as its own commit.

**`input_hashes` is the load-bearing part.** The comparison means nothing if the
two sides read different inputs, which makes the pinned caches and the corpus
dump release artifacts rather than working files. An unbacked corpus is an
unreproducible gate — see `PROMOTION_GATE.md` §2.3.

---

## 5. Generation

`analysis/dump_conformance_fixtures.py`, run against the settled configuration
recorded in `ALLOCATOR_OPERATING_MODEL.md` §0.

- It **observes**; it does not re-simulate. The dumper hooks the existing
  decision path and records what it saw and emitted. A second code path that
  computes the fixtures independently would be a third implementation to keep
  correct.
- One fixture per decision point, including the no-trade ones.
- Serialize money as a decimal string, never a float, so JSON round-tripping
  cannot alter a gated value. Shares are integers.
- Flush per fixture. The generator is subject to `CLAUDE.md`'s resumability rule
  like any other long run.

---

## 6. Consumption

Production's test suite loads `fixtures.jsonl` and, for each line, constructs the
allocator's input state directly from `state_before` — no database, no fetch —
calls the sizing/decision entry point, and asserts the gated fields.

- Runs in CI on **every commit**, not on demand. The whole reason fixtures beat a
  replay engine is that they catch the divergence on the commit that caused it.
- Test time is a design constraint. If 312 fixtures cannot run in seconds, the
  allocator entry point is too entangled with I/O, and that is itself the finding.
- The fixture set is checked in. It is small, it is the contract, and a contract
  fetched at test time is a contract that can change without a diff.

---

## 7. Failure reporting

On any mismatch the suite reports:

1. the **first** diverging fixture — `fixture_id`, `session_date`, and both
   sides' `(ticker, side, shares, account_id)`;
2. how many fixtures matched before it;
3. the ungated diagnostics for that fixture, as context only.

Everything after the first divergence is downstream noise and is not reported as
additional failures. `entries 0–75 match, entry 76 does not` is the output this
gate exists to produce.

---

## 8. Coverage

A fixture set that only contains ordinary Adds proves very little. The set must
contain at least one of each, and the generator reports the census:

| Case | Why it is in the set |
|---|---|
| No-trade session | The most common naive-implementation failure |
| Add, fully funded | Baseline |
| Add, partially funded | §11 defect #3 — unfundable trades fail silently |
| Add clipped by the session limit `X` | Invariant #9, per session, aggregate |
| Add clipped by the tier cap | Invariant #2 — **target**, not realized weight |
| Swap funding with a donor trim | The funding path the settled config uses |
| Donor trim hitting the `minPositionPct` stub rule | Whole-position sale branch |
| Ratchet trim, each tranche | §3 of `CLAUDE.md` — four distinct behaviors |
| Full exit | Terminal ratchet tranche |
| Multi-event date, pooled | 44.2% of events in this corpus share a date |
| Cross-account trim ordering | Tax-advantaged first (`CLAUDE.md` §4) |
| Year-end forced liquidation | The `cbba37e` Dec-31 anchoring fix |
| Position above 30% of portfolio | The 48-hour waiting period |

Cases that `ALLOCATOR_OPERATING_MODEL.md` §11 documents as **known unfixed
defects** are included as fixtures reflecting **current behavior**, explicitly
annotated `"known_defect": "s11#2"`. The gate asks whether production matches the
validated model, not whether the model is right. When a §11 defect is fixed, the
fix is a design change: it goes through §2.1, and the fixtures are regenerated
afterward.

---

## 9. Regeneration policy

Regenerating fixtures is how this gate gets quietly disabled, so:

- Fixtures are regenerated **only** as the recorded consequence of a design change
  that has already passed `PROMOTION_GATE.md` §2.1 — never to make a failing test
  pass.
- Regeneration is logged in the experiment ledger (`data/gate_ledger.json`) with
  the adopted change, the old and new `config_hash`, and the fixture-count delta.
- A regeneration commit touches fixtures and manifest **only**. A diff that
  changes fixtures and production code together is unreviewable, and reviewing it
  is the entire control.

---

## 10. What this does not test

Restated from `PROMOTION_GATE.md` §2.3 because it will be misread otherwise:
execution (slippage, partial fills, rejections, routing), the analyst layer, the
UI, and anything outside the fixture window.

**And, most importantly, input assembly.** A fixture supplies `state_before` and
checks what comes out. It never checks that the app builds that state correctly
from the database and the broker — which is exactly where §9 invariant #5 (no
trade set sized against stale state) and §11 defect #2 (starter and Add sized
against the same stale cash snapshot) live. Those cannot fail a fixture. That is
tier 2's job: the headless replay driver of `PROMOTION_GATE.md` §2.3, which
advances the app's own session entry point across the window against a seeded
database. Fixtures prove the allocator computes correctly; the replay driver
proves it is asked the right question.

A green fixture suite says the app **decides** what the validated model decides,
given the same inputs. It says nothing about whether it received the right
inputs, or whether the resulting order fills at the assumed price.

---

## 11. Build steps

1. `dump_conformance_fixtures.py` + manifest, at the §0 settled configuration.
2. The §8 coverage census, printed by the generator and reviewed once by hand.
3. Production test harness that loads the set and asserts the gated fields.
4. Wire into CI.
5. Tier 1 of `PROMOTION_GATE.md` §2.3 becomes enforceable at that point.
6. The **tier-2 headless replay driver** (`PROMOTION_GATE.md` §2.3, §9.7) — a
   separate build, sharing this document's pinned inputs and manifest discipline.
   Neither `CLAUDE.md` Step 8(a) nor anything downstream of it ships before both
   tiers are green.

---

## 12. Open items

- **Exact `state_before` shape** depends on the production allocator's entry
  signature, which does not exist yet. The schema above is the intent; settle the
  field names when the entry point is written, and keep the *gated* set fixed.
- **Multi-account fixtures** need the per-account funding model of
  `PER_ACCOUNT_PORTFOLIO_CONSTRUCTION.md`; confirm the fixture carries enough
  per-account state to reproduce the trim ordering without inference.
- **Share rounding** — confirm the simulator and production round identically
  (direction and tie behavior). If they cannot, that is the one place a gated
  field may need a documented ±1-share tolerance, and it must be argued in this
  document rather than assumed in code.
