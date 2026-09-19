# Pre-execution review of `prompts/P3-guidance-ledger.md`

**Date:** 2026-09-19 · **Verdict:** architecture captured; **fix five items
before executing.** Each could cause the CLI to implement the wrong thing.
None changes the design. Two trivial consistency items at the end.

---

## 1. The candidate prompt file is needed in Phase 1 but is defined in Phase 2

§6a (Phase 2) is where `docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md`
and the ledger block format are specified. But Step 0d registers that file's
sha256 in the registry before anything runs, and the pre-flight (§5f, Phase 1)
scores 200 calls with it. As written, a session working top-down reaches the
pre-flight without the candidate existing, or writes it late and the registry
hash is wrong.

**Fix:** state in Step 0d that the candidate file is written *there*, to §6a's
specification, and hashed; §6a then describes it, it does not create it. One
sentence in 0d and one in 5f ("scored with the candidate registered at 0d").

## 2. Two different things are both called "tier"

The noise arm (§5f) stratifies and nets on **megacap / large / mid /
small_micro** — Test 4's four strata. Diagnostic 8.7 and §1.2 use **established
/ speculative** — the 3-axis classifier. The netting rule says "per tier,
re-weighted to the train tier mix" without saying which. A session could net
against the two-way classifier, which has no measured noise rates, and the
whole correction would be wrong.

**Fix:** name the field. The four-way stratum used for netting comes from the
corpus_v2 manifest (whatever field Test 4's driver read — name it by reading
`analysis/test4_noise_floor.py`); the two-way tier is only for diagnostic 8.7.
Call them "stratum" and "tier" throughout, or at minimum define both in §0 of
the wrap-up.

## 3. `withdrawn` calls fall into the wrong pre-flight arm and can trigger a false stop

`N_eligible` (§5e) is defined on `missed`/`unreported` only. `withdrawn` is
excluded — but §7 expects flips on withdrawn calls and diagnostic 8.1 groups
them with misses. So a withdrawn-guidance call lands in the **"no-miss" arm**,
and when it flips bearish (through the mechanism, as designed) it counts as a
*leak* in the mechanism-failure stop. Enough of those and the stop fires on a
candidate that is working.

Same rule, second defect: the eligible arm excludes calls v6 already called
bearish, but the no-miss arm does not. A bearish-direction flip is impossible
on a call that is already bearish, so the no-miss denominator is padded with
unflippable calls, its rate is biased down, and the stop is *less* likely to
fire than it should be.

**Fix:** (a) add `withdrawn` to `N_eligible`, or give withdrawn calls their own
small stratum — either way they must not be in the no-miss arm; (b) compute
both arms' bearish-direction flip rates over v6-non-bearish calls only.

## 4. Growth-rate framing will manufacture `unreported` and `basis_mismatch`

Guidance is very often stated as growth ("revenue growth of 20–22%"), and
actuals as levels ("revenue of $912M, up 14%") — or the reverse. The schema
carries `unit` but the join rule says only "same metric and basis." A level
guide against a growth-only actual, or vice versa, will grade `unreported` or
`basis_mismatch` at scale. `unreported` feeds `N_eligible` and the stumble
test, so this is the single most likely source of reflexive trims, and it
would look like the mechanism firing.

**Fix, in 5a and 5c:** extract `framing` (`level` | `growth_pct` | `margin_pct`)
on every entry; the driver grades level-to-level and growth-to-growth, and
converts between them only when the prior-year base is itself in the ledger
(then the conversion is recorded on the row). A metric present in the
transcript in *any* numeric framing is never `unreported`. `unreported`
requires the metric to be absent from the call — the driver checks the
transcript for the metric's name and synonyms before assigning it. Report the
count of framing conversions and framing mismatches as their own line.

## 5. Provenance gaps: the extraction prompt, and two prompts under one guard

(a) The Pass A extraction prompt determines every ledger row and is not
mentioned as an artifact. Under the reproducibility contract it must be a
committed file with its sha256 in `SCORING_PROTOCOL_P3A.json` and in
`progress.json`. Otherwise the ledger is unreproducible from the day the
extraction prompt is next edited.

(b) The run submits two analyst prompts: the candidate (eligible, no-miss,
empty-ledger arms, Pass B) and **unmodified v6** (the 21a arm). The version
guard runs under `PROMPT_CANDIDATE=v6+P3a`. State that 21a's requests are
guarded against the *promoted* v6 hash and everything else against the
candidate hash, and that both assertions are recorded. A session that runs one
guard for the whole batch will either block 21a or, worse, let a wrong file
through for it.

---

## Trivial, fix while there

- §5f says "confirm the four new fields populate"; §6a defines **six**.
- The accuracy formula and flip tables use 1,184 as the denominator; the
  resolved predecessor-bearing count is 1,140 (§0f). Use 1,140 throughout so
  the projections and the net counts agree.

Nothing else. The Phase 1 checkpoint carries what Luis needs to authorize
Phase 2, the falsifiers are stated net, the guard on the netted win rate will
fire in the likely case and the prompt says so, and the architecture has not
moved.
