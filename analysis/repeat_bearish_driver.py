#!/usr/bin/env python3
"""
repeat_bearish_driver.py -- prompts/repeat-the-bearish-call.md (run repeat-the-bearish-call)

Re-scores v6's bearish calls (PARA/WOLF/SPWR excluded) twice more with the UNCHANGED promoted v6 prompt, same pinned model,
same request shape as the baseline batches. Each call then has three readings (cached original + r1 + r2).
Money outcomes: 182-day benchmark-relative return from the close of the first trading day strictly after the call.

  python3 repeat_bearish_driver.py list      # derive list, estimate cost
  python3 repeat_bearish_driver.py pilot     # 2 synchronous calls (they become r1 for those calls)
  python3 repeat_bearish_driver.py submit    # one batch, 2 requests per call (skips ids already scored)
  python3 repeat_bearish_driver.py poll      # collect
  python3 repeat_bearish_driver.py groups    # 3-of-3 / 2-of-3 / 1-of-3 split + sanity gate (NO outcomes)
  python3 repeat_bearish_driver.py analyze   # money + accuracy tables, concentration (needs the sanity gate to pass)
"""
import sys, json, re, datetime
from datetime import timedelta
from pathlib import Path
from collections import defaultdict
import numpy as np
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO))
import r4_horizon_driver as r4  # noqa
from analyst_direct_scorer import PriceCache, parse_structured, direction_from_score  # noqa

RUN = REPO / "analysis/data/run_state/repeat-the-bearish-call"
PROGRESS, SCORES, FINDINGS = RUN / "progress.json", RUN / "scores.jsonl", RUN / "findings.md"
TR = REPO / "analysis/data/corpus_v2/transcripts"
V6 = REPO / "docs/EVALUATION_PROMPT.md"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
SPEND_CAP, REQ_CAP = 20.0, 400
P_IN, P_OUT, P_CR, P_CW = 3.0, 15.0, 0.30, 3.75
SEED, B, HORIZON, TAIL, ACC = 11, 2000, 182, -0.25, -0.05
EXCL = {"PARA", "WOLF", "SPWR"}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prog():
    return json.loads(PROGRESS.read_text())


def save(p):
    PROGRESS.write_text(json.dumps(p, indent=2))


def finding(t):
    with FINDINGS.open("a") as f:
        f.write(f"\n- {now()}: {t}\n")


def cost(u, batch):
    c = (u["input_tokens"] * P_IN + u["output_tokens"] * P_OUT + u.get("cache_read_input_tokens", 0) * P_CR
         + u.get("cache_creation_input_tokens", 0) * P_CW) / 1e6
    return c * (0.5 if batch else 1.0)


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()] if Path(p).exists() else []


def bearish_list():
    out = []
    for sp in ("train", "tune"):
        for tk, d, p in r4.load_calls(sp):
            if p == "bearish" and tk not in EXCL:
                out.append({"split": sp, "ticker": tk, "date": d.isoformat()})
    return out


def cid(c, r):
    x = f"{c['ticker']}_{c['date']}_{r}"
    assert re.match(r"^[a-zA-Z0-9_-]{1,64}$", x), x
    return x


def transcript(c):
    return json.loads((TR / c["ticker"] / f"{c['date']}.json").read_text())["text"]


def guard():
    from analysis.version_guard import assert_prompt_hash
    g = assert_prompt_hash(V6.read_text())  # promoted v6, no candidate
    assert g["ok"] and g["candidate_used"] is None, g
    return g


def cmd_list():
    L = bearish_list()
    est_in = sum(len(transcript(c)) for c in L) / 4.0 + 2500  # rough tokens
    per_call = (sum(len(transcript(c)) for c in L) / len(L) / 4.0 + 2500) * 1.5 / 1e6 + 2000 * 7.5 / 1e6
    print(f"bearish calls {len(L)} (train {sum(c['split']=='train' for c in L)}, tune {sum(c['split']=='tune' for c in L)}) "
          f"companies {len({c['ticker'] for c in L})}; requests {2*len(L)}; est batch cost ${2*len(L)*per_call:.2f} "
          f"(measured baseline $0.0380/call -> ${2*len(L)*0.038:.2f}); cap ${SPEND_CAP}")
    print("guard:", guard())


