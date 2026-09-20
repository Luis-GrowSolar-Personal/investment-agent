#!/usr/bin/env python3
"""
disaster_profile_driver.py -- prompts/disaster-profile-test.md (run disaster-profile-test)

$0. No model calls. Population: v6's 187 bearish calls (train + tune, WOLF/SPWR excluded) with a graded
182-day TRADEABLE return: entry = close of the first trading day strictly after the call date;
end = close on/after (call date + 182 days); benchmark-relative (stock minus SPY, same dates).

Targets (fixed before looking):
  T1 worst quartile of the pooled 187 by return (46 calls), a fixed cut applied to both splits
  T2 return below -25% (lagged the S&P by more than 25 points)

Features (binary "flagged" bucket, predicted direction = flagged bucket has MORE disasters), fixed in the pre-registration:
  F1 stratum S4 (failures stratum)           F2 thesisHealth != Intact (Weakening/Broken)
  F3 stumbleType == Structural               F4 threatMechanismImpaired == True
  F5 blind spots flagged >= 1                F6 recommendedSize <= pooled median (deeper cut)
  F7 >=1 immediately preceding bearish call  F8 call year >= 2023 (control)
  F9 prior-90-day benchmark-relative return below the pooled median (control); window = first close on/after (d-90)
     to the last close strictly BEFORE the call date (so it is knowable at the call)

  python3 disaster_profile_driver.py premise | run | loco
"""
import sys, json, csv
from datetime import timedelta, date
from pathlib import Path
from collections import defaultdict
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))
import r4_horizon_driver as r4  # noqa
from analyst_direct_scorer import PriceCache  # noqa

RUN = REPO / "analysis/data/run_state/disaster-profile-test"
JOINED = REPO / "analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv"
HORIZON, SEED, B, T2 = 182, 11, 2000, -0.25
FEATURES = [("F8", "year >= 2023 (control)"), ("F9", "prior-90d return below median (control)"),
            ("F1", "stratum S4"), ("F2", "thesisHealth Weakening/Broken"), ("F3", "stumbleType Structural"),
            ("F4", "mechanism impaired"), ("F5", "blind spots >= 1"), ("F6", "recommendedSize <= median"),
            ("F7", "prior call also bearish")]


def prev_close(prices, tk, d):
    days = prices._data.get(tk, {})
    for i in range(1, 8):
        k = (d - timedelta(days=i)).isoformat()
        if k in days:
            return days[k]
    return None


def stratum_map():
    sp = json.loads(r4.SPLIT.read_text())
    a = r4.alias_map()
    m = {}
    for s, dd in sp["per_stratum"].items():
        for split in ("train", "tune"):
            for t in dd[split]:
                m[a.get(t, t)] = s
                m[t] = s
    return m


def build():
    prices = PriceCache(r4.PRICE_CACHE)
    smap = stratum_map()
    feat = {}
    with JOINED.open() as f:
        for r in csv.DictReader(f):
            feat[(r["split"], r["ticker"], r["call_date"])] = r
    cases = []
    for split in ("train", "tune"):
        by = defaultdict(list)
        for tk, d, p in r4.load_calls(split):
            by[tk].append((d, p))
        for tk, l in by.items():
            l.sort()
            chain = 0
            for i, (d, p) in enumerate(l):
                if p == "bearish":
                    fr = feat.get((split, tk, d.isoformat()))
                    pe, _ = prices.price_on_or_after(tk, d + timedelta(days=1))
                    be, _ = prices.price_on_or_after(r4.BENCH, d + timedelta(days=1))
                    p1, _ = prices.price_on_or_after(tk, d + timedelta(days=HORIZON))
                    b1, _ = prices.price_on_or_after(r4.BENCH, d + timedelta(days=HORIZON))
                    ps, _ = prices.price_on_or_after(tk, d - timedelta(days=90))
                    bs, _ = prices.price_on_or_after(r4.BENCH, d - timedelta(days=90))
                    pp, bp = prev_close(prices, tk, d), prev_close(prices, r4.BENCH, d)
                    if fr and all([pe, be, p1, b1]):
                        prior = ((pp / ps - 1) - (bp / bs - 1)) if all([ps, bs, pp, bp]) else None
                        try:
                            rs = float(fr["recommendedSize"])
                        except (ValueError, TypeError):
                            rs = None
                        cases.append({"split": split, "ticker": tk, "date": d.isoformat(), "year": d.year,
                                      "ret": (p1 / pe - 1) - (b1 / be - 1), "stratum": smap.get(tk),
                                      "thesisHealth": fr["thesisHealth"], "stumbleType": fr["stumbleType"],
                                      "mech": fr["threatMechanismImpaired"], "blind": int(fr["blindSpotsTriggered_count"] or 0),
                                      "size": rs, "chain": chain, "prior90": prior})
                chain = chain + 1 if p == "bearish" else 0
    return cases


