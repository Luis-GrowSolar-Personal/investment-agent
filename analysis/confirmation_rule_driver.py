#!/usr/bin/env python3
"""
confirmation_rule_driver.py -- prompts/confirmation-rule-test.md (run confirmation-rule-test)

$0. No model calls. For every bearish v6 call that has a following call by the same company:
  E  = close of the first trading day STRICTLY AFTER the bearish call date (tradeable entry)
  X  = close of the first trading day STRICTLY AFTER the next call's date (tradeable exit)
  END= close on/after (bearish call date + 182 days)   -- fixed horizon from the ORIGINAL call for all strategies
Returns are benchmark-relative (stock return minus SPY return over the same dates), as fractions.
  A hold      : rel(E -> END)
  B sell now  : 0 (out from E); "loss avoided" = -A
  C confirm   : if next call bearish: rel(E -> X) else rel(E -> END)
  D always    : rel(E -> X)
  wait cost   : rel(E -> X)
If X falls after END (next call more than ~182 days out) the exit is clipped to END (counted).

  python3 confirmation_rule_driver.py run
"""
import sys, json
from datetime import timedelta
from pathlib import Path
from collections import defaultdict
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))
import r4_horizon_driver as r4  # noqa
from analyst_direct_scorer import PriceCache  # noqa

RUN = REPO / "analysis/data/run_state/confirmation-rule-test"
HORIZON = 182
SEED, B = 11, 2000
STRATS = ["A", "B", "C", "D"]


def build_cases(prices):
    cases, dropped = [], defaultdict(int)
    for split in ("train", "tune"):
        by = defaultdict(list)
        for tk, d, p in r4.load_calls(split):
            by[tk].append((d, p))
        for tk, l in by.items():
            l.sort()
            for i, (d, p) in enumerate(l):
                if p != "bearish":
                    continue
                if i + 1 >= len(l):
                    dropped["last_call_no_follow"] += 1
                    continue
                nd, npred = l[i + 1]
                pe, de = prices.price_on_or_after(tk, d + timedelta(days=1))
                be, _ = prices.price_on_or_after(r4.BENCH, d + timedelta(days=1))
                pend, dend = prices.price_on_or_after(tk, d + timedelta(days=HORIZON))
                bend, _ = prices.price_on_or_after(r4.BENCH, d + timedelta(days=HORIZON))
                px, dx = prices.price_on_or_after(tk, nd + timedelta(days=1))
                bx, _ = prices.price_on_or_after(r4.BENCH, nd + timedelta(days=1))
                if not all([pe, be, pend, bend, px, bx]):
                    dropped["missing_price"] += 1
                    continue
                clipped = dx > dend
                if clipped:
                    px, bx = pend, bend
                    dropped["exit_clipped_to_END"] += 1
                rel = lambda p1, b1: (p1 / pe - 1) - (b1 / be - 1)
                A = rel(pend, bend)
                Xr = rel(px, bx)
                C = Xr if npred == "bearish" else A
                cases.append({"split": split, "ticker": tk, "call_date": d.isoformat(), "next_date": nd.isoformat(),
                              "next": npred, "A": A, "B": 0.0, "C": C, "D": Xr, "wait_cost": Xr, "clipped": bool(clipped),
                              "entry_date": de.isoformat(), "days_to_next": (nd - d).days})
    return cases, dict(dropped)


def boot_stats(cases, fn_keys, seed=SEED):
    """Ticker-block bootstrap of the mean of each column in fn_keys (dict name -> callable(case)->value)."""
    tks = sorted({c["ticker"] for c in cases})
    ix = {t: i for i, t in enumerate(tks)}
    names = list(fn_keys)
    S = np.zeros((len(tks), len(names)))
    N = np.zeros(len(tks))
    NEG = np.zeros((len(tks), len(names)))
    for c in cases:
        i = ix[c["ticker"]]
        N[i] += 1
        for j, nme in enumerate(names):
            v = fn_keys[nme](c)
            S[i, j] += v
            NEG[i, j] += 1 if v < 0 else 0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(tks), size=(B, len(tks)))
    n = N[idx].sum(axis=1)
    means = S[idx].sum(axis=1) / n[:, None]
    negs = NEG[idx].sum(axis=1) / n[:, None]
    out = {}
    for j, nme in enumerate(names):
        vals = np.array([fn_keys[nme](c) for c in cases])
        out[nme] = {"n": len(cases), "companies": len(tks), "mean_pct": round(100 * float(vals.mean()), 2),
                    "median_pct": round(100 * float(np.median(vals)), 2),
                    "share_negative_pct": round(100 * float((vals < 0).mean()), 1),
                    "mean_ci95": [round(100 * float(np.percentile(means[:, j], 2.5)), 2), round(100 * float(np.percentile(means[:, j], 97.5)), 2)],
                    "share_negative_ci95": [round(100 * float(np.percentile(negs[:, j], 2.5)), 1), round(100 * float(np.percentile(negs[:, j], 97.5)), 1)]}
    return out


