#!/usr/bin/env python3
"""
r4_horizon_driver.py -- prompts/R4-grading-horizon.md (run_id r4-grading-horizon)

$0. No model calls. Re-grades the v6 eval caches already on disk against the price cache
already on disk, varying ONE thing: the forward horizon. Imports parsing/direction logic
from analyst_direct_scorer (unmodified). Grading logic (price on/after target within 30
days, stock minus SPY, +-5% dead band) is a line-for-line copy of score_eval_dir with the
horizon as a parameter.

  python3 r4_horizon_driver.py check          # alias/holdout/count asserts
  python3 r4_horizon_driver.py sweep <split>  # train | tune ; appends cells.jsonl
"""
import sys, json, glob, random, datetime
from datetime import date, timedelta
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))
from analyst_direct_scorer import PriceCache, parse_structured, direction_from_score  # noqa

RUN = REPO / "analysis/data/run_state/r4-grading-horizon"
C2 = REPO / "analysis/data/corpus_v2"
PRICE_CACHE = C2 / "scorer_price_cache_v1.json"
SPLIT = C2 / "SPLIT_V7_RESERVE_REPLACEMENTS.json"
ALIASES = C2 / "TICKER_ALIASES.json"
EVALS = {"train": REPO / "analysis/data/evals/v6_claude-sonnet-4-6",
         "tune": REPO / "analysis/data/evals/v6_claude-sonnet-4-6_tune"}
HORIZONS = [30, 60, 90, 182, 270, 365]
DEAD_BAND = 0.05
BENCH = "SPY"
EXCLUDE = {"WOLF", "SPWR"}
SEED = 11
B = 2000
CLS = ["bullish", "bearish", "neutral"]


def alias_map():
    raw = json.loads(ALIASES.read_text())
    return {e["original_symbol"]: e["working_symbol"] for e in raw["entries"] if e.get("working_symbol")}


def split_symbols(name):
    sp = json.loads(SPLIT.read_text())
    a = alias_map()
    return {a.get(t, t) for t in sp[name]} | set(sp[name])


def load_calls(split):
    """[(ticker, date, predicted)] from the eval dir, WOLF/SPWR excluded entirely."""
    out = []
    for f in sorted(glob.glob(str(EVALS[split] / "*.txt"))):
        tk, ds = Path(f).stem.rsplit("_", 1)
        if tk in EXCLUDE:
            continue
        d = direction_from_score(parse_structured(Path(f).read_text(errors="replace")))
        if d is None:
            continue
        out.append((tk, date.fromisoformat(ds), d))
    return out


def grade(prices, tk, d, horizon):
    p0, _ = prices.price_on_or_after(tk, d)
    b0, _ = prices.price_on_or_after(BENCH, d)
    t = d + timedelta(days=horizon)
    p1, _ = prices.price_on_or_after(tk, t)
    b1, _ = prices.price_on_or_after(BENCH, t)
    if not all([p0, b0, p1, b1]):
        return None, None
    rel = (p1 - p0) / p0 - (b1 - b0) / b0
    gt = "bullish" if rel > DEAD_BAND else "bearish" if rel < -DEAD_BAND else "neutral"
    return gt, rel


def cmd_check():
    sp = json.loads(SPLIT.read_text())
    tr, tu, ho = split_symbols("train"), split_symbols("tune"), split_symbols("holdout")
    res = {}
    for s in ("train", "tune"):
        files = glob.glob(str(EVALS[s] / "*.txt"))
        tks = {Path(f).stem.rsplit("_", 1)[0] for f in files}
        allowed = tr if s == "train" else tu
        res[s] = {"files": len(files), "tickers": len(tks), "not_in_split": sorted(tks - allowed),
                  "in_holdout": sorted(tks & ho), "wolf_spwr_files": sum(1 for f in files if Path(f).stem.rsplit('_',1)[0] in EXCLUDE)}
    print(json.dumps(res, indent=1))
    ok = (res["train"]["files"] == 1240 and not res["train"]["not_in_split"] and not res["tune"]["not_in_split"]
          and not res["train"]["in_holdout"] and not res["tune"]["in_holdout"])
    (RUN / "check.json").write_text(json.dumps({**res, "asserts_pass": ok}, indent=1))
    if not ok:
        raise SystemExit("CHECK FAILED")


