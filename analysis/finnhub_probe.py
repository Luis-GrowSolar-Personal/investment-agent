#!/usr/bin/env python3
"""
finnhub_probe.py -- prompts/finnhub-coverage-probe.md (run finnhub-coverage-probe)

Probes what a FREE Finnhub key reaches: which endpoints, how deep the history, how well the consensus `estimate`
field is populated across our corpus companies. It does NOT test the consensus-surprise hypothesis (the free window holds
about six bearish calls) and scores nothing.

Rate limit ~60 calls/minute: every live call is spaced >= 1.2 s. Hard stop at 600 calls. The key is read from the
environment, sent ONLY in the X-Finnhub-Token header (never in a URL), and never written to raw/ or any log.
Every raw response is cached under raw/; a cached call costs nothing and is never re-requested.

  python3 finnhub_probe.py get <path> k=v ..      # generic cached GET
  python3 finnhub_probe.py step1                  # six endpoints for MSFT (+ calendar/earnings as an extra probe)
  python3 finnhub_probe.py step2                  # /stock/earnings for every train+tune company
"""
import os, sys, json, hashlib, re, time
import urllib.request, urllib.parse, urllib.error
from pathlib import Path
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
RUN = REPO / "analysis/data/run_state/finnhub-coverage-probe"
RAW, PROGRESS, FINDINGS = RUN / "raw", RUN / "progress.json", RUN / "findings.md"
BASE = "https://finnhub.io/api/v1/"
CAP, SPACING = 600, 1.2
_last = [0.0]


def now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def progress():
    return json.loads(PROGRESS.read_text())


def save(p):
    PROGRESS.write_text(json.dumps(p, indent=2))


def finding(t):
    with FINDINGS.open("a") as f:
        f.write(f"\n- {now()}: {t}\n")


def cache_name(path, params):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", path.strip("/"))
    sym = params.get("symbol", "")
    h = hashlib.sha1(json.dumps(sorted(params.items())).encode()).hexdigest()[:8]
    return RAW / f"{slug}__{sym}__{h}.json"


class NetworkBlocked(SystemExit):
    pass


