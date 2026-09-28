#!/usr/bin/env python3
"""
allocator_book_test.py -- prompts/allocator-book-test.md ($0, no API calls,
no DB writes, no scoring, no cache refresh, no fetches).

Severity-sized trims (B flags, P9 severity, proceeds to QQQ) tested on
hundreds of train-company books, against holding the book and against a
no-skill (random-call) control at the same sizes and sessions.

Reuses (import, do not fork):
  - maxdd, daily_nav_path from analysis/resolve_open_four.py
  - the ticker-block bootstrap (A.boot) from analysis/p6_output_format_analysis.py,
    fed one row per BOOK (the book id in the "ticker" slot), so resampling
    books with replacement is the same machinery as resampling companies
    elsewhere in this project.
  - the gate metric formula from analysis/e2e_scorer.py (CAGR / max_drawdown,
    capped at 999 when max_drawdown <= 0.001) -- inlined here as a one-line
    function since e2e_scorer.py computes it inline, not as an importable
    function (see wrap-up "Deviations").
  - p_after / PriceCache from r4b_tradeable_entry_driver / analyst_direct_scorer
    for each call's tradeable-entry date (forward-looking), same convention
    as per_trim_value.py.
  - p3_guidance_ledger_driver.stratum_map / read_jsonl for strata and score files.

Price marking for the simulation itself (session-level buys/trims and the
daily path fed to maxdd) uses a purpose-built forward-filled daily price
array (pandas, ffill(limit=7) -- the same lookback semantics as
simulator.data.PriceLookup.price_on, vectorized for the ~400 books x 8 arms
x 3 phases this run needs). Performance choice, not a pricing-rule change;
see wrap-up "Deviations".

Usage:
  python3 allocator_book_test.py freeze         # Step 1: freeze t1/t2, then commit
  python3 allocator_book_test.py run [--quick]  # Step 2-4: all arms, all books
"""
from __future__ import annotations
import sys, json, csv, math, random
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A          # noqa: E402
import p3_guidance_ledger_driver as p3         # noqa: E402
from r4b_tradeable_entry_driver import p_after  # noqa: E402
from analyst_direct_scorer import PriceCache    # noqa: E402
from resolve_open_four import maxdd, daily_nav_path  # noqa: E402

RS = REPO / "analysis/data/run_state"
ORIG = RS / "p6-output-format-round"
STATE = RS / "allocator-book-test"
CANON_CACHE = REPO / "analysis/data/corpus_v2/scorer_price_cache_v1.json"
SPLIT_PATH = REPO / "analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json"

SEED = 11
N_RANDOM_BOOKS = 200
N_STRAT_BOOKS = 200
BOOK_SIZE = 16
INITIAL = 100_000.0
K = 30
PHASES = (0, 10, 20)
X_PP = 2.5
FRAC_STEP = 0.40
TRAIN6 = ["MSFT", "AMPX", "EOSE", "QS", "RUN", "TTD"]
DAYS_HORIZON = 182
BOOT_B = 2000

ARMS_FIXED = ["0", "1", "2", "3", "3F", "3S"]
ARMS_CONTROL = ["2R", "3R"]


class Snap:
    __slots__ = ("date", "position_values", "cash_total")
    def __init__(self, d, pv):
        self.date = d
        self.position_values = pv
        self.cash_total = 0.0


def return_per_dd(cagr, dd):
    return (cagr / dd) if dd > 0.001 else 999.0


def cagr_of(initial, final, start, end):
    days = (end - start).days or 1
    years = days / 365.25
    return (final / initial) ** (1 / years) - 1 if initial > 0 else 0.0


