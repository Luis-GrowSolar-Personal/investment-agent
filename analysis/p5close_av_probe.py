#!/usr/bin/env python3
"""p5close_av_probe.py -- prompts/P5-close-sector-and-drift.md Step 4 (<= 3 Alpha Vantage requests, 1 per 15s). EARNINGS function for MU, RUN, JPM."""
import sys, json, time, urllib.request, urllib.parse, urllib.error, os
from pathlib import Path
from dotenv import load_dotenv
REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
STATE = REPO / "analysis/data/run_state/p5-close-sector-drift"
KEY = os.environ["AV_API_KEY"]
out = {}
for i, tk in enumerate(("MU", "RUN", "JPM")):
    if i: time.sleep(15)
    url = "https://www.alphavantage.co/query?" + urllib.parse.urlencode({"function": "EARNINGS", "symbol": tk, "apikey": KEY})
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            st, body = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        st, body = e.code, e.read().decode("utf-8", "replace")
    (STATE / f"av_{tk}.json").write_text(body)
    try: d = json.loads(body)
    except json.JSONDecodeError: d = {"_raw": body[:500]}
    qe = d.get("quarterlyEarnings", [])
    fields_present = {f: sum(1 for q in qe if q.get(f) not in (None, "", "None")) for f in ("reportedDate", "reportedEPS", "estimatedEPS", "surprise", "surprisePercentage")}
    from_2019 = [q for q in qe if q.get("fiscalDateEnding", "9999") >= "2019-01-01"]
    est_nonempty_2019 = sum(1 for q in from_2019 if q.get("estimatedEPS") not in (None, "", "None"))
    out[tk] = {"status": st, "top_level_keys": sorted(d.keys()), "n_quarterly": len(qe), "earliest_fiscalDateEnding": min((q.get("fiscalDateEnding", "") for q in qe), default=None),
              "latest_fiscalDateEnding": max((q.get("fiscalDateEnding", "") for q in qe), default=None), "fields_present_counts": fields_present,
              "n_from_2019_on": len(from_2019), "n_from_2019_on_with_estimatedEPS": est_nonempty_2019, "note_or_information": d.get("Note") or d.get("Information") or d.get("Error Message"),
              "sample_row": qe[0] if qe else None}
(STATE / "av_probe.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
