# P5 phase 0 — record the decisions, probe the two data sources. $0

**Run ID:** `p5-phase0`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P5-phase0-probes-out.md`
**Cost: $0 in model calls.** At most **30 SEC EDGAR requests** (free,
public) and at most **20 EarningsCall.biz vendor calls**. No Claude API
calls, no DB writes, no scoring of anything.

---

## Framing

P5, peer read-through, is designed in
`docs/handoffs/2026-09-26-p5-peer-readthrough-design.md`. That design is
**under architect review**. This phase is the part that does not depend
on the review:
- It records three decisions Luis has already made (design §2).
- It answers two yes/no questions that decide whether P5 can be built at
  all:
  1. **Can this Mac pull point-in-time 10-K filings from EDGAR?**
  2. **Can the transcript vendor supply calls for companies whose
     transcripts are not on disk?** These are holdout companies (NVDA,
     AMD, AVGO…), which were locked before any were fetched, and
     non-corpus companies (ENPH, and others).
- It sets up the file where Luis draws his hand peer maps. He draws them
  **before** any filing-derived map exists.

**Nothing here scores a call or looks at an outcome.** Fetching a holdout
company's transcript as future peer input is allowed by decision 2. It
reveals nothing about what the stock did next.

**Read first:** the P5 design doc (all); `docs/architecture/DESIGN_PRINCIPLES.md`
§1; `docs/architecture/PROMPT_ARCHITECTURE.md` §1.4 and §2.2;
`analysis/baseline_v6_train_batch_driver.py` → `vendor_get_local`, which
is the vendor-call pattern to reuse (spacing, 401/429 hard stop, call
counting).

---

## Ground rules

1. **No Claude API calls. No DB writes. No scoring.** Do not read any
   price or return data in this run.
2. **SEC etiquette:**
   - At most 1 request per second, far under SEC's 10 per second.
   - Every request sends a `User-Agent` header read from `.env` as
     `SEC_USER_AGENT`. **If `SEC_USER_AGENT` is not in `.env`, stop at
     Step 2 and ask Luis to add a line of the form
     `SEC_USER_AGENT="Full Name contact-email"`.** SEC requires a real
     name and contact.
   - Never print its value in logs or the wrap-up.
3. **Vendor calls:** reuse the `vendor_get_local` pattern and its hard
   stop on 401/429. Hard cap 20 calls, counted in `progress.json`.
4. **Do not act on the design beyond this phase.** No link extraction, no
   digests, no peer map.
5. Report, do not decide.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/p5-phase0/`. `progress.json` first.
Then, before the clean-tree check, commit in this order, each as its own
commit:
1. this prompt file;
2. `docs/handoffs/2026-09-26-p5-peer-readthrough-design.md`, if
   untracked (`docs: P5 peer read-through design, draft for review`);
3. any review file for P5 in `prompts/` or `docs/handoffs/`, if present.

Any other modified or untracked file → stop and report. Then clean tree;
hard stop if `git_dirty` cannot be recorded `false`. Probe script(s)
committed before any output.

---

## Step 1 — record the three decisions, $0 (one commit)

Wording is from the design doc §2. Mark each insertion
`(amended 2026-09-26, Luis)`.

**1a. `docs/architecture/DESIGN_PRINCIPLES.md` §1.** After the sentence
saying the analyst never receives "data about any other ticker", add:

> **Amended 2026-09-26 (Luis):** peer transcripts, and factual digests of
> them, dated strictly before the target call may be given to the
> analyst. Portfolio membership, positions, sizes and any price data
> about other tickers may not. The firewall's purpose (no portfolio data,
> no hindsight) is unchanged.

**1b. `docs/architecture/PROMPT_ARCHITECTURE.md` §1.4.** Append the same
sentence, plus:

> Peer text may cross the train / tune / holdout split **as input only**.
> Holdout calls are never scored until the final look. Links between
> companies come from filings dated before the call, not from judgement
> (P5 design §3).

**1c. `PROMPT_ARCHITECTURE.md` §2.2, the P5 row:** "design drafted
2026-09-26 (`docs/handoffs/2026-09-26-p5-peer-readthrough-design.md`),
under review; phase 0 probes running".

Commit: `docs: firewall amended for peer transcripts dated before the call; peer text may cross splits as input only (Luis, 2026-09-26)`.