def quarter(d):
    return (d.year, (d.month - 1) // 3 + 1)


# ============================================================== inputs
def load_calls():
    calls = A.load_calls(ORIG / "calls.csv")
    assert len(calls) == 1217, len(calls)
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1]
          for r in p3.read_jsonl(RS / "b-champion-and-noise-floor/scores_b_rerun1.jsonl")}

    def per(path):
        return {(r["ticker"], r["call_date"]): float(r["expectedReturn"]) for r in csv.DictReader(open(path))}
    p1 = per(RS / "p9-expected-return-train/per_call_diffs.csv")
    p2 = per(RS / "p9-second-draw/per_call_diffs_draw2.csv")

    rows = []
    for c in calls:
        k = (c["ticker"], c["call_date"])
        rows.append({
            "ticker": c["ticker"], "call_date": date.fromisoformat(c["call_date"]),
            "stratum": c["stratum"],
            "b_mean": (c["b_score"] + b2[k]) / 2,
            "p9_avg": (p1[k] + p2[k]) / 2,
        })
    return rows


def companies_and_strata(calls):
    companies = sorted({r["ticker"] for r in calls})
    assert len(companies) == 55, len(companies)
    split = json.loads(SPLIT_PATH.read_text())
    tune, holdout = set(split["tune"]), set(split["holdout"])
    bad = [t for t in companies if t in tune or t in holdout]
    assert not bad, f"train companies also in tune/holdout: {bad}"

    sm = p3.stratum_map()
    megacap = sorted([t for t in companies if sm.get(t) == "S1"]) + ["MSFT"]
    mid = sorted([t for t in companies if sm.get(t) == "S2"])
    spec = sorted([t for t in companies if sm.get(t) == "S4"]) + ["AMPX", "EOSE", "QS", "RUN", "TTD"]
    assert len(megacap) == 16 and len(mid) == 9 and len(spec) == 7, (len(megacap), len(mid), len(spec))
    for t in TRAIN6:
        assert t in companies
    return companies, megacap, mid, spec


def load_fast_prices(tickers, start, end):
    raw = json.loads(CANON_CACHE.read_text())
    assert "QQQ" in raw, "QQQ missing from canonical cache -- run per-trim-value-qqq first"
    idx = pd.date_range(start, end, freq="D")
    arrays, first_date = {}, {}
    for t in list(dict.fromkeys(tickers + ["QQQ", "SPY"])):
        series = raw.get(t, {})
        if not series:
            arrays[t] = np.full(len(idx), np.nan)
            first_date[t] = None
            continue
        s = pd.Series({pd.Timestamp(k): v for k, v in series.items()}).sort_index()
        first_date[t] = s.index[0].date()
        s = s.reindex(idx).ffill(limit=7)
        arrays[t] = s.to_numpy(dtype=float)
    return arrays, first_date


class FastPrices:
    def __init__(self, arrays, start):
        self.arrays = arrays
        self.start = start

    def price_on(self, ticker, d):
        i = (d - self.start).days
        arr = self.arrays.get(ticker)
        if arr is None or i < 0 or i >= len(arr):
            return None
        v = arr[i]
        return None if v != v else float(v)


def sessions_for_phase(start, end, ph):
    out, d = [], start + timedelta(days=ph)
    while d <= end:
        out.append(d)
        d += timedelta(days=K)
    return out


def action_session_idx(sessions, entry_date):
    if entry_date is None:
        return None
    for i, s in enumerate(sessions):
        if s >= entry_date:
            return i
    return None


# ============================================================== Step 1: freeze t1/t2
def cmd_freeze():
    calls = load_calls()
    companies, megacap, mid, spec = companies_and_strata(calls)
    flagged = [c for c in calls if c["b_mean"] <= -2]
    n_flagged = len(flagged)
    rng = random.Random(SEED)
    order = list(range(n_flagged)); rng.shuffle(order)
    asc = sorted(range(n_flagged), key=lambda i: (flagged[i]["p9_avg"], order[i]))
    idx1 = math.ceil(0.20 * n_flagged) - 1
    idx2 = math.ceil(0.40 * n_flagged) - 1
    t1 = flagged[asc[idx1]]["p9_avg"]
    t2 = flagged[asc[idx2]]["p9_avg"]

    out = {
        "n_calls_total": len(calls), "n_companies": len(companies),
        "n_flagged": n_flagged, "t1": t1, "t2": t2,
        "idx1_0based": idx1, "idx2_0based": idx2,
        "megacap_pool": megacap, "mid_pool": mid, "spec_pool": spec,
        "note": "expected mismatch vs per-trim-value(-qqq): this flags on the mean "
                "of B's two draws, not each draw separately -- amendment 1a item 6.",
    }
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "results.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


