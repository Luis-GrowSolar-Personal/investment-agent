# P5 phase 1 — sector diagnostics, then the point-in-time peer map and coverage. About $10–15

**Run ID:** `p5-phase1`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P5-phase1-peer-map-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $10–15** (model extraction
from pre-filtered filing and call passages). **Hard cap $20**, counted
before every `create()`. Luis approves at Step 0 or stop and ask.

**Other budgets:**
- at most **1,600 SEC EDGAR requests**, at 1 per second (about 30
  minutes);
- at most **150 EarningsCall.biz vendor calls**, event lists only, no
  transcripts.

**No scoring. No price or return data except in Step 1.**

---

## Framing

P5, peer read-through, gives the analyst factual digests of calls from a
company's customers, suppliers and competitors, reported **before** its
own call. The design and its review are settled:
- `docs/handoffs/2026-09-26-p5-peer-readthrough-design.md`, with
  Addendum A;
- `docs/handoffs/2026-09-26-p5-design-review.md`, which is **go with
  three changes, all binding here**.

This phase does three things, in this order:

1. **Sector diagnostics, $0 in model calls** (review change 3). Does B
   already rank calls *within* a sector and year? If it does, P5 must be
   compared with that bar, not with B's overall 0.13. Otherwise P5 gets
   credit for sector effects B already captures.
2. **Build the point-in-time peer map** from **filings** and **earlier
   earnings calls of either company**, with verbatim quotes.
3. **Count coverage.** How many train calls have at least one linked
   peer call, dated before them and readable? **Stop if under 300**
   (design §3).

**Nothing is scored. No digest is written. No P5 prompt runs.** Those are
phases 2 and 3.

**Already established; do not rediscover.**
- EDGAR works from this Mac, and the vendor serves transcripts for
  holdout and non-corpus companies (`wrap-ups/P5-phase0-probes-out.md`).
- Filings name competitors in 3 of 4 cases, and customers mostly in the
  **financial notes**, not the business section. Calls name another
  listed company in about two thirds of cases. Operator lines naming
  **analyst firms** swamp raw name matching
  (`wrap-ups/P5-phase0b-link-sources-out.md`).
- `docs/peers/NAME_ALIASES.csv` exists. Reuse and extend it.

**Read first:** the design doc (all); the review (all); both phase 0
wrap-ups; `analysis/p5_edgar_probe.py`, `p5b_names.py`,
`p5b_filings_offline.py`, `p5b_calls.py`, `p5b_linktype.py` (extend; do
not fork).

---

## Ground rules

1. **Hand links (review change 2):** built from `docs/peers/HAND_MAP.csv`,
   tagged `HAND`, **reported with and without**. They **never** count
   toward the coverage stop or any gate.
2. **Only train targets are counted.** Tune and holdout **text** may be
   read as link sources and peer candidates, as input only (design §2
   decision 2). **No tune or holdout call is scored, and no tune or
   holdout return is read.**
3. **Point in time, always:**
   - A filing link is valid from its **filing date** until that
     company's next 10-K.
   - A call link is valid from the **call date** onward.
   - Neither is ever applied to a target call dated before its source.
4. **Every link carries a verbatim quote**, checked by script to appear
   in the source text. No quote, no link.
