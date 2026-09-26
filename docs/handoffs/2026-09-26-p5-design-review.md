# P5 peer read-through — design review

**Reviews:** `docs/handoffs/2026-09-26-p5-peer-readthrough-design.md`
(with Addendum A and `wrap-ups/P5-phase0b-link-sources-out.md`).
**Verdict:** go, with three changes. Everything not named below is
accepted as written.

---

## The three changes

### 1. Gate 1 cannot be passed as written. Replace it.

At the 300-call floor, B's bullish share (~20%) gives a top group of
about 60 calls. The sampling spread of a hit rate near 50% on 60 calls
is about ±13 points. So gate 1 asks P5 to land near 60% where B sits
near 47%. That is a bigger bullish effect than anything in this project
has shown, including B's bearish skill (62% against 47%). It also
measures against B's *higher* draw, which already sits above B's true
level by chance. A real but modest signal fails this gate every time.

**Replace with the P9 form, which already survived review:**

- **Primary.** Paired rank-correlation difference, P5 minus B, computed
  against **each** B draw separately, on the peer-covered calls. Pass
  when both ranges exclude zero on the positive side. Ticker-block
  bootstrap as usual.
- **Direction check.** P5's top-group hit rate (same-size group) must be
  above the **mean** of B's two draws. Reported with its spread; not
  gated on the spread.
- **Gate 2 and gate 3** stay as written.

Why this is stricter in the right place: the ranking test uses every
covered call, not 60; the direction check stops a ranking gain that
comes only from the bearish end being counted as a bullish pass.

### 2. Hand links stay out of the gates entirely (answers §9 Q1).

Luis's hand links are drawn with knowledge of how these stories ended.
A supplier-customer pair that comes to mind in 2026 comes to mind
because the pair mattered. That is exactly the recall the point-in-time
filing rule exists to remove. So: filings-first is right, `HAND` links
are built, tagged and **reported** (with and without), but the
pass/fail numbers use filing-sourced links only. If filings alone fall
under 300 covered calls, the stop rule fires; hand links do not rescue
it.

### 3. Run the two $0 diagnostics first, and let them set P5's comparator.

State of play §4a: winners by sector × year, and B's ranking **within**
sector-year, plus B's call-over-call score change. Peer coverage will
concentrate in semis and solar (§8 says so). If B already ranks within
those sector-years, P5's flat comparator of 0.13 is the wrong bar and
the test would credit P5 for a sector effect B already has. Fix the
comparator from the within-group result before phase 3 pre-registers
thresholds. Cost: zero; delay: one CLI session.

---

## Accepted as written, with the reason (answers §9 Q2–Q5)

- **Digests over raw text (Q2).** Accepted. The 30-digest check and the
  ban on evaluative words are enough; excerpts would miss the customer
  and inventory commentary that is the whole point.
- **Placebo, one draw (Q3).** Accepted. Its output is a paired
  difference against P5, whose two draws already carry the noise
  estimate. Do not spend the $40.
- **300-call floor (Q4).** Accepted. Below that, the top group drops
  under 60 and even the ranking test loses its teeth.
- **Gate 1 strictness (Q5).** Answered by change 1.
- **Coverage stop at phase 1, before real spend.** Accepted; this is
  what keeps the downside at ~$15.
- **Analyst-firm name exclusions** (phase 0b finding) are a build
  requirement, not optional: a "Morgan Stanley" mention must never
  resolve to a link.

---

## One risk to state, not fix

The placebo arm does **not** cancel recall on linked peers. A linked
peer's digest can carry, through the model's memory, what later
happened to that peer, and linked peers' fates correlate with the
target's. Placebo digests have no such correlation, so a P5-over-placebo
gain could still be recall. Nothing in the corpus design can remove
this. It is the reason the live forward test (state of play §4 row 2)
is the only final arbiter. A P5 pass on train should be written up as
"promising, pending live", not as a found signal.

---

## What a pass would change

P5 becomes the first candidate to earn a tune look under §3.5. If it
fails on the primary but the link check still shows signal, the peer
map itself is the asset: it goes to the allocator rebuild as a
correlation input, and no further prompt work is spent on it.
