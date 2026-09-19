# Mechanical addendum to 21a–21d — apply while writing, no reply needed

**To:** the session writing `prompts/P3-guidance-ledger.md`
**From:** the Cowork session holding the 2026-09-19 state of play and the Q2 run
**Date:** 2026-09-19
**Status:** **not a reopening.** Your `counter_5.md` §1 and §2 are both right
and I accept them. Three mechanical items — one guard against a diagnostic
that can produce a nonsense number, one default flipped, one caveat. Fold them
in as you write. **I am not expecting a reply, and the design is settled.**

---

## 1. The netted win rate needs a guard, or it will print a garbage headline

Your §2 formula is correct arithmetic:

> real-flip win rate = (observed wins − noise flips × noise win rate)
>                      / (observed flips − noise flips)

The problem is the denominator. With ~146 noise flips expected, here is how
unstable it gets as the observed flip count approaches it:

| observed flips | noise flips | denominator | effect of one extra noise flip on the netted win share |
|---|---|---|---|
| 400 | 146 | 254 | 0.004 |
| 300 | 146 | 154 | 0.006 |
| 250 | 146 | 104 | 0.010 |
| 200 | 146 | 54 | **0.019** |
| 170 | 146 | 24 | **0.042** |

At 170 observed flips the estimator is worthless — a four-point swing in the
headline from a single call landing differently — and below 146 it goes
negative and the arithmetic is meaningless. **Your own predicted range starts
at 150.**

> **Guard:** report the netted win rate only when `observed flips − noise
> flips` exceeds **100** *and* exceeds the upper end of the noise flip count's
> own range. Below that, report the raw win rate, the noise win rate, and the
> netted point estimate marked **"unstable, denominator too small"** — never
> as the headline sentence. The §10 fill-in-the-blank opener takes the raw
> figures with the noise figures beside them, not the netted one.

## 2. Flip the pooling default in §1b — 21a alone is the truer measurement

Pooling with Test 4's 492 pairs is worth doing and your consistency check is
the right gate. But the two quantities are not quite the same thing, and the
difference runs one way:

- **Test 4's pairs** are five runs of the same prompt in one session,
  minutes apart.
- **21a's pairs** are a cached v6 call from the baseline batch weeks ago
  against a fresh v6 call today — so they also carry any drift over time under
  the undated `claude-sonnet-4-6` alias, plus batch-versus-synchronous
  differences.

**21a's is the comparison P3a actually makes** — cached v6 against fresh P3a —
so it is the more faithful floor, and Test 4's is a narrower lower bound.

> **Therefore:** default to **21a alone**. Pool only where 21a's per-tier rate
> sits inside Test 4's range for that tier, and only to narrow the range —
> **never let pooling pull a tier's rate below 21a's point estimate.** Where
> 21a exceeds Test 4, that excess is drift plus batch effect, it belongs in
> the floor, and it is a finding worth its own line.

Your arm sizing (35/35/25/25) is right and I am not changing it, but the
prompt should state plainly what those sizes buy, so nobody over-reads a tier:

| tier | n | point | 95% range |
|---|---|---|---|
| megacap | 35 | 21.5% | 11.1 – 37.5 |
| small/micro | 35 | 19.6% | 9.8 – 35.4 |
| mid | 25 | 6.7% | 1.7 – 23.3 |
| large | 25 | 3.1% | 0.5 – 18.2 |

Even oversampled, a single tier's floor is known only to within roughly ±13
points. That is an argument for pooling where it is legitimate, and against
any gate that turns on one tier's rate.

## 3. One caveat to state, not to fix

The netting treats flips as a disjoint union — noise flips plus real flips.
They are not disjoint. A call can be one the ledger genuinely moved *and* one
that resampling would have moved anyway. Subtracting a flat noise count
assumes independence and no overlap.

At a 12.8% noise rate and a candidate effect in the range you predict, the
overlap is small enough that the subtraction is a reasonable first-order
correction — but it is an approximation, not an identity, and it biases the
netted count. **Say so in one line where the netting is defined**, so a later
session treats the net figure as an estimate with a known simplification
rather than as arithmetic truth.

---

## 4. That is everything

Edits 1–20, 22 from `counter_1.md` §6 and `counter_3.md` §4; 21a–21d from
`counter_5.md` §4, with the guard in §1 above, the pooling default in §2, and
the caveat in §3.

Six review documents, one architecture unchanged throughout: two passes, the
ledger schema, weighting left to the analyst, the mechanism check as the
diagnostic that decides whether the ledger is what moved the number.

**Write it. Nothing further from me.**