# ============================================================== global precompute for run
def precompute_schedules(calls, start, end, t1, t2, acache):
    for c in calls:
        _, ed = p_after(acache, c["ticker"], c["call_date"])
        c["entry_date"] = ed
    n_no_entry = sum(c["entry_date"] is None for c in calls)

    by_ticker = defaultdict(list)
    for c in calls:
        by_ticker[c["ticker"]].append(c)
    for t in by_ticker:
        by_ticker[t].sort(key=lambda c: c["call_date"])

    schedules = {}
    for ph in PHASES:
        sessions = sessions_for_phase(start, end, ph)
        all_action = defaultdict(list)
        for t, cs in by_ticker.items():
            for c in cs:
                idx = action_session_idx(sessions, c["entry_date"])
                if idx is not None:
                    all_action[t].append((idx, c))
        for t in all_action:
            all_action[t].sort(key=lambda x: x[0])

        arm2_groups = defaultdict(list)
        arm3_groups = defaultdict(list)
        for t, acts in all_action.items():
            pending = None
            for idx, c in acts:
                if c["b_mean"] > -2:
                    continue
                arm2_groups[t].append([idx])
                if pending is not None:
                    if idx < pending["second"]:
                        pending = None
                    else:
                        arm3_groups[t].append([pending["first"], pending["second"]])
                        pending = None
                if c["p9_avg"] <= t1:
                    if idx + 1 < len(sessions):
                        pending = {"first": idx, "second": idx + 1}
                    else:
                        arm3_groups[t].append([idx])
                elif c["p9_avg"] <= t2:
                    arm3_groups[t].append([idx])
            if pending is not None:
                arm3_groups[t].append([pending["first"], pending["second"]])
        schedules[ph] = {"sessions": sessions, "all_action": dict(all_action),
                          "arm2_groups": dict(arm2_groups), "arm3_groups": dict(arm3_groups)}
    return schedules, n_no_entry


