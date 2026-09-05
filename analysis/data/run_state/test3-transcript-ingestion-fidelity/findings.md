# Findings — test3-transcript-ingestion-fidelity

(append-only)

## Step 1 — DB corpus completeness census (ALL16, 337 transcripts)
Zero outliers by the 40%-of-own-ticker-median rule, across all 337 ALL16
transcripts. Closing-language keyword match 245/337 (73%); Q&A presence
337/337 (100%). The 92 rows failing the closing keyword match are spread
across 11 of 16 tickers (SPWR 8/8 = all of them; AAPL 18; ENVX 16; FSLR 14;
QS 10; TSLA 9; EOSE 8; NVDA 3; RUN 3; AVGO 2; TTD 1) — a keyword-list
limitation (many real transcripts end without one of the six listed idioms),
not evidence of truncation on its own, since none of these rows are
word-count outliers and all have Q&A sections present.

**Load-bearing comparison — the four pilot-flagged rows, DB side:**
| id | ticker/qtr | DB word count | ticker median | ratio | closing | Q&A | outlier |
|---|---|---|---|---|---|---|---|
| 23 | EOSE Q2 2025 | 9053 | 9062.5 | 1.00 | Y | Y | N |
| 32 | SPWR Q1 2025 | 11517 | 9806 | 1.17 | N | Y | N |
| 31 | SPWR Q3 2025 | 10839 | 9806 | 1.11 | N | Y | N |
| 17 | AMPX Q3 2025 | 8735 | 5754 | 1.52 | Y | Y | N |

**All four look normal-to-above-median on the DB side.** AMPX Q3 (id 17) is
especially telling: DB word count is 52% ABOVE its own ticker's median (8735
vs 5754), while the AV version of the same quarter is the one with only 15
speaker turns vs 47-53 for AMPX's other quarters. This squarely identifies
AV, not the DB corpus, as the truncated side for this sample.

## Step 2 — AV-side qualitative classification (7 saved raw samples, 0 new AV calls)
| sample | turns | last speaker | closing match | pilot ratio | classification |
|---|---|---|---|---|---|
| AMPX Q1 | 47 | Operator | Y | 0.7071 | complete-like |
| AMPX Q2 | 53 | Operator | Y | 0.7801 | complete-like |
| AMPX Q3 | 15 | Operator | Y (false positive — see below) | 0.3395 | **truncated** |
| EOSE Q1 | 50 | Joe Mastrangelo (CEO) | N | 0.6949 | unclear (mechanical) |
| EOSE Q2 | 24 | Operator | Y | 0.1142 | summarized-but-complete |
| SPWR Q1 | 29 | T.J. Rodgers (CEO) | N | 0.1768 | unclear (mechanical) |
| SPWR Q3 | 29 | Thurman Rodgers (Chairman/CEO) | N | 0.1717 | unclear (mechanical) |

**AMPX Q3's keyword match is a false positive**: the matched word "concludes"
refers to "this concludes our question-and-answer session," and the actual
last sentence hands off to Dr. Sun for closing remarks that never appear in
the AV JSON. Confirmed truncated by content inspection, not just word count.

**EOSE Q2's low ratio (0.1142) is NOT truncation** — the AV transcript's last
turn is a full, standard operator sign-off ("This concludes today's
conference call... You may all disconnect."), so despite the biggest
similarity gap of all 7 samples, the call's full arc (remarks through
sign-off) is present in the AV data. Different mechanism from AMPX Q3
entirely — low similarity here reflects paraphrasing/summarization density,
not a missing ending.

**EOSE Q1 and both SPWR samples end on the company officer's own informal
remark ("Thank you," "I appreciate your coming in and listening to us")
with no operator sign-off and no keyword-list match** — the mechanical
classifier calls these "unclear." Combined with Step 1's DB-side word counts
(all three are at or above their own ticker's median with Q&A present), the
more likely reading is that these AV transcripts capture a genuinely
informal call-ending convention (no operator outro at all) rather than a cut
transcript — but this is a judgment call from convergent evidence, not a
mechanical certainty the way AMPX Q3's truncation is.

## Step 3 — SPWR rename-timing check
SPWR Q1 2025 (2025-04-30, at the April 2025 rename) and Q3 2025 (2025-10-21,
six months clear) show the **identical** AV classification and identical
ending pattern (CEO informal thanks, no operator sign-off, no keyword
match), and both are at/above their own DB-side ticker median with no
outlier flag. **This argues AGAINST a rename-transition artifact and FOR a
persistent, ticker-specific AV convention/coverage characteristic for SPWR**
— the low similarity ratio for both SPWR quarters looks like the same
mechanism operating identically before and after the rename, not a
transition glitch. Control comparison: AMPX Q3 (no rename event) shows
genuine truncation (a different, more severe mechanism); EOSE Q1 (no rename
event) shows the same "informal officer close, no operator outro" pattern as
SPWR — suggesting this ending style is not SPWR-specific after all, but
occurs on calls of multiple tickers where the company itself, not an
operator, runs the sign-off.

## Direct DB rawText tail verification (beyond the mechanical checks)
Read the literal last ~400-500 chars of `rawText` for ids 17, 32, 31, 23
directly (not just the mechanical checker's output):
- **id 17 (AMPX Q3): DB text ends with the real closing remarks AND the
  operator sign-off** ("...thank our employees, partners and shareholders
  for their continued support. Operator: Thank you for joining us today...
  You may now disconnect. Have a good day.") — this is exactly the content
  AV's version cut before reaching. **Decisive**: AV truncated, DB did not.
- **id 32 (SPWR Q1) and id 31 (SPWR Q3): DB text ends WORD-FOR-WORD
  IDENTICAL to the AV version** (T.J. Rodgers' "I talked long as usual..."
  and Thurman Rodgers' "long-winded dissertation" lines respectively, both
  verified present in both DB and AV). SPWR's calls genuinely end on the
  CEO's own informal remark in both sources — not a truncation in either,
  just this company's real call-ending style (no operator outro at all).
- **id 23 (EOSE Q2): DB text ends with the same full operator sign-off** as
  the AV version. Confirms Step 2's "summarized-but-complete" read directly.

This upgrades Step 3's "unclear" mechanical classification for both SPWR
rows to a confirmed reading: **not truncated, on either side** — the
low DB/AV similarity ratio for SPWR reflects paraphrasing of the middle of
the call, not a missing ending, and has nothing to do with the April 2025
rename.

## Note — git lock
`.git/index.lock` present at session start (mtime 2026-09-05 13:13),
unchanged through Step 1-3 (checked repeatedly through ~13:29), consistent
with the prompt's warning that other sessions may be active on this branch.
Not deleted. Read-only `git status`/`git log` work fine without it; only the
final commit needs it cleared. Waiting before attempting to commit.
