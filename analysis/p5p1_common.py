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


# ---------------------------------------------------------------- sector groups (Step 1a)
GROUPS = ["semis", "solar/storage/clean energy", "software/IT", "internet/media", "banks/financials", "pharma/health", "energy (oil & gas)", "utilities", "industrials",
          "consumer staples", "consumer discretionary/retail", "telecom", "REITs", "materials", "other"]


def sic_group(sic):
    s = int(sic)
    if s in (3674,): return "semis"
    if 3570 <= s <= 3579 or s in (3661, 3663, 3669, 3576, 7370, 7371, 7372, 7373, 7374, 7389): return "software/IT"
    if s in (4832, 4833, 4841, 7310, 7311, 7812, 7841, 7900, 7990, 2711): return "internet/media"
    if 6000 <= s <= 6499: return "banks/financials"
    if s == 6798 or 6500 <= s <= 6553: return "REITs"
    if 2830 <= s <= 2836 or 3841 <= s <= 3845 or 8000 <= s <= 8099 or s in (5912, 3826, 3829, 3823): return "pharma/health"
    if s in (1311, 1381, 1382, 1389, 2911, 5171, 5172, 4922, 4923, 4610): return "energy (oil & gas)"
    if 4900 <= s <= 4991: return "utilities"
    if s in (4812, 4813, 4899): return "telecom"
    if 2000 <= s <= 2199 or s in (2840, 2844, 2080, 5140, 5141, 5411, 5331, 2670, 2621): return "consumer staples"
    if s in (3711, 3714, 3021, 5211, 5810, 5812, 5200, 5399) or 5300 <= s <= 5999: return "consumer discretionary/retail"
    if 1000 <= s <= 1499 or 2800 <= s <= 2829 or 2850 <= s <= 2899 or 3300 <= s <= 3399 or 2600 <= s <= 2699: return "materials"
    if 3400 <= s <= 3599 or 3600 <= s <= 3699 or 3700 <= s <= 3799 or 4000 <= s <= 4799 or 1500 <= s <= 1799 or 3800 <= s <= 3899 or s in (3089,): return "industrials"
    return "other"


# Overrides where the SIC group is misleading (documented in docs/peers/SECTOR_MAP.csv, basis = override)
OVERRIDE = {
    "LRCX": ("semis", "semiconductor equipment (SIC 3559)"), "ENTG": ("semis", "semiconductor materials (SIC 3089)"), "QCOM": ("semis", "fabless chips (SIC 3663)"),
    "AMAT": ("semis", "semiconductor equipment"), "GOOG": ("internet/media", "internet (SIC 7370)"), "TTD": ("internet/media", "advertising platform (SIC 7370)"),
    "PYPL": ("banks/financials", "payments (SIC 7389)"), "XYZ": ("banks/financials", "payments (SIC 7372)"), "ACN": ("software/IT", "IT services"),
    "MMM": ("industrials", "conglomerate (SIC 3841)"), "ROK": ("industrials", "automation (SIC 3829)"), "COST": ("consumer staples", "warehouse retailer (SIC 5331)"),
    "KMB": ("consumer staples", "paper-based consumer products (SIC 2670)"), "ECL": ("materials", "chemicals (SIC 2840)"), "TSLA": ("consumer discretionary/retail", "autos"),
    "DD": ("materials", "chemicals"), "NOW": ("software/IT", "software"), "CMCSA": ("internet/media", "cable/media"), "CHTR": ("internet/media", "cable/media"),
    "UPS": ("industrials", "logistics"), "UNP": ("industrials", "railroad"), "TMO": ("pharma/health", "life-science tools"), "DHR": ("pharma/health", "life-science tools"),
    "NEM": ("materials", "gold mining"), "FCX": ("materials", "copper mining"), "KHC": ("consumer staples", "food"), "GIS": ("consumer staples", "food"),
}
