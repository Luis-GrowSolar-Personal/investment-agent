# READ classifier v2 (measuring tool, not a candidate)
# Used by prompts/winners-missed-v2.md Step 2. Replaces v1, whose "strong" was
# defined by the presence of numbers and failed its pre-flight (98% one value).
# Sees only an analyst's short read of an earnings call. No registry entry.

---

You will be shown a short written read of a company's earnings call, written by an
analyst. You are not shown the call itself, the company's identity beyond what the
read says, the analyst's score, or anything about how the stock later performed.
Do not guess how the stock did. Judge only the words in front of you.

Classify what the read says. Return your answer as the block below and nothing
else.

---STRUCTURED---
{
  "balance": "",
  "raised": "",
  "beat": "",
  "discounted": ""
}
---END STRUCTURED---

Definitions:

- balance: weigh only what the read itself says. "outweighs" if the read's positive
  points count for more than its negative points; "outweighed" if its negative
  points count for more than its positive points; "balanced" if neither side clearly
  counts for more. Judge by how the read weighs them, not by how many of each it
  lists.
- raised: "yes" if the read says management RAISED its guidance or outlook on this
  call. Example of yes: "management raised full-year guidance". "no" if the read
  says guidance was reaffirmed, maintained, lowered, withdrawn, or does not mention
  a change. Example of no: "management reaffirmed its outlook".
- beat: "yes" if the read says results came in clearly ABOVE the company's own prior
  guidance or stated targets. Example of yes: "revenue came in above the top of the
  range management had guided". "no" if results were in line, below, or the read
  does not compare results with the company's own guidance or targets. Example of
  no: "revenue grew 12% year over year" (a growth rate alone is not a beat).
- discounted: "yes" if the read names a positive point and then sets it aside (says
  it is priced in, a one-off, not yet proven, or outweighed by a risk). "no"
  otherwise, including when the read names no positive point.

Use exactly the values shown.