# ============================================================== simulation core
def simulate(tickers, weight_dollar, sessions, dest, fp, first_date, base_groups, mode, resolver):
    """base_groups: list of (orig_ticker, [session_idx,...]) any order.
    resolver(orig_ticker, first_idx, shares) -> target_ticker or None.
    mode 'pct': each step trims X_PP% of total book value from target, capped at position.
    mode 'frac': each step trims FRAC_STEP fraction of a reference value (the
      position's own pre-trim value for a single-step group or a group's first
      step; the value captured at the first step, for a group's second step)."""
    shares = {t: 0.0 for t in tickers}
    embryo = {t: 0.0 for t in tickers}
    bought_in = {t: False for t in tickers}
    dest_shares = 0.0
    stored_ref = {}
    n_trims = 0
    points_moved = 0.0
    full_sells = 0
    flag_pcts = []

    groups_by_first = defaultdict(list)
    for ot, g in base_groups:
        groups_by_first[g[0]].append((ot, g))
    dynamic_steps = defaultdict(list)  # session_idx -> [(ticker, is_step2)]

    snaps = []
    for i, sd in enumerate(sessions):
        for t in tickers:
            if bought_in[t]:
                continue
            fdt = first_date.get(t)
            if fdt is None or fdt > sd:
                if i == 0:
                    qp = fp.price_on("QQQ", sd)
                    if qp:
                        embryo[t] = weight_dollar / qp
                continue
            if i == 0:
                pr = fp.price_on(t, sd)
                if pr:
                    shares[t] = weight_dollar / pr
                    bought_in[t] = True
            elif embryo[t] > 0:
                ev = embryo[t] * (fp.price_on("QQQ", sd) or 0.0)
                pr = fp.price_on(t, sd)
                if pr:
                    shares[t] = ev / pr
                    bought_in[t] = True
                    embryo[t] = 0.0

        for ot, g in groups_by_first.get(i, []):
            target = resolver(ot, i, shares)
            if target is None:
                continue
            dynamic_steps[i].append((target, False))
            if len(g) == 2:
                dynamic_steps[g[1]].append((target, True))

        total_val = (sum(shares[t] * (fp.price_on(t, sd) or 0.0) for t in tickers if bought_in[t])
                     + sum(embryo[t] * (fp.price_on("QQQ", sd) or 0.0) for t in tickers if not bought_in[t])
                     + dest_shares * (fp.price_on(dest, sd) or 0.0))

        for target, is_step2 in dynamic_steps.get(i, []):
            price_t = fp.price_on(target, sd)
            pos_val = shares.get(target, 0.0) * (price_t or 0.0)
            if mode == "pct":
                want = (X_PP / 100.0) * total_val
            else:
                base = stored_ref.get(target, pos_val) if is_step2 else pos_val
                want = FRAC_STEP * base
            sell_val = min(want, pos_val) if pos_val > 0 else 0.0
            full = pos_val > 0 and sell_val >= pos_val - 1e-9
            if not is_step2:
                stored_ref[target] = pos_val
            if price_t and sell_val > 0:
                shares[target] -= sell_val / price_t
            dp = fp.price_on(dest, sd)
            if dp and sell_val > 0:
                dest_shares += sell_val / dp
            n_trims += 1
            if full:
                full_sells += 1
            if total_val > 0:
                points_moved += 100 * sell_val / total_val
                flag_pcts.append(100 * pos_val / total_val)

        pv = {}
        for t in tickers:
            if bought_in[t] and shares[t] > 0:
                pv[t] = pv.get(t, 0.0) + shares[t] * (fp.price_on(t, sd) or 0.0)
            elif not bought_in[t]:
                pv["QQQ"] = pv.get("QQQ", 0.0) + embryo[t] * (fp.price_on("QQQ", sd) or 0.0)
        if dest_shares > 0:
            pv[dest] = pv.get(dest, 0.0) + dest_shares * (fp.price_on(dest, sd) or 0.0)
        snaps.append(Snap(sd, pv))

    return {"snaps": snaps, "n_trims": n_trims, "points_moved": points_moved,
            "full_sells": full_sells, "flag_pcts": flag_pcts}


def fixed_resolver(ot, i, shares):
    return ot


def make_control_resolver(book_tickers, all_action, sessions, rng):
    def resolver(ot, i, shares):
        q = quarter(sessions[i])
        candidates = []
        for t in book_tickers:
            if shares.get(t, 0.0) <= 0:
                continue
            for idx, _c in all_action.get(t, []):
                if quarter(sessions[idx]) == q:
                    candidates.append(t)
        if not candidates:
            return None
        return candidates[rng.randrange(len(candidates))]
    return resolver


def metrics_from_snaps(snaps, fp_prices_obj, start, end):
    dp = daily_nav_path(snaps, fp_prices_obj)
    vals = [v for _, v in dp]
    dd = maxdd(vals)
    final_value = vals[-1] if vals else 0.0
    cagr = cagr_of(INITIAL, final_value, start, end)
    return {"final_value": final_value, "cagr": cagr, "max_dd": dd,
            "return_per_dd": return_per_dd(cagr, dd)}


