# Allocator porting methodology — backlog design note

**Status: requirement recorded, not designed in detail, nothing built.**
Written 2026-09-12. Do not act on this before the Test 1-6 program and its
follow-ons have converged on a settled allocator design.

## Why this exists

The live allocator (`server/routes/moves.js`, "moves.js v2") and the
allocator being validated (`analysis/simulator/allocator_v3`) are
**deliberately different artifacts**, not an accidental drift.
**Correction (2026-09-12, `wrap-ups/drift-guards-followup-out.md`):** the
settled figures are produced by `allocator_v3` specifically —
`run_db_corpus_baseline.py` imports it. `allocator_v4` (a Wall Street
consensus sizing modifier) is a separate, untested candidate used only by
`run_expanded_test.py`; it is not the newer-and-therefore-better version of
`v3` and is not load-bearing for anything settled. `allocator_v2` and the
un-suffixed `allocator.py` are earlier phases, also not in use by the
settled configuration. The app
allocates by rules that were never an exact copy of the backtest's — that
divergence is the *premise* of the Test 1-6 validation program, not a bug
discovered by it.

**Therefore: do not attempt a behavioral comparison of the two today.** It
would confirm a known, expected difference and consume effort for no new
information.

What *is* needed, once the tests conclude and the allocator's intended
behavior is settled, is a disciplined way to translate that design into the
code that moves real money. This note records the requirement and a
skeleton, so the thinking is not lost between now and then.

## The problem shape

A design validated in Python (simulator, backtest, ~5 years of transcripts)
must come to govern real money in JavaScript (`moves.js`). The translation
has to be **verifiable, not reviewed** — "I read both and they look the
same" is how the current divergence became invisible.

Note also the two implementations do not currently share a rule vocabulary.
The simulator speaks in `TYPE_A_SPECULATIVE_CAP_PCT`, `PROFIT_TAKE_*`,
first-call starter, Rule 3 no-average-down, `swap_funding`, X=2.5pp. The app
speaks in `hardCapPct`, `TRIM_CAP`/`TRIM_RATCHET`/`TRIM_MODEL`/`TRIM_SIGNAL`,
`specExitSpeed`, `ratchetTranche`, barbell pool percentages, `maxPositions`.
The version numbers do not correspond either ("moves.js v2" vs
"allocator_v3" — corrected 2026-09-12; this section previously said
"allocator_v4", which is not the version backing the settled figures).

## Skeleton of the methodology

1. **One normative spec; two implementations, neither authoritative.**
   `ALLOCATOR_OPERATING_MODEL.md` §9 already holds assertable invariants —
   that is the right shape. The spec is the source of truth. The simulator
   and the app are both *implementations of it*, and neither wins an
   argument against the other by being older or by being in production.
2. **Conformance fixtures are the bridge** — already build item #1
   (`CONFORMANCE_FIXTURES.md`, `PROMOTION_GATE.md` §9.6). Concretely: golden
   vectors of (input state -> expected decision set). Input: portfolio
   state, prices, one scored event, tier/type classification. Output: the
   exact trade set, including reasons. Generated from the simulator once the
   design settles; the app must reproduce them exactly.
3. **Fixtures cannot be written before the design settles.** That is the
   sequencing constraint and the reason this note is a backlog item.
4. **Declare the direction of authority explicitly, in writing, before the
   port begins.** When the design settles, the simulator becomes the
   reference and `moves.js` is brought to it — not the reverse, and not a
   negotiated middle. A negotiated middle produces a third variant, which is
   strictly worse than the current two.
5. **Version the spec, not the implementations.** Both implementations
   declare which spec version they implement; the version registry records
   it. This removes the current situation where two unrelated numbering
   schemes describe the same subsystem.
6. **Parity is a gate, not a code review.** The port lands only when the
   fixture suite passes 100%. A fixture failure blocks deploy the same way
   `PROMOTION_GATE.md` blocks an ungated prompt.
7. **One-way ratchet afterward.** Any later change to allocator rules goes
   into the spec first, then both implementations, then regenerated
   fixtures. No hotfix to `moves.js` that does not travel back through the
   spec — unmediated production edits are how the present divergence
   happened.

## The one piece of adjacent work that IS worth doing before the tests end

**A feature inventory of `moves.js` — an enumeration, not a comparison.**

The app implements machinery the simulator does not model at all:
`ratchetTranche`, `specExitSpeed` ('fast'/'patient'), `TRIM_SIGNAL`,
`TRIM_MODEL`, barbell pool percentages, `maxPositions`, full-reset mode,
rank scores. For each, exactly one of two things is true:

- it is a **real requirement**, in which case the simulator does not yet
  model a load-bearing production behavior, and the "settled configuration"
  is not a complete allocator design yet; or
- it is **production cruft** to be dropped at the port.

That distinction changes what the test program still owes. It requires only
reading `moves.js` and listing what it does — no behavioral comparison, no
backtest, no spend. Related live design threads that likely own some of
these: `docs/architecture/TRACK_RECORD_SPEC.md` and the exit-latency /
winner-runway thread (`docs/handoffs/2026-09-05-exit-latency-framework.md`).

