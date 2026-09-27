#!/usr/bin/env python3
"""
p5p2a_leadlag.py -- prompts/P5-phase2a-tight-map.md Step 2 ($0; scorer_price_cache_v1.json only, no fetches).
For each (target, peer) selection in target_peers.csv: x = peer's return vs SPY, last close before the peer's call to the
3rd close after it. y1 = target's return vs SPY over the SAME start (peer's pre-call close) to the last close before the
target's call. y2 = target's own 182-day tradeable return vs SPY (train only; reused from calls.csv, same definition).
Holdout peers and non-corpus peers are excluded and counted (never read here). Tune peers contribute only x (y1/y2 are
properties of the TARGET, not the peer, so no tune 182-day window is ever read). Control: one same-sector (peer's sector)
company, excluding every phase 1 peer of the target, train/tune only, call within +/-10 days of the peer's call, seed p5-2a-11.
"""
import sys, json, csv, random
from pathlib import Path
from datetime import date, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
import p6_output_format_analysis as A
from analyst_direct_scorer import PriceCache
REPO = C.REPO
STATE = REPO / "analysis/data/run_state/p5-phase2a"
D_ = date.fromisoformat
PRICE_CACHE = REPO / "analysis/data/corpus_v2/scorer_price_cache_v1.json"


def prev_close(prices, tk, d):
    days = prices._data.get(tk, {})
    for i in range(1, 10):
        k = (d - timedelta(days=i)).isoformat()
        if k in days: return days[k], D_(k)
    return None, None


def nth_close_after(prices, tk, d, n):
    days = prices._data.get(tk, {})
    found = 0
    for i in range(0, 30):
        k = (d + timedelta(days=i)).isoformat()
        if k in days:
            found += 1
            if found == n: return days[k], D_(k)
    return None, None


def ret(prices, tk, d0, d1):
    p0, _ = prev_close(prices, tk, d0 + timedelta(days=1)) if False else (prices._data.get(tk, {}).get(d0.isoformat()), d0)
    return p0


def rel_ret(prices, tk, date0, date1):
    """(tk return - SPY return) between two DATE objects, using the exact stored close on each date (dates must be keys already present)."""
    p0 = prices._data.get(tk, {}).get(date0.isoformat()); p1 = prices._data.get(tk, {}).get(date1.isoformat())
    b0 = prices._data.get("SPY", {}).get(date0.isoformat()); b1 = prices._data.get("SPY", {}).get(date1.isoformat())
    if None in (p0, p1, b0, b1) or p0 == 0 or b0 == 0: return None
    return 100 * ((p1 - p0) / p0 - (b1 - b0) / b0)


