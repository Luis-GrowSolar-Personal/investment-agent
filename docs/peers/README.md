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