# ============================================================== per-book, all arms, all phases
def run_book_all(book_tickers, book_id, schedules, arrays, first_date, start, end):
    fp = FastPrices(arrays, start)
    weight = INITIAL / len(book_tickers)
    per_phase = {arm: [] for arm in ARMS_FIXED + ARMS_CONTROL}

    for ph in PHASES:
        sched = schedules[ph]
        sessions = sched["sessions"]
        all_action_book = {t: sched["all_action"].get(t, []) for t in book_tickers}
        arm2_groups_book = [(t, g) for t in book_tickers for g in sched["arm2_groups"].get(t, [])]
        arm3_groups_book = [(t, g) for t in book_tickers for g in sched["arm3_groups"].get(t, [])]

        r0 = simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, [], "pct", fixed_resolver)
        m0 = metrics_from_snaps(r0["snaps"], fp, start, end)
        per_phase["0"].append({**m0, "n_trims": 0, "points_moved": 0.0, "full_sells": 0, "flag_pcts": []})

        r1 = simulate(["QQQ"], INITIAL, sessions, "QQQ", fp, first_date, [], "pct", fixed_resolver)
        m1 = metrics_from_snaps(r1["snaps"], fp, start, end)
        per_phase["1"].append({**m1, "n_trims": 0, "points_moved": 0.0, "full_sells": 0, "flag_pcts": []})

        r2 = simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm2_groups_book, "pct", fixed_resolver)
        per_phase["2"].append({**metrics_from_snaps(r2["snaps"], fp, start, end),
                                "n_trims": r2["n_trims"], "points_moved": r2["points_moved"],
                                "full_sells": r2["full_sells"], "flag_pcts": []})

        r3 = simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm3_groups_book, "pct", fixed_resolver)
        per_phase["3"].append({**metrics_from_snaps(r3["snaps"], fp, start, end),
                                "n_trims": r3["n_trims"], "points_moved": r3["points_moved"],
                                "full_sells": r3["full_sells"], "flag_pcts": r3["flag_pcts"]})

        r3f = simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm3_groups_book, "frac", fixed_resolver)
        per_phase["3F"].append({**metrics_from_snaps(r3f["snaps"], fp, start, end),
                                 "n_trims": r3f["n_trims"], "points_moved": r3f["points_moved"],
                                 "full_sells": r3f["full_sells"], "flag_pcts": []})

        r3s = simulate(book_tickers, weight, sessions, "SPY", fp, first_date, arm3_groups_book, "pct", fixed_resolver)
        per_phase["3S"].append({**metrics_from_snaps(r3s["snaps"], fp, start, end),
                                 "n_trims": r3s["n_trims"], "points_moved": r3s["points_moved"],
                                 "full_sells": r3s["full_sells"], "flag_pcts": []})

        rng2 = random.Random((SEED, book_id, "2R", ph))
        resolver2 = make_control_resolver(book_tickers, all_action_book, sessions, rng2)
        r2r = simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm2_groups_book, "pct", resolver2)
        per_phase["2R"].append({**metrics_from_snaps(r2r["snaps"], fp, start, end),
                                 "n_trims": r2r["n_trims"], "points_moved": r2r["points_moved"],
                                 "full_sells": r2r["full_sells"], "flag_pcts": []})

        rng3 = random.Random((SEED, book_id, "3R", ph))
        resolver3 = make_control_resolver(book_tickers, all_action_book, sessions, rng3)
        r3r = simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm3_groups_book, "pct", resolver3)
        per_phase["3R"].append({**metrics_from_snaps(r3r["snaps"], fp, start, end),
                                 "n_trims": r3r["n_trims"], "points_moved": r3r["points_moved"],
                                 "full_sells": r3r["full_sells"], "flag_pcts": []})

    out = {"book_id": book_id, "tickers": book_tickers}
    for arm, runs in per_phase.items():
        out[arm] = {
            "final_value": float(np.mean([r["final_value"] for r in runs])),
            "cagr": float(np.mean([r["cagr"] for r in runs])),
            "max_dd": float(np.mean([r["max_dd"] for r in runs])),
            "return_per_dd": float(np.mean([r["return_per_dd"] for r in runs])),
            "n_trims": float(np.mean([r["n_trims"] for r in runs])),
            "points_moved": float(np.mean([r["points_moved"] for r in runs])),
            "full_sell_share": (sum(r["full_sells"] for r in runs) / sum(r["n_trims"] for r in runs)
                                 if sum(r["n_trims"] for r in runs) > 0 else None),
            "median_flag_pct": (float(np.median([x for r in runs for x in r["flag_pcts"]]))
                                 if any(r["flag_pcts"] for r in runs) else None),
        }
    return out


def _worker(args):
    book_tickers, book_id, schedules, arrays, first_date, start, end = args
    return run_book_all(book_tickers, book_id, schedules, arrays, first_date, start, end)


