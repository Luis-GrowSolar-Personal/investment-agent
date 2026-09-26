# P5 — peer read-through: design for review

**Date:** 2026-09-26 · **Status:** DRAFT for architect review. Nothing run.
**Context:** `docs/handoffs/2026-09-26-state-of-play.md`. B is the
research incumbent. Transcript-only routes to a bullish signal have
failed three ways. P5 is the one untried transcript-based route.

---

## §0 Terms

- **Target call.** The call being scored.
- **Peer call.** Another company's earnings call, given to the analyst as
  context.
- **Supply-chain link.** One company sells to the other. Example: ENPH
  and SEDG supply RUN.
- **Shared-customer link.** Rivals selling to the same buyers. Example:
  NVDA, AMD and AVGO all sell to cloud data centres.
- **Peer digest.** A short, factual summary of a peer call: numbers,
  guidance, demand and inventory commentary. No score, no opinion.
- **Peer-covered call.** A target call with at least one linked peer call
  dated before it.
- **Placebo arm.** The same prompt fed digests from *unlinked* companies
  that reported on similar dates. It tells "the peer link matters" apart
  from "any extra context helps".
- All other terms as in the state of play §0.

---

## §1 What P5 tests

**Question.** Does knowing what a company's customers, suppliers and
rivals said *before* its call help the analyst rank that company's next
six months? In particular, does it help pick winners?

**Two mechanisms, reported separately, because they can point opposite
ways:**

1. **Supply chain.** Demand at a customer shows up at its suppliers with
   a lag. The reverse also holds: a supplier's inventory comments warn
   about its customers. There is published evidence that investors
   underreact to news from linked companies (the "economic links" effect,
   Cohen and Frazzini).
2. **Shared customers.**
   - *Rising tide:* strong peers mean strong end demand.
   - *Losing share:* strong peers plus a flat target means the target is
     losing ground.

   The tide is usually priced on the peer's own report day, before our
   entry. The unpriced part is the gap between the target's tone and its
   peers'.

**What P5 is not.** It is not a new reading of the target's own call.
B's text is kept word for word, and the output is B's −5..+5 score.

---

## §2 Decisions recorded before any build (Luis, 2026-09-26)

1. **Firewall amendment.**
   - `DESIGN_PRINCIPLES.md` §1 currently says the analyst never receives
     "data about any other ticker". Amend to: *peer transcripts, and
     factual digests of them, dated strictly before the target call may
     be given to the analyst. Portfolio membership, positions, sizes and
     any price data about other tickers may not.*
   - `PROMPT_ARCHITECTURE.md` §1.4 gets the same sentence.
2. **Peer text may cross the train / tune / holdout split, as input
   only.**
   - Reading a holdout company's call reveals nothing about what its
     stock did next.
   - Holdout calls are still never *scored* until the final look.
   - Non-corpus companies (ENPH, for example) may be fetched as peer
     input only.
3. **Links come from filings, not from judgement.** A link counts only if
   a public document dated before the target call names it (§3). Luis's
   hand-drawn maps (semis, solar, storage, software) are a check and a
   tagged supplement, not the source.

*Why ENPH is missing:* the corpus was drawn at random within size bands
(seed 20201231). ENPH was in the small-cap pool and not drawn. It went
to the reserve list and was never needed. The omission was not a
choice.

---

## §3 Building the peer map, point in time

**Source, for each corpus company and each fiscal year 2019–2025:** the
10-K filed **before** the target call. The filing date comes from EDGAR's
submissions JSON.

**Extracted by a model, as extraction only.** The model reads one 10-K
section at a time and returns named companies with the **verbatim
sentence** that names each one:

| link | where in the 10-K | example |
|---|---|---|
| `CUSTOMER` (≥10% of revenue) | Item 1 "Customers"; concentration-risk notes | a solar supplier naming a large installer |
| `SUPPLIER` (named key, sole or limited source) | Item 1 "Suppliers / Manufacturing"; Item 1A risk factors | an installer naming its inverter supplier |
| `COMPETITOR` | Item 1 "Competition" | a chipmaker naming its rivals |

**Rules:**
- **The verbatim sentence is required.** A link with no quote is dropped.
  A script checks that each quote appears in the filing text.
- **A link is valid from its filing date until the next 10-K.** Links are
  never carried backward in time.