5. **Analyst firms never become links** (review, build requirement):
   - Drop any mention inside an operator line ("next question comes from
     … with …", "… from [firm]") and any analyst's self-introduction.
   - Keep a committed **exclusion list** of sell-side firms (Morgan
     Stanley, Goldman Sachs, JPMorgan, BofA, Citi, UBS, Barclays, Wells
     Fargo, Jefferies, Evercore, Bernstein, Cowen, Piper Sandler, Raymond
     James, KeyBanc, Needham, Oppenheimer, Baird, Truist, Stifel, Mizuho,
     Deutsche Bank, Credit Suisse, RBC, BMO, TD Cowen, Wolfe, Guggenheim,
     Loop, Rosenblatt, Craig-Hallum, Roth, …).
   - **Exception:** a bank is linked only when the passage names it in a
     business relation, e.g. JPMorgan as a lender or customer.
6. **Model use is extraction only.** It says *who is named, and in what
   relation*, from a short passage. It never proposes a link that is not
   in the text. `claude-sonnet-4-6`, Batch API, no temperature.
7. SEC etiquette as phase 0: `SEC_USER_AGENT` from `.env`, never logged;
   1 request per second; use overflow pages only when needed.

A diagnostic that contradicts an expectation here is a finding, not a
reason to stop.

## Step −1 / Step 0 — git bookends and the hand-map check

State in `analysis/data/run_state/p5-phase1/`. `progress.json` first.
Commit, each as its own commit:
1. this prompt;
2. `docs/handoffs/2026-09-26-p5-design-review.md`, if untracked;
3. `docs/peers/HAND_MAP.csv` (canonical), `docs/peers/HAND_MAP.xlsx`
   (helper) and `docs/peers/README.md`, if new or modified.

Any other modified or untracked file → stop and report. Clean tree.
Scripts committed before output. Batch ids committed at `create()`.

**Hand-map check, before anything else runs.** `docs/peers/HAND_MAP.csv`
is **canonical**. Luis edits it directly; the workbook is only a helper.
Read only its first seven columns (`company` … `note`) and ignore any
helper columns after them. Keep rows where `linked_company` is filled
in. Validate every kept row:
- `link_type` is CUSTOMER, SUPPLIER or COMPETITOR;
- `valid_from_year` is a whole number, 1990–2026; `valid_to_year` is
  blank or a whole number no earlier than it;
- `linked_company` holds one or more tickers, separated by commas,
  semicolons or spaces. Split them into one link per ticker, each
  inheriting the row's type, years, confidence and note;
- no ticker links to itself.

**Invalid rows → stop and list them for Luis.** Do not fix or guess. Do
not overwrite the CSV. Report any linked ticker that is in neither the
corpus nor EDGAR's ticker list. Count the kept rows and the split links.

**If it has no rows, stop and ask Luis:**

> "Your hand map is empty. This run builds and shows the filing- and
> call-based peer map, and hand links must be drawn before seeing it.
> Fill it now and re-run, or proceed without hand links permanently for
> P5?"

Record his answer in `progress.json`. If he says proceed, write
`hand_links: "declined 2026-09-26"` and never build hand links for P5.

---

## Step 1 — sector diagnostics ($0 model; ~170 SEC requests; run first)

**1a. Sector labels.** For each of the 164 corpus companies, plus ELV,
GOOG and PARA if they appear in train, fetch the EDGAR submissions JSON
and record its **SIC code**.

Map SIC to a small set of groups: semis, solar/storage/clean energy,
software/IT, internet/media, banks/financials, pharma/health, energy
(oil & gas), utilities, industrials, consumer staples, consumer
discretionary/retail, telecom, REITs, materials, other.
- Commit the mapping table (`docs/peers/SECTOR_MAP.csv`) with each
  company's SIC and group.
- Flag solar and storage companies whose SIC puts them elsewhere (e.g. an
  electrical-equipment code). Move them to solar/storage **only if** the
  company's own 10-K business description says solar or storage, and
  quote it.

**1b. Winners by sector and year (train).**
- Rows: sector group; columns: calendar year of the call; cells: number
  of calls and share that became **big winners** (beat the S&P by 20+
  points over the 182 days after the tradeable entry).
- Say in one line whether winners cluster in a few sector-years.

**1c. B's ranking within sector-year**, both B draws:
- Compute the rank correlation of B's score with the 182-day return
  **inside each sector-year cell with at least 12 calls**.
- Average across cells, weighting by call count.
- Give a range by resampling companies (ticker-block, 2,000 draws, seed
  11).
- Report beside B's overall 0.130 / 0.099.
- Also report the share of train calls in cells of 12 or more.

**1d. B's call-over-call change.** For each train call with a previous
call of the same company, compute the change in B's score (this call
minus the previous). Report the rank correlation of that change with the
182-day return, per B draw, with its range.

**Pre-registered reading, fixed now:**
- **"B already ranks within sector-year"** if 1c's weighted figure, on
  both draws, is at least **0.08** with its range above zero. Then P5's
  phase 3 primary gate is computed **within sector-year** as well as
  overall. Both must pass.
- Otherwise **"B's ranking is mostly across sectors"**. Phase 3 still
  reports within sector-year, but gates on the overall comparison, per
  the review's change 1.

Commit `sector_diagnostics.json`.

---

## Step 2 — filing links (~1,300 SEC requests; ~$4–6)

**2a. Fetch.** For each of the 164 corpus companies, fetch every 10-K
and 10-K/A filed **2019-01-01 to 2025-12-31**, and record the filing
date. Save the text gitignored under
`analysis/data/evals/p5_filings/`. Resume-safe: skip files already saved.

**2b. Pre-filter mechanically, $0.** Split each filing into paragraphs.
Keep a paragraph only if it contains **both** of these:
- a name from the name list plus aliases (phase 0b list plus
  `NAME_ALIASES.csv`), after exclusions;
- one of: *customer, client, competitor, compete, competition, supplier,
  supply, vendor, sole source, single source, manufacturer, foundry,
  distributor, partner, % of revenue / net revenue / total revenue*.

Search the **whole document**, not only Item 1. INTC's and MU's named
customers sat in the financial notes.

**2c. Extract**, one paragraph per request. Return a list of
`{named_company, relation: CUSTOMER|SUPPLIER|COMPETITOR|PARTNER|OTHER, quote}`.
- The relation is **from the filer's point of view**. `CUSTOMER` means
  the named company buys from the filer.
- The quote must be verbatim. Verify it by script and drop any link that
  fails.