def flags(cases):
    sizes = [c["size"] for c in cases if c["size"] is not None]
    priors = [c["prior90"] for c in cases if c["prior90"] is not None]
    med_size, med_prior = float(np.median(sizes)), float(np.median(priors))
    for c in cases:
        c["F"] = {
            "F1": c["stratum"] == "S4",
            "F2": c["thesisHealth"] in ("Weakening", "Broken"),
            "F3": c["stumbleType"] == "Structural",
            "F4": str(c["mech"]).lower() == "true",
            "F5": c["blind"] >= 1,
            "F6": (c["size"] is not None and c["size"] <= med_size),
            "F7": c["chain"] >= 1,
            "F8": c["year"] >= 2023,
            "F9": (c["prior90"] is not None and c["prior90"] < med_prior),
        }
    return {"median_recommendedSize": med_size, "median_prior90": med_prior}


def targets(cases, cut=None):
    r = np.array([c["ret"] for c in cases])
    n1 = len(cases) // 4
    thr1 = np.sort(r)[n1 - 1] if cut is None else cut
    for c in cases:
        c["T1"] = c["ret"] <= thr1
        c["T2"] = c["ret"] < T2
    return float(thr1), n1


def diff_stats(cases, fk, tk_):
    """call-level and company-level difference in disaster rate, flagged minus unflagged."""
    def rate(g):
        return np.mean([c[tk_] for c in g]) if g else np.nan
    fl = [c for c in cases if c["F"][fk]]
    un = [c for c in cases if not c["F"][fk]]
    call = 100 * (rate(fl) - rate(un)) if fl and un else np.nan
    def comp(g):
        by = defaultdict(list)
        for c in g:
            by[c["ticker"]].append(c[tk_])
        return np.mean([np.mean(v) for v in by.values()]) if by else np.nan
    company = 100 * (comp(fl) - comp(un)) if fl and un else np.nan
    return call, company, rate(fl) * 100, rate(un) * 100, len(fl), len(un)


def boot_diff(cases, fk, tk_, seed=SEED):
    tks = sorted({c["ticker"] for c in cases})
    by = {t: [c for c in cases if c["ticker"] == t] for t in tks}
    rng = np.random.default_rng(seed)
    call_d, comp_d = [], []
    for _ in range(B):
        samp = [by[tks[i]] for i in rng.integers(0, len(tks), size=len(tks))]
        g = [c for s in samp for c in s]
        # per-company rates need the multiset of companies
        cf = [np.mean([c[tk_] for c in s if c["F"][fk]]) for s in samp if any(c["F"][fk] for c in s)]
        cu = [np.mean([c[tk_] for c in s if not c["F"][fk]]) for s in samp if any(not c["F"][fk] for c in s)]
        fl = [c[tk_] for c in g if c["F"][fk]]
        un = [c[tk_] for c in g if not c["F"][fk]]
        if fl and un:
            call_d.append(100 * (np.mean(fl) - np.mean(un)))
        if cf and cu:
            comp_d.append(100 * (np.mean(cf) - np.mean(cu)))
    q = lambda v: [round(float(np.percentile(v, 2.5)), 1), round(float(np.percentile(v, 97.5)), 1)] if v else None
    return q(call_d), q(comp_d)