def get(path, params=None, note=""):
    """Cached GET -> (status, parsed_body, from_cache). Never exposes the key. Retries a 429 once after a pause."""
    params = {k: v for k, v in (params or {}).items() if k != "token"}
    fp = cache_name(path, params)
    if fp.exists():
        r = json.loads(fp.read_text())
        return r["status"], r["body"], True
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        raise SystemExit("FINNHUB_API_KEY not in environment")
    for attempt in (1, 2):
        p = progress()
        if p["calls_used"] >= CAP:
            raise SystemExit(f"CALL CAP {CAP} reached -- stop and report")
        wait = SPACING - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        p["calls_used"] += 1  # counted BEFORE the call
        p.setdefault("call_log", []).append({"n": p["calls_used"], "path": path, "params": params, "note": note, "at": now()})
        save(p)
        req = urllib.request.Request(BASE + path + "?" + urllib.parse.urlencode(params),
                                     headers={"X-Finnhub-Token": key, "User-Agent": "investment-agent-probe"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                status, text = r.status, r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            status, text = e.code, e.read().decode("utf-8", errors="replace")
        except Exception as e:  # never echo the exception (could contain request details)
            raise NetworkBlocked(f"network error on {path}: {type(e).__name__} -- if a connection refusal, STOP AND REPORT")
        _last[0] = time.time()
        if status == 429 and attempt == 1:
            time.sleep(65)
            continue
        break
    text = text.replace(key, "<redacted>")
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        body = text
    RAW.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps({"path": path, "params": params, "status": status, "fetched_at": now(), "body": body}))
    return status, body, False


def kind(status, body):
    if status == 200 and isinstance(body, (list, dict)) and body:
        empty = (isinstance(body, dict) and not any(v for v in body.values() if v not in (None, "", [], {}, 0)))
        return "populated" if not empty else "empty"
    if status == 200:
        return "empty"
    return f"HTTP {status}: {str(body)[:90]}"


def cmd_get(path, *kv):
    st, body, cached = get(path, dict(x.split("=", 1) for x in kv))
    print(st, "cached" if cached else "live", kind(st, body)); print(json.dumps(body, indent=1)[:1200])


def cmd_step1():
    rows = [("stock/earnings (limit=100)", "stock/earnings", {"symbol": "MSFT", "limit": "100"}),
            ("stock/earnings (default)", "stock/earnings", {"symbol": "MSFT"}),
            ("stock/eps-estimate", "stock/eps-estimate", {"symbol": "MSFT", "freq": "quarterly"}),
            ("stock/revenue-estimate", "stock/revenue-estimate", {"symbol": "MSFT", "freq": "quarterly"}),
            ("stock/recommendation", "stock/recommendation", {"symbol": "MSFT"}),
            ("stock/price-target", "stock/price-target", {"symbol": "MSFT"}),
            ("stock/metric", "stock/metric", {"symbol": "MSFT", "metric": "all"}),
            ("calendar/earnings (EXTRA, not in prompt)", "calendar/earnings", {"symbol": "MSFT", "from": "2020-01-01", "to": "2026-01-01"})]
    out = []
    for label, path, prm in rows:
        st, body, cached = get(path, prm, "step1")
        n = len(body) if isinstance(body, list) else (len(body.get("earningsCalendar", [])) if isinstance(body, dict) and "earningsCalendar" in body else (len(body.get("data", [])) if isinstance(body, dict) and isinstance(body.get("data"), list) else "-"))
        out.append({"endpoint": label, "status": st, "kind": kind(st, body), "items": n})
        print(f"{label:42} {st} {kind(st, body):30} items={n} calls_used={progress()['calls_used']}")
    (RUN / "step1_endpoints.json").write_text(json.dumps(out, indent=1))


def universe():
    sys.path.insert(0, str(REPO / "analysis"))
    import r4_horizon_driver as r4
    sp = json.loads(r4.SPLIT.read_text())
    a = r4.alias_map()
    skip = {"PARA", "VIAC", "WOLF", "SPWR"}
    out = {}
    for st, d in sp["per_stratum"].items():
        for split in ("train", "tune"):
            for t in d[split]:
                if t in skip:
                    continue
                for sym in {t, a.get(t, t)} - skip:
                    out[sym] = {"original": t, "stratum": st, "split": split}
    return out


def cmd_step2():
    u = universe()
    print(f"{len(u)} probe symbols")
    for i, sym in enumerate(sorted(u), 1):
        st, body, cached = get("stock/earnings", {"symbol": sym, "limit": "100"}, "step2")
        n = len(body) if isinstance(body, list) else 0
        print(f"{i:3}/{len(u)} {sym:6} {st} items={n} {'cached' if cached else 'live'} calls={progress()['calls_used']}")
        if st == 429:
            print("   rate limited; sleeping 65s"); time.sleep(65)


def cmd_analyze():
    import datetime
    from collections import defaultdict
    u = universe()
    per = {}
    for sym, meta in u.items():
        st, body, _ = get("stock/earnings", {"symbol": sym, "limit": "100"}, "analyze (cached)")
        rows = body if isinstance(body, list) else []
        per[sym] = {"meta": meta, "status": st, "n": len(rows),
                    "est": sum(1 for r in rows if r.get("estimate") is not None), "act": sum(1 for r in rows if r.get("actual") is not None),
                    "sur": sum(1 for r in rows if r.get("surprise") is not None or r.get("surprisePercent") is not None),
                    "first": min((r["period"] for r in rows), default=None), "last": max((r["period"] for r in rows), default=None),
                    "rows": rows}
    # one row per company: the probe symbol (original or working) with the most quarters
    comp = {}
    for sym, d in per.items():
        o = d["meta"]["original"]
        if o not in comp or d["n"] > comp[o]["n"]:
            comp[o] = {**d, "symbol": sym}
    out = {"per_symbol": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in per.items()},
           "per_company": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in comp.items()}}
    tot = lambda cs: (sum(c["n"] for c in cs), sum(c["est"] for c in cs), sum(c["act"] for c in cs), sum(c["sur"] for c in cs))
    allc = list(comp.values())
    n, e, a, su = tot(allc)
    print(f"companies {len(allc)}; with zero quarters returned: {sorted(k for k,v in comp.items() if v['n']==0)}")
    print(f"quarters {n}; estimate populated {e} ({100*e/n:.1f}%); actual {a} ({100*a/n:.1f}%); surprise {su} ({100*su/n:.1f}%)")
    print("quarters per company:", dict(sorted({k: v['n'] for k, v in comp.items()}.items(), key=lambda kv: kv[1])[:0]), "distribution:", {q: sum(1 for v in allc if v['n'] == q) for q in range(0, 6)})
    print("period range across companies:", min(v['first'] for v in allc if v['first']), "to", max(v['last'] for v in allc if v['last']))
    by = defaultdict(list)
    for k, v in comp.items():
        by[v["meta"]["stratum"]].append(v)
    print("by stratum (companies, with any quarters, quarters, est populated):")
    strat = {}
    for st in sorted(by):
        cs = by[st]
        n_, e_, a_, s_ = tot(cs)
        strat[st] = {"companies": len(cs), "covered": sum(1 for c in cs if c["n"] > 0), "quarters": n_, "estimate": e_, "share_pct": round(100 * e_ / n_, 1) if n_ else None}
        print(f"  {st}: {len(cs)} companies, {strat[st]['covered']} with data, {n_} quarters, estimate populated {e_} ({strat[st]['share_pct']}%)")
    out["by_stratum"] = strat
    print("call-outs:")
    for t in ["INTC", "VZ", "KHC", "SBUX", "UPS", "SEDG", "EOSE", "ENVX", "BLDP", "AMPX", "QS", "SUNW"]:
        c = comp.get(t)
        if c:
            print(f"  {t:5} via {c['symbol']:5} stratum {c['meta']['stratum']} quarters {c['n']} est {c['est']} act {c['act']} sur {c['sur']} periods {c['first']}..{c['last']}")
        else:
            print(f"  {t}: not in universe")
    # alias preference
    for pair in (("ANTM", "ELV"), ("GOOGL", "GOOG"), ("BK", "BNY"), ("MAXN", "MAXNQ")):
        print("alias", pair, {x: per[x]["n"] if x in per else "not probed" for x in pair})
    # internal consistency: surprise == actual - estimate
    bad = tot_ = 0
    for d in per.values():
        for r in d["rows"]:
            if all(r.get(k) is not None for k in ("estimate", "actual", "surprise")):
                tot_ += 1
                if abs((r["actual"] - r["estimate"]) - r["surprise"]) > 0.011:
                    bad += 1
    print(f"surprise == actual - estimate on {tot_ - bad} of {tot_} rows")
    out["surprise_consistency"] = {"rows": tot_, "inconsistent": bad}
    # date alignment: corpus calls whose date falls inside/after the Finnhub window
    sys.path.insert(0, str(REPO / "analysis"))
    import glob
    trs = REPO / "analysis/data/corpus_v2/transcripts"
    al = []
    for o, c in comp.items():
        if not c["n"]:
            continue
        for f in glob.glob(str(trs / c["symbol"] / "*.json")) + (glob.glob(str(trs / o / "*.json")) if o != c["symbol"] else []):
            t = json.loads(Path(f).read_text())
            cd = datetime.date.fromisoformat(Path(f).stem)
            if cd < datetime.date(2025, 9, 20):
                continue
            best = None
            for r in c["rows"]:
                pe = datetime.date.fromisoformat(r["period"])
                lag = (cd - pe).days
                if 0 <= lag <= 120 and (best is None or lag < best[0]):
                    best = (lag, r)
            al.append({"ticker": o, "call_date": cd.isoformat(), "our_label": [t.get("year"), t.get("quarter")],
                       "lag_days": best[0] if best else None, "their_label": [best[1]["year"], best[1]["quarter"]] if best else None,
                       "period": best[1]["period"] if best else None})
    matched = [x for x in al if x["lag_days"] is not None]
    lab = [x for x in matched if x["our_label"] == x["their_label"]]
    inw = [x for x in matched if 10 <= x["lag_days"] <= 75]
    print(f"overlapping corpus calls (on/after 2025-09-20, train+tune): {len(al)}; matched to a Finnhub quarter ending 0-120 days earlier: {len(matched)}; "
          f"lag 10-75 days: {len(inw)}; fiscal (year, quarter) labels identical: {len(lab)} of {len(matched)}")
    if matched:
        import statistics
        print("   lag days (call date minus period end): median", statistics.median(x["lag_days"] for x in matched), "range", min(x["lag_days"] for x in matched), max(x["lag_days"] for x in matched))
    mism = [x for x in matched if x["our_label"] != x["their_label"]][:8]
    print("   label mismatches sample:", mism)
    out["alignment"] = {"overlap_calls": len(al), "matched": len(matched), "lag_10_75": len(inw), "labels_identical": len(lab), "sample_mismatch": mism, "rows": al}
    (RUN / "step2_coverage.json").write_text(json.dumps(out, indent=1))
    # point-in-time stability: re-fetch MSFT under a different parameter (live) and compare with the first fetch
    st, b2, cached = get("stock/earnings", {"symbol": "MSFT", "limit": "4"}, "stability re-fetch")
    st0, b0, _ = get("stock/earnings", {"symbol": "MSFT", "limit": "100"}, "")
    same = isinstance(b2, list) and [(r["period"], r["estimate"], r["actual"]) for r in b2] == [(r["period"], r["estimate"], r["actual"]) for r in b0]
    print("stability re-fetch (MSFT, later in run, live=%s): identical to first fetch: %s" % (not cached, same))
    out["stability_refetch_identical"] = same
    (RUN / "step2_coverage.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    {"get": cmd_get, "step1": cmd_step1, "step2": cmd_step2, "analyze": cmd_analyze}.get(c, lambda *a: print(__doc__))(*sys.argv[2:])
