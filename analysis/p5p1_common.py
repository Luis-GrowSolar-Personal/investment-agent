"""p5p1_common.py -- shared helpers for prompts/P5-phase1-peer-map.md (P5 phase 1). SEC etiquette: SEC_USER_AGENT from .env (never logged), 1 request/second,
request counter in run_state/p5-phase1/progress.json (cap 1,600). Vendor: EarningsCall.biz event lists only (cap 150)."""
import json, re, time, html, os, urllib.request, urllib.parse, urllib.error
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
STATE = REPO / "analysis/data/run_state/p5-phase1"
PROG = STATE / "progress.json"
EV = REPO / "analysis/data/evals/p5_filings"; (EV / "submissions").mkdir(parents=True, exist_ok=True); (EV / "docs").mkdir(parents=True, exist_ok=True)
C2 = REPO / "analysis/data/corpus_v2"
SEC_CAP = 1600
_UA = None
_LAST = [0.0]


def ua():
    global _UA
    if _UA is None:
        _UA = next(l.split("=", 1)[1].strip().strip('"').strip("'") for l in (REPO / ".env").read_text().splitlines() if l.startswith("SEC_USER_AGENT="))
    return _UA


def prog(): return json.loads(PROG.read_text())
def save_prog(p): PROG.write_text(json.dumps(p, indent=2))


def sec_get(url):
    p = prog()
    assert p.get("edgar_requests_used", 0) < SEC_CAP, "SEC request cap reached"
    w = 1.05 - (time.time() - _LAST[0])
    if w > 0: time.sleep(w)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": ua(), "Accept-Encoding": "identity"}), timeout=90) as r: st, b = r.status, r.read()
    except urllib.error.HTTPError as e: st, b = e.code, e.read()
    except Exception as e: st, b = 0, str(e).encode()
    _LAST[0] = time.time()
    p = prog(); p["edgar_requests_used"] = p.get("edgar_requests_used", 0) + 1; save_prog(p)
    if st in (403, 429): raise SystemExit(f"SEC HARD STOP {st} {url}")
    return st, b


def alias_map():
    a = json.loads((C2 / "TICKER_ALIASES.json").read_text())
    return {e["original_symbol"]: e["working_symbol"] for e in a["entries"] if e.get("working_symbol")}


def universe():
    """164 corpus companies as (original_symbol, working_symbol, split)."""
    s = json.loads((C2 / "SPLIT_V7_RESERVE_REPLACEMENTS.json").read_text()); am = alias_map(); out = []
    for sp in ("train", "tune", "holdout"):
        for c in s[sp]: out.append((c, am.get(c, c), sp))
    return out


def plain(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", raw))))


def tickers_json():
    return {v["ticker"]: v for v in json.loads((REPO / "analysis/data/evals/p5_phase0b/company_tickers.json").read_text()).values()}