# ============================================================== books
def build_random_books(companies):
    rng = np.random.default_rng(SEED)
    return [sorted(rng.choice(companies, BOOK_SIZE, replace=False).tolist()) for _ in range(N_RANDOM_BOOKS)]


def build_stratified_books(megacap, mid, spec):
    rng = np.random.default_rng(SEED)
    books = []
    for _ in range(N_STRAT_BOOKS):
        b = (rng.choice(megacap, 8, replace=False).tolist()
             + rng.choice(mid, 4, replace=False).tolist()
             + rng.choice(spec, 4, replace=False).tolist())
        books.append(sorted(b))
    return books


# ============================================================== readings
def gain_stats(books_results, arm, base="0"):
    gains = [b[arm]["return_per_dd"] - b[base]["return_per_dd"] for b in books_results]
    win_share = 100 * sum(g > 0 for g in gains) / len(gains)
    rows = [{"ticker": f"book{i}", "gain": g} for i, g in enumerate(gains)]
    lo, hi, nv = A.boot(rows, lambda s: float(np.median([r["gain"] for r in s])))
    return {"n": len(gains), "win_share_pct": round(win_share, 1),
            "median_gain": round(float(np.median(gains)), 4),
            "range": [round(lo, 4), round(hi, 4)], "valid_draws": nv}


def company_removal(books_results, all_companies_in_pool, arm, base="0"):
    lowest = (101.0, None)
    per_company = {}
    for co in all_companies_in_pool:
        kept = [b for b in books_results if co not in b["tickers"]]
        if len(kept) < 5:
            continue
        gains = [b[arm]["return_per_dd"] - b[base]["return_per_dd"] for b in kept]
        ws = 100 * sum(g > 0 for g in gains) / len(gains)
        per_company[co] = round(ws, 1)
        if ws < lowest[0]:
            lowest = (ws, co)
    return {"lowest_win_share_pct": round(lowest[0], 1), "company": lowest[1], "per_company": per_company}


def pass_rule(books_results, all_companies_in_pool, arm, base="0"):
    g = gain_stats(books_results, arm, base)
    cr = company_removal(books_results, all_companies_in_pool, arm, base)
    passed = g["win_share_pct"] >= 70.0 and g["range"][0] > 0 and cr["lowest_win_share_pct"] >= 70.0
    return {**g, "company_removal": cr, "passes_70pct_rule": bool(passed)}


# ============================================================== Step 4: band 5 lead ($0, reported only)
def band5_lead():
    import per_trim_value as PTV
    rows, _, _ = PTV.build_rows()
    pop = [r for r in rows if r["priced"]]
    out = {}
    for dest in ("QQQ", "SPY"):
        dpop = PTV.dest_pop(pop, dest)
        a_rows = PTV.flag_rows(dpop, "pooled")
        sizes, band_of, bands = PTV.band_sizes(a_rows)
        band5_idx = bands[4]
        band5_rows = [a_rows[i] for i in band5_idx]
        vals = [PTV.val(r, dest, 1.0) for r in band5_rows]
        mean_v = float(np.mean(vals))
        median_v = float(np.median(vals))
        lo, hi, nv = PTV.boot_range(dpop, lambda s, d=dest: (
            (lambda ar: (float(np.mean([PTV.val(ar[i], d, 1.0) for i in PTV.band_sizes(ar)[2][4]]))
                         if len(PTV.band_sizes(ar)[2][4]) else float("nan")))(PTV.flag_rows(s, "pooled"))
        ))
        by_ticker = defaultdict(list)
        for r, v in zip(band5_rows, vals):
            by_ticker[r["ticker"]].append(v)
        contrib = sorted(((t, sum(vs)) for t, vs in by_ticker.items()), key=lambda x: -x[1])[:3]
        out[dest] = {"n": len(band5_rows), "median_value_per_point_pts": round(median_v, 4),
                     "mean_value_per_point_pts": round(mean_v, 4), "range": [round(lo, 4), round(hi, 4)],
                     "valid_draws": nv,
                     "top3_contributors": [{"ticker": t, "sum_value_pts": round(v, 4)} for t, v in contrib]}
    return out