## Explicitly out of scope here

- Any behavioral comparison of `moves.js` against `allocator_v*.py`.
- Writing fixtures, or choosing a fixture format.
- Changing either implementation.

---

# Which levers belong where — scoping, 2026-09-12

**Framing, and the standing priority this serves:** the top priority right
now is **preventing anything built later — backtest or app — from silently
drifting away from the benchmarks that were actually proven.** Every
decision below is therefore recorded in the closed-decision form: what was
decided, on what evidence, and what would have to change to reopen it. A
disposition without its reason gets re-litigated or quietly reversed; that
is the failure mode this section exists to prevent.

## The allocator's sandbox: cash and equities only

The allocator can see several buckets — crypto, ETFs, commodities, cash,
equities. **Its sandbox is cash and equities. Nothing else.**

Reason: no methodology exists here for choosing gold over silver, or QQQ
over TMFC. Allocating where there is no tested basis for a decision is not
a capability, it is an unmeasured risk. Everything outside cash and
equities is the user's to allocate manually. The existing bucket machinery
(per-account views, bucket tagging, ETF role classification) stays — it
serves display and manual management, not automated allocation.

Reopening condition: a tested selection methodology for a non-equity
bucket.

## The denominator question — OPEN, and load-bearing

**The simulator has no asset-class concept at all.** `total_value()` =
`total_cash()` + `total_position_value()`, summing every lot in every
account (`analysis/simulator/accounts.py:113-130`). In the backtest that
was exactly equities + cash, because nothing else existed. So **every
percentage in the settled design — the 15/35/50 caps, the 5%/8%
first-call starter, X=2.5pp, the 25% profit-take — is implicitly a
percentage of the equities+cash sleeve.** The question never arose.

In production it arises immediately, and the two answers differ sharply.
On a $500k portfolio holding $250k equities+cash, $150k ETFs, $60k crypto,
$40k gold, a 35% established cap means:

| Denominator | Cap in dollars | Consequence |
|---|---|---|
| **Sleeve** ($250k) | $87.5k = **17.5% of net worth** | caps no longer bound *true* concentration |
| **Whole portfolio** ($500k) | $175k = **70% of the sleeve** | and a 30% gold rally raises the cap by $4.2k — the allocator buys equities because an asset outside its sandbox appreciated |

**Leaning: sleeve.** It is what was actually tested, and it keeps the
sandbox sealed — the allocator should not take instructions from assets it
does not control. But the consequence must be accepted explicitly: **"35%
cap" then means 35% of the sleeve, not 35% of the user's money.** If
concentration against true net worth matters, that is an outer constraint
on sleeve size — a manual user decision under the scoping above, not an
allocator rule.

**This must be decided and written down before any port**, and it should
be asserted in a conformance fixture rather than left to implementation —
it is precisely the kind of unstated assumption that drifts.

## Lever dispositions

### Barbell pools — ELIMINATE
`moves.js` enforces explicit `estPoolPct` / `specPoolPct`. **The simulator
has no pool enforcement whatsoever.** In the validated design, barbell is
an *emergent property of per-name caps by type and tier*, not an enforced
split.

These are not equivalent: an explicit pool can block a name that is under
its own cap because its pool is full; per-name caps cannot. Eliminating the
pools makes production match what was tested.

**Reason to record: not "redundant" — "never validated, and it changes
behavior."** Reopening condition: a sweep that tests pool enforcement as an
axis and shows it beats per-name caps alone.

### Minimum cash floor — ELIMINATE, but not as a redundancy
This was a **swept axis**, not a duplicate. `sweep_funding_modes.py` tested
`no_reserve`, `cash_reserve` at 5/10/20%, and `swap_funding`.
**`swap_funding` won and is the settled configuration.** Consequences on
record: the backtest portfolio ends at **$0 cash, fully deployed**, and
SPWR's first-call starter failed to fund for exactly that reason
(`binding: 'cash available'`, $0 against $8,062.74 intended — 09-05 §5.2).

So a production min-cash floor does not duplicate the allocator, it
**overrides a tested decision in the direction the sweep rejected.**

**Reason to record: "swap_funding won the sweep."** Without that reason
attached, a future session re-adds a cash floor as an obvious safety
feature and silently un-does a measured result. Reopening condition: a
re-run of the funding-mode sweep on the daily ruler.

### Cash as an allocatable choice — GAP, decide rather than inherit
The sandbox is nominally cash *and* equities, but under `swap_funding` the
settled design holds zero cash and funds buys by selling. **The allocator
therefore cannot choose cash; it has no way to go defensive.** If that
capability is wanted it is a **new, untested axis**, not a lever to keep or
drop. Decide deliberately; do not let it arrive by implication from the
word "cash" appearing in the sandbox definition.