def load_cases(excl=()):
    cases = [c for c in build() if c["ticker"] not in excl]
    info = flags(cases)
    return cases, info


def cmd_premise():
    cases, info = load_cases()
    thr, n1 = targets(cases)
    r = np.array([c["ret"] for c in cases])
    t1 = [c for c in cases if c["T1"]]
    t2 = [c for c in cases if c["T2"]]
    print(f"bearish calls with graded tradeable return: {len(cases)} (train {sum(c['split']=='train' for c in cases)}, tune {sum(c['split']=='tune' for c in cases)})")
    print(f"mean return {100*r.mean():.1f}%, median {100*np.median(r):.1f}%")
    print(f"T1 worst quartile: n={len(t1)} cut {100*thr:.1f}% mean {100*np.mean([c['ret'] for c in t1]):.1f}%  companies {len({c['ticker'] for c in t1})}")
    cnt = defaultdict(int)
    for c in t1:
        cnt[c["ticker"]] += 1
    print("  by company:", sorted(cnt.items(), key=lambda x: -x[1]))
    print("  PARA+SUNW+SEDG:", sum(cnt[t] for t in ("PARA", "SUNW", "SEDG")), "| 2023-25:", sum(c["year"] >= 2023 for c in t1),
          "| train/tune:", sum(c["split"] == "train" for c in t1), sum(c["split"] == "tune" for c in t1))
    print(f"T2 (< -25%): n={len(t2)} companies {len({c['ticker'] for c in t2})}")
    print("medians (features only):", info)
    print("missing feature counts: size", sum(c['size'] is None for c in cases), "prior90", sum(c['prior90'] is None for c in cases), "stratum", sum(c['stratum'] is None for c in cases))
    (RUN / "premise.json").write_text(json.dumps({"n": len(cases), "T1": {"n": len(t1), "cut": thr, "mean": float(np.mean([c['ret'] for c in t1])),
                                                 "companies": len({c['ticker'] for c in t1}), "by_company": dict(cnt)},
                                                 "T2": {"n": len(t2)}, "info": info}, indent=1))


def evaluate(cases, label, write=True):
    """Nine features x 2 targets x (train, tune, pooled); returns rows and the conditions table."""
    thr, n1 = targets(cases)
    rows, table = [], {}
    for fk, desc in FEATURES:
        conds = {}
        detail = {}
        for tk_ in ("T1", "T2"):
            res = {}
            for split in ("train", "tune", "pooled"):
                sub = cases if split == "pooled" else [c for c in cases if c["split"] == split]
                call, comp, fr, ur, nf, nu = diff_stats(sub, fk, tk_)
                ci_call, ci_comp = boot_diff(sub, fk, tk_)
                res[split] = {"call_diff": None if np.isnan(call) else round(float(call), 1), "company_diff": None if np.isnan(comp) else round(float(comp), 1),
                              "flagged_rate": round(float(fr), 1), "unflagged_rate": round(float(ur), 1), "n_flagged": nf, "n_unflagged": nu,
                              "call_ci": ci_call, "company_ci": ci_comp}
            detail[tk_] = res
            tr, tu, po = res["train"], res["tune"], res["pooled"]
            c1 = tr["call_diff"] is not None and tr["call_diff"] > 0 and tr["call_ci"] and tr["call_ci"][0] > 0
            c2 = tu["call_diff"] is not None and tu["call_diff"] > 0
            c3 = (tr["company_diff"] or -1) > 0 and (tu["company_diff"] or -1) > 0 and po["company_ci"] is not None and po["company_ci"][0] > 0
            conds[tk_] = (bool(c1), bool(c2), bool(c3))
        c4 = conds["T1"][0] and conds["T2"][0]
        met = {"train_sep": all(conds[t][0] for t in ("T1", "T2")), "tune_same_dir": all(conds[t][1] for t in ("T1", "T2")),
               "per_company": all(conds[t][2] for t in ("T1", "T2")), "both_targets": all(all(conds[t]) for t in ("T1", "T2"))}
        met["ALL_FOUR"] = met["train_sep"] and met["tune_same_dir"] and met["per_company"] and met["both_targets"]
        table[fk] = {"desc": desc, "conditions": met, "by_target": conds}
        rows.append({"label": label, "feature": fk, "desc": desc, "detail": detail, "conditions": met})
    if write:
        with (RUN / "cells.jsonl").open("a") as f:
            for r_ in rows:
                f.write(json.dumps(r_) + "\n"); f.flush()
    return rows, table, thr, n1


