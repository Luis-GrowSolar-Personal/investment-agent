#!/usr/bin/env python3
"""
r4b_tradeable_entry_driver.py -- prompts/R4b-short-horizon-and-tradeable-entry.md (run r4b-tradeable-entry)

$0. No model calls. Two arms per cell, identical except the starting price:
  A  p0 = close on/after the call date (current scorer behaviour)
  B  p0 = close on the first trading day STRICTLY AFTER the call date
End price p1 = close on/after (call date + horizon) in both arms. Benchmark SPY, same rule per arm.
Imports helpers from r4_horizon_driver (unchanged) and analyst_direct_scorer (unmodified).

  python3 r4b_tradeable_entry_driver.py gate     # arm A reproduction at 182/30/60/90 (hard stop)
  python3 r4b_tradeable_entry_driver.py sweep    # all cells, both arms, both splits
  python3 r4b_tradeable_entry_driver.py timing   # per-call D / D+1 classification + split tables
"""
import sys, json, csv
from datetime import date, timedelta
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))
import r4_horizon_driver as r4  # noqa
from analyst_direct_scorer import PriceCache  # noqa

RUN = REPO / "analysis/data/run_state/r4b-tradeable-entry"
HORIZONS = [1, 2, 3, 5, 10, 21, 30, 60, 90, 182]
CLS = r4.CLS
SEED = 11
B = 2000
DEAD = 0.05
RATIO, MINABS = 2.0, 0.02  # timing threshold, pre-registered


def load():
    prices = PriceCache(r4.PRICE_CACHE)
    return prices, {s: r4.load_calls(s) for s in ("train", "tune")}


def p_after(prices, tk, d):
    """Close on the first trading day STRICTLY after d."""
    return prices.price_on_or_after(tk, d + timedelta(days=1))


def rel_ret(prices, tk, d0, arm, h):
    if arm == "A":
        p0, _ = prices.price_on_or_after(tk, d0)
        b0, _ = prices.price_on_or_after(r4.BENCH, d0)
    else:
        p0, _ = p_after(prices, tk, d0)
        b0, _ = p_after(prices, r4.BENCH, d0)
    t = d0 + timedelta(days=h)
    p1, _ = prices.price_on_or_after(tk, t)
    b1, _ = prices.price_on_or_after(r4.BENCH, t)
    if not all([p0, b0, p1, b1]):
        return None
    return (p1 - p0) / p0 - (b1 - b0) / b0


def truth(rel):
    return None if rel is None else ("bullish" if rel > DEAD else "bearish" if rel < -DEAD else "neutral")


def prev_close(prices, tk, d):
    days = prices._data.get(tk, {})
    for i in range(1, 8):
        k = (d - timedelta(days=i)).isoformat()
        if k in days:
            return days[k]
    return None


def close_on(prices, tk, d):
    return prices._data.get(tk, {}).get(d.isoformat())


def day_moves(prices, tk, d):
    """benchmark-relative move on D (prev close -> close D) and on D+1 (close D -> next trading close).
    If D is not a trading day, D's close is the next trading day's; returns None for missing legs."""
    cD, _dD = prices.price_on_or_after(tk, d)
    bD, dD = prices.price_on_or_after(r4.BENCH, d)
    if cD is None or dD is None:
        return None, None
    pc = prev_close(prices, tk, dD)
    pb = prev_close(prices, r4.BENCH, dD)
    c1, _ = prices.price_on_or_after(tk, dD + timedelta(days=1))
    b1, _ = prices.price_on_or_after(r4.BENCH, dD + timedelta(days=1))
    if None in (pc, pb, c1, b1):
        return None, None
    return (cD / pc - 1) - (bD / pb - 1), (c1 / cD - 1) - (b1 / bD - 1)


def classify(mD, m1, ratio=RATIO, minabs=MINABS):
    if mD is None:
        return "unclassifiable"
    a, b = abs(mD), abs(m1)
    if a >= ratio * b and a >= minabs:
        return "gap_on_D"
    if b >= ratio * a and b >= minabs:
        return "gap_on_D1"
    return "ambiguous"