- **Pre-flight first:** 40 paragraphs, seeded. Stop if parsing fails, if
  more than 10% of quotes fail verification, or if any relation label
  takes more than 80% of the 40.

**2d. Anonymised customers.** Record "one customer accounted for X%" as a
fact about the filer, with no link. Report how many filers anonymise.

---

## Step 3 — call links (~$3–5)

**3a. Sources:** every transcript on disk under
`analysis/data/corpus_v2/transcripts/`, meaning train and tune. Holdout
and non-corpus calls are **not** fetched in this phase. They are peer
inputs for phase 2, not link sources now. Say so in the wrap-up as a
coverage limit.

**3b. Pre-filter mechanically, $0.** Find every name-list match, **after
the analyst-firm and operator-line exclusions**. Keep the sentence plus
two sentences either side. Tag each passage prepared remarks or Q&A.

**3c. Extract** with the same schema as 2c. The relation is **from the
calling company's point of view**. Tell the model which company is
holding the call, and **only** that. Same 40-passage pre-flight and stop
rules.

**3d. Recurrence.** For each company pair and relation, record how many
distinct calls and filings name it, and the first date named. A link
named once is kept but flagged `single_source`.

---

## Step 4 — the map

- Resolve names to tickers with the alias table, then normalise every
  ticker through `analysis/data/corpus_v2/TICKER_ALIASES.json`. Old and
  new symbols of one company are one peer (SQ/XYZ Block, GOOGL/GOOG
  Alphabet). Apply the same normalisation to hand-map tickers and vendor
  event lists. Report any linked ticker that looks like a renamed
  company but is not in the file; do not add entries. List unresolved names
  (private companies, foreign names without a US listing) and keep them
  out.
- **Links are directional facts. Use them both ways for peer lookup.** If
  ENPH's filing says RUN is a customer, then RUN's peers include ENPH as
  a supplier, from ENPH's filing date.
- Output `analysis/data/run_state/p5-phase1/peer_links.csv` with columns
  `company, peer, relation_from_company_view, source_type (FILING|CALL|HAND), source_date, source_id, quote, recurrence, single_source`.
- Build `HAND` links from `HAND_MAP.csv`, if any, into the same file,
  tagged. They are never mixed into the counts in Step 5's headline.

---

## Step 5 — coverage and readability

**5a. For each train call** (the target), list its eligible peers:
- the link is valid on the target's date (Step 4 rules);
- the peer has a call dated **strictly before** the target and **within
  120 days**. Use the peer's transcript dates if on disk; otherwise the
  vendor's event list.

**5b. Readability, ≤ 150 vendor calls.** For peers **not on disk**
(holdout and non-corpus), fetch the vendor **event list once per peer**
to confirm a call exists in the window. No transcripts. Prioritise peers
by how many train targets they would cover. Stop at the cap and report
how many peers were left unchecked.

**5c. Coverage count**, headline on **FILING + CALL links only**:
- train calls with at least 1 eligible, readable peer;
- the same split by link type (supply chain: CUSTOMER or SUPPLIER; shared
  customer: COMPETITOR; PARTNER) and by sector group;
- the same with `single_source` links excluded;
- the same with `HAND` links added, reported **separately**.

**Stop rule (design §3, review): fewer than 300 covered train calls on
FILING + CALL links → P5 stops here.** Hand links do not rescue it.

---

## Report step

**Scope boundary: report, do not decide.** No digests, no scoring, no
phase 2.

`wrap-ups/P5-phase1-peer-map-out.md`, `.md` only. Open with:

> Within sector and year, B ranks calls at ___ and ___ on its two draws
> (overall 0.130 / 0.099): **[B already ranks within sector-year /
> mostly across sectors]**. From ___ 10-Ks and ___ earnings calls, the
> point-in-time peer map holds ___ links (___ from filings, ___ from
> calls; ___ supply-chain, ___ competitor, ___ partner). ___ of 1,217
> train calls have at least one linked peer call dated before them,
> within 120 days, and readable: **[P5 continues to phase 2 / P5 stops:
> coverage under 300]**. Supply-chain links alone cover ___ calls.

Then:
- Steps 1–5 in detail;
- the ten most-linked train companies with their peers, with quotes for
  the top three;
- extraction pre-flight results and quote-verification failure rates;
- vendor and SEC requests used, and cost.

**Close with what it means, both ways.**
- **Continue:** phase 2 is the digests. State which peers must be fetched
  as transcripts, how many calls, and the vendor budget needed.
- **Stop:** say whether the peer map is still worth keeping as an
  allocator input (review, "What a pass would change").

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure. One prompt in, one wrap-up out. **Resumable:**
long fetches and batches resume from state; see `CLAUDE.md` "Long CLI
runs must be resumable". **Finish with `git push`** after the wrap-up
commit, and report the pushed hash; on failure, say so and never force.
**Budget stop:** Step 1 always runs first. If the extraction projection
breaches $20, stop and report.
