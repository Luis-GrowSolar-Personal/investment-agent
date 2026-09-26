#!/usr/bin/env python3
"""
p5b_linktype.py -- prompts/P5-phase0b-link-sources.md Step 3 (optional; Luis approved a $3 cap). 10 seeded mentions from Step 2's by-eye company mentions (>= 3 from solar and
semis calls), each shown to claude-sonnet-4-6 as ONLY the sentence plus two sentences either side, never the whole call. Label: CUSTOMER / SUPPLIER / COMPETITOR / PARTNER / OTHER
with a supporting quote. Direct API calls (10), model claude-sonnet-4-6, max_tokens 300, no temperature parameter. Output: p5-phase0b/linktype_probe.json
"""
import sys, json, re, random, os
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv
load_dotenv(REPO / ".env")
import anthropic
STATE = REPO / "analysis/data/run_state/p5-phase0b"
TD = REPO / "analysis/data/corpus_v2/transcripts"
MODEL, CAP = "claude-sonnet-4-6", 3.0
P_IN, P_OUT = 3.0, 15.0     # $/MTok, standard (non-batch) sonnet-4-6
SYSTEM = """You will be shown a short passage from an earnings call transcript. You are not shown the rest of the call. The passage mentions a named company. Say how the named company relates to the company that is holding the call (the speaker's company), judging only from the passage.

Return only this block:

---STRUCTURED---
{
  "relation": "",
  "quote": ""
}
---END STRUCTURED---

- relation: exactly one of
  "CUSTOMER" (the named company buys from the speaker's company),
  "SUPPLIER" (the named company sells to the speaker's company),
  "COMPETITOR" (the named company competes with the speaker's company),
  "PARTNER" (a collaboration, alliance, investment or joint work that is not a plain sale),
  "OTHER" (a macro or market reference, an analyst's firm, a name used as an example, or anything that is not a business relation of the speaker's company).
- quote: the exact words from the passage that support the relation, copied verbatim, as short as possible."""


def sents(txt):
    return [x.strip() for x in re.split(r"(?<=[.?!])\s+", txt) if x.strip()]


def main():
    P = json.loads((STATE / "calls_probe.json").read_text())
    pool = []
    for r in P["calls"]:
        seen = set()
        for m in r["matches"]:
            if m["excluded_second_pass"] or m["by_eye_false_positive"] or (r["ticker"], m["name"]) in seen: continue
            seen.add((r["ticker"], m["name"])); pool.append({"call": r["ticker"], "date": r["date"], "sector": r["sector"], "name": m["name"], "in": m["in"]})
    rng = random.Random("p5-0b-step3-11")
    core = [x for x in pool if x["sector"] in ("semis", "solar")]; rest = [x for x in pool if x["sector"] == "other"]
    pick = rng.sample(core, 5) + rng.sample(rest, 5)
    cl = anthropic.Anthropic(); out = []; cost = 0.0
    for x in pick:
        text = json.loads((TD / x["call"] / f"{x['date']}.json").read_text())["text"]
        turns = text.split("\n\n")
        hit = None
        for tn in turns:
            m = re.match(r"([^:\n]{1,160}?\)):\s", tn); body = tn[m.end():] if m else tn
            if m and "operator" in m.group(1).lower(): continue
            i = body.find(x["name"])
            if i >= 0:
                ss = sents(body); k = next((j for j, s_ in enumerate(ss) if x["name"] in s_), None)
                if k is not None: hit = " ".join(ss[max(0, k - 2): k + 3]); break
        assert hit, x
        assert cost < CAP
        r = cl.messages.create(model=MODEL, max_tokens=300, system=SYSTEM, messages=[{"role": "user", "content": f"Named company: {x['name']}\n\nPassage:\n{hit}"}])
        txt = "".join(b.text for b in r.content if b.type == "text"); c = (r.usage.input_tokens * P_IN + r.usage.output_tokens * P_OUT) / 1e6; cost += c
        m = re.search(r"---STRUCTURED---\s*(\{.*?\})\s*---END STRUCTURED---", txt, re.S)
        lab = json.loads(m.group(1)) if m else {}
        out.append({**x, "passage": hit, "relation": lab.get("relation"), "quote": lab.get("quote"), "quote_in_passage": bool(lab.get("quote")) and lab["quote"] in hit, "cost_usd": round(c, 5), "stop": r.stop_reason})
        print(x["call"], x["name"], "->", lab.get("relation"), "|", (lab.get("quote") or "")[:100])
    from collections import Counter
    cnt = Counter(o["relation"] for o in out)
    res = {"model": MODEL, "n": len(out), "seed": "p5-0b-step3-11", "label_counts": dict(cnt), "max_label_share_over_8_of_10": max(cnt.values()) > 8, "cost_usd": round(cost, 4), "cap_usd": CAP, "mentions": out}
    (STATE / "linktype_probe.json").write_text(json.dumps(res, indent=1)); print(dict(cnt), "cost", round(cost, 4))


if __name__ == "__main__":
    main()
