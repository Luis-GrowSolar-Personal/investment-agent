# P5 phase 0b — how often do filings and calls name linked companies? About $0–2

**Run ID:** `p5-phase0b`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P5-phase0b-link-sources-out.md`
**Cost: about $0–2.** At most **15 SEC EDGAR requests**. Name matching is
$0. One optional model step on 10 mentions costs about $1. **Hard cap
$3**; Luis approves at Step 0, or the model step is skipped. **No vendor
calls.**

---

## Framing

Phase 0 found that RUN's 2022 10-K names no suppliers and no competitor
companies. The design now takes links from **filings and from earlier
earnings calls of either company**
(`docs/handoffs/2026-09-26-p5-peer-readthrough-design.md`, Addendum A).
Before phase 1 builds a map from these sources, this run answers one
question cheaply:

**Do filings and calls name other listed companies often enough to build
a peer map from them?**

**Read first:** the design doc (all, including Addendum A);
`wrap-ups/P5-phase0-probes-out.md`; `analysis/p5_edgar_probe.py` (reuse
its SEC request code: `User-Agent` from `.env` `SEC_USER_AGENT`, 1
request per second, never logged).

## Ground rules

1. No DB writes, no scoring, no price or return data.
2. **Train transcripts only** for the name matching, from the corpus
   transcripts on disk. No holdout or tune transcripts are read in this
   run.
3. SEC etiquette as phase 0. If a company's submissions need overflow
   pages, use the EDGAR company-browse route or fetch only the needed
   page, not newest-first paging (the phase 0 JPM lesson).
4. Report, do not decide.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/p5-phase0b/`. `progress.json` first.
Commit, each as its own commit:
1. this prompt;
2. the design doc's Addendum A (`docs: P5 design addendum A — links from filings and earlier calls of either company`);
3. any P5 review file present.

Any other modified or untracked file → stop and report. Clean tree.
Scripts committed before output.

---

## Step 1 — four more filings (≤ 15 requests)

The 2022 10-K (fiscal 2021 for most) of each of:
- **MU**: memory; expect named rivals and anonymous customers;
- **INTC**: chips; customer concentration;
- **ENPH**: supplier side of resi solar. It is non-corpus, but a filing
  is public data and allowed;
- **NOW**: software; a different sector.

For each, report:
- the Customers, Suppliers or Supply Chain, and Competition sections
  found, by heading search;
- **every other company named in them.** Match against the name list in
  Step 2a, then read the matches by eye, and quote each named sentence
  verbatim;
- whether customers are named or anonymous ("Customer A", "one
  customer").

## Step 2 — company names in 30 train transcripts ($0)

**2a. The name list.** From `https://www.sec.gov/files/company_tickers.json`
(re-fetch once, or reuse phase 0's copy if saved), build a match list of
listed-company names.
- Strip suffixes (Inc., Corp., Holdings, plc…).
- Keep names of **two or more words**, or single words of **seven or
  more letters**, to avoid matching common words.
- Add a **hand-written alias list** for the 60 best-known names that
  differ from their legal names ("Google" → GOOGL, "Facebook" / "Meta" →
  META, "Enphase" → ENPH, "SolarEdge" → SEDG, "Tesla" → TSLA, and so on).
  Commit the list.

**2b. The sample.** 30 train transcripts, seeded (`p5-0b-11`):
- the 2022 calls of **RUN, MU, INTC, JKS, QCOM, NXPI**, which are
  required;
- 24 more drawn across the other train companies, one call each, from
  2021–2023.

**2c. Count**, per transcript:
- how many other listed companies are named;
- which ones;
- whether each mention is in prepared remarks or in Q&A;
- the sentence around each mention.

Also report:
- the share of the 30 calls that name **at least one** other listed
  company;
- the mean number named per call;
- the same, split into semis / solar / other.

**Also, from the 6 required calls:** list which named companies are
**in the corpus** (any split) or **fetchable as peers** (listed in the
vendor's symbol list from phase 0, if saved). A link is only usable if
the peer's calls can be read.

## Step 3 — optional, ~$1: can the link type be read?

Only if Luis approved the cap. Take 10 mentions from Step 2 (seeded), at
least 3 from the solar and semis calls. Give `claude-sonnet-4-6` **only
the sentence plus two sentences either side**, never the whole call, and
ask for:
- `relation`: `CUSTOMER` (named company buys from the speaker's company),
  `SUPPLIER` (named company sells to it), `COMPETITOR`, `PARTNER`, or
  `OTHER` (e.g. a macro reference, an analyst's firm name);
- the quote that supports it.

Report the 10 labels beside Luis-checkable context. **Stop rule, P7's
lesson:** if one label is more than 8 of 10, say so; the classifier needs
a rewrite before phase 1.

---

## Pre-registered reading, fixed now

- **"Sources sufficient"** if **at least 60%** of the 30 calls name at
  least one other listed company **and** at least 3 of the 4 filings name
  at least one competitor or customer company.
- **"Calls carry the map"** if the calls pass and the filings do not.
  Phase 1 builds mainly from transcripts, with filings as supplement.
- **"Too thin"** if under 60% of calls name another listed company. The
  map would rest on hand links; report that plainly.

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/P5-phase0b-link-sources-out.md`, `.md` only. Open with:

> Of 4 more 10-Ks, ___ named at least one competitor or customer company
> (___ named customers; ___ anonymised them). Of 30 train earnings calls,
> ___% named at least one other listed company, a mean of ___ per call
> (semis ___, solar ___, other ___). **[Sources sufficient / calls carry
> the map / too thin].** [Step 3: the link type was read correctly on ___
> of 10 by Luis's check-list / not run.]

Then Steps 1–3 in detail, with quotes. Close with what it means for phase
1's source hierarchy.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. `sweep/db-corpus-baseline`. Provenance for
every figure. One prompt in, one wrap-up out. **Finish with `git push`**
after the wrap-up commit, and report the pushed hash; on failure, say so
and never force.
