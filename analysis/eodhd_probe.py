#!/usr/bin/env python3
"""
eodhd_probe.py -- prompts/eodhd-coverage-probe.md (run eodhd-coverage-probe)

Probes the EODHD free tier: (1) do its prices agree with scorer_price_cache_v1.json on companies believed correct;
(2) is consensus (`estimate`) populated in the earnings calendar for our universe.

HARD CALL BUDGET: 300 calls. The counter is incremented and persisted BEFORE every network call; cached responses in
raw/ cost nothing. The API token is read from the environment only. It is never printed, never written to raw/, and
never appears in any logged URL or exception text.

  python3 eodhd_probe.py user              # account/usage (counts as a call)
  python3 eodhd_probe.py get <path> k=v .. # generic cached GET, e.g. get eod/MSFT.US from=2020-01-01
  python3 eodhd_probe.py step1             # price validation (7 calls)
  python3 eodhd_probe.py analyze1          # compare vendor prices to our cache (no calls)
"""
import os, sys, json, hashlib, re, time
import urllib.request, urllib.parse, urllib.error
from pathlib import Path
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
RUN = REPO / "analysis/data/run_state/eodhd-coverage-probe"
RAW = RUN / "raw"
PROGRESS = RUN / "progress.json"
FINDINGS = RUN / "findings.md"
BASE = "https://eodhd.com/api/"
CAP = 300


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


class Blocked(SystemExit):
    pass


def cache_name(path, params):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", path.strip("/"))
    h = hashlib.sha1(json.dumps(sorted(params.items())).encode()).hexdigest()[:10]
    return RAW / f"{slug}__{h}.json"