### Still to be dispositioned (enumeration pending, see the inventory note above)
`ratchetTranche`, `specExitSpeed` ('fast'/'patient'), `TRIM_SIGNAL`,
`TRIM_MODEL`, `maxPositions`, full-reset mode, rank scores, **and Type A/B
caps** (added 2026-09-12, `wrap-ups/drift-guards-followup-out.md`). For each:
real requirement the simulator must model before the design can be called
settled, or cruft to drop at the port. Related live threads:
`TRACK_RECORD_SPEC.md`, `docs/handoffs/2026-09-05-exit-latency-framework.md`.

**Type A/B caps are a different kind of gap than the others on this list.**
The others (`ratchetTranche`, `TRIM_SIGNAL`, etc.) are cases where `moves.js`
implements *something the simulator doesn't model* — extra machinery, not
yet disposed. Type A/B is the reverse: the simulator's design calls for a
fixed 35% (Type A) / 50% (Type B) cap keyed off
`analysis/data/type_classifications.json` (`CLAUDE.md` "Key Design
Decisions" #2), and confirmed 2026-09-12 (`version-registry-and-drift-guards`
run): **`moves.js`/`dashboard.js`/`radar.js` never read that file and
enforce no computed Type A/B rule at all.** Caps come entirely from hand-set
`Ticker.capPercent` / `OwnerTickerConfig.capPercent`. So production does not
implement the cap structure *differently* from the validated design — **it
does not implement the concept.** This is a bigger gap than a naming or
threshold mismatch and should be weighted accordingly when this list is
finally dispositioned.

---

# Comparison protocol — what may be compared to what

**Why this is here:** a version registry makes the *machinery* unambiguous.
It does not make a *comparison* legitimate. A session can read two
correctly-recorded figures, subtract them, and produce a number that looks
authoritative and is meaningless. These rules make the illegal subtraction
illegal rather than merely visible.

## 1. Absolute figures are tuple-scoped

Final value, absolute return and absolute drawdown are comparable **only
within an identical tuple**: (corpus tickers, window, prompt version+hash,
model, allocator version, settled configuration).

Across any difference in that tuple they are **not comparable** — not
"comparable with an adjustment," not comparable. There is no
"improved 2pp over corpus" measurement to get right when the tickers or the
window differ.

Live example of why: the existing corpus was scored by
`claude-sonnet-4-20250514`, which is **retired and cannot be regenerated at
any price** (09-05 §6). Any new corpus is scored by a different model, so
absolute comparison against $179,944.91 / $184,819 is confounded before
anyone even changes the tickers.

## 2. Across tuples, only benchmark-relative metrics travel

And each must be computed over the run's **own** window:

- portfolio return vs SPY / QQQ / TMFC over that same window;
- analyst-direct hit rate vs the always-bullish baseline (lift).

Caveat that must travel with lift: it is mechanically capped at
(1 − baseline). With a baseline near 0.85, a *perfect* analyst scores at
most +15pp, and a declining lift series across a bullish stretch is the
**null expectation, not a signal** (Test 2).

**So a new corpus is compared against market benchmarks over its own
window — never against a prior run's absolute figures.**

## 3. Every drawdown names its ruler, on BOTH sides

Session-sampled and daily-marked drawdowns differ by 1.9–8.3pp on this
project's own data. The published "8.04pp advantage over SPY" was portfolio
session-sampled against SPY daily-marked; like-for-like on the daily ruler
it is **1.90pp** (09-05 §5.1).

A drawdown pair without two rulers named is not a result. Reject it in
review.

## 4. EW is not a measured benchmark

`$120,427 / 42.76%` was never reproduced and its ruler is unknown
(`baseline.py` computes SPY/QQQ/TMFC only). **Do not quote it as measured.**
Either reproduce it or remove it from the tables it sits in — it currently
looks legitimate because three real figures surround it.

## 5. Staleness is computed, not remembered

A benchmark figure is stale the moment any artifact hash it was measured
under changes. That is what the registry's benchmark records are for, and
why `whats_live.py` reports stale figures rather than relying on a human to
recall which numbers expired.

## 6. Noise floors are sample-scoped

A hit-rate noise floor depends on n **and on the specific transcripts**.
Test 4's per-tier floors (0.0 / 0.0 / 3.77 / 14.34pp) transfer only to runs
on the identical 50-transcript sample — which is exactly why Test 6 was
designed as a paired reuse of it rather than a fresh draw. **A new corpus
needs its own floor before any effect on it can be called detectable.**

## 7. Cross-model comparison requires paired rows

`gate_ledger.json` entry 1 had **zero paired rows** (champion n=6, all
`Add`; challenger n=36) — 09-05 §5.5. A model comparison without
overlapping scored transcripts is **confounded, not merely weak**. Pair, or
do not compare.

## 8. State the minimum detectable effect before calling anything significant

And derive it correctly. Test 6 computed its MDE by dividing a binomial CI
by √5 on the grounds that each arm averaged 5 runs — **not defensible**:
the 5 runs re-score the *same* transcripts, so averaging reduces scoring
noise, not sampling uncertainty about which transcripts were drawn.
Separately, an unpaired binomial is too conservative for a paired design;
the natural test is on **discordant pairs** (McNemar). Fix before reuse.
