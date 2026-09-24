#!/usr/bin/env python3
"""
p6_output_format_analysis.py -- prompts/P6-output-format-round.md sections 5d and 6. $0: no model calls.

  python3 p6_output_format_analysis.py calls   # build calls.csv; reproduce the v6 train reference (hard stop on mismatch)
  python3 p6_output_format_analysis.py tests   # 6.1-6.5 -> results.json + tests_report.md

Imports (unmodified): PriceCache, parse_structured, score_eval_dir, compute_luck_corrected_metrics, CallRecord from
analyst_direct_scorer; rel_ret (arm "B" = first close strictly after the call date) and truth from r4b_tradeable_entry_driver;
alias resolution / stratum_map / wilson / read_jsonl from p3_guidance_ledger_driver via p6_output_format_driver.
Score -> direction thresholds are FIXED (prompt rule 3): <= -2 bearish, >= +2 bullish, else neutral. They are not tuned here.
Every figure is a call-level statistic on TRAIN (WOLF, SPWR, PARA excluded); every bootstrap resamples TICKERS, not calls.
"""
import sys, json, csv, statistics
from datetime import date
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))
import p6_output_format_driver as d  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402
from analyst_direct_scorer import (PriceCache, parse_structured, direction_from_score, score_eval_dir,  # noqa: E402
                                   compute_luck_corrected_metrics, CallRecord)
from r4b_tradeable_entry_driver import rel_ret, truth  # noqa: E402

STATE = d.STATE
CALLS = STATE / "calls.csv"
BOOT_B, SEED = 2000, 11
BASE = {"bearish": 46.6, "bullish": 32.8, "neutral": 20.6}     # P3a block, prompt section 8
V6_REF = {"accuracy_pct": 30.3, "gap_pp": 2.48, "bearish_calls": 103, "bearish_precision_pct": 60.2}


def thr(s):
    if s is None:
        return None
    return "bearish" if s <= -2 else "bullish" if s >= 2 else "neutral"


def parse_score(content):
    sc = parse_structured(content)
    s = sc.get("score")
    ok = isinstance(s, int) and not isinstance(s, bool) and -5 <= s <= 5
    nr = sc.get("noRead")
    return sc, (s if ok else None), (nr if isinstance(nr, bool) else None)


def num(x):
    return "" if x is None else x


# ------------------------------------------------------------------------------------------ calls.csv
def build_rows():
    smap = p3.stratum_map()
    prices = PriceCache(REPO / d.PRICE_CACHE_REL)
    sc_b = {(r["ticker"], r["date"]): r for r in p3.read_jsonl(d.scores_path("B"))}
    sc_c = {(r["ticker"], r["date"]): r for r in p3.read_jsonl(d.scores_path("C"))}
    rows, c_keys = [], []
    for rec in d.universe():
        tk, dt = rec["ticker"], rec["date"]
        d0 = date.fromisoformat(dt)
        fwd = rel_ret(prices, tk, d0, "B", 182)
        gt = truth(rel_ret(prices, tk, d0, "A", 182))          # old ruler: scorer entry (on/after call date)
        v6t = (d.V6_EVAL_DIR / f"{tk}_{dt}.txt").read_text()
        v6s = parse_structured(v6t)
        v6d = direction_from_score(v6s)
        r = {"ticker": tk, "call_date": dt, "stratum": smap[tk], "tier": "NA",
             "fwd_rel_ret_tradeable": num(None if fwd is None else round(fwd * 100, 4)), "gt_old_ruler": num(gt),
             "v6_rec": v6s.get("recommendation", ""), "v6_dir": num(v6d), "v6_hit": num(None if not (v6d and gt) else int(v6d == gt))}
        for arm, tab in (("b", sc_b), ("c", sc_c)):
            row = tab.get((tk, dt))
            if row:
                sc, s, nr = parse_score(row["content"])
                dr = thr(s)
                r.update({f"{arm}_score": num(s), f"{arm}_noRead": num(nr), f"{arm}_dir": num(dr),
                          f"{arm}_hit": num(None if not (dr and gt) else int(dr == gt)),
                          f"{arm}_completion_tokens": row["usage"]["output_tokens"], f"{arm}_stop": row["stop_reason"]})
                if arm == "c":
                    for k, v in sc.items():
                        if k not in ("score", "noRead"):
                            r[f"c_{k}"] = json.dumps(v) if isinstance(v, (list, dict)) else v
                            if f"c_{k}" not in c_keys:
                                c_keys.append(f"c_{k}")
        rows.append(r)
    return rows, c_keys