def matrices(calls, prices, horizon):
    """per-ticker 3x3 count matrices [pred][truth], plus gradable/total counts."""
    per = {}
    n_tot = n_grad = 0
    rels = []
    for tk, d, pred in calls:
        n_tot += 1
        gt, rel = grade(prices, tk, d, horizon)
        if gt is None:
            continue
        n_grad += 1
        m = per.setdefault(tk, np.zeros((3, 3), dtype=np.int64))
        m[CLS.index(pred), CLS.index(gt)] += 1
    return per, n_tot, n_grad


def stats_from(M):
    n = M.sum()
    out = {"n": int(n)}
    if n == 0:
        return out
    truth = M.sum(axis=0) / n
    predc = M.sum(axis=1)
    out["base_rate_pct"] = {c: round(100 * truth[i], 1) for i, c in enumerate(CLS)}
    acc = np.trace(M) / n
    exp = float(((predc / n) * truth).sum())
    out["accuracy_pct"] = round(100 * acc, 2)
    out["gap_pts"] = round(100 * (acc - exp), 2)
    for i, c in enumerate(CLS):
        k = int(M[i, i])
        out[c] = {"calls": int(predc[i]), "share_pct": round(100 * predc[i] / n, 1), "hits": k,
                  "hit_rate_pct": round(100 * k / predc[i], 1) if predc[i] else None,
                  "edge_pts": round(100 * (k / predc[i] - truth[i]), 2) if predc[i] else None}
    return out


def boot(per, seed=SEED):
    tks = sorted(per)
    arr = np.stack([per[t] for t in tks])  # T x 3 x 3
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(tks), size=(B, len(tks)))
    Ms = arr[idx].sum(axis=1)  # B x 3 x 3
    n = Ms.sum(axis=(1, 2)).astype(float)
    truth = Ms.sum(axis=1) / n[:, None]
    predc = Ms.sum(axis=2)
    diag = np.stack([Ms[:, i, i] for i in range(3)], axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        edge = 100 * (diag / predc - truth)
        acc = diag.sum(axis=1) / n
        exp = ((predc / n[:, None]) * truth).sum(axis=1)
    gap = 100 * (acc - exp)
    ci = {}
    for i, c in enumerate(CLS):
        e = edge[:, i][np.isfinite(edge[:, i])]
        ci[c] = [round(float(np.percentile(e, 2.5)), 2), round(float(np.percentile(e, 97.5)), 2)] if len(e) else None
    ci["gap"] = [round(float(np.percentile(gap, 2.5)), 2), round(float(np.percentile(gap, 97.5)), 2)]
    return ci


def cells_path():
    return RUN / "cells.jsonl"


def done_keys():
    p = cells_path()
    if not p.exists():
        return set()
    return {(r["split"], r["horizon"]) for r in (json.loads(l) for l in p.read_text().splitlines() if l.strip())}


def cmd_sweep(split):
    prices = PriceCache(PRICE_CACHE)
    calls = load_calls(split)
    have = done_keys()
    order = [182] + [h for h in HORIZONS if h != 182]  # 182 first: reproduction check
    for h in order:
        if (split, h) in have:
            print("reuse", split, h)
            continue
        per, n_tot, n_grad = matrices(calls, prices, h)
        M = sum(per.values())
        st = stats_from(M)
        st["ci95"] = boot(per)
        st["ticker_block_seed"] = SEED
        st["bootstrap_resamples"] = B
        rec = {"split": split, "horizon": h, "calls_total": n_tot, "calls_gradable": n_grad,
               "companies": len(per), "matrix_pred_by_truth": M.tolist(), "cls_order": CLS, "results": st,
               "per_ticker": {t: per[t].tolist() for t in per},
               "params": {"dead_band": DEAD_BAND, "benchmark": BENCH, "price_cache": str(PRICE_CACHE.relative_to(REPO)),
                          "eval_dir": str(EVALS[split].relative_to(REPO))}}
        with cells_path().open("a") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
        b = st.get("bearish", {})
        print(f"{split} {h:>3}d n={n_grad}/{n_tot} base={st.get('base_rate_pct')} bearish calls={b.get('calls')} "
              f"hit={b.get('hit_rate_pct')} edge={b.get('edge_pts')} ci={st['ci95']['bearish']}")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "check":
        cmd_check()
    elif c == "sweep":
        cmd_sweep(sys.argv[2])
    else:
        print(__doc__)