def summarize(cases):
    cols = {"A": lambda c: c["A"], "B": lambda c: c["B"], "C": lambda c: c["C"], "D": lambda c: c["D"],
            "loss_avoided_B_vs_A": lambda c: -c["A"], "C_minus_A": lambda c: c["C"] - c["A"],
            "C_minus_B": lambda c: c["C"] - c["B"], "D_minus_A": lambda c: c["D"] - c["A"],
            "wait_cost": lambda c: c["wait_cost"]}
    return boot_stats(cases, cols)


def cmd_run():
    prices = PriceCache(r4.PRICE_CACHE)
    cases, dropped = build_cases(prices)
    (RUN / "cases.json").write_text(json.dumps(cases, indent=1))
    print("cases", len(cases), "dropped/notes", dropped)
    outp = RUN / "cells.jsonl"
    if outp.exists():
        outp.unlink()
    for split in ("train", "tune", "pooled"):
        sub = cases if split == "pooled" else [c for c in cases if c["split"] == split]
        for grp in ("all", "next_bearish", "next_neutral", "next_bullish"):
            g = sub if grp == "all" else [c for c in sub if c["next"] == grp.split("_")[1]]
            if not g:
                continue
            rec = {"split": split, "group": grp, "results": summarize(g),
                   "params": {"horizon_days": HORIZON, "entry": "first trading day strictly after call", "seed": SEED,
                              "resamples": B, "benchmark": "SPY", "price_cache": str(r4.PRICE_CACHE.relative_to(REPO))}}
            with outp.open("a") as f:
                f.write(json.dumps(rec) + "\n"); f.flush()
            r = rec["results"]
            print(f"{split:6} {grp:13} n={r['A']['n']:3} cos={r['A']['companies']:2} | A {r['A']['mean_pct']:+.1f} B avoided {r['loss_avoided_B_vs_A']['mean_pct']:+.1f} "
                  f"C {r['C']['mean_pct']:+.1f} D {r['D']['mean_pct']:+.1f} wait {r['wait_cost']['mean_pct']:+.1f} | C-A {r['C_minus_A']['mean_pct']:+.1f} {r['C_minus_A']['mean_ci95']} "
                  f"C-B {r['C_minus_B']['mean_pct']:+.1f} {r['C_minus_B']['mean_ci95']}")


