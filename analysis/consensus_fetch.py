#!/usr/bin/env python3
"""
consensus_fetch.py -- shared by consensus-surprise-screen.md Step 1 (fetch) and consensus-surprise-test.md Step 1 (full, reuses this unchanged).
Fetches Alpha Vantage EARNINGS for the given tickers (default: this run's selection.json), reusing p5-close-sector-drift's MU/RUN/JPM probe files
verbatim where present. Raw responses saved gitignored under analysis/data/evals/consensus_av/. Stops on any rate-limit Note/Information.
Usage: python3 analysis/consensus_fetch.py <run_dir_name> [max_requests]
"""
import sys, json, time, os, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from dotenv import load_dotenv
REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
EV = REPO / "analysis/data/evals/consensus_av"; EV.mkdir(parents=True, exist_ok=True)
KEY = os.environ.get("AV_API_KEY_PREMIUM") or os.environ["AV_API_KEY"]        # full test: premium key (Luis); screen used the free key
PROBE_REUSE = {"MU": REPO / "analysis/data/run_state/p5-close-sector-drift/av_MU.json", "RUN": REPO / "analysis/data/run_state/p5-close-sector-drift/av_RUN.json",
              "JPM": REPO / "analysis/data/run_state/p5-close-sector-drift/av_JPM.json"}


def fetch_one(tk):
    dest = EV / f"{tk}.json"
    if dest.exists(): return "cached", None
    if tk in PROBE_REUSE and PROBE_REUSE[tk].exists() and not dest.exists():
        dest.write_text(PROBE_REUSE[tk].read_text()); return "reused_probe", None
    url = "https://www.alphavantage.co/query?" + urllib.parse.urlencode({"function": "EARNINGS", "symbol": tk, "apikey": KEY})
    def one_call():
        try:
            with urllib.request.urlopen(url, timeout=30) as r: return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8", "replace")
    st, body = one_call()
    try: d = json.loads(body)
    except json.JSONDecodeError: return "bad_json", None
    note = d.get("Note") or d.get("Information")
    if note:          # full-test ground rule: wait 60s, retry once; stop only if it recurs
        time.sleep(60)
        st, body = one_call()
        try: d = json.loads(body)
        except json.JSONDecodeError: return "bad_json", None
        note = d.get("Note") or d.get("Information")
    dest.write_text(body)
    return ("rate_limited" if note else "fetched"), note


def main():
    run_dir, max_req = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
    STATE = REPO / "analysis/data/run_state" / run_dir
    sel = json.loads((STATE / "selection.json").read_text())
    tickers = [x["ticker"] for x in sel.get("selected", sel.get("fetch_order", []))]
    if not tickers and "tickers" in sel: tickers = sel["tickers"]
    done = 0; results = {}
    for i, tk in enumerate(tickers):
        status, note = fetch_one(tk)
        results[tk] = status
        print(tk, status, note or "")
        if status == "fetched":
            done += 1
            if done >= max_req: print("max_req reached this run"); break
            time.sleep(13)   # < 5/min
        if status == "rate_limited":
            print("RATE LIMIT HIT -- stopping for today:", note); break
    (STATE / "fetch_status.json").write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