# ============================================================== arm M feasibility
def arm_m_feasibility():
    """The settled production CELL (swap_funding, K=30, new_calls_only, X=2.5,
    pooled, per_event_date) runs through S.run_session_sweep_cell, which needs
    events from sweep_cadence_and_session_model.load_events_dedup_on(). That
    loader calls simulator.data.load_call_events (a DB query against the
    Analysis/Transcript tables) and fetch_extra_fields(ALL16, C) (also DB),
    and both are hardcoded to the 16-name ALL16 universe -- not parameterized
    for an arbitrary train-company book. Running arm M on these books would
    require rewriting that loader for 55 train companies without a DB path,
    which is a workaround the prompt explicitly forbids building."""
    v6_dir_exists = (REPO / "analysis/data/evals/v6_claude-sonnet-4-6").exists()
    return {
        "ran": False,
        "v6_eval_dir_exists_for_train_companies": v6_dir_exists,
        "missing": "sweep_cadence_and_session_model.load_events_dedup_on() calls "
                   "simulator.data.load_call_events (DB query) and fetch_extra_fields "
                   "(DB query), both hardcoded to ALL16 -- not available or "
                   "parameterizable for the 55 train companies without a DB-loader rewrite",
        "decision": "arm M not run, per the prompt's explicit branch (no workaround built); "
                    "reading 4 ('the matrix costs money') deferred",
    }


