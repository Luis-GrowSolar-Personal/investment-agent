#!/usr/bin/env python3
"""
per_trim_value.py -- prompts/per-trim-value.md ($0, no model calls, no DB writes, no cache refresh).

Per-trim value of B's bearish flags (score <= -2), against a no-skill,
calendar-quarter-matched control. Reuses PriceCache / p_after / rel_ret from
r4b_tradeable_entry_driver and spearman / boot / load_calls from
p6_output_format_analysis (import, do not fork).

Definitions (fixed by the prompt):
  value(row, D, s) = s * (D_ret_pct - name_ret_pct) / 100   [points of the book]
Row A: B's flagged calls (score <= -2), draw 1 / draw 2 / pooled (stacked, a call
  flagged on both draws appears twice).
Row B matched: for each call in A, the average per-trim value over every priced
  train call in the same calendar quarter (flagged or not), same destination/size.
Row B unmatched: average per-trim value over every priced train call (reference only).
A - B: Row A mean minus Row B matched mean.
Ranges: 95% ticker-block bootstrap, 2000 draws, seed 11; A, the quarter averages
  behind B, and A - B are recomputed together from the resampled companies.

Output: analysis/data/run_state/per-trim-value/results.json
"""
import sys, json, csv, random
from pathlib import Path
from datetime import date, timedelta
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402
from r4b_tradeable_entry_driver import p_after  # noqa: E402
from analyst_direct_scorer import PriceCache  # noqa: E402
import r4_horizon_driver as r4  # noqa: E402

RS = REPO / "analysis/data/run_state"
ORIG = RS / "p6-output-format-round"
STATE = RS / "per-trim-value"
BOOT_B, SEED, H = 2000, 11, 182
DESTS = ("QQQ", "SPY")


# ------------------------------------------------------------------------------------------ Step 0.5 preflight
def price_return_pct(prices, tk, d0, h=H):
    p0, _ = p_after(prices, tk, d0)
    p1, _ = prices.price_on_or_after(tk, d0 + timedelta(days=h))
    if not (p0 and p1):
        return None
    return round((p1 - p0) / p0 * 100, 6)


def build_rows():
    prices = PriceCache(r4.PRICE_CACHE)
    calls = A.load_calls(ORIG / "calls.csv")
    assert len(calls) == 1217, len(calls)
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1]
          for r in p3.read_jsonl(RS / "b-champion-and-noise-floor/scores_b_rerun1.jsonl")}
    assert len(b2) == 1217, len(b2)

    def per(path):
        return {(r["ticker"], r["call_date"]): float(r["expectedReturn"]) for r in csv.DictReader(open(path))}
    p1 = per(RS / "p9-expected-return-train/per_call_diffs.csv")
    p2 = per(RS / "p9-second-draw/per_call_diffs_draw2.csv")
    assert len(p1) == 1217 and len(p2) == 1217, (len(p1), len(p2))

    beat_raise = set()
    for r in p3.read_jsonl(RS / "winners-missed-v3/read_labels_v3.jsonl"):
        q = r.get("parsed", {})
        if q.get("raised") == "yes" and q.get("beat") == "yes":
            beat_raise.add((r["ticker"], r["date"]))

    rows = []
    n_missing_price = 0
    max_mismatch = 0.0
    for c in calls:
        tk, dt = c["ticker"], c["call_date"]
        k = (tk, dt)
        d0 = date.fromisoformat(dt)
        quarter = f"{d0.year}Q{(d0.month - 1) // 3 + 1}"
        name_ret = price_return_pct(prices, tk, d0)
        spy_ret = price_return_pct(prices, "SPY", d0)
        qqq_ret = price_return_pct(prices, "QQQ", d0)  # always None: QQQ absent from this cache (see findings.md)
        priced = name_ret is not None and spy_ret is not None
        if not priced:
            n_missing_price += 1
        else:
            fwd = c["fwd_rel_ret_tradeable"]
            if fwd is not None:
                max_mismatch = max(max_mismatch, abs(round(name_ret - spy_ret, 4) - round(fwd, 4)))
        rows.append({
            "ticker": tk, "call_date": dt, "quarter": quarter,
            "b1": c["b_score"], "b2": b2[k],
            "p1": p1[k], "p2": p2[k], "pavg": (p1[k] + p2[k]) / 2,
            "beat_and_raise": k in beat_raise,
            "name_ret": name_ret, "spy_ret": spy_ret, "qqq_ret": qqq_ret,
            "priced": priced,
        })
    return rows, n_missing_price, max_mismatch