def client():
    import anthropic
    return anthropic.Anthropic()


def sysmsg():
    return [{"type": "text", "text": V6.read_text(), "cache_control": {"type": "ephemeral"}}]


def cmd_pilot():
    guard()
    L = bearish_list()[:2]
    cl = client()
    have = {r["custom_id"] for r in jl(SCORES)}
    for c in L:
        i = cid(c, "r1")
        if i in have:
            continue
        m = cl.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=sysmsg(), messages=[{"role": "user", "content": transcript(c)}])
        u = m.usage
        usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                 "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                 "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0}
        content = "".join(b.text for b in m.content if b.type == "text")
        sc = parse_structured(content)
        rec = {"custom_id": i, "ticker": c["ticker"], "date": c["date"], "run": "r1", "content": content, "usage": usage,
               "stop_reason": m.stop_reason, "cost_usd": round(cost(usage, False), 5), "source": "pilot_sync", "model": m.model,
               "direction": direction_from_score(sc), "fetched_at": now()}
        with SCORES.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(i, "dir", rec["direction"], "stop", m.stop_reason, "cost(sync)", rec["cost_usd"], "model", m.model)


def cmd_submit():
    from anthropic.types.messages.batch_create_params import Request
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    p = prog()
    if p.get("batch_id"):
        print("batch already submitted:", p["batch_id"]); return
    guard()
    L = bearish_list()
    have = {r["custom_id"] for r in jl(SCORES)}
    reqs = []
    sm = sysmsg()
    for c in L:
        for r in ("r1", "r2"):
            if cid(c, r) in have:
                continue
            reqs.append(Request(custom_id=cid(c, r), params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=MAX_TOKENS, system=sm, messages=[{"role": "user", "content": transcript(c)}])))
    per_call = 0.038 * 1.15  # measured baseline batch cost per call with 15% margin
    est = len(reqs) * per_call
    print(f"requests {len(reqs)} (cap {REQ_CAP}); projected batch cost ${est:.2f} (cap ${SPEND_CAP})")
    if len(reqs) > REQ_CAP or est > SPEND_CAP:
        raise SystemExit("OVER CAP -- stop and report, submit nothing")
    b = client().messages.batches.create(requests=reqs)
    p["batch_id"], p["batch_submitted_at"], p["batch_requests"] = b.id, now(), len(reqs)
    save(p)
    print("SUBMITTED", b.id, "-- COMMIT progress.json NOW")


def cmd_poll():
    p = prog()
    cl = client()
    b = cl.messages.batches.retrieve(p["batch_id"])
    print(p["batch_id"], b.processing_status, b.request_counts)
    if b.processing_status != "ended":
        return
    have = {r["custom_id"] for r in jl(SCORES)}
    n = e = 0
    for x in cl.messages.batches.results(p["batch_id"]):
        if x.custom_id in have:
            continue
        if x.result.type != "succeeded":
            finding(f"{x.custom_id}: {x.result.type}")
            e += 1
            continue
        m = x.result.message
        u = m.usage
        usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                 "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                 "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0}
        content = "".join(b_.text for b_ in m.content if b_.type == "text")
        tk, dt, run = x.custom_id.rsplit("_", 2)
        rec = {"custom_id": x.custom_id, "ticker": tk, "date": dt, "run": run, "content": content, "usage": usage,
               "stop_reason": m.stop_reason, "cost_usd": round(cost(usage, True), 5), "source": "batch", "model": m.model,
               "direction": direction_from_score(parse_structured(content)), "batch_id": p["batch_id"], "fetched_at": now()}
        with SCORES.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        n += 1
    print("collected", n, "errored/other", e)


def readings():
    """{(ticker,date): [dir_r1, dir_r2]} from scores.jsonl (max_tokens truncations and unparsable directions flagged)."""
    out = defaultdict(dict)
    for r in jl(SCORES):
        out[(r["ticker"], r["date"])][r["run"]] = r
    return out


