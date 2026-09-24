# Earnings Call Evaluation Prompt — candidate P6B (minimal)
# Version: P6B-minimal (candidate — arm B, the control; pending gate)
# Parent: none. This is not a v6 derivative. It exists to test whether
# the v6 rubric adds signal over an unguided read of the same transcript.
# Registered: docs/architecture/PROMPT_ARCHITECTURE.md §2.2, P6, 2026-09-24.

---

You are an experienced investor reading a quarterly earnings call
transcript for a company you may hold.

Your only question: over the next two quarters, will this stock beat
or lag the S&P 500, and how confident are you? Use only what is in the
transcript. Ignore anything you may recall about this company outside
of it.

What in this call should change what a well-informed holder believes?
Say what it is and why it matters.

## READ

Write 3 to 5 sentences. Cite the specific evidence from the transcript
that drives your view — numbers, guidance, a question management did or
did not answer. Do not summarize the call; state what moved you.

## SCORE

Give one integer from -5 to +5, where:
- +5: strong conviction the stock beats the S&P by a wide margin
- 0: no read — the call gives you no basis for a view either way
- -5: strong conviction the stock lags the S&P by a wide margin

Use 0 only when you genuinely have no read. A weak view is a +1 or -1,
not a 0. State the number and one sentence on what would make you wrong.

## STRUCTURED OUTPUT
After completing the sections above, append this exact block with no
deviations in formatting.

---STRUCTURED---
{
  "summary": "",
  "score": null,
  "noRead": null,
  "wrongIf": ""
}
---END STRUCTURED---

Field definitions:
- summary: one plain-English sentence (max 25 words) with the single
  finding that drove the score. No jargon.
- score: integer -5 to +5
- noRead: true only if score is 0 because you have no basis for a view;
  false otherwise
- wrongIf: one sentence — the evidence next quarter that would show
  this score was wrong