def val(row, dest, size):
    d_ret = row["qqq_ret"] if dest == "QQQ" else row["spy_ret"]
    return size * (d_ret - row["name_ret"]) / 100


def dest_pop(pop, dest):
    key = "qqq_ret" if dest == "QQQ" else "spy_ret"
    return [r for r in pop if r[key] is not None]


# ------------------------------------------------------------------------------------------ bootstrap machinery
def by_ticker(rows):
    g = {}
    for r in rows:
        g.setdefault(r["ticker"], []).append(r)
    return g


def resample_draws(rows, B=BOOT_B, seed=SEED):
    """Ticker-block bootstrap. Yields resampled row-lists (with duplication)."""
    g = list(by_ticker(rows).values())
    rng = np.random.default_rng(seed)
    for _ in range(B):
        pick = rng.integers(0, len(g), len(g))
        yield [r for i in pick for r in g[i]]


def boot_range(rows, stat, B=BOOT_B, seed=SEED):
    vals = []
    for samp in resample_draws(rows, B, seed):
        try:
            v = stat(samp)
        except Exception:
            v = float("nan")
        if v is not None and v == v:
            vals.append(v)
    if not vals:
        return [float("nan"), float("nan"), 0]
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 4), round(vals[min(int(0.975 * len(vals)), len(vals) - 1)], 4), len(vals)]


def flag_rows(pop, draw):
    """draw in ('b1','b2','pooled')."""
    if draw == "pooled":
        return [r for r in pop if r["b1"] <= -2] + [r for r in pop if r["b2"] <= -2]
    return [r for r in pop if r[draw] <= -2]


def quarter_means(pop, dest, size):
    m = {}
    for r in pop:
        m.setdefault(r["quarter"], []).append(val(r, dest, size))
    return {q: float(np.mean(v)) for q, v in m.items()}


def a_b(pop, draw, dest, size):
    """Returns (A_mean, B_matched_mean, A_minus_B, B_unmatched_mean, n_A)."""
    a_rows = flag_rows(pop, draw)
    if not a_rows:
        return (float("nan"),) * 3 + (float("nan"), 0)
    qm = quarter_means(pop, dest, size)
    a_vals = [val(r, dest, size) for r in a_rows]
    b_vals = [qm[r["quarter"]] for r in a_rows]
    a_mean, b_mean = float(np.mean(a_vals)), float(np.mean(b_vals))
    unmatched = float(np.mean([val(r, dest, size) for r in pop]))
    return (a_mean, b_mean, a_mean - b_mean, unmatched, len(a_rows))


# ------------------------------------------------------------------------------------------ Step 1
def step1(pop):
    out = {}
    for dest in DESTS:
        dpop = dest_pop(pop, dest)
        if not dpop:
            out[dest] = {"blocked": True, "reason": f"{dest} has zero priced rows in this price cache; see findings.md"}
            continue
        dtab = {}
        for draw in ("b1", "b2", "pooled"):
            a_mean, b_mean, ab, unmatched, n = a_b(dpop, draw, dest, 2.5)
            ab_lo, ab_hi, nv = boot_range(dpop, lambda s, dr=draw, d=dest: a_b(s, dr, d, 2.5)[2])
            a_lo, a_hi, _ = boot_range(dpop, lambda s, dr=draw, d=dest: a_b(s, dr, d, 2.5)[0])
            a_rows = flag_rows(dpop, draw)
            a_vals = sorted(val(r, dest, 2.5) for r in a_rows)
            n10 = max(1, round(0.10 * len(a_vals)))
            total = sum(a_vals)
            best10_share = round(100 * sum(a_vals[-n10:]) / total, 1) if total else None
            worst10_share = round(100 * sum(a_vals[:n10]) / total, 1) if total else None
            mid80 = round(sum(a_vals[n10:-n10]) if len(a_vals) > 2 * n10 else 0.0, 4)
            big_winners = [r for r in a_rows if (r["name_ret"] - r["spy_ret"]) >= 20]
            big_winner_total = round(sum(val(r, dest, 2.5) for r in big_winners), 4)
            dtab[draw] = {
                "n": n,
                "A_mean_pts": round(a_mean, 4), "A_mean_range": [round(a_lo, 4), round(a_hi, 4)],
                "A_mean_usd_on_100k": round(a_mean * 1000, 2),
                "B_matched_mean_pts": round(b_mean, 4),
                "B_unmatched_mean_pts": round(unmatched, 4),
                "A_minus_B_pts": round(ab, 4), "A_minus_B_range": [ab_lo, ab_hi], "valid_draws": nv,
                "A_minus_B_usd_on_100k": round(ab * 1000, 2),
                "median_pts_reference_only": round(float(np.median(a_vals)), 4) if a_vals else None,
                "tail": {
                    "n_in_10pct": n10, "best10pct_share_of_A_total_pct": best10_share,
                    "worst10pct_share_of_A_total_pct": worst10_share, "middle80pct_sum_pts": mid80,
                    "n_future_big_winners_beat_spy_20plus": len(big_winners),
                    "big_winners_total_value_pts": big_winner_total,
                },
            }
        out[dest] = dtab
    return out


