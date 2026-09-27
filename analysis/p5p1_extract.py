#!/usr/bin/env python3
"""
p5p1_extract.py -- Steps 2c and 3c. Extraction only: from ONE short passage the model says who is named and in what relation, with a verbatim quote. claude-sonnet-4-6, Batch API,
max_tokens 1200, no temperature. Filings: relation from the FILER's point of view (the filer's name is given). Calls: relation from the CALLING company's point of view (only that company is named).
Commands: prep {F|C}   preflight-submit/poll/report {F|C}   submit-rest {F|C}   poll {F|C}
Requests are one per (unique paragraph, filer) for filings and one per passage for calls. Cost counted before every create(); hard cap $20 total (progress.json luis_approved_usd).
Quote verification: every returned quote must appear verbatim (whitespace-normalised) in the passage text, else the link is dropped and counted.
"""
import sys, json, re, random, hashlib, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
from dotenv import load_dotenv
load_dotenv(C.REPO / ".env")
import anthropic
MODEL = "claude-sonnet-4-6"; MAXTOK = 2000        # v2 (Luis-approved amendment after the v1 pre-flight failed the quote gate): 2000, was 1200
P_IN, P_OUT, P_CR, P_CW = 1.5, 7.5, 0.15, 1.875       # $/MTok, batch = 0.5 x standard (3 / 15 / 0.30 / 3.75)
SYSTEM_F = """You will be shown one short passage from a company's annual report (10-K). You are told which company filed it. List every OTHER company that the passage names, and how that named company relates to the filer, judging only from the passage.

Return only this block (the list may be empty):

---STRUCTURED---
{"links": [{"named_company": "", "relation": "", "quote": ""}]}
---END STRUCTURED---

- named_company: the company exactly as written in the passage.
- relation, from the FILER's point of view: "CUSTOMER" (the named company buys from the filer), "SUPPLIER" (the named company sells to the filer), "COMPETITOR", "PARTNER" (a collaboration, alliance, investment or joint work that is not a plain sale), or "OTHER" (a lender or bank, an analyst firm, an auditor, a name used only as an example, an acquisition target, a macro or industry reference, or anything that is not a business relation of the filer).
- quote: ONE contiguous span of the passage that supports the relation, copied verbatim (do not join separate pieces with "..." and do not change any character), as short as possible.
Do not include the filer itself. Never add a company that is not written in the passage, and never infer a relation the passage does not state."""
SYSTEM_C = """You will be shown a short passage from an earnings call transcript. You are told which company is holding the call, and nothing else about the call. List every OTHER company that the passage names, and how that named company relates to the company holding the call, judging only from the passage.

Return only this block (the list may be empty):

---STRUCTURED---
{"links": [{"named_company": "", "relation": "", "quote": ""}]}
---END STRUCTURED---

- named_company: the company exactly as written in the passage.
- relation, from the CALLING company's point of view: "CUSTOMER" (the named company buys from the calling company), "SUPPLIER" (the named company sells to the calling company), "COMPETITOR", "PARTNER" (a collaboration, alliance, investment or joint work that is not a plain sale), or "OTHER" (an analyst's firm, a name used only as an example or in a macro or market reference, a past employer, or anything that is not a business relation of the calling company).
- quote: ONE contiguous span of the passage that supports the relation, copied verbatim (do not join separate pieces with "..." and do not change any character), as short as possible.
Do not include the calling company itself. Never add a company that is not written in the passage, and never infer a relation the passage does not state."""


def nws(s):
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'").replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()


def quote_ok(q, text):
    """v2 verifier (Luis-approved amendment): whitespace and quote/dash characters normalised; a quote joined with '...' is accepted only if EVERY segment appears verbatim in order."""
    t = nws(text); q = nws(q or "")
    if not q: return False
    segs = [x.strip(" .") for x in re.split(r"\.\.\.|\u2026", q) if x.strip(" .")]
    pos = 0
    for sg in segs:
        i = t.find(sg, pos)
        if i < 0: return False
        pos = i + len(sg)
    return True


def name_of(w):
    tk = C.tickers_json()
    if w in tk: return tk[w]["title"].title()
    return {"FRC": "First Republic", "SUNW": "Sunworks", "NOVA": "Sunnova"}.get(w, w)


def units(kind):
    """List of dicts: id, system, user, text (for quote verification)."""
    out = []
    if kind == "F":
        for l in open(C.EV / "filing_paras.jsonl"):
            e = json.loads(l)
            for co in sorted({s["company"] for s in e["sources"]}):
                uid = f"F__{e['para_id']}__{co}"
                out.append({"id": uid, "text": e["text"], "system": SYSTEM_F, "user": f"Filer: {name_of(co)} ({co})\n\nPassage:\n{e['text']}"})
    else:
        for l in open(C.EV / "call_passages.jsonl"):
            e = json.loads(l)
            out.append({"id": f"C__{e['passage_id']}", "text": e["text"], "system": SYSTEM_C, "user": f"Company holding the call: {name_of(e['call'])} ({e['call']})\n\nPassage:\n{e['text']}"})
    return out


def est_cost(us, out_tok=140):
    tin = sum((len(u["system"]) + len(u["user"])) / 3.6 for u in us)
    return tin * P_IN / 1e6 + len(us) * out_tok * P_OUT / 1e6


def client(): return anthropic.Anthropic()


def cost_of(u): return (u.input_tokens * P_IN + u.output_tokens * P_OUT + (getattr(u, "cache_read_input_tokens", 0) or 0) * P_CR + (getattr(u, "cache_creation_input_tokens", 0) or 0) * P_CW) / 1e6