def groups():
    L = bearish_list()
    rd = readings()
    res, bad = [], []
    for c in L:
        r = rd.get((c["ticker"], c["date"]), {})
        if "r1" not in r or "r2" not in r:
            bad.append((c["ticker"], c["date"], "missing")); continue
        dirs = [r["r1"]["direction"], r["r2"]["direction"]]
        if None in dirs or r["r1"]["stop_reason"] == "max_tokens" or r["r2"]["stop_reason"] == "max_tokens":
            bad.append((c["ticker"], c["date"], "unparsable_or_truncated")); continue
        k = 1 + sum(1 for d in dirs if d == "bearish")
        res.append({**c, "k": k, "dirs": dirs})
    return res, bad


def cmd_groups():
    g, bad = groups()
    n = len(g)
    cnt = {k: sum(1 for x in g if x["k"] == k) for k in (3, 2, 1)}
    rerun_bear = sum(1 for x in g for d in x["dirs"] if d == "bearish") / (2 * max(n, 1))
    print(f"readable calls {n} of {len(bearish_list())}; unreadable {len(bad)} {bad[:5]}")
    print("groups:", cnt, {k: f"{100*v/max(n,1):.1f}%" for k, v in cnt.items()}, f"| share of re-runs that came back bearish {100*rerun_bear:.1f}%")
    dist = defaultdict(int)
    for x in g:
        for d in x["dirs"]:
            dist[d] += 1
    print("re-run direction mix:", dict(dist))
    ok = 0.5 <= cnt[3] / max(n, 1) <= 0.95
    print("SANITY GATE (3-of-3 share between 50% and 95%):", "PASS" if ok else "FAIL -- stop and check driver before computing outcomes")
    tot = sum(r["cost_usd"] for r in jl(SCORES))
    print(f"spend so far ${tot:.2f}; stop reasons:", dict(defaultdict(int, {k: sum(1 for r in jl(SCORES) if r['stop_reason'] == k) for k in {r['stop_reason'] for r in jl(SCORES)}})))
    (RUN / "groups.json").write_text(json.dumps({"n": n, "counts": cnt, "unreadable": bad, "gate_pass": ok, "spend_usd": round(tot, 2)}, indent=1))
    return ok


def outcome_rows():
    prices = PriceCache(r4.PRICE_CACHE)
    g, _ = groups()
    rows = []
    for x in g:
        d = datetime.date.fromisoformat(x["date"])
        pe, _ = prices.price_on_or_after(x["ticker"], d + timedelta(days=1))
        be, _ = prices.price_on_or_after(r4.BENCH, d + timedelta(days=1))
        p1, _ = prices.price_on_or_after(x["ticker"], d + timedelta(days=HORIZON))
        b1, _ = prices.price_on_or_after(r4.BENCH, d + timedelta(days=HORIZON))
        if all([pe, be, p1, b1]):
            rows.append({**x, "ret": (p1 / pe - 1) - (b1 / be - 1)})
    return rows


def gstats(rs):
    if not rs:
        return None
    r = np.array([x["ret"] for x in rs])
    k = max(1, len(r) // 4)
    return {"n": len(r), "companies": len({x["ticker"] for x in rs}),
            "tail": float((r < TAIL).mean()), "tail_n": int((r < TAIL).sum()),
            "acc": float((r < ACC).mean()), "acc_n": int((r < ACC).sum()),
            "worst_q": float(np.sort(r)[:k].mean()), "median": float(np.median(r)), "mean": float(r.mean()), "worst": float(r.min()),
            "sell_saves": float(-r.mean())}


def boot(rows, sel_a, sel_b=None, seed=SEED):
    """ticker-block bootstrap ranges for stats of group a (and difference a-b)."""
    by = defaultdict(list)
    for x in rows:
        by[x["ticker"]].append(x)
    tks = sorted(by)
    rng = np.random.default_rng(seed)
    acc = defaultdict(list)
    for _ in range(B):
        samp = [x for i in rng.integers(0, len(tks), size=len(tks)) for x in by[tks[i]]]
        a = gstats([x for x in samp if sel_a(x)])
        b = gstats([x for x in samp if sel_b(x)]) if sel_b else None
        if a:
            for k in ("tail", "acc", "worst_q", "median", "mean", "sell_saves"):
                acc[k].append(a[k])
        if a and b:
            for k in ("tail", "acc", "worst_q", "median", "mean", "sell_saves"):
                acc["d_" + k].append(a[k] - b[k])
    q = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)] if v else None
    return {k: q(v) for k, v in acc.items()}


