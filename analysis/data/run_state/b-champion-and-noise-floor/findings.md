# findings (append-only)

- 2026-09-26 step 1: analysis/data/gate_ledger.json is matched by .gitignore (analysis/data/*) and has never been tracked; entry 1 is also uncommitted. Entry 2 written to disk only.
- whats_live.py reports MATCH for evaluation_prompt (v6) and does not print the research_champion block.