def cmd_run():
    (RUN / "cells.jsonl").exists() and (RUN / "cells.jsonl").unlink()
    for label, excl in (("with_PARA", ()), ("without_PARA", ("PARA",))):
        cases, info = load_cases(excl)
        rows, table, thr, n1 = evaluate(cases, label)
        print(f"==== {label}: n={len(cases)} T1 n={n1} cut {100*thr:.1f}% T2 n={sum(c['T2'] for c in cases)}")
        for r_ in rows:
            d = r_["detail"]
            def s(t, sp):
                x = d[t][sp]
                return f"{x['call_diff']:+.1f}{x['call_ci']}|co {x['company_diff']:+.1f}" if x['call_diff'] is not None else "n/a"
            print(f"{r_['feature']} {r_['desc'][:34]:34} T1 tr {s('T1','train')} tu {s('T1','tune')} | T2 tr {s('T2','train')} tu {s('T2','tune')} | {r_['conditions']}")


def cmd_loco():
    """Leave-one-company-out for the strongest analyst feature (F2-F7) by pooled call-level T1 difference, plus any ALL_FOUR feature."""
    out = {}
    for label, excl in (("with_PARA", ()), ("without_PARA", ("PARA",))):
        cases, info = load_cases(excl)
        thr, n1 = targets(cases)
        pooled = {}
        for fk, _ in FEATURES:
            pooled[fk] = diff_stats(cases, fk, "T1")[0]
        cand = [fk for fk in ("F2", "F3", "F4", "F5", "F6", "F7") if not np.isnan(pooled[fk])]
        best = max(cand, key=lambda k: pooled[k])
        overall = max(pooled, key=lambda k: pooled[k])
        dis_cos = sorted({c["ticker"] for c in cases if c["T1"]})
        res = {}
        for fk in {best, overall}:
            vals = []
            for co in dis_cos:
                sub = [c for c in cases if c["ticker"] != co]
                t_, _ = targets(sub, cut=thr)  # keep the fixed T1 line so dropping a company does not move the target
                vals.append((round(float(diff_stats(sub, fk, "T1")[0]), 1), co))
            v = [x for x, _ in vals]
            res[fk] = {"full_sample": round(float(pooled[fk]), 1), "min": min(vals), "max": max(vals), "n_companies": len(dis_cos),
                       "all": vals}
            print(f"[{label}] LOCO {fk} ({dict(FEATURES)[fk]}): full {pooled[fk]:.1f} | range {min(v):.1f} (drop {min(vals)[1]}) to {max(v):.1f} (drop {max(vals)[1]}) over {len(dis_cos)} companies")
        out[label] = {"pooled_call_diff_T1": {k: (None if np.isnan(v) else round(float(v), 1)) for k, v in pooled.items()}, "best_analyst_feature": best,
                      "strongest_overall": overall, "loco": res}
    (RUN / "loco.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"premise": cmd_premise, "run": cmd_run, "loco": cmd_loco}.get((sys.argv[1:] or [""])[0], lambda: print(__doc__))()