def cmd_gate():
    prices, calls = load()
    ref = [json.loads(l) for l in (REPO / "analysis/data/run_state/r4-grading-horizon/cells.jsonl").read_text().splitlines() if l.strip()]
    ok = True
    out = {}
    for s in ("train", "tune"):
        for h in (182, 30, 60, 90):
            per, n, ng = r4.matrices(calls[s], prices, h)  # r4's own grader = the scorer's logic
            # independent re-implementation inside this driver:
            M = np.zeros((3, 3), dtype=np.int64)
            for tk, d, pred in calls[s]:
                g = truth(rel_ret(prices, tk, d, "A", h))
                if g:
                    M[CLS.index(pred), CLS.index(g)] += 1
            refM = np.array(next(c for c in ref if c["split"] == s and c["horizon"] == h)["matrix_pred_by_truth"])
            same = bool((M == refM).all())
            ok &= same
            out[f"{s}_{h}"] = same
            print(s, h, "arm A matches R4 cell:", same)
    # pooled 182 reference
    Ms = sum(np.array(next(c for c in ref if c["split"] == s and c["horizon"] == 182)["matrix_pred_by_truth"]) for s in ("train", "tune"))
    n = Ms.sum(); e = [round(100 * (Ms[i, i] / Ms[i].sum() - Ms[:, i].sum() / n), 1) for i in range(3)]
    print("pooled 182 edges [bull,bear,neut]:", e, "(reference 4.4, 13.3, 0.0)")
    ok &= e == [4.4, 13.3, -0.0] or e == [4.4, 13.3, 0.0]
    (RUN / "gate.json").write_text(json.dumps({"passes": bool(ok), "cells": out, "pooled182_edges": e}, indent=1))
    if not ok:
        raise SystemExit("GATE FAILED: arm A does not reproduce R4 -- stop and report")
    print("GATE PASSED")


def per_ticker(calls, prices, arm, h, filt=None):
    per = {}
    ng = 0
    for tk, d, pred in calls:
        if filt is not None and not filt(tk, d):
            continue
        g = truth(rel_ret(prices, tk, d, arm, h))
        if g is None:
            continue
        ng += 1
        per.setdefault(tk, np.zeros((3, 3), dtype=np.int64))[CLS.index(pred), CLS.index(g)] += 1
    return per, ng


