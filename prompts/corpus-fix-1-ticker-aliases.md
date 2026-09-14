# Corpus fix 1 of 3 — ticker aliases

**Run ID:** `corpus-construction` — continuation. **This run does one thing.**
**Cost:** **$0 Anthropic API. No transcript scored.** Vendor metadata only.
**Branch:** `sweep/db-corpus-baseline`. No merge, no push.
**Wrap-up:** `wrap-ups/corpus-fix-1-ticker-aliases-out.md` — **short**. No
defined-terms table required; a plain-language summary and the tables below.

**Read first:** `wrap-ups/corpus-construction-fix-out.md` Steps B and C, and
`analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json` (78 companies, sha256
`9b256b71…`).

---

## 1. The one thing

Two companies are recorded as **structurally absent from the vendor**: GOOGL
(S5, exempt, so it stayed) and SIVB (S4, which is why that stratum sits at 5 of
8). Both were treated as unfixable coverage gaps.

**They may be identity failures, not coverage failures.** A vendor may file
Alphabet under `GOOG` rather than `GOOGL`, and a company that goes through
bankruptcy usually keeps trading under a modified symbol — SVB Financial became
`SIVBQ` after its filing. Querying the original symbol returns nothing while the
data sits under the variant.

This run resolves identity. **It changes no eligibility rule and no availability
threshold** — a company still has to pass the same rules it faced before. If a
company's data appears under an alias, it is the same company, and this is
bookkeeping, not a rule change. Record that reasoning as an addendum to
`PREREGISTRATION_FIX.json` before querying anything, with the same
coverage-only justification the fix pass used.

---

## 2. Constraints

1. **ZERO Anthropic API calls.** Nothing scored.
2. **Vendor metadata only** — symbol lists and event dates. No transcript text.
   Report calls consumed and the running period total (167 so far).
3. **Do not modify `analysis/data/price_cache.json`.**
4. **No eligibility or threshold changes.** Domain and point-in-time rules stand
   exactly as registered.
5. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 3. Steps

**3a. Build the alias candidate list**, before querying, for every company that
currently fails availability **because the vendor returned nothing or near
nothing** — not for companies with a genuine measured gap. On the current
evidence that is GOOGL and SIVB; confirm from the manifest whether any other
company shows zero events, and include it if so.

Candidate sources, in order:
- **share-class variants** — GOOGL / GOOG, and any other dual-class name in the
  corpus;
- **post-bankruptcy symbols** — the original symbol with a `Q` suffix, and the
  five-letter delisted form (SIVB → SIVBQ);
- **the vendor's own symbol list searched by company name** rather than ticker.

**3b. Query each candidate** for event counts and dates, exactly as Step B did.

**3c. Apply the existing rules unchanged.** A company recovered under an alias
must still pass its stratum's registered availability rule — the general
240-day rule, or A2's rule for the failures stratum. **Do not relax anything to
let a recovered company in.**

**3d. Report, and re-freeze only if membership changed.** If any company's
status changes, write `CORPUS_MANIFEST_V3.json` as a new file, leaving V2
intact, and record its sha256 in `progress.json`. If nothing changes, say so and
write no new manifest.

Record the alias map itself — original symbol, working symbol, evidence — in
`analysis/data/corpus_v2/TICKER_ALIASES.json`, because the scoring run will need
it later.

---

## 4. Report

Short. A plain-language summary written to the project instructions' language
rules, then:

- the alias candidates tried, per company, and what each returned;
- which companies were recovered and which remain absent;
- the resulting stratum counts against V2's S1 22 / S2 15 / S3 20 / S4 5 / S5 16
  = 78;
- vendor calls consumed and the period total.

**State plainly whether the failures stratum reached 6 of 8**, and whether
Alphabet is now retrievable.

Do not start the outcome balance, the split, or the threshold projection. Those
are prompts 2 and 3.

---

## 5. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`.
- Driver committed before any manifest, as its own commit. Run-specific files
  only; no `git add .`.
- **A diagnostic that contradicts this prompt is a finding.** The most likely:
  aliases recovering nothing, which would confirm the gaps are real.