# ------------------------------------------------------------------------------------------ Step 2: P9 severity bands
def band_sizes(a_rows, seed=SEED):
    """Rank by pavg most-negative-first, ties by seeded shuffle; fifths -> sizes 5/2.5/0/0/0."""
    n = len(a_rows)
    rng = random.Random(seed)
    order = list(range(n)); rng.shuffle(order)
    idx_sorted = sorted(range(n), key=lambda i: (a_rows[i]["pavg"], order[i]))
    bands = np.array_split(idx_sorted, 5)
    size_for_band = [5.0, 2.5, 0.0, 0.0, 0.0]
    sizes = [0.0] * n
    band_of = [0] * n
    for bi, idxs in enumerate(bands):
        for i in idxs:
            sizes[i] = size_for_band[bi]
            band_of[i] = bi
    return sizes, band_of, bands


def step2(full_pop):
    out = {}
    for dest in DESTS:
        pop = dest_pop(full_pop, dest)
        if not pop:
            out[dest] = {"blocked": True, "reason": f"{dest} has zero priced rows in this price cache; see findings.md"}
            continue
        dtab = {}
        for draw in ("b1", "b2", "pooled"):
            a_rows = flag_rows(pop, draw)
            if not a_rows:
                dtab[draw] = None
                continue
            sizes, band_of, bands = band_sizes(a_rows)

            def per_band_stat(band_idx, samp_pop=None):
                sp = samp_pop if samp_pop is not None else pop
                sa = flag_rows(sp, draw)
                if not sa:
                    return float("nan")
                sz, bof, bds = band_sizes(sa)
                idxs = bds[band_idx]
                if len(idxs) == 0:
                    return float("nan")
                return float(np.mean([val(sa[i], dest, 1.0) for i in idxs]))

            by_band = []
            for bi in range(5):
                idxs = bands[bi]
                mean_pp = float(np.mean([val(a_rows[i], dest, 1.0) for i in idxs])) if len(idxs) else float("nan")
                lo, hi, nv = boot_range(pop, lambda s, bi=bi: per_band_stat(bi, s))
                by_band.append({"band": bi + 1, "n": len(idxs), "trim_size": [5.0, 2.5, 0.0, 0.0, 0.0][bi],
                                 "value_per_point_pts": round(mean_pp, 4), "range": [round(lo, 4), round(hi, 4)], "valid_draws": nv})

            def sized_a_mean(sp=None):
                p = sp if sp is not None else pop
                sa = flag_rows(p, draw)
                if not sa:
                    return float("nan")
                sz, _, _ = band_sizes(sa)
                return float(np.mean([val(r, dest, s) for r, s in zip(sa, sz)]))

            def sized_ab(sp=None):
                p = sp if sp is not None else pop
                sa = flag_rows(p, draw)
                if not sa:
                    return float("nan")
                sz, _, _ = band_sizes(sa)
                qm_pp = quarter_means(p, dest, 1.0)  # per-point quarter average
                a_vals = [val(r, dest, s) for r, s in zip(sa, sz)]
                b_vals = [qm_pp[r["quarter"]] * s for r, s in zip(sa, sz)]
                return float(np.mean(a_vals)) - float(np.mean(b_vals))

            def sized_ab_per_point(sp=None):
                p = sp if sp is not None else pop
                sa = flag_rows(p, draw)
                if not sa:
                    return float("nan")
                sz, _, _ = band_sizes(sa)
                qm_pp = quarter_means(p, dest, 1.0)
                a_vals = [val(r, dest, s) for r, s in zip(sa, sz)]
                b_vals = [qm_pp[r["quarter"]] * s for r, s in zip(sa, sz)]
                tot_pts = sum(sz)
                if tot_pts == 0:
                    return float("nan")
                return (sum(a_vals) - sum(b_vals)) / tot_pts

            sm = sized_a_mean()
            sm_lo, sm_hi, _ = boot_range(pop, sized_a_mean)
            sab = sized_ab()
            sab_lo, sab_hi, nv = boot_range(pop, sized_ab)
            sabpp = sized_ab_per_point()
            sabpp_lo, sabpp_hi, nv2 = boot_range(pop, sized_ab_per_point)
            step1_ab_pp = a_b(pop, draw, dest, 2.5)[2] / 2.5

            dtab[draw] = {
                "n": len(a_rows),
                "by_band_value_per_point": by_band,
                "sized_A_mean_pts": round(sm, 4), "sized_A_mean_range": [round(sm_lo, 4), round(sm_hi, 4)],
                "sized_A_minus_B_pts": round(sab, 4), "sized_A_minus_B_range": [round(sab_lo, 4), round(sab_hi, 4)],
                "sized_A_minus_B_valid_draws": nv,
                "sized_A_minus_B_per_point_pts": round(sabpp, 4),
                "sized_A_minus_B_per_point_range": [round(sabpp_lo, 4), round(sabpp_hi, 4)],
                "step1_A_minus_B_per_point_pts": round(step1_ab_pp, 4),
                "p9_adds_value_vs_step1": bool(sabpp > step1_ab_pp),
            }
        out[dest] = dtab
    return out