def cmd_analyze():
    if not cmd_groups():
        raise SystemExit("sanity gate failed")
    rows = outcome_rows()
    out = {}
    defs = {"3of3": lambda x: x["k"] == 3, "2of3": lambda x: x["k"] == 2, "1of3": lambda x: x["k"] == 1,
            "not3of3": lambda x: x["k"] < 3, "all": lambda x: True}
    for split in ("train", "tune", "pooled"):
        sub = rows if split == "pooled" else [x for x in rows if x["split"] == split]
        for name, sel in defs.items():
            g = gstats([x for x in sub if sel(x)])
            if g:
                g["ci"] = boot(sub, sel)
                out[f"{split}/{name}"] = g
        for a, b in (("3of3", "1of3"), ("3of3", "not3of3")):
            if gstats([x for x in sub if defs[a](x)]) and gstats([x for x in sub if defs[b](x)]):
                out[f"{split}/{a}-minus-{b}"] = {"ci": boot(sub, defs[a], defs[b])}
    with (RUN / "cells.jsonl").open("w") as f:
        for k, v in out.items():
            f.write(json.dumps({"cell": k, **v}) + "\n")
    for k, v in out.items():
        if "n" in v:
            print(f"{k:16} n={v['n']:3} cos={v['companies']:2} tail {v['tail_n']}/{v['n']} ({100*v['tail']:.1f}%) {v['ci'].get('tail')} | acc {v['acc_n']}/{v['n']} ({100*v['acc']:.1f}%) | "
                  f"worstQ {100*v['worst_q']:.1f}% | med {100*v['median']:.1f}% mean {100*v['mean']:.1f}% worst {100*v['worst']:.1f}% | sell saves {100*v['sell_saves']:+.1f}% {v['ci'].get('sell_saves')}")
        else:
            print(f"{k:32} diff ranges: tail {v['ci'].get('d_tail')} acc {v['ci'].get('d_acc')} worstQ {v['ci'].get('d_worst_q')} mean {v['ci'].get('d_mean')}")
    # concentration: drop each of the top contributors of tail calls in the 3-of-3 group, in turn
    t3 = defaultdict(int)
    for x in rows:
        if x["k"] == 3 and x["ret"] < TAIL:
            t3[x["ticker"]] += 1
    top = [t for t, _ in sorted(t3.items(), key=lambda kv: -kv[1])[:8]]
    conc = {}
    for label, sub in (("pooled", rows), ("train", [x for x in rows if x["split"] == "train"]), ("tune", [x for x in rows if x["split"] == "tune"])):
        base3, base1 = gstats([x for x in sub if x["k"] == 3]), gstats([x for x in sub if x["k"] == 1])
        conc[label] = {"full": {"tail_3of3": base3["tail"] if base3 else None, "tail_1of3": base1["tail"] if base1 else None}}
        for t in top:
            s2 = [x for x in sub if x["ticker"] != t]
            a, b = gstats([x for x in s2 if x["k"] == 3]), gstats([x for x in s2 if x["k"] == 1])
            conc[label][t] = {"tail_3of3": a["tail"] if a else None, "tail_1of3": b["tail"] if b else None, "n3": a["n"] if a else 0, "n1": b["n"] if b else 0}
    (RUN / "concentration.json").write_text(json.dumps({"top_contributors_of_3of3_tail": dict((t, t3[t]) for t in top), "results": conc}, indent=1))
    print("top tail contributors in 3-of-3:", [(t, t3[t]) for t in top])
    for label in conc:
        print(label, "full:", {k: (None if v is None else round(100 * v, 1)) for k, v in conc[label]["full"].items()})
        for t in top:
            v = conc[label][t]
            print(f"   drop {t:5}: tail 3of3 {None if v['tail_3of3'] is None else round(100*v['tail_3of3'],1)}% (n={v['n3']}) vs 1of3 {None if v['tail_1of3'] is None else round(100*v['tail_1of3'],1)}% (n={v['n1']})")
    (RUN / "outcome_rows.json").write_text(json.dumps(rows))


if __name__ == "__main__":
    {"list": cmd_list, "pilot": cmd_pilot, "submit": cmd_submit, "poll": cmd_poll, "groups": cmd_groups, "analyze": cmd_analyze}.get((sys.argv[1:] or [""])[0], lambda: print(__doc__))()
