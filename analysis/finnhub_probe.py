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


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    {"get": cmd_get, "step1": cmd_step1, "step2": cmd_step2}.get(c, lambda *a: print(__doc__))(*sys.argv[2:])
