# READ classifier v1 (measuring tool, not a candidate)
# Used by prompts/winners-missed-analysis.md Step 2. Sees only an analyst's short
# read of an earnings call. No registry entry.

---

You will be shown a short written read of a company's earnings call, written by an
analyst. You are not shown the call itself, the company's identity beyond what the
read says, the analyst's score, or anything about how the stock later performed.
Do not guess how the stock did. Judge only the words in front of you.

Classify what the read says. Return your answer as the block below and nothing
else.

---STRUCTURED---
{
  "positive": "",
  "negative": "",
  "forwardPositive": "",
  "discounted": ""
}
---END STRUCTURED---

Definitions:

- positive: the strongest positive evidence the read cites about the company.
  "none": the read cites no positive evidence. "weak": positive evidence that is
  general or qualitative (for example "demand looks healthy", "management is
  confident"). "strong": positive evidence that is specific and material, such as a
  number, a raised guide, a named contract, or a measured improvement.
- negative: the strongest negative evidence the read cites. Same three values and
  the same meaning of "weak" and "strong", applied to negative evidence.
- forwardPositive: "yes" if any positive evidence in the read is about the FUTURE
  (guidance, bookings, backlog, pipeline, a new product, a margin path), not only
  about past results. "no" otherwise.
- discounted: "yes" if the read names positive evidence and then sets it aside
  (says it is priced in, a one-off, not yet proven, or uncertain). "no" otherwise,
  including when the read names no positive evidence.

Use exactly the values shown ("none" / "weak" / "strong" for the first two,
"yes" / "no" for the last two).
