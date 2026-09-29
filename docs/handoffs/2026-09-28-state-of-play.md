# State of play — 2026-09-28

**Supersedes `docs/handoffs/2026-09-26-state-of-play.md`.**
Branch: `sweep/db-corpus-baseline`. Layer 1 (allocator) work, using the
analyst as a downside detector only.

**If you read one thing:** the analyst's flags pick better trims than
chance **at the portfolio level**. In 200 random 16-name train books,
trimming 2.5 points of every name B flags into QQQ beat trimming the same
money out of randomly chosen names in **91%** of books (87% with any one
company removed). P9's severity sizing **adds nothing** on top. This
conflicts with a per-trim test that said plain trims don't pay. **Proposed:**
settle it on tune with one rule, plain flag trims into QQQ, with both
readings registered before any tune data is touched. Start at §3.

---

## §0 — Defined terms

**Carried from 2026-09-26:** B (the 50-line incumbent prompt, −5 to +5),
P9 (expected six-month return, used here only to grade severity), train /
tune / holdout, the ticker-block range. See that document's §0.

**New today**

- **Flag.** B scores a call −2 or lower. In the book tests, the mean of
  B's two runs is used.
- **Trim.** Move part of a flagged name into the index. **2.5 points** means
  2.5% of the whole portfolio's value.
- **Per-trim value.** One trim's result six months later, in points of the
  book. Worked: a name falls 15% while QQQ rises 1%; moving 2.5 points
  saved 2.5 × 0.16 = **0.40 points**, $400 on $100,000.
- **Book.** A 16-name portfolio bought at equal weight on 2020-01-02 and
  otherwise left alone. **Random books:** 200 drawn from the 55 train
  companies. **Stratified books:** 200 of 8 megacap, 4 mid, 4 speculative.
- **Return per drawdown.** Yearly growth divided by the worst fall from a
  peak, marked daily. The project's gate for allocator changes
  (`PROMOTION_GATE.md` §3.2).
- **No-skill control.** The same trims, moving the same money at the same
  time, but out of names picked at random. It answers "did the analyst
  choose, or would any trim into QQQ have done as well?"
- **The arms.** 0: hold the book. 2: trim 2.5 points of every flagged name.
  3: trim only flagged names P9 rates most severe (5 points if P9 ≤ −10,
  2.5 if ≤ −8, else nothing). 2M / 3M: their money-matched no-skill
  controls.

---

## §1 What ran today

All train. **$0 in model spend.** One free price download (QQQ).

| run | outcome | wrap-up |
|---|---|---|
| Per-trim value, SPY | Plain flag trims: **does not pay** (range includes zero). P9-sized: pays | `per-trim-value-out.md` |
| Per-trim value, QQQ (QQQ added to the price file) | Same on QQQ. The index choice barely moves the analyst's contribution | `per-trim-value-qqq-out.md` |
| Book test, first run | Headline "own more QQQ": **withdrawn**, because the controls moved about twice the money | `allocator-book-test-out.md` |
| Book test, money-matched controls | Flags beat random trims; **P9 adds nothing** | `allocator-book-test-matched-out.md` |

Design and review trail: `2026-09-28-per-trim-value-*.md`,
`2026-09-28-allocator-book-test-design.md` (Amendments 1 and 1a),
`2026-09-28-book-test-amendment-1-review.md`,
`2026-09-28-allocator-book-test-prompt-review.md`.

---

## §2 What we know now

### 2.1 Per trim, plain flag trims do not clearly pay

Moving 2.5 points out of each flagged name (374 trims, both runs pooled):

| per trim, $100,000 book | into QQQ | into SPY |
|---|---|---|
| flagged names | +$215 (range −$52 to +$470) | +$138 (range −$129 to +$387) |
| random name, same quarter | +$102 | +$28 |
| **analyst's contribution** | +$113 (range −$94 to +$304) | +$110 (range −$100 to +$304) |

The typical flagged trim saves money (middle value +$252 into SPY). But 52
of the 374 flagged names went on to beat the S&P by 20+ points. Each of
those trims cost about $2,160, and together they cancel the savings.

### 2.2 Per trim, P9's severity grades the flags cleanly

Among flagged names, by P9's rating from most to least severe, the
average gap against SPY over six months was: **−30, −13, −12, 0, +28
points**. The mildest fifth rose 28 points on average, but that is made by
three names (EOSE, AMPX, OXY); its middle value is about flat. Trimming only
the two most severe fifths beat random trims by about $343 per flagged
call, range above zero, on both indexes.

### 2.3 In books, the flags beat chance, and P9 does not help

Money-matched controls, return per drawdown:

| test | random books | lowest, one company removed | stratified books |
|---|---|---|---|
| arm 3 beats holding | 96.0% | 94.2% | 100% |
| **arm 2 beats its money-matched random trims** | **91.0%** | **87.0%** | **100%** |
| arm 3 beats its money-matched random trims | 87.5% | 82.0% | 99.5% |
| P9's edge exceeds plain trims' edge | **32.5%** | 26.6% | 21.0% |

Per point of money moved, arms 2 and 3 beat random by the same amount
(0.00078 vs 0.00081). Choosing the severe names adds nothing per dollar.
The per-trim severity edge does not survive real positions, drift and
repeated flags. **P9 is closed as an allocator input.**