- **Names are resolved to tickers with a fixed, reviewed alias table.**
  Private companies and non-US companies with no transcripts are recorded
  but unused.
- **Industry code (SIC) peers are a labelled fallback,** used only when a
  company's 10-K names no competitors. The SIC code EDGAR reports is the
  current one, not point in time. It rarely changes, but this is flagged.

**Luis's hand maps.**
- Built for semis, solar, storage and software, **before** seeing the
  filing-derived map.
- Compared with the filing-derived map: agreements, links only Luis has,
  links only the filings have.
- Links only Luis has enter as `HAND`, tagged. The run reports results
  **with and without** them. If they help only when included, and only in
  famous names, that is treated as hindsight, not knowledge.

**Coverage report, the first stop point:** how many train calls are
peer-covered?
- **Proposed stop rule:** if fewer than **300 of the 1,217** train calls
  have at least one linked peer call dated before them, stop. P5 cannot
  be measured at a useful size.
- Also report coverage by link type and by stratum.

---

## §4 Building the peer input

**For each peer-covered target call:**
- Take each linked peer's most recent call dated **strictly before** the
  target call, and within **120 days**.
- Order the peers: supply-chain first, then competitors.
- Cap at **5 peers**.

**Peer digests, not full transcripts.** Five full transcripts would
multiply the cost about fivefold and bury the target call.
- Each peer call gets one **factual digest** of about 200 words. It
  covers reported growth, the guidance change, demand and order
  commentary, inventory commentary, and anything said about named
  customers or suppliers.
- **The digest prompt forbids opinions, scores and predictions.** It is
  written to `docs/prompts/diagnostics/PEER_DIGEST_v1.md`.
- **P7's lesson applies.** On 30 digests, check that each one contains
  the call's actual guidance numbers and no evaluative words before
  producing the rest.
- **Each peer call is digested once and reused.** Digests are keyed by
  peer and call date, and made only for peer calls that some target
  actually needs.

**Timing edge case:** the same-day rule. A peer that reported earlier the
same day as the target counts only if its call timestamp is known to be
earlier. Otherwise it is excluded. Same-day conflicts should be rare.

---

## §5 The candidate and the controls

**P5 candidate.** B word for word, plus one section before READ:

> **PEERS.** Below are factual summaries of calls from companies linked
> to this one: its customers, suppliers or competitors. Each was reported
> before this call. Compare this company's results and outlook with
> theirs. Where they diverge, say which way and why it matters to a
> holder.

The peer digests follow, each labelled with the link type and the
number of days before the target call. There is one added structured
field, `peerRead`: `"confirms"`, `"better_than_peers"`, `"worse_than_peers"`
or `"not_informative"`. It is diagnostic only. The early-stop rule
applies: if any one value lands on more than 85% of pre-flight calls,
stop.

**Controls, both on the same peer-covered calls:**
- **B**, both existing train draws. B is P5 with no peers. No new cost.
- **Placebo arm.** Same prompt and format, with digests from **unlinked**
  companies in a different industry that reported within the same window,
  matched on count and date gap. If P5 beats B but not placebo, the gain
  is extra context, not the link.

**Runs.**
- P5: two draws on the peer-covered train calls (§2.3a rule 7).
- Placebo: **one** draw. Its job is to separate "link" from "context",
  and that is decided on the paired difference with P5.

---

## §6 Measurement, pre-registered once coverage is known

**Sample sizes depend on coverage.** So the exact thresholds are fixed
**after** the coverage report (§3) and **before** any scoring. The rule
for fixing them is set now:

- **Same-size groups** as §2.3a rule 1, scaled to the peer-covered
  count. The top group size is B's bullish share of those calls, and the
  bottom group size is B's bearish share.
- **Gate 1, the purpose (bullish).** P5's top-group hit rate must beat
  the higher of B's two draws by at least the sampling spread of a group
  that size. That spread is written down, as a number, in the
  pre-registration.
- **Gate 2, ranking non-inferiority.** The paired difference against both
  B draws has its range's lower end no worse than −0.03.
- **Gate 3, bearish non-regression.** The bottom-group hit rate is no
  more than 5 points below B's lower draw.
- **Link check, reported with a reading fixed in advance.** P5 against
  placebo, paired ranking difference.
  - "The link carries signal" only if the range excludes zero.
  - Otherwise: "extra context, not the link".

**Reported, not gated:**
- the gain split by link type: supply chain (customer → supplier and
  supplier → customer separately) against shared customer;