# ============================================================== run orchestration
def cmd_run():
    STATE.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((STATE / "results.json").read_text())
    t1, t2 = frozen["t1"], frozen["t2"]
    megacap, mid, spec = frozen["megacap_pool"], frozen["mid_pool"], frozen["spec_pool"]

    calls = load_calls()
    companies, megacap2, mid2, spec2 = companies_and_strata(calls)
    assert megacap2 == megacap and mid2 == mid and spec2 == spec, "pool mismatch vs frozen results.json"

    acache = PriceCache(CANON_CACHE)
    spy_dates = sorted(acache._data["QQQ"].keys())
    last_call = max(c["call_date"] for c in calls)
    start = date(2020, 1, 2)
    target_end = last_call + timedelta(days=DAYS_HORIZON)
    end = next(date.fromisoformat(d) for d in spy_dates if date.fromisoformat(d) >= target_end)

    tickers_all = companies
    arrays, first_date = load_fast_prices(tickers_all, start, end)
    fp_check = FastPrices(arrays, start)
    assert fp_check.price_on("QQQ", start) is not None, "QQQ has no price at window start"

    late = {t: first_date[t] for t in tickers_all if first_date[t] and first_date[t] > start}
    schedules, n_no_entry = precompute_schedules(calls, start, end, t1, t2, acache)

    random_books = build_random_books(companies)
    strat_books = build_stratified_books(megacap, mid, spec)
    strat_pool = sorted(set(megacap) | set(mid) | set(spec))

    print(f"Window: {start} .. {end}  ({(end-start).days} days)  n_no_entry={n_no_entry}")
    print(f"Late listings: {late}")
    print(f"Simulating {len(random_books)} random + {len(strat_books)} stratified books...")

    def run_set(books, tag):
        jobs = [(b, f"{tag}{i}", schedules, arrays, first_date, start, end) for i, b in enumerate(books)]
        results = [None] * len(jobs)
        with ProcessPoolExecutor() as ex:
            futs = {ex.submit(_worker, j): i for i, j in enumerate(jobs)}
            done = 0
            for fut in as_completed(futs):
                i = futs[fut]
                results[i] = fut.result()
                done += 1
                if done % 50 == 0:
                    print(f"  {tag}: {done}/{len(jobs)}")
        return results

    random_results = run_set(random_books, "R")
    strat_results = run_set(strat_books, "S")

    train6_result = run_book_all(TRAIN6, "TRAIN6", schedules, arrays, first_date, start, end)
    loo_results = []
    for drop in TRAIN6:
        book = [t for t in TRAIN6 if t != drop]
        loo_results.append({"dropped": drop, "result": run_book_all(book, f"TRAIN6_loo_{drop}",
                                                                      schedules, arrays, first_date, start, end)})

    band5 = band5_lead()
    arm_m = arm_m_feasibility()

    out = dict(frozen)
    out["window"] = {"start": start.isoformat(), "end": end.isoformat(), "n_no_entry_date": n_no_entry}
    out["late_listings"] = {t: d.isoformat() for t, d in late.items()}

    def summarize(results, pool):
        s = {}
        for arm in ARMS_FIXED + ARMS_CONTROL:
            s[arm] = {
                "median_final_value": round(float(np.median([b[arm]["final_value"] for b in results])), 2),
                "median_cagr": round(float(np.median([b[arm]["cagr"] for b in results])), 4),
                "median_max_dd": round(float(np.median([b[arm]["max_dd"] for b in results])), 4),
                "median_return_per_dd": round(float(np.median([b[arm]["return_per_dd"] for b in results])), 4),
            }
            if arm != "0":
                s[arm]["vs_arm0"] = pass_rule(results, pool, arm, "0")
        s["3_vs_2"] = pass_rule(results, pool, "3", "2")
        s["3_vs_3R"] = pass_rule(results, pool, "3", "3R")
        s["2_vs_2R"] = pass_rule(results, pool, "2", "2R")
        arm3 = [b["3"] for b in results]
        s["arm3_diagnostics"] = {
            "median_full_sell_share": float(np.median([b["3"]["full_sell_share"] for b in results
                                                         if b["3"]["full_sell_share"] is not None])),
            "median_of_median_flag_pct": float(np.median([b["3"]["median_flag_pct"] for b in results
                                                            if b["3"]["median_flag_pct"] is not None])),
        }
        units_3F = s["3F"]["vs_arm0"]["win_share_pct"] if "3F" in s else None
        units_3 = s["3"]["vs_arm0"]["win_share_pct"]
        s["units_reading"] = {
            "arm3_win_share": units_3, "arm3F_win_share": units_3F,
            "within_10pts": abs(units_3 - units_3F) <= 10 if units_3F is not None else None,
            "verdict": ("units do not matter" if units_3F is not None and abs(units_3 - units_3F) <= 10
                        else "units matter"),
        }
        return s

    out["random_books"] = {"n": len(random_results), "summary": summarize(random_results, companies),
                            "books": [{"book_id": b["book_id"], "tickers": b["tickers"],
                                       **{a: {"final_value": b[a]["final_value"], "cagr": b[a]["cagr"],
                                              "max_dd": b[a]["max_dd"], "return_per_dd": b[a]["return_per_dd"]}
                                          for a in ARMS_FIXED + ARMS_CONTROL}} for b in random_results]}
    out["stratified_books"] = {"n": len(strat_results), "summary": summarize(strat_results, strat_pool),
                                "books": [{"book_id": b["book_id"], "tickers": b["tickers"]} for b in strat_results]}
    out["train6"] = train6_result
    out["train6_leave_one_out"] = loo_results
    out["band5_lead"] = band5
    out["arm_M"] = arm_m

    # headline
    r3v0 = out["random_books"]["summary"]["3"]["vs_arm0"]
    r3v3r = out["random_books"]["summary"]["3_vs_3R"]
    headline = ("severity-sized trims add value" if r3v0["passes_70pct_rule"] and r3v3r["passes_70pct_rule"]
                else "own more QQQ" if r3v0["passes_70pct_rule"] and not r3v3r["passes_70pct_rule"]
                else "do not add value")
    out["headline"] = headline

    (STATE / "results.json").write_text(json.dumps(out, indent=1, default=float))
    print("HEADLINE:", headline)
    print(json.dumps({"headline": headline, "random_3_vs_0": r3v0, "random_3_vs_3R": r3v3r,
                       "units": out["random_books"]["summary"]["units_reading"], "arm_M": arm_m},
                      indent=1, default=float))


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("freeze", "run"):
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "freeze":
        cmd_freeze()
    else:
        cmd_run()