### 2.4 The two tests disagree on plain flag trims

Both were fixed in advance. The per-trim test measures the **average
six-month return**, which a few clipped winners dominate. It says plain
trims don't pay. The book test measures **return per drawdown**, the
project's allocator gate, and says they beat chance. The likeliest reading
is that B's value is cutting names before they crash, which shows up in
drawdown more than in average return. That is an explanation, not a
finding. It is **not** settled by picking the result we like. See §3.2.

### 2.5 Mechanics learned

- **Controls must match on money, not on trim count.** Arm 3 kept
  "trimming" names already sold to zero (55% of its trims moved nothing).
  A control matched on count moved about twice the money. On this window
  more money in QQQ wins almost by itself (QQQ alone 0.36 return per
  drawdown; a held book 0.14).
- **B re-flags names the book has already exited.** A live allocator should
  skip those.
- **Trim size in points of the book or as a fraction of the position makes
  no difference** (96.5% vs 96.0%).
- **The guidance veto is closed.** Only one flagged call carried the tag.
- **ALL16 cannot be a train book.** Six of its names are train, five tune,
  five holdout. It belongs to the final tune/holdout check.

### 2.6 Bullish research is closed (from 2026-09-27)

P5 peer read-through stopped at its map gate. Consensus surprise failed
on its pre-registered primary. With the four routes of 2026-09-26, six
routes have failed. All six used information public on the day of the
call. **Reopen only** for information not derivable from the transcript,
price history or reported-versus-expected EPS: analyst **revisions**
before the call, or a **revenue**-surprise source. Both are dormant.

---

## §3 Decisions

### Decided today

1. **The analyst is used as a downside detector only.** No bullish
   input to the allocator.
2. **Every no-skill control matches its arm on timing and on money moved.**
   Standing rule for all allocator tests.
3. **Decision 5 of 2026-09-26 is rewritten:** the next tune (and holdout)
   look goes to the **finished allocator**, on tune-company books, not to
   the analyst. B's bearish skill is already confirmed on tune (ranking
   0.140).
4. **P9 as an allocator input: closed** (2.3). **Guidance veto: closed.**
5. **QQQ is in the canonical price file** (`scorer_price_cache_v1.json`,
   commit `678017f`), added by the same method as SPY.

### Proposed, for review and Luis

1. **The tune candidate is arm 2:** trim 2.5 points of every name B flags
   (mean of two runs ≤ −2), into QQQ, at monthly sessions; skip names
   already at zero; never add; never spread proceeds.
2. **Settle §2.4 on tune, not on train.** Pre-register **both** readings
   before touching tune data: (a) the per-trim reading, flagged vs
   same-quarter random, both indexes; (b) the book reading, arm 2 vs
   arm 2M, 70% of books plus range plus company removal. **Decide now**
   what each combination of pass/fail means, including the case where
   they disagree again.
3. **Needs:** a second B run on the tune companies (one exists), about $30.
   No P9. Tune books built from the 51 tune companies the same way.

---

## §4 Next

| # | step | cost | why |
|---|---|---|---|
| 1 | **Review §3 proposals** | $0 | the tune look is spent once |
| 2 | **Sleeve/index decision** (written doc): the index as the default holding, direct names as bets against it, the split, and whether the base book is cap-weighted (review of 2026-09-27) | $0 | trim proceeds need a named home; P6D depends on it |
| 3 | **Tune pre-registration + second B run on tune** | ~$30 | §3 proposals 1–3 |
| 4 | **Live forward test:** score each new call for Luis's names (B on Sonnet and Opus) and the full corpus (Sonnet); grade in six months. Include the "B flags, P9 rates mild" cases as a watch line | pennies per call | the only evidence memory cannot touch |
| 5 | **Arm M loader:** make the production allocator run on arbitrary books without the DB | $0, code | "does the production allocator cost money" is still unmeasured |
| 6 | **P6D** against the tune result | — | after 1–3 |

Housekeeping: **cancel the Alpha Vantage premium key** (review of
2026-09-27). Update `PROMPT_ARCHITECTURE.md`, the registry and the gate
ledger with today's closures (P9 as allocator input, the veto) and
standing rule 2.

---

## §5 Open, not scheduled (carried)

Settle `PROMOTION_GATE.md` §3.1a R3; terminal-value grading (WOLF, SPWR,
NOVA); BK/BNY history; `ratchetTranche` null on 26% of bearish calls;
trend-layer override rate; the Rule 3 guard; the state dashboard.
`whats_live.py` does not report the research incumbent. Sector-relative
grading unresolved; dividends ignored (the price file uses unadjusted
closes). The first book-test run did not save per-book stratified figures.

---

## §6 Commits today

Per-trim: `5465845` (prompt), `026051f` (SPY leg), `45d4caa` (QQQ prompt,
Amendment 1), `678017f` (QQQ added), `4f5fbba` (QQQ leg). Book test:
`107e06c`/`17b1125` (prompt), `e105aba` (t1/t2 frozen), `9de97b5` (first
run), `5efd4d0` (first wrap-up), `b42fd5b` (matched prompt), `04e2158`
(matched results and wrap-up). Reviews and amendments: see `git log`.