- the gain by `peerRead` value;
- the gain by peer recency: under 30 days against 30–120;
- the gain with and without `HAND` links;
- famous names (S1) against the rest, as the usual recall check.

---

## §7 Phases and costs

| phase | work | cost | stop point |
|---|---|---|---|
| 0 | Record §2 amendments; probe EDGAR from the CLI (submissions JSON and one 10-K for 3 tickers); check that vendor transcripts are available for 5 non-corpus peers (ENPH first) | $0 | EDGAR unreachable, or no transcript source for non-corpus peers → report and decide |
| 1 | Fetch 10-Ks (164 companies × ~7 years); extract links with quotes; verify quotes; alias table; Luis's hand maps; coverage report | ~$10–15 | fewer than 300 peer-covered train calls → stop |
| 2 | Fetch needed non-corpus peer transcripts; make peer digests (30-digest early check first) | ~$15–40 | digest early check fails → stop |
| 3 | Pre-registration fixed from coverage; P5 two draws + placebo one draw on peer-covered train calls | ~$100–130 | as §6 |

**Total ~$125–185**, all but ~$15 of it in phase 3, and phase 3 runs
only if phases 0–2 pass. Tune gets one look only if P5 passes on train,
under the tune-reservation decision (state of play §3.5).

---

## §8 Risks

- **Recall in the digests.** The digest model knows what happened to
  these companies. Mitigations: factual-only instructions, the 30-digest
  check, and the placebo arm, which carries the same risk and so cancels
  some of it.
- **Name resolution errors.** A wrong alias creates a false link. The
  alias table is fixed, reviewed and committed before extraction output
  is used.
- **Coverage skew.** Supply-chain links will concentrate in a few
  industries (solar, semis, autos). The results split by link type and
  stratum show this.
- **Non-corpus transcripts.** Availability depends on the stalled vendor
  thread. Phase 0 checks this before anything is spent.
- **The share-loss signal needs same-quarter peers.** Only late
  reporters get it. Expect it to be weaker in aggregate than the supply
  chain.

---

## §9 Questions for the reviewer

1. Is **filings-first** the right source hierarchy, with hand links
   tagged and tested separately? Or should hand links be excluded
   entirely from the pass/fail gates?
2. **Digests versus raw peer text.** Is a factual digest an acceptable
   stand-in, given it adds one model step? The alternative is excerpts
   (the guidance paragraph only), which is cheaper but more brittle.
3. **Placebo arm.** Is one draw enough for its purpose? Or does §2.3a
   rule 7 require two draws for it too? That would add ~$40.
4. **Coverage stop rule.** Is 300 peer-covered train calls the right
   floor?
5. **Gate 1 form.** "Beat B's higher draw by one group-size sampling
   spread" is stricter than P7's fixed 47%. Is it too strict for a
   smaller sample?

---

## Addendum A — link sources after phase 0 (2026-09-26)

**Finding (`wrap-ups/P5-phase0-probes-out.md`).** RUN's 2022 10-K names
**no** suppliers and **no** competitor companies. It gives categories
only ("a limited number of manufacturers and suppliers"; "traditional
utilities"). Many filers also disclose big customers anonymously
("Customer A"). A filings-only map would likely be thin, which pushes the
load onto hand links: the hindsight risk this design exists to avoid.

**Amended source hierarchy (Luis, 2026-09-26).** A link counts if it is
named, with a verbatim quote, in either of these:

1. **a 10-K** of either company, filed before the target call (§3,
   unchanged); or
2. **an earnings call of either company dated before the target call.**
   Management or analysts name the other company as a customer,
   supplier or competitor. Example: an inverter maker's call naming an
   installer as a customer creates a link for **both** companies.

**Hand links** stay a tagged supplement, tested separately (§3,
unchanged).

**Rules carried over:**
- Every link needs a verbatim quote, checked by script.
- A link is valid from its source date forward only.
- Model use is extraction only: *who is named, and in what relation*.
- A transcript-sourced link carries the source call's date. It is never
  applied to a target call dated before it.

**Why this keeps the firewall.** A call dated before the target is
exactly as point-in-time as a filing. A company named on it is a fact of
that date, not a judgement made with hindsight.

**New stop point, before phase 1:** a $0–2 check of how often filings and
calls actually name linked companies (`prompts/P5-phase0b-link-sources.md`).