**Propagation check:** `git grep` for other files that restate the old
firewall sentence ("any other ticker"). List them; do not edit them.

---

## Step 2 — EDGAR probe (≤ 30 requests)

Tickers: **RUN** (installer; its 10-K should name suppliers), **MU**
(chips; customer concentration), **JPM** (a sector with few supply
links).

1. Fetch `https://www.sec.gov/files/company_tickers.json` once. Resolve
   the three CIKs.
2. For each, fetch `https://data.sec.gov/submissions/CIK##########.json`.
   List every **10-K** (and 10-K/A) with its **filing date** and
   accession number, 2019 through 2025. Note whether older filings sit in
   the `filings.files` overflow pages.
3. For **RUN only**, fetch the primary document of one 10-K (the one
   filed in 2022). Report:
   - its size;
   - whether plain text search finds headings for **Customers**,
     **Suppliers** (or "Manufacturing" / "sole source"), and
     **Competition**;
   - the **first sentence naming a supplier company**, quoted verbatim,
     with its character offset. This is the extraction target shape for
     phase 1.
4. Record every request (URL without the query secrets, status, bytes,
   elapsed) in `edgar_probe.json`.

**Pass** if all three CIKs resolve, submissions JSON lists dated 10-Ks
for 2019–2025, and the RUN 10-K text is retrievable and searchable.

---

## Step 3 — transcript-source probe (≤ 20 vendor calls)

1. **On disk, $0:** list which companies have transcripts under
   `analysis/data/corpus_v2/transcripts/`. Confirm that **holdout
   companies have none** (expected: holdout was locked before fetching).
   Report the count per split.
2. **Vendor:** for **ENPH** (not in corpus), **NVDA** and **AMD**
   (holdout), and **KLAC** and **ADI** (not in corpus):
   - request the event list;
   - report quarters available from 2020 onward;
   - fetch **one** transcript each (a 2022 call);
   - report its length and whether it has the prepared remarks and the
     Q&A.
3. **Do not write these transcripts into the corpus transcript
   directory.** Save them under
   `analysis/data/run_state/p5-phase0/peer_probe/`, which is gitignored.
   Commit only the metadata (`transcript_probe.json`).
4. **Holdout rule, restated:** these transcripts are **peer input only**.
   Do not score, digest or summarize them in this run, and do not read
   anything about their stock prices.

**Pass** if at least 4 of the 5 companies return an event list covering
2020–2025 and a full transcript.

---

## Step 4 — hand peer map file, $0

Create `docs/peers/HAND_MAP.csv` with this header only, no rows:

```
company,linked_company,link_type,valid_from_year,valid_to_year,confidence,note
```

- `link_type`: one of `CUSTOMER` (linked_company buys from company),
  `SUPPLIER` (linked_company sells to company), or `COMPETITOR`.
- `confidence`: `high`, `medium` or `low`.

Create `docs/peers/README.md` in plain language:
- Luis fills `HAND_MAP.csv` for semis, solar, storage and software, **from
  his own knowledge, before any filing-derived map is built or shown**.
- It is committed **before** phase 1 runs.
- Use years as he understood the relationship **at the time**, not in
  hindsight. If a link only became obvious later, leave it out or mark
  it `low` with a note.
- These links are tested separately from the filing links (design §3).

Commit both.

---

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/P5-phase0-probes-out.md`, `.md` only. Open with:

> EDGAR [works / does not work] from this Mac: ___ of 3 companies
> resolved, with dated 10-Ks for 2019–2025, and RUN's 2022 10-K
> [names / does not name] a supplier in searchable text ("___").
> Transcripts for companies not on disk [are / are not] available: ___
> of 5 returned 2020–2025 event lists and a full transcript. Holdout
> companies have ___ transcripts on disk. **Phase 1 is [unblocked /
> blocked by ___].**

Then Steps 1–4 in detail, requests and vendor calls used, and the
propagation hits.

**Close with what it means.**
- **Unblocked:** phase 1 waits on two things only, the architect review
  of the design and Luis's hand map.
- **Blocked:** name the blocker and the cheapest way around it.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure. One prompt in, one wrap-up out. **Finish with
`git push`** of `sweep/db-corpus-baseline` after the wrap-up commit, and
report the pushed hash; on failure, say so and never force.