def paired_boot(perA, perB):
    """ticker-block bootstrap of edge_A - edge_B per direction (same resampled companies in both arms)."""
    tks = sorted(set(perA) | set(perB))
    z = np.zeros((3, 3), dtype=np.int64)
    A = np.stack([perA.get(t, z) for t in tks]); Bm = np.stack([perB.get(t, z) for t in tks])
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(tks), size=(B, len(tks)))
    def edges(arr):
        Ms = arr[idx].sum(axis=1); n = Ms.sum(axis=(1, 2)).astype(float)
        t = Ms.sum(axis=1) / n[:, None]; p = Ms.sum(axis=2)
        d = np.stack([Ms[:, i, i] for i in range(3)], axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            return 100 * (d / p - t)
    diff = edges(A) - edges(Bm)
    out = {}
    for i, c in enumerate(CLS):
        v = diff[:, i][np.isfinite(diff[:, i])]
        out[c] = [round(float(np.percentile(v, 2.5)), 2), round(float(np.percentile(v, 97.5)), 2)] if len(v) else None
    return out


def write_cell(rec):
    with (RUN / "cells.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n"); f.flush()


def done(name):
    p = RUN / "cells.jsonl"
    if not p.exists():
        return set()
    return {(r["kind"], r["split"], r["arm"], r["horizon"], r.get("cls")) for r in (json.loads(l) for l in p.read_text().splitlines() if l.strip())}


def cmd_sweep():
    prices, calls = load()
    have = done(None)
    for s in ("train", "tune"):
        for h in HORIZONS:
            per = {}
            for arm in ("A", "B"):
                p, ng = per_ticker(calls[s], prices, arm, h)
                per[arm] = p
                if ("sweep", s, arm, h, None) in have:
                    continue
                M = sum(p.values()) if p else np.zeros((3, 3), dtype=np.int64)
                st = r4.stats_from(M)
                st["ci95"] = r4.boot(p) if p else None
                write_cell({"kind": "sweep", "split": s, "arm": arm, "horizon": h, "cls": None, "calls_total": len(calls[s]),
                            "calls_gradable": ng, "matrix_pred_by_truth": M.tolist(), "results": st,
                            "params": {"dead_band": DEAD, "benchmark": "SPY", "seed": SEED, "resamples": B}})
            pdiff = paired_boot(per["A"], per["B"])
            write_cell({"kind": "diff", "split": s, "arm": "A-B", "horizon": h, "cls": None, "paired_ci95_edge_diff": pdiff})
            a = next(json.loads(l) for l in (RUN / "cells.jsonl").read_text().splitlines() if l.strip() and json.loads(l)["kind"] == "sweep" and json.loads(l)["split"] == s and json.loads(l)["arm"] == "A" and json.loads(l)["horizon"] == h)
            b = next(json.loads(l) for l in (RUN / "cells.jsonl").read_text().splitlines() if l.strip() and json.loads(l)["kind"] == "sweep" and json.loads(l)["split"] == s and json.loads(l)["arm"] == "B" and json.loads(l)["horizon"] == h)
            print(s, h, "bear edge A", a["results"]["bearish"]["edge_pts"], "B", b["results"]["bearish"]["edge_pts"], "diff CI", pdiff["bearish"],
                  "| grad A/B", a["calls_gradable"], b["calls_gradable"])


def cmd_timing():
    prices, calls = load()
    rows = []
    for s in ("train", "tune"):
        for tk, d, pred in calls[s]:
            mD, m1 = day_moves(prices, tk, d)
            rows.append({"split": s, "ticker": tk, "date": d.isoformat(), "pred": pred,
                         "mD": None if mD is None else round(mD, 5), "m1": None if m1 is None else round(m1, 5)})
    with (RUN / "call_timing.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    def cl(r, ratio=RATIO, minabs=MINABS):
        return classify(None if r["mD"] is None else r["mD"], None if r["m1"] is None else r["m1"], ratio, minabs)
    sens = {}
    for label, (ratio, minabs) in {"registered (2x, 2%)": (2, .02), "min-abs halved (2x, 1%)": (2, .01), "min-abs doubled (2x, 4%)": (2, .04),
                                    "ratio halved (1x, 2%)": (1, .02), "ratio doubled (4x, 2%)": (4, .02)}.items():
        c = {}
        for r in rows:
            k = cl(r, ratio, minabs); c[k] = c.get(k, 0) + 1
        sens[label] = c
        n = len(rows)
        print(label, {k: f"{v} ({100*v/n:.1f}%)" for k, v in sorted(c.items())})
    (RUN / "timing_sensitivity.json").write_text(json.dumps(sens, indent=1))
    cmap = {(r["split"], r["ticker"], r["date"]): cl(r) for r in rows}
    # split tables, both arms, every horizon, per class, per split
    for s in ("train", "tune"):
        for k in ("gap_on_D", "gap_on_D1", "ambiguous"):
            filt = lambda tk, d, s=s, k=k: cmap.get((s, tk, d.isoformat())) == k
            for h in HORIZONS:
                pp = {}
                for arm in ("A", "B"):
                    p, ng = per_ticker(calls[s], prices, arm, h, filt)
                    pp[arm] = p
                    M = sum(p.values()) if p else np.zeros((3, 3), dtype=np.int64)
                    st = r4.stats_from(M) if M.sum() else {"n": 0}
                    st["ci95"] = r4.boot(p) if len(p) > 1 else None
                    write_cell({"kind": "timing_split", "split": s, "arm": arm, "horizon": h, "cls": k, "calls_gradable": ng,
                                "matrix_pred_by_truth": M.tolist(), "results": st})
                if pp["A"] and pp["B"]:
                    write_cell({"kind": "timing_diff", "split": s, "arm": "A-B", "horizon": h, "cls": k,
                                "paired_ci95_edge_diff": paired_boot(pp["A"], pp["B"]) if len(pp["A"]) > 1 else None})
    print("timing split cells written")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    {"gate": cmd_gate, "sweep": cmd_sweep, "timing": cmd_timing}.get(c, lambda: print(__doc__))()