def get(path, params=None, note=""):
    """Cached GET. Returns (status, parsed_or_text, from_cache). Never exposes the token."""
    params = {k: v for k, v in (params or {}).items() if k != "api_token"}
    fp = cache_name(path, params)
    if fp.exists():
        rec = json.loads(fp.read_text())
        return rec["status"], rec["body"], True
    token = os.environ.get("EODHD_API_TOKEN")
    if not token:
        raise SystemExit("EODHD_API_TOKEN not in environment")
    p = progress()
    if p["calls_used"] >= CAP:
        raise SystemExit(f"CALL CAP {CAP} reached -- stopping. next_action: {p.get('next_action')}")
    p["calls_used"] += 1          # count BEFORE the call
    p.setdefault("call_log", []).append({"n": p["calls_used"], "path": path, "params": params, "note": note, "at": now()})
    save(p)
    q = urllib.parse.urlencode({**params, "api_token": token})
    req = urllib.request.Request(BASE + path + "?" + q, headers={"User-Agent": "investment-agent-probe"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status, text = r.status, r.read().decode("utf-8", errors="replace")
            hdr = {k.lower(): v for k, v in r.headers.items() if k.lower().startswith(("x-ratelimit", "x-api", "content-type"))}
    except urllib.error.HTTPError as e:
        status, text, hdr = e.code, e.read().decode("utf-8", errors="replace"), {}
    except Exception as e:  # never echo the exception (may contain the URL)
        raise SystemExit(f"network error on {path}: {type(e).__name__}")
    if token in text:
        text = text.replace(token, "<redacted>")
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        body = text
    RAW.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps({"path": path, "params": params, "status": status, "headers": hdr, "fetched_at": now(), "body": body}))
    if status in (401, 403, 429):
        finding(f"HTTP {status} on {path} -- stopping per prompt. Body: {str(body)[:200]}")
        raise Blocked(f"HTTP {status} on {path}: {str(body)[:200]}  (calls used {p['calls_used']}) -- STOP AND REPORT")
    return status, body, False


def cmd_user():
    st, body, cached = get("user", {"fmt": "json"}, "account/usage")
    print(st, "cached" if cached else "live", json.dumps(body)[:600])


def cmd_get(path, *kv):
    params = dict(x.split("=", 1) for x in kv)
    params.setdefault("fmt", "json")
    st, body, cached = get(path, params)
    n = len(body) if isinstance(body, list) else "obj"
    print(st, "cached" if cached else "live", "items:", n)
    print(json.dumps(body, indent=1)[:1500])


STEP1 = ["MSFT", "INTC", "DUK", "ENPH", "EOSE", "JKS"]


def cmd_step1():
    for t in STEP1 + ["PARA"]:
        st, body, cached = get(f"eod/{t}.US", {"from": "2020-01-01", "to": "2026-09-14", "period": "d", "fmt": "json"}, "step1 prices")
        n = len(body) if isinstance(body, list) else 0
        first = body[0]["date"] if n else None
        last = body[-1]["date"] if n else None
        print(f"{t}: status {st} rows {n} first {first} last {last} {'(cached)' if cached else ''}  calls_used={progress()['calls_used']}")
        if st != 200:
            print("   body:", str(body)[:200])


def cmd_analyze1():
    cache = json.loads((REPO / "analysis/data/corpus_v2/scorer_price_cache_v1.json").read_text())
    out = {}
    for t in STEP1 + ["PARA"]:
        fp = cache_name(f"eod/{t}.US", {"from": "2020-01-01", "to": "2026-09-14", "period": "d", "fmt": "json"})
        if not fp.exists():
            continue
        body = json.loads(fp.read_text())["body"]
        if not isinstance(body, list) or not body:
            print(t, "no vendor rows:", str(body)[:120]); continue
        ours = cache.get(t, {})
        vend = {r["date"]: r for r in body}
        shared = sorted(set(vend) & set(ours))
        res = {"vendor_rows": len(body), "vendor_first": body[0]["date"], "vendor_last": body[-1]["date"], "our_rows": len(ours), "shared_dates": len(shared)}
        for fld in ("close", "adjusted_close"):
            diffs = []
            for d in shared:
                v = vend[d].get(fld)
                o = ours[d]
                if v and o:
                    diffs.append((abs(v / o - 1), d, v, o))
            if diffs:
                within = sum(1 for x in diffs if x[0] <= 0.01)
                worst = max(diffs)
                res[fld] = {"within_1pct": within, "of": len(diffs), "share_pct": round(100 * within / len(diffs), 2),
                            "worst_pct": round(100 * worst[0], 2), "worst_date": worst[1], "worst_vendor": worst[2], "worst_ours": worst[3]}
        out[t] = res
        print(t, json.dumps(res))
    (RUN / "step1_price_comparison.json").write_text(json.dumps(out, indent=1))


# ---------------------------------------------------------------- step 2: earnings calendar
def universe():
    """{probe_symbol: {"original": orig, "stratum": S?, "split": train|tune}} -- train + tune, PARA/VIAC, WOLF, SPWR excluded.
    For aliased companies BOTH the original and the working symbol are probed (same batch, no extra calls)."""
    sys.path.insert(0, str(REPO / "analysis"))
    import r4_horizon_driver as r4
    sp = json.loads(r4.SPLIT.read_text())
    a = r4.alias_map()
    strat = {}
    for st, d in sp["per_stratum"].items():
        for split in ("train", "tune"):
            for t in d[split]:
                strat[t] = (st, split)
    skip = {"PARA", "VIAC", "WOLF", "SPWR"}
    out = {}
    for t, (st, split) in strat.items():
        if t in skip:
            continue
        for sym in {t, a.get(t, t)} - skip:
            out[sym] = {"original": t, "stratum": st, "split": split, "aliased": sym != t or a.get(t, t) != t}
    return out


def cmd_calendar(batch="12", frm="2020-01-01", to="2026-01-01"):
    u = universe()
    syms = sorted(u)
    n = int(batch)
    batches = [syms[i:i + n] for i in range(0, len(syms), n)]
    print(f"{len(syms)} probe symbols -> {len(batches)} batches of <= {n}")
    for b in batches:
        st, body, cached = get("calendar/earnings", {"symbols": ",".join(x + ".US" for x in b), "from": frm, "to": to, "fmt": "json"}, f"calendar batch {b[0]}..{b[-1]}")
        ev = body.get("earnings") if isinstance(body, dict) else None
        print(f"{b[0]}..{b[-1]} status {st} {'cached' if cached else 'live'} events {len(ev) if ev is not None else 'n/a'} calls_used={progress()['calls_used']}")
        if st != 200:
            print("   body:", str(body)[:200])
            break


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    {"user": cmd_user, "get": cmd_get, "step1": cmd_step1, "analyze1": cmd_analyze1, "calendar": cmd_calendar}.get(c, lambda *a: print(__doc__))(*sys.argv[2:])