def cmd_extra():
    """Added AFTER the point estimates were seen (flag in report): (1) ticker-block range on
    confirmed-minus-neutral for A, wait cost and C; (2) concentration: how much the worst cases drive means."""
    cases = json.loads((RUN / "cases.json").read_text())
    out = {}
    for split in ("train", "tune", "pooled"):
        sub = cases if split == "pooled" else [c for c in cases if c["split"] == split]
        conf = [c for c in sub if c["next"] == "bearish"]
        neut = [c for c in sub if c["next"] == "neutral"]
        tks = sorted({c["ticker"] for c in sub})
        rng = np.random.default_rng(SEED)
        res = {"A": [], "C": [], "wait_cost": [], "after_X": []}
        def m(g, key):
            if not g:
                return np.nan
            return np.mean([(c["A"] - c["D"]) if key == "after_X" else c[key] for c in g])
        for _ in range(B):
            pick = rng.choice(len(tks), size=len(tks))
            names = [tks[i] for i in pick]
            cnt = {}
            for n_ in names:
                cnt[n_] = cnt.get(n_, 0) + 1
            cf = [c for c in conf for _ in range(cnt.get(c["ticker"], 0))]
            nt = [c for c in neut for _ in range(cnt.get(c["ticker"], 0))]
            for k in res:
                res[k].append(m(cf, k) - m(nt, k))
        o = {}
        for k, v in res.items():
            v = np.array(v); v = v[np.isfinite(v)]
            pt = 100 * (m(conf, k) - m(neut, k))
            o[k] = {"point_pts": round(float(pt), 2), "ci95": [round(100 * float(np.percentile(v, 2.5)), 2), round(100 * float(np.percentile(v, 97.5)), 2)]}
        o["n_confirmed"], o["n_neutral"] = len(conf), len(neut)
        # concentration
        A = sorted([(c["A"], c["ticker"], c["call_date"]) for c in sub])
        tot = sum(a for a, _, _ in A)
        o["worst5_A"] = [(round(100 * a, 1), t, d) for a, t, d in A[:5]]
        o["mean_A_pct"] = round(100 * tot / len(A), 2)
        o["mean_A_excl_worst5_pct"] = round(100 * (tot - sum(a for a, _, _ in A[:5])) / (len(A) - 5), 2)
        o["median_A_pct"] = round(100 * float(np.median([a for a, _, _ in A])), 2)
        out[split] = o
        print(split, json.dumps(o))
    (RUN / "extra.json").write_text(json.dumps(out, indent=1))


def cmd_nopara():
    """Sensitivity added after finding the PARA price series corrupt (levels of ~100,000 decaying to ~1):
    (1) this run's four strategies with PARA excluded; (2) v6 baseline 182-day edges (arm A, call-date entry, as in the
    scorer) with and without PARA. Does NOT touch the cache."""
    prices = PriceCache(r4.PRICE_CACHE)
    cases = json.loads((RUN / "cases.json").read_text())
    out = {}
    for split in ("train", "tune", "pooled"):
        sub = [c for c in cases if c["ticker"] != "PARA" and (split == "pooled" or c["split"] == split)]
        for grp in ("all", "next_bearish", "next_neutral"):
            g = sub if grp == "all" else [c for c in sub if c["next"] == grp.split("_")[1]]
            r = summarize(g)
            out[f"{split}/{grp}"] = r
            print(f"NO-PARA {split:6} {grp:13} n={r['A']['n']:3} cos={r['A']['companies']:2} | A {r['A']['mean_pct']:+.1f} {r['A']['mean_ci95']} "
                  f"C {r['C']['mean_pct']:+.1f} D {r['D']['mean_pct']:+.1f} wait {r['wait_cost']['mean_pct']:+.1f} | C-A {r['C_minus_A']['mean_pct']:+.1f} {r['C_minus_A']['mean_ci95']}")
    base = {}
    for label, excl in (("with PARA", set()), ("without PARA", {"PARA"})):
        Ms = {}
        for sp in ("train", "tune"):
            calls = [c for c in r4.load_calls(sp) if c[0] not in excl]
            per, n, ng = r4.matrices(calls, prices, 182)
            Ms[sp] = sum(per.values())
        for name, M in (("train", Ms["train"]), ("tune", Ms["tune"]), ("pooled", Ms["train"] + Ms["tune"])):
            st = r4.stats_from(M)
            base[f"{label}/{name}"] = {"n": st["n"], "base_rate": st["base_rate_pct"], "bear_calls": st["bearish"]["calls"],
                                       "bear_hit": st["bearish"]["hit_rate_pct"], "bear_edge": st["bearish"]["edge_pts"],
                                       "bull_edge": st["bullish"]["edge_pts"], "neut_edge": st["neutral"]["edge_pts"], "gap": st["gap_pts"]}
            print("BASELINE-182", label, name, json.dumps(base[f"{label}/{name}"]))
    pa = [c for s_ in ("train", "tune") for c in r4.load_calls(s_) if c[0] == "PARA"]
    print("PARA calls in corpus:", len(pa), "bearish:", sum(1 for c in pa if c[2] == "bearish"))
    (RUN / "nopara.json").write_text(json.dumps({"strategies": out, "baseline182": base}, indent=1))


if __name__ == "__main__":
    {"run": cmd_run, "extra": cmd_extra, "nopara": cmd_nopara}.get((sys.argv[1:] or [""])[0], lambda: print(__doc__))()
