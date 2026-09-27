# Hand peer map

`HAND_MAP.csv` is where Luis writes down, from his own knowledge, which
companies are linked to which. It has a header row and no data rows yet.

## Columns

| column | meaning |
|---|---|
| `company` | the company whose call would read the link (the "target") |
| `linked_company` | the company it is linked to |
| `link_type` | `CUSTOMER` (linked_company buys from company), `SUPPLIER` (linked_company sells to company), or `COMPETITOR` |
| `valid_from_year`, `valid_to_year` | the years the link held, as you understood it **at the time** |
| `confidence` | `high`, `medium` or `low` |
| `note` | anything worth a sentence (why you believed it; where you saw it) |

## Rules

- Fill it for **semis, solar, storage and software**, **from your own
  knowledge, before any filing-derived map is built or shown to you**. If you
  see the filing-derived links first, you will find it hard to unsee them and
  the two maps stop being independent.
- It is **committed before phase 1 runs**. That is what makes it a fair test
  later.
- Use years as you understood the relationship **at the time**, not in
  hindsight. If a link only became obvious later, leave it out, or mark it
  `low` and say so in the note.
- These links are tested **separately** from the filing-derived links (P5
  design §3): the two maps answer different questions (what an informed
  reader knew, versus what the filings said).

Design: `docs/handoffs/2026-09-26-p5-peer-readthrough-design.md`.


## Update 2026-09-26: fill the workbook, not the CSV

Edit `docs/peers/HAND_MAP.xlsx`:

- **HAND_MAP tab.** One row per corpus company is pre-seeded, with focus
  sectors shaded and sorted first. Fill the yellow columns (B–G). Insert
  a row per extra link, repeating the ticker. Rows left blank are
  ignored.
- **CANDIDATES tab.** Companies to pick links from. It lists the whole
  corpus plus non-corpus names in semis, solar/storage and software,
  with where each one's transcripts come from.
- **LEGEND tab.** How to fill it in.

Phase 1 exports the filled rows to `HAND_MAP.csv` itself. The sector
labels are rough and only for sorting. The CANDIDATES tab is a list of
names, not suggested pairings.

**Several peers in one cell is fine.** Example: `NVDA` → `AMD, AVGO`
with link type COMPETITOR. Phase 1 splits the cell into one link per
ticker, each with the same type, years, confidence and note. Use a
separate row only when the type, years or confidence differ.

## The kept allocator input (2026-09-27)

P5 closed at phase 2a: its lead-lag gate failed
(`wrap-ups/P5-phase2a-tight-map-out.md`), so it is not used to feed the
analyst. But the **tight, point-in-time, quoted peer map** it built is
kept as a candidate **allocator** input (correlated-positions, not
analyst read-ahead):

`analysis/data/run_state/p5-phase2a/peer_links_tight.csv`

| column | meaning |
|---|---|
| `company` | the company the link is about |
| `peer` | the linked company |
| `relation` | `CUSTOMER`, `SUPPLIER` or `COMPETITOR`, from `company`'s point of view |
| `rule` | which tight-map rule kept it: `S1` (customer/supplier named in a 10-K), `S2` (named in 3+ calls), `C1` (same-sector competitor, named by the company itself, 2+ sources), `C2` (mutual competitors, 2+ sources each side, any sector) |
| `qualified_from` | the date the link's evidence first met its rule's threshold; the link applies from this date forward only |
| `dual_role` | true if the pair is also a competitor pair, superseded here by its supply-chain entry |
| `n_filing`, `n_call` | distinct filing / call sources (S1/S2 only) |
| `n_self_named`, `n_peer_named`, `n_total` | distinct competitor-naming sources, by who named it (C1/C2 only) |
| `sector_company`, `sector_peer` | `docs/peers/SECTOR_MAP.csv` groups at qualification |
| `quote` | one verbatim supporting quote |

The loose map (`analysis/data/run_state/p5-phase1/peer_links.csv`, 28,902
rows) and the hand map stay on disk for provenance; the tight file above
is the one meant for reuse.