def spent(p): return sum(p.get("spend_by_batch", {}).values())


def submit(kind, key, us):
    from anthropic.types.messages.batch_create_params import Request
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    p = C.prog()
    if p.get(key): print(key, "already submitted", p[key]); return
    est = est_cost(us); total = spent({"spend_by_batch": {k: v for k, v in p.get("spend_by_batch", {}).items() if k != key}}) + est
    print(f"{key}: {len(us)} requests, est ${est:.2f}; committed after ${total:.2f} (cap $20)")
    if total > 20: raise SystemExit(f"BUDGET STOP: ${total:.2f} > $20. Stop and report.")
    reqs = [Request(custom_id=u["id"], params=MessageCreateParamsNonStreaming(model=MODEL, max_tokens=MAXTOK, system=[{"type": "text", "text": u["system"], "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": u["user"]}])) for u in us]
    b = client().messages.batches.create(requests=reqs)
    p = C.prog(); p[key] = b.id; p.setdefault("spend_by_batch", {})[key] = round(est, 2); p.setdefault("batches_n", {})[key] = len(us); C.save_prog(p); print("SUBMITTED", key, b.id, "-- COMMIT progress.json NOW")


def poll(kind, key, raw):
    p = C.prog(); bid = p.get(key); cl = client(); b = cl.messages.batches.retrieve(bid); print(bid, b.processing_status, b.request_counts)
    if b.processing_status != "ended": return False
    f = C.STATE / raw; have = {json.loads(l)["custom_id"] for l in open(f)} if f.exists() else set(); n = 0; cost = 0.0
    with open(f, "a") as o:
        for e in cl.messages.batches.results(bid):
            if e.custom_id in have: continue
            if e.result.type == "succeeded":
                m = e.result.message; c = cost_of(m.usage); cost += c
                o.write(json.dumps({"custom_id": e.custom_id, "content": "".join(x.text for x in m.content if x.type == "text"), "stop": m.stop_reason, "in": m.usage.input_tokens, "out": m.usage.output_tokens, "cost": round(c, 6)}) + "\n"); n += 1
            else: o.write(json.dumps({"custom_id": e.custom_id, "error": e.result.type}) + "\n"); n += 1
    p = C.prog(); p.setdefault("spend_actual_by_batch", {})[key] = round(sum(json.loads(l).get("cost", 0) for l in open(f)), 4); C.save_prog(p)
    print("collected", n, "actual so far", p["spend_actual_by_batch"][key]); return True


LABELS = {"CUSTOMER", "SUPPLIER", "COMPETITOR", "PARTNER", "OTHER"}


def parse(content):
    m = re.search(r"---STRUCTURED---\s*(\{.*\})\s*---END STRUCTURED---", content, re.S)
    if not m: return None
    try: d = json.loads(m.group(1))
    except json.JSONDecodeError: return None
    return d.get("links") if isinstance(d, dict) and isinstance(d.get("links"), list) else None


def report(kind, raw, sel_ids=None):
    us = {u["id"]: u for u in units(kind)}
    rows = [json.loads(l) for l in open(C.STATE / raw)]
    bad_parse = trunc = links = qfail = 0; lab = {}
    for r in rows:
        if sel_ids is not None and r["custom_id"] not in sel_ids: continue
        if "error" in r: bad_parse += 1; continue
        if r["stop"] == "max_tokens": trunc += 1
        L = parse(r["content"])
        if L is None: bad_parse += 1; continue
        for x in L:
            links += 1; lab[x.get("relation")] = lab.get(x.get("relation"), 0) + 1
            if not quote_ok(x.get("quote"), us[r["custom_id"]]["text"]): qfail += 1
    n = len([1 for r in rows if sel_ids is None or r["custom_id"] in sel_ids])
    top = max(lab.values()) / max(links, 1) if lab else 0
    rep = {"requests": n, "unparseable_or_error": bad_parse, "max_tokens": trunc, "links": links, "quote_fail": qfail, "quote_fail_pct": round(100 * qfail / max(links, 1), 1),
           "label_counts": lab, "top_label_share_pct": round(100 * top, 1), "cost": round(sum(r.get("cost", 0) for r in rows if sel_ids is None or r["custom_id"] in sel_ids), 4)}
    rep["STOP"] = bool(bad_parse or rep["quote_fail_pct"] > 10 or top > 0.8)
    return rep


def main():
    cmd, kind = sys.argv[1], sys.argv[2]; us = units(kind)
    pre = C.STATE / f"preflight2_{kind}.json"
    if cmd == "prep":
        print(kind, len(us), "requests; est cost $%.2f" % est_cost(us)); return
    if cmd == "preflight-submit":
        rng = random.Random(f"p5p1-preflight2-{kind}-11"); sel = rng.sample(us, 40); pre.write_text(json.dumps([u["id"] for u in sel])); submit(kind, f"batch_{kind}_preflight2", sel)
    elif cmd == "preflight-poll": poll(kind, f"batch_{kind}_preflight2", f"raw_{kind}_preflight2.jsonl")
    elif cmd == "preflight-report":
        ids = set(json.loads(pre.read_text())); rep = report(kind, f"raw_{kind}_preflight2.jsonl", ids); (C.STATE / f"preflight2_report_{kind}.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))
    elif cmd == "submit-rest":
        ids = set(json.loads(pre.read_text())); submit(kind, f"batch_{kind}_full", [u for u in us if u["id"] not in ids])
    elif cmd == "poll": poll(kind, f"batch_{kind}_full", f"raw_{kind}_full.jsonl")


if __name__ == "__main__":
    main()