def cmd_calls():
    rows, c_keys = build_rows()
    base = ["ticker", "call_date", "stratum", "tier", "fwd_rel_ret_tradeable", "gt_old_ruler", "v6_rec", "v6_dir", "v6_hit",
            "b_score", "b_noRead", "b_dir", "b_hit", "b_completion_tokens", "b_stop",
            "c_score", "c_noRead", "c_dir", "c_hit", "c_completion_tokens", "c_stop"]
    cols = base + [k for k in c_keys if k not in base]
    with CALLS.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    print("wrote", CALLS, len(rows), "rows")
    # ---- reproduce the v6 train reference (with PARA: the exact published population), then PARA-adjusted
    prices = PriceCache(REPO / d.PRICE_CACHE_REL)
    p3.EXCLUDE = {"WOLF", "SPWR"}
    withp = {r["ticker"] for r in p3.all_train_records()}
    p3.EXCLUDE = set(d.EXCLUDE)
    recs = score_eval_dir(d.V6_EVAL_DIR, prices, tickers=sorted(withp))
    sc = [r for r in recs if r.ground_truth is not None]
    m = compute_luck_corrected_metrics(sc)
    bear = [r for r in sc if r.predicted == "bearish"]
    ref = {"population": "resolved train incl. PARA, excl. WOLF/SPWR", "n_gradable": len(sc),
           "accuracy_pct": m["observed_accuracy_pct"], "gap_pp": m["luck_corrected_gap_pp"],
           "bearish_calls": len(bear), "bearish_precision_pct": round(100 * sum(r.hit for r in bear) / max(len(bear), 1), 1)}
    sc2 = [r for r in sc if r.ticker != "PARA"]
    m2 = compute_luck_corrected_metrics(sc2)
    bear2 = [r for r in sc2 if r.predicted == "bearish"]
    adj = {"population": "PARA excluded (this run)", "n_gradable": len(sc2), "accuracy_pct": m2["observed_accuracy_pct"],
           "gap_pp": m2["luck_corrected_gap_pp"], "bearish_calls": len(bear2),
           "bearish_precision_pct": round(100 * sum(r.hit for r in bear2) / max(len(bear2), 1), 1),
           "n_para_gradable_removed": len(sc) - len(sc2)}
    # same numbers again from calls.csv (tradeable-independent old-ruler columns) to prove the file carries them
    g = [r for r in rows if r["v6_dir"] and r["gt_old_ruler"]]
    csv_acc = round(100 * sum(int(r["v6_hit"]) for r in g) / len(g), 1)
    out = {"published_reference": V6_REF, "reproduced_with_PARA": ref, "adjusted_ex_PARA": adj,
           "calls_csv_v6_accuracy_ex_PARA_pct": csv_acc, "calls_csv_n": len(g),
           "source_of_reference": "wrap-ups/scorer-price-cache-backfill-out.md (30.3% / +2.48); bearish 103 / 60.2% from the same corpus"}
    match = (ref["accuracy_pct"] == V6_REF["accuracy_pct"] and abs(ref["gap_pp"] - V6_REF["gap_pp"]) < 0.006
             and ref["bearish_calls"] == V6_REF["bearish_calls"] and abs(ref["bearish_precision_pct"] - V6_REF["bearish_precision_pct"]) < 0.06)
    out["match_with_PARA"] = match
    out["calls_csv_matches_scorer_ex_PARA"] = csv_acc == adj["accuracy_pct"]
    (STATE / "v6_reference_repro.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    if not (match and out["calls_csv_matches_scorer_ex_PARA"]):
        raise SystemExit("HARD STOP: v6 train reference does not reproduce beyond the PARA exclusion -- report")


# ------------------------------------------------------------------------------------------ stats helpers
def load_calls():
    out = []
    with CALLS.open() as f:
        for r in csv.DictReader(f):
            for k in ("fwd_rel_ret_tradeable", "b_score", "c_score"):
                r[k] = float(r[k]) if r[k] != "" else None
            for k in ("b_score", "c_score"):
                r[k] = None if r[k] is None else int(r[k])
            for k in ("b_noRead", "c_noRead"):
                r[k] = None if r[k] == "" else (r[k] == "True")
            out.append(r)
    return out


def rank(a):
    a = np.asarray(a, float)
    o = np.argsort(a, kind="mergesort")
    r = np.empty(len(a))
    r[o] = np.arange(len(a))
    for v in np.unique(a):                       # average ties
        m = a == v
        if m.sum() > 1:
            r[m] = r[m].mean()
    return r


def spearman(x, y):
    if len(x) < 3:
        return float("nan")
    rx, ry = rank(x), rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def by_ticker(rows):
    g = {}
    for r in rows:
        g.setdefault(r["ticker"], []).append(r)
    return g


def boot(rows, stat, B=BOOT_B, seed=SEED):
    """ticker-block bootstrap: resample companies, not calls. Returns (lo, hi, n_valid)."""
    g = list(by_ticker(rows).values())
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(B):
        pick = rng.integers(0, len(g), len(g))
        samp = [r for i in pick for r in g[i]]
        try:
            v = stat(samp)
        except Exception:
            v = float("nan")
        if v is not None and v == v:
            vals.append(v)
    if not vals:
        return (float("nan"), float("nan"), 0)
    vals.sort()
    return (vals[int(0.025 * len(vals))], vals[min(int(0.975 * len(vals)), len(vals) - 1)], len(vals))


def med(xs):
    return float(np.median(xs)) if len(xs) else float("nan")


def mean(xs):
    return float(np.mean(xs)) if len(xs) else float("nan")


def f(x, nd=2):
    return "n/a" if x is None or x != x else f"{x:.{nd}f}"


# ------------------------------------------------------------------------------------------ 6.1
def bucket_table(rows, arm):
    """per score bucket: n, median, mean fwd return (points vs S&P, tradeable entry), share beat >5 / lagged >5."""
    sk, nk = f"{arm}_score", f"{arm}_noRead"
    g = [r for r in rows if r[sk] is not None and r["fwd_rel_ret_tradeable"] is not None]
    out = []
    for s in range(-5, 6):
        for nr in ((None,) if s != 0 else (False, True)):
            xs = [r["fwd_rel_ret_tradeable"] for r in g if r[sk] == s and (nr is None or r[nk] == nr)]
            if not xs:
                continue
            out.append({"bucket": f"{s:+d}" + ("" if nr is None else (" noRead" if nr else " read-0")), "n": len(xs),
                        "median": med(xs), "mean": mean(xs),
                        "beat_gt5_pct": 100 * sum(x > 5 for x in xs) / len(xs), "lag_gt5_pct": 100 * sum(x < -5 for x in xs) / len(xs)})
    return out


def rank_stats(rows, arm, exclude_noread=False):
    sk, nk = f"{arm}_score", f"{arm}_noRead"
    g = [r for r in rows if r[sk] is not None and r["fwd_rel_ret_tradeable"] is not None and not (exclude_noread and r[nk])]

    def rho(rs):
        return spearman([r[sk] for r in rs], [r["fwd_rel_ret_tradeable"] for r in rs])

    def spread(rs):
        hi = [r["fwd_rel_ret_tradeable"] for r in rs if r[sk] >= 3]
        lo = [r["fwd_rel_ret_tradeable"] for r in rs if r[sk] <= -3]
        if not hi or not lo:
            return float("nan")
        return med(hi) - med(lo)

    hi = [r["fwd_rel_ret_tradeable"] for r in g if r[sk] >= 3]
    lo = [r["fwd_rel_ret_tradeable"] for r in g if r[sk] <= -3]
    return {"n": len(g), "rho": rho(g), "rho_range": boot(g, rho)[:2], "n_ge3": len(hi), "n_le_m3": len(lo),
            "spread": spread(g), "spread_range": boot(g, spread)}


def a_buckets(rows):
    out = {}
    g = [r for r in rows if r["v6_dir"] and r["fwd_rel_ret_tradeable"] is not None]
    for dr in ("bearish", "neutral", "bullish"):
        xs = [r["fwd_rel_ret_tradeable"] for r in g if r["v6_dir"] == dr]
        out[dr] = {"n": len(xs), "median": med(xs), "mean": mean(xs),
                   "beat_gt5_pct": 100 * sum(x > 5 for x in xs) / max(len(xs), 1),
                   "lag_gt5_pct": 100 * sum(x < -5 for x in xs) / max(len(xs), 1)}

    def spread(rs):
        hi = [r["fwd_rel_ret_tradeable"] for r in rs if r["v6_dir"] == "bullish"]
        lo = [r["fwd_rel_ret_tradeable"] for r in rs if r["v6_dir"] == "bearish"]
        return med(hi) - med(lo) if hi and lo else float("nan")

    out["spread_bullish_minus_bearish_median"] = spread(g)
    out["spread_range"] = boot(g, spread)
    return out


# ------------------------------------------------------------------------------------------ 6.3-6.4 helpers
def dir_of(r, arm):
    return r["v6_dir"] if arm == "A" else r[f"{arm.lower()}_dir"]


def records(rows, arm):
    return [CallRecord(ticker=r["ticker"], call_date=date.fromisoformat(r["call_date"]), predicted=dir_of(r, arm),
                       ground_truth=r["gt_old_ruler"], benchmark_rel_return=None, hit=(dir_of(r, arm) == r["gt_old_ruler"]),
                       always_bullish_hit=None) for r in rows if dir_of(r, arm) and r["gt_old_ruler"]]


def precision(rows, arm, dr):
    xs = [r for r in rows if dir_of(r, arm) == dr and r["gt_old_ruler"]]
    if not xs:
        return None
    return 100 * sum(r["gt_old_ruler"] == dr for r in xs) / len(xs), len(xs)


def money(rows, arm):
    g = [r for r in rows if dir_of(r, arm) and r["fwd_rel_ret_tradeable"] is not None]
    bear = [r["fwd_rel_ret_tradeable"] for r in g if dir_of(r, arm) == "bearish"]
    bull = [r["fwd_rel_ret_tradeable"] for r in g if dir_of(r, arm) == "bullish"]
    return {"n_calls": len(g), "n_bear": len(bear), "n_bull": len(bull),
            "bear_share_pct": 100 * len(bear) / max(len(g), 1), "bull_share_pct": 100 * len(bull) / max(len(g), 1),
            "bear_mean": mean(bear), "bear_median": med(bear), "bull_mean": mean(bull), "bull_median": med(bull),
            "swap_mean": mean(bull) - mean(bear) if bear and bull else float("nan"),
            "swap_median": med(bull) - med(bear) if bear and bull else float("nan")}


def flips(rows, arm, ref="A"):
    g = [r for r in rows if dir_of(r, arm) and dir_of(r, ref)]
    fl = [r for r in g if dir_of(r, arm) != dir_of(r, ref)]
    gr = [r for r in fl if r["gt_old_ruler"]]
    win = sum(dir_of(r, arm) == r["gt_old_ruler"] for r in gr)
    loss = sum(dir_of(r, ref) == r["gt_old_ruler"] for r in gr)
    return {"n_shared": len(g), "flips": len(fl), "graded_flips": len(gr), "wins": win, "losses": loss,
            "both_wrong": len(gr) - win - loss, "win_rate_of_flips_pct": 100 * win / max(len(gr), 1), "rows": fl}


def noise_arm(rows):
    """21a: v6 re-score vs its own cached v6 call, per S1-S5 stratum."""
    smap = p3.stratum_map()
    byk = {(r["ticker"], r["call_date"]): r for r in rows}
    out = {"per_stratum": {}, "pairs": []}
    for r in p3.read_jsonl(d.scores_path("N")):
        k = (r["ticker"], r["date"])
        if k not in byk:
            continue
        fresh = direction_from_score(parse_structured(r["content"]))
        old = byk[k]["v6_dir"]
        if not (fresh and old):
            continue
        gt = byk[k]["gt_old_ruler"]
        out["pairs"].append({"k": k, "stratum": smap[k[0]], "old": old, "fresh": fresh, "gt": gt,
                             "tokens": r["usage"]["output_tokens"]})
    P = out["pairs"]
    out["n"] = len(P)
    fl = [p for p in P if p["old"] != p["fresh"]]
    out["flips"] = len(fl)
    out["rate_pct"] = 100 * len(fl) / max(len(P), 1)
    out["rate_wilson"] = p3.wilson(len(fl), len(P)) if P else (float("nan"),) * 2
    gfl = [p for p in fl if p["gt"]]
    out["win_rate_pct"] = 100 * sum(p["fresh"] == p["gt"] for p in gfl) / max(len(gfl), 1)   # fresh call right
    out["win_n"] = len(gfl)
    out["loss_rate_pct"] = 100 * sum(p["old"] == p["gt"] for p in gfl) / max(len(gfl), 1)
    for s in sorted({p["stratum"] for p in P}):
        ps = [p for p in P if p["stratum"] == s]
        k = sum(p["old"] != p["fresh"] for p in ps)
        out["per_stratum"][s] = {"n": len(ps), "flips": k, "rate_pct": 100 * k / len(ps), "wilson": p3.wilson(k, len(ps))}
    return out


def net_count(rows, arm, noise):
    """flips of `arm` vs A, raw and net of 21a re-weighted to the train mix (per-stratum rate x stratum share)."""
    fl = flips(rows, arm)
    n_by_s = {}
    for r in rows:
        if dir_of(r, arm) and dir_of(r, "A"):
            n_by_s[r["stratum"]] = n_by_s.get(r["stratum"], 0) + 1
    tot = sum(n_by_s.values())
    overall = noise["rate_pct"] / 100
    exp = sum(n * noise["per_stratum"].get(s, {"rate_pct": noise["rate_pct"]})["rate_pct"] / 100 for s, n in n_by_s.items())
    lo, hi = noise["rate_wilson"][0] / 100 * tot, noise["rate_wilson"][1] / 100 * tot
    net = fl["flips"] - exp
    guard_ok = (fl["flips"] - exp) > 100 and (fl["flips"] - exp) > hi
    nwr = noise["win_rate_pct"] / 100
    gr, wins = fl["graded_flips"], fl["wins"]
    exp_g = exp * gr / max(fl["flips"], 1)              # noise flips among the graded flips
    netted_wr = (wins - exp_g * nwr) / (gr - exp_g) * 100 if gr - exp_g > 0 else float("nan")
    return {"raw": fl["flips"], "expected_noise_flips_reweighted": exp, "expected_noise_flips_overall_rate": overall * tot,
            "noise_count_range": (lo, hi), "net": net, "guard_passed_for_netted_win_rate": guard_ok,
            "raw_win_rate_pct": fl["win_rate_of_flips_pct"], "noise_win_rate_pct": noise["win_rate_pct"],
            "netted_win_rate_pct": netted_wr, "n_shared": tot,
            "netted_win_rate_label": "reportable" if guard_ok else "UNSTABLE, denominator too small -- not a headline"}


# ------------------------------------------------------------------------------------------ tests
def cmd_tests():
    rows = load_calls()
    R = {"n_calls": len(rows), "n_priced": sum(r["fwd_rel_ret_tradeable"] is not None for r in rows)}
    L = []                                              # markdown report lines
    P = L.append
    P(f"# P6 tests report ($0). Train, WOLF/SPWR/PARA excluded. {R['n_calls']} calls, {R['n_priced']} with a 182-day tradeable-entry return.\n")
    # ---- 6.1
    P("## 6.1 Rank-ordering (tradeable entry, 182 days, points vs S&P; ticker-block bootstrap 95% range)\n")
    R["A_buckets"] = a_buckets(rows)
    P("**Arm A (v6), three buckets:**\n\n| bucket | n | median | mean | beat >5 % | lag >5 % |\n|---|---|---|---|---|---|")
    for k in ("bearish", "neutral", "bullish"):
        b = R["A_buckets"][k]
        P(f"| {k} | {b['n']} | {f(b['median'])} | {f(b['mean'])} | {f(b['beat_gt5_pct'],1)} | {f(b['lag_gt5_pct'],1)} |")
    sp = R["A_buckets"]["spread_range"]
    P(f"\nA best-minus-worst (median bullish minus median bearish): {f(R['A_buckets']['spread_bullish_minus_bearish_median'])} points "
      f"(range {f(sp[0])} to {f(sp[1])}).\n")
    for arm in ("b", "c"):
        tab = bucket_table(rows, arm)
        st = rank_stats(rows, arm)
        st2 = rank_stats(rows, arm, exclude_noread=True)
        R[f"{arm}_buckets"], R[f"{arm}_rank"], R[f"{arm}_rank_ex_noread"] = tab, st, st2
        P(f"**Arm {arm.upper()} score buckets:**\n\n| bucket | n | median | mean | beat >5 % | lag >5 % |\n|---|---|---|---|---|---|")
        for b in tab:
            P(f"| {b['bucket']} | {b['n']} | {f(b['median'])} | {f(b['mean'])} | {f(b['beat_gt5_pct'],1)} | {f(b['lag_gt5_pct'],1)} |")
        P(f"\nArm {arm.upper()}: Spearman rank correlation **{f(st['rho'],3)}** (range {f(st['rho_range'][0],3)} to {f(st['rho_range'][1],3)}), n={st['n']}; "
          f"excluding noRead {f(st2['rho'],3)} ({f(st2['rho_range'][0],3)} to {f(st2['rho_range'][1],3)}). "
          f"Top-minus-bottom spread (median of score >= +3 minus median of score <= -3): **{f(st['spread'])}** points "
          f"(range {f(st['spread_range'][0])} to {f(st['spread_range'][1])}; {st['spread_range'][2]}/{BOOT_B} valid draws); n(>=+3)={st['n_ge3']}, n(<=-3)={st['n_le_m3']}.\n")
    # ---- 6.2
    P("## 6.2 The neutral pile\n")
    scored = [r for r in rows if r["v6_dir"]]
    a_share = 100 * sum(r["v6_dir"] == "neutral" for r in scored) / len(scored)
    R["neutral_share"] = {"A": a_share}
    gt_n = [r for r in rows if r["gt_old_ruler"]]
    base = {k: 100 * sum(r["gt_old_ruler"] == k for r in gt_n) / len(gt_n) for k in ("bearish", "neutral", "bullish")}
    R["base_rates_this_population"] = base
    P(f"Base rates in this population (old ruler, arm-A entry, n={len(gt_n)}): " + ", ".join(f"{k} {v:.1f}%" for k, v in base.items()) +
      f" (prompt reference: {BASE}).\n")
    for arm in ("b", "c"):
        g = [r for r in rows if r[f"{arm}_dir"]]
        sh = 100 * sum(r[f"{arm}_dir"] == "neutral" for r in g) / max(len(g), 1)
        nr = 100 * sum(r[f"{arm}_noRead"] is True for r in g) / max(len(g), 1)
        weak = 100 * sum(r[f"{arm}_score"] in (-1, 1) for r in g) / max(len(g), 1)
        z_read = 100 * sum(r[f"{arm}_score"] == 0 and r[f"{arm}_noRead"] is False for r in g) / max(len(g), 1)
        R["neutral_share"][arm.upper()] = {"neutral_pct": sh, "noRead_pct": nr, "weak_pm1_pct": weak, "read_zero_pct": z_read, "n": len(g)}
        P(f"- Arm {arm.upper()}: neutral share {sh:.1f}% vs A {a_share:.1f}%; of which noRead {nr:.1f}%, weak (+/-1) {weak:.1f}%, score 0 with a read {z_read:.1f}% (n={len(g)}).")
    P("")
    for arm, nm in (("A", "A neutral"), ("c", "C neutral"), ("b", "B neutral")):
        gg = [r for r in rows if dir_of(r, arm.upper() if arm != "A" else "A") == "neutral" and r["gt_old_ruler"]]
        if gg:
            h = 100 * sum(r["gt_old_ruler"] == "neutral" for r in gg) / len(gg)
            R.setdefault("neutral_edge", {})[arm.upper()] = {"n": len(gg), "hit_pct": h, "base_pct": base["neutral"], "edge": h - base["neutral"]}
            P(f"- {nm} bucket: n={len(gg)}, share of calls that really were neutral {h:.1f}% vs base {base['neutral']:.1f}% -> edge {h - base['neutral']:+.1f}.")
    P("")
    for arm in ("C", "B"):
        moved = [r for r in rows if r["v6_dir"] == "neutral" and dir_of(r, arm) in ("bearish", "bullish")]
        gmv = [r for r in moved if r["gt_old_ruler"]]

        def pooled(rs, arm=arm):
            rs = [r for r in rs if r["gt_old_ruler"]]
            if not rs:
                return float("nan")
            return sum((r["gt_old_ruler"] == dir_of(r, arm)) - base[dir_of(r, arm)] / 100 for r in rs) / len(rs) * 100
        pe = pooled(moved)
        pr = boot(moved, pooled)
        det = {}
        for dr in ("bearish", "bullish"):
            xs = [r for r in gmv if dir_of(r, arm) == dr]
            fw = [r["fwd_rel_ret_tradeable"] for r in xs if r["fwd_rel_ret_tradeable"] is not None]
            det[dr] = {"n": len(xs), "hit_pct": 100 * sum(r["gt_old_ruler"] == dr for r in xs) / max(len(xs), 1), "base": base[dr],
                       "median_fwd": med(fw), "mean_fwd": mean(fw)}
        R.setdefault("moved_out_of_neutral", {})[arm] = {"n_A_neutral": sum(r["v6_dir"] == "neutral" for r in rows if dir_of(r, arm)),
                                                          "n_moved": len(moved), "pooled_edge": pe, "pooled_edge_range": pr[:2], "by_dir": det}
        P(f"**Arm {arm}: {len(moved)} of {R['moved_out_of_neutral'][arm]['n_A_neutral']} of A's neutral (Hold) calls left neutral.** "
          f"Pooled edge (hit rate minus each direction's own base rate) {pe:+.1f} points (range {f(pr[0],1)} to {f(pr[1],1)}). "
          + "; ".join(f"{k}: n={v['n']}, hit {v['hit_pct']:.1f}% vs base {v['base']:.1f}%, median return {f(v['median_fwd'])}, mean {f(v['mean_fwd'])}" for k, v in det.items()) + ".\n")
    # ---- 6.3
    P("## 6.3 Old ruler (fixed thresholds): accuracy, precision, flips\n")
    noise = noise_arm(rows)
    R["noise"] = {k: v for k, v in noise.items() if k != "pairs"}
    R["old_ruler"] = {}
    P("| arm | n graded | accuracy % | luck % | gap (pp) | bearish calls | bearish precision % (base 46.6) | bullish calls | bullish precision % (base 32.8) |\n|---|---|---|---|---|---|---|---|---|")
    for arm in ("A", "B", "C"):
        rc = records(rows, arm)
        m = compute_luck_corrected_metrics(rc)
        pb, pu = precision(rows, arm, "bearish"), precision(rows, arm, "bullish")
        R["old_ruler"][arm] = {"n": len(rc), **m, "bear": pb, "bull": pu}
        P(f"| {arm} | {len(rc)} | {m['observed_accuracy_pct']} | {m['expected_by_luck_pct']} | {m['luck_corrected_gap_pp']:+} | "
          f"{pb[1] if pb else 0} | {f(pb[0],1) if pb else 'n/a'} | {pu[1] if pu else 0} | {f(pu[0],1) if pu else 'n/a'} |")
    P("")
    P(f"**Noise arm (21a: v6 re-scored vs its own cached call):** n={noise['n']}, disagreement {noise['flips']} ({noise['rate_pct']:.1f}%, Wilson {noise['rate_wilson'][0]:.1f} to {noise['rate_wilson'][1]:.1f}); "
      f"fresh call right in {noise['win_rate_pct']:.1f}% of graded noise flips (n={noise['win_n']}), cached call right in {noise['loss_rate_pct']:.1f}%. Per stratum:\n")
    P("| stratum | n | flips | rate % | Wilson |\n|---|---|---|---|---|")
    for s, v in noise["per_stratum"].items():
        P(f"| {s} | {v['n']} | {v['flips']} | {v['rate_pct']:.1f} | {v['wilson'][0]:.1f} to {v['wilson'][1]:.1f} |")
    outl = [s for s, v in noise["per_stratum"].items() if v["wilson"][1] < noise["rate_pct"] or v["wilson"][0] > noise["rate_pct"]]
    P(f"\nStrata whose range excludes the overall rate ({noise['rate_pct']:.1f}%): {outl or 'none'}.\n")
    R["noise"]["strata_excluding_overall"] = outl
    P("**Flips against A, raw and net (netting rule, findings.md):**\n\n| arm | shared calls | raw flips | expected noise flips (21a, re-weighted) | net | noise-count range | flip win rate raw % | noise win rate % | netted win rate |\n|---|---|---|---|---|---|---|---|---|")
    R["flips"] = {}
    for arm in ("B", "C"):
        nc = net_count(rows, arm, noise)
        fl = flips(rows, arm)
        R["flips"][arm] = {**nc, "wins": fl["wins"], "losses": fl["losses"], "both_wrong": fl["both_wrong"], "graded_flips": fl["graded_flips"]}
        P(f"| {arm} | {nc['n_shared']} | {nc['raw']} | {nc['expected_noise_flips_reweighted']:.0f} | {nc['net']:.0f} | {nc['noise_count_range'][0]:.0f} to {nc['noise_count_range'][1]:.0f} | "
          f"{nc['raw_win_rate_pct']:.1f} | {nc['noise_win_rate_pct']:.1f} | {f(nc['netted_win_rate_pct'],1)} ({nc['netted_win_rate_label']}) |")
    P("\nCaveat (netting rule): noise flips and real flips are not disjoint; the subtraction assumes independence and no overlap.\n")
    # ---- 6.4
    P("## 6.4 Money (tradeable entry, 182 days, points vs S&P)\n")
    P("Reference rows in the prompt (bearish 7.4% of calls, edge +12.3, median -10.09%; bullish 34.3%, +4.4, -1.43%; swap +2.4 mean / +8.7 median) are pooled TRAIN+TUNE (2,385 calls) -- they will not match a train-only A row.\n")
    P("| arm | bearish share % | bearish mean | bearish median | bullish share % | bullish mean | bullish median | swap mean | swap median |\n|---|---|---|---|---|---|---|---|---|")
    R["money"] = {}
    for arm in ("A", "B", "C"):
        m = money(rows, arm)
        R["money"][arm] = {"all": m}
        P(f"| {arm} | {m['bear_share_pct']:.1f} | {f(m['bear_mean'])} | {f(m['bear_median'])} | {m['bull_share_pct']:.1f} | {f(m['bull_mean'])} | {f(m['bull_median'])} | {f(m['swap_mean'])} | {f(m['swap_median'])} |")
    P("")
    for arm in ("A", "B", "C"):
        for nm, fn in (("swap_mean", lambda rs, a=arm: money(rs, a)["swap_mean"]), ("swap_median", lambda rs, a=arm: money(rs, a)["swap_median"])):
            lo, hi, nv = boot(rows, fn)
            R["money"][arm][nm + "_range"] = (lo, hi)
        P(f"Arm {arm} swap range: mean {f(R['money'][arm]['swap_mean_range'][0])} to {f(R['money'][arm]['swap_mean_range'][1])}; median {f(R['money'][arm]['swap_median_range'][0])} to {f(R['money'][arm]['swap_median_range'][1])}.")
    P("\n**Per stratum (S1-S5) and 2020 vs the rest:**\n\n| slice | arm | n | bearish n | bearish median | bullish n | bullish median | swap median |\n|---|---|---|---|---|---|---|---|")
    slices = [(s, [r for r in rows if r["stratum"] == s]) for s in sorted({r["stratum"] for r in rows})]
    slices += [("2020", [r for r in rows if r["call_date"][:4] == "2020"]), ("ex-2020", [r for r in rows if r["call_date"][:4] != "2020"])]
    for nm, rs in slices:
        for arm in ("A", "B", "C"):
            m = money(rs, arm)
            R["money"][arm][nm] = m
            P(f"| {nm} | {arm} | {m['n_calls']} | {m['n_bear']} | {f(m['bear_median'])} | {m['n_bull']} | {f(m['bull_median'])} | {f(m['swap_median'])} |")
    # ---- 6.5
    P("\n## 6.5 Diagnostics\n")
    both = [r for r in rows if r["b_score"] is not None and r["c_score"] is not None]
    rbc = spearman([r["b_score"] for r in both], [r["c_score"] for r in both])
    R["bc_corr"] = {"rho": rbc, "range": boot(both, lambda rs: spearman([r["b_score"] for r in rs], [r["c_score"] for r in rs]))[:2], "n": len(both)}
    P(f"- **B vs C score agreement:** Spearman {rbc:.3f} (range {R['bc_corr']['range'][0]:.3f} to {R['bc_corr']['range'][1]:.3f}), n={len(both)}.")
    dis = [r for r in both if abs(r["b_score"] - r["c_score"]) >= 3 and r["fwd_rel_ret_tradeable"] is not None]
    sgn = lambda x: (x > 0) - (x < 0)
    bw = sum(sgn(r["b_score"]) == sgn(r["fwd_rel_ret_tradeable"]) != 0 and sgn(r["c_score"]) != sgn(r["fwd_rel_ret_tradeable"]) for r in dis)
    cw = sum(sgn(r["c_score"]) == sgn(r["fwd_rel_ret_tradeable"]) != 0 and sgn(r["b_score"]) != sgn(r["fwd_rel_ret_tradeable"]) for r in dis)
    R["disagree3"] = {"n": len(dis), "B_right": bw, "C_right": cw, "neither_or_both": len(dis) - bw - cw}
    P(f"- **Disagree by >=3 points:** {len(dis)} calls; only B's sign matches the realized return in {bw}, only C's in {cw}, neither/both {len(dis)-bw-cw} (sign of tradeable-entry return).")
    intact_none = [r for r in rows if r.get("c_thesisHealth") == "Intact" and str(r.get("c_stumbleType", "")).strip('"').lower() in ("none", "null", "")]
    xt = {}
    for r in rows:
        if r["c_score"] is not None:
            xt.setdefault((r.get("c_thesisHealth", "?"), r.get("c_stumbleType", "?")), []).append(r["c_score"])
    R["c_crosstab"] = {f"{h}|{s}": {"n": len(v), "median": statistics.median(v), "share_in_pm1": 100 * sum(-1 <= x <= 1 for x in v) / len(v)} for (h, s), v in xt.items()}
    P("- **What the rubric did (arm C score by thesisHealth x stumbleType):**\n\n| thesisHealth | stumbleType | n | median score | share in {-1,0,+1} % |\n|---|---|---|---|---|")
    for (h, s), v in sorted(xt.items(), key=lambda t: -len(t[1])):
        P(f"| {h} | {s} | {len(v)} | {statistics.median(v):g} | {100*sum(-1 <= x <= 1 for x in v)/len(v):.1f} |")
    inn = [r["c_score"] for r in rows if r["c_score"] is not None and r.get("c_thesisHealth") == "Intact" and str(r.get("c_stumbleType")).strip('"').lower() == "none"]
    R["intact_none"] = {"n": len(inn), "share_in_pm1_pct": 100 * sum(-1 <= x <= 1 for x in inn) / max(len(inn), 1)}
    P(f"\n  Intact + None: n={len(inn)}, {R['intact_none']['share_in_pm1_pct']:.1f}% score in {{-1,0,+1}} (100% would mean the matrix is being reproduced from habit).")
    tokB = [int(r["b_completion_tokens"]) for r in rows if r.get("b_completion_tokens") not in ("", None)]
    tokC = [int(r["c_completion_tokens"]) for r in rows if r.get("c_completion_tokens") not in ("", None)]
    tokN = [p["tokens"] for p in noise["pairs"]]
    R["tokens"] = {"B_median": med(tokB), "C_median": med(tokC), "v6_noise_median": med(tokN)}
    P(f"- **Length (median completion tokens):** B {med(tokB):.0f}, C {med(tokC):.0f}, v6 (from the {len(tokN)} noise re-scores) {med(tokN):.0f}.")
    # Q2 re-run: score as a strength axis inside C's bearish bucket. Axis prediction is written in findings.md BEFORE this runs.
    bb = [r for r in rows if r["c_dir"] == "bearish" and r["gt_old_ruler"]]
    if bb:
        cut = statistics.median([r["c_score"] for r in bb])
        strong = [r for r in bb if r["c_score"] < cut] or [r for r in bb if r["c_score"] <= cut]
        weak = [r for r in bb if r not in strong]
        pr = lambda rs: 100 * sum(r["gt_old_ruler"] == "bearish" for r in rs) / max(len(rs), 1)

        def dd(rs, cut=cut):
            s = [r for r in rs if r["c_score"] < cut] or [r for r in rs if r["c_score"] <= cut]
            w = [r for r in rs if r not in s]
            return pr(s) - pr(w) if s and w else float("nan")
        rng = boot(bb, dd)
        rr = spearman([r["c_score"] for r in bb if r["fwd_rel_ret_tradeable"] is not None], [r["fwd_rel_ret_tradeable"] for r in bb if r["fwd_rel_ret_tradeable"] is not None])
        R["q2"] = {"n": len(bb), "cut": cut, "strong_n": len(strong), "weak_n": len(weak), "strong_prec": pr(strong), "weak_prec": pr(weak),
                   "diff": pr(strong) - pr(weak), "diff_range": rng[:2], "rho_within": rr}
        P(f"- **Q2 re-run (discovery only):** inside C's bearish bucket (n={len(bb)}), split at median score {cut}: stronger half (n={len(strong)}) precision {pr(strong):.1f}% vs weaker (n={len(weak)}) {pr(weak):.1f}% -> difference {pr(strong)-pr(weak):+.1f} points (range {f(rng[0],1)} to {f(rng[1],1)}); Spearman of score vs return within the bucket {f(rr,3)}.")
    # per-call diffs to disk
    with (STATE / "per_call_diffs.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ticker", "call_date", "stratum", "v6_dir", "b_score", "b_dir", "c_score", "c_dir", "gt_old_ruler", "fwd_rel_ret_tradeable"])
        for r in rows:
            if len({x for x in (r["v6_dir"], r["b_dir"], r["c_dir"]) if x}) > 1:
                w.writerow([r["ticker"], r["call_date"], r["stratum"], r["v6_dir"], num(r["b_score"]), r["b_dir"], num(r["c_score"]), r["c_dir"], r["gt_old_ruler"], num(r["fwd_rel_ret_tradeable"])])
    (STATE / "results.json").write_text(json.dumps(R, indent=1, default=str))
    (STATE / "tests_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"calls": cmd_calls, "tests": cmd_tests}.get(cmd, lambda: print(__doc__))()