def main():
    prices = PriceCache(PRICE_CACHE)
    split = json.loads((REPO / "analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json").read_text())
    am = C.alias_map(); splitof = {}
    for s in ("train", "tune", "holdout"):
        for t in split[s]: splitof[am.get(t, t)] = s
    smap = {r["symbol"]: r["final_group"] for r in csv.DictReader(open(REPO / "docs/peers/SECTOR_MAP.csv"))}
    by_group = {}
    for t, sp in splitof.items():
        if sp in ("train", "tune"): by_group.setdefault(smap.get(t, "other"), []).append(t)

    # every phase 1 peer of each target (loose map), for control exclusion
    p1_peers = {}
    for r in csv.DictReader(open(REPO / "analysis/data/run_state/p5-phase1/peer_links.csv")):
        p1_peers.setdefault(r["company"], set()).add(r["peer"])

    calls = {(c["ticker"], c["call_date"]): c for c in A.load_calls(REPO / "analysis/data/run_state/p6-output-format-round/calls.csv")}
    target_dates = {}
    for w, dates in {}.items(): pass
    train_calls = {}
    for tk in set(splitof) | {"SPY"}:
        d = C.C2 / "transcripts" / tk
        train_calls[tk] = sorted(f.stem for f in d.glob("*.json")) if d.is_dir() else []

    rng = random.Random("p5-2a-11")
    rows = list(csv.DictReader(open(STATE / "target_peers.csv")))
    out = []; excl = {"holdout_peer": 0, "noncorpus_peer": 0, "no_prices": 0, "no_control": 0}
    for r in rows:
        peer, target, td = r["peer"], r["target"], r["target_date"]
        psp = splitof.get(peer)
        if psp == "holdout": excl["holdout_peer"] += 1; continue
        if psp is None: excl["noncorpus_peer"] += 1; continue
        pcd = D_(r["peer_call_date"])
        p0, d0 = prev_close(prices, peer, pcd)
        px, dx = nth_close_after(prices, peer, pcd, 3)
        pT, dT = prev_close(prices, target, D_(td))
        if None in (p0, px, pT): excl["no_prices"] += 1; continue
        x = rel_ret(prices, peer, d0, dx)
        y1 = rel_ret(prices, target, d0, dT)
        c = calls.get((target, td))
        y2 = c["fwd_rel_ret_tradeable"] if c and c["fwd_rel_ret_tradeable"] is not None else None
        y1_days = (dT - d0).days
        if x is None or y1 is None: excl["no_prices"] += 1; continue

        # control
        group = smap.get(peer, "other")
        pool = [t for t in by_group.get(group, []) if t != peer and t != target and t not in p1_peers.get(target, set()) and t not in p1_peers.get(peer, set())]
        pool = sorted(pool)
        ctl_x = None; ctl_peer = None
        rng2 = random.Random(f"p5-2a-11-{target}-{td}-{peer}")
        rng2.shuffle(pool)
        for cand in pool:
            for dt in train_calls.get(cand, []):
                if abs((D_(dt) - pcd).days) <= 10:
                    cp0, cd0 = prev_close(prices, cand, D_(dt)); cpx, cdx = nth_close_after(prices, cand, D_(dt), 3)
                    if cp0 is not None and cpx is not None:
                        cx = rel_ret(prices, cand, cd0, cdx)
                        if cx is not None: ctl_x, ctl_peer, ctl_date = cx, cand, dt; break
            if ctl_x is not None: break
        if ctl_x is None: excl["no_control"] += 1
        out.append({"target": target, "target_date": td, "peer": peer, "rule": r["rule"], "x": x, "y1": y1, "y1_days": y1_days, "y2": y2,
                    "ctl_peer": ctl_peer, "ctl_x": ctl_x, "train_target": target in split["train"] or am.get(target, target) in split["train"]})

    with open(STATE / "leadlag_pairs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

    def rho(rs, a, b):
        rs2 = [r for r in rs if r[a] is not None and r[b] is not None]
        return A.spearman([r[a] for r in rs2], [r[b] for r in rs2]), len(rs2)

    scored = out
    res = {"total_selections": len(rows), "excluded": excl, "scored_pairs": len(scored), "scored_pct_of_selections": round(100 * len(scored) / len(rows), 1),
           "n_with_control": sum(1 for r in scored if r["ctl_x"] is not None), "y1_days_under5": sum(1 for r in scored if r["y1_days"] < 5)}
    def block(rs, label):
        b = {}
        r1, n1 = rho(rs, "x", "y1"); b["x_to_y1"] = {"tight": r1, "n": n1}
        lo, hi, _ = A.boot([r for r in rs if r["x"] is not None and r["y1"] is not None], lambda s: A.spearman([r["x"] for r in s], [r["y1"] for r in s]))
        b["x_to_y1"]["range"] = [lo, hi]
        ctl = [r for r in rs if r["ctl_x"] is not None and r["y1"] is not None]
        rc, nc = A.spearman([r["ctl_x"] for r in ctl], [r["y1"] for r in ctl]), len(ctl)
        b["x_to_y1"]["control"] = rc; b["x_to_y1"]["control_n"] = nc
        diff = lambda s: A.spearman([r["x"] for r in s], [r["y1"] for r in s]) - A.spearman([r["ctl_x"] for r in s], [r["y1"] for r in s])
        dl, dh, _ = A.boot(ctl, diff)
        b["x_to_y1"]["diff"] = (r1 - rc) if r1 == r1 and rc == rc else None; b["x_to_y1"]["diff_range"] = [dl, dh]
        rs2 = [r for r in rs if r["train_target"] and r["x"] is not None and r["y2"] is not None]
        if rs2:
            r2 = A.spearman([r["x"] for r in rs2], [r["y2"] for r in rs2])
            lo2, hi2, _ = A.boot(rs2, lambda s: A.spearman([r["x"] for r in s], [r["y2"] for r in s]))
            ctl2 = [r for r in rs2 if r["ctl_x"] is not None]
            rc2 = A.spearman([r["ctl_x"] for r in ctl2], [r["y2"] for r in ctl2]) if ctl2 else float("nan")
            diff2 = lambda s: A.spearman([r["x"] for r in s], [r["y2"] for r in s]) - A.spearman([r["ctl_x"] for r in s], [r["y2"] for r in s])
            dl2, dh2, _ = A.boot(ctl2, diff2) if ctl2 else (float("nan"), float("nan"), 0)
            b["x_to_y2"] = {"tight": r2, "n": len(rs2), "range": [lo2, hi2], "control": rc2, "control_n": len(ctl2), "diff": r2 - rc2 if rc2 == rc2 else None, "diff_range": [dl2, dh2]}
        return b
    res["overall"] = block(scored, "overall")
    for rule in ("S1", "S2", "C1", "C2"):
        rs = [r for r in scored if r["rule"] == rule]
        if len(rs) >= 15: res[f"rule_{rule}"] = block(rs, rule)
    lo, hi = res["overall"]["x_to_y1"]["diff_range"]
    res["reading"] = "links transmit" if lo is not None and lo == lo and lo > 0 else "P5 stops"
    (STATE / "leadlag_report.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
