#!/usr/bin/env python3
"""consensus-surprise-screen.md Step 1 ($0). Winner-rich selection of 20 train companies. Output: selection.json."""
import sys, json
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p6_output_format_analysis as A
REPO = Path(__file__).resolve().parent.parent
STATE = REPO / "analysis/data/run_state/consensus-surprise-screen"
EXCLUDE = {"FRC", "MAXN", "MAXNQ", "SUNW", "VIAC", "PARA"}


def main():
    calls = [c for c in A.load_calls(REPO / "analysis/data/run_state/p6-output-format-round/calls.csv") if c["fwd_rel_ret_tradeable"] is not None]
    by = {}
    for c in calls:
        if c["ticker"] in EXCLUDE: continue
        by.setdefault(c["ticker"], {"winners": 0, "other": 0, "total": 0})
        by[c["ticker"]]["total"] += 1
        if c["fwd_rel_ret_tradeable"] >= 20: by[c["ticker"]]["winners"] += 1
        else: by[c["ticker"]]["other"] += 1
    elig = {t: v for t, v in by.items() if v["winners"] >= 2 and v["other"] >= 6}
    ranked = sorted(elig.items(), key=lambda kv: (-kv[1]["winners"], -kv[1]["total"], kv[0]))
    top20 = ranked[:20]
    out = {"n_train_companies_considered": len(by), "excluded": sorted(EXCLUDE), "n_eligible": len(elig), "eligible_all": dict(sorted(elig.items())),
           "selected": [{"ticker": t, **v} for t, v in top20], "n_selected": len(top20),
           "RUN_MU_JPM_status": {t: (dict(elig[t], selected=t in dict(top20)) if t in elig else {"eligible": False, **by.get(t, {})}) for t in ("RUN", "MU", "JPM")}}
    (STATE / "selection.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