# ------------------------------------------------------------------------------------------ Step 3: guidance veto (reported only)
def step3(full_pop):
    out = {}
    for dest in DESTS:
        pop = dest_pop(full_pop, dest)
        if not pop:
            out[dest] = {"blocked": True, "reason": f"{dest} has zero priced rows in this price cache; see findings.md"}
            continue
        dtab = {}
        for draw in ("b1", "b2", "pooled"):
            a_rows = flag_rows(pop, draw)
            removed = [r for r in a_rows if r["beat_and_raise"]]
            kept = [r for r in a_rows if not r["beat_and_raise"]]
            if not kept:
                dtab[draw] = None
                continue
            qm = quarter_means(pop, dest, 2.5)
            kept_vals = [val(r, dest, 2.5) for r in kept]
            b_vals = [qm[r["quarter"]] for r in kept]
            veto_a_mean = float(np.mean(kept_vals))
            veto_ab = veto_a_mean - float(np.mean(b_vals))

            def veto_ab_stat(sp):
                sa = flag_rows(sp, draw)
                sk = [r for r in sa if not r["beat_and_raise"]]
                if not sk:
                    return float("nan")
                sqm = quarter_means(sp, dest, 2.5)
                return float(np.mean([val(r, dest, 2.5) for r in sk])) - float(np.mean([sqm[r["quarter"]] for r in sk]))

            lo, hi, nv = boot_range(pop, veto_ab_stat)
            removed_mean = float(np.mean([val(r, dest, 2.5) for r in removed])) if removed else None
            dtab[draw] = {
                "n_A": len(a_rows), "n_removed": len(removed), "n_kept": len(kept),
                "vetoed_A_mean_pts": round(veto_a_mean, 4),
                "vetoed_A_minus_B_pts": round(veto_ab, 4), "vetoed_A_minus_B_range": [round(lo, 4), round(hi, 4)],
                "valid_draws": nv,
                "removed_calls_mean_value_pts": round(removed_mean, 4) if removed_mean is not None else None,
            }
        out[dest] = dtab
    return out


def main():
    rows, n_missing_price, max_mismatch = build_rows()
    pop = [r for r in rows if r["priced"]]
    out = {
        "n_calls_total": len(rows),
        "n_priced": len(pop),
        "n_dropped_unpriced": n_missing_price,
        "sanity_max_mismatch_name_minus_spy_vs_fwd_rel_ret_tradeable": round(max_mismatch, 6),
        "step1_base_result": step1(pop),
        "step2_p9_severity": step2(pop),
        "step3_guidance_veto_reported_only": step3(pop),
    }
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "results.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
