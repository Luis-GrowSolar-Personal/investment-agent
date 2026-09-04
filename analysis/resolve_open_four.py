#!/usr/bin/env python3
"""resolve_open_four.py -- close the four open questions raised by the
analyst-sensitivity wrap-up review (2026-09-04).

Read-only. No LLM calls, no API spend, no DB writes, no cache refresh.
Requires DB access (Railway) for checks B and D, so it must run on the
laptop, not in the Cowork VM (no egress there).

    cd analysis
    python3 resolve_open_four.py            # all checks
    python3 resolve_open_four.py A          # one check

  A  drawdown granularity -- session-sampled vs daily-marked, portfolio
     and benchmarks, phases 0/10/20. Answers whether the published
     17.32% vs SPY 25.36% comparison is like-for-like.
  B  SPWR -- is it absent because the analyst declined it, or for a
     mechanical reason? Also: distinct_tickers counts END-state holdings.
  C  tie-break seed -- why 15 draws are bit-identical. Census of exact
     rank_key ties and of same-date event buckets.
  E  gate scope -- lift by ticker scope vs the ledger's 7-name scope.
  D  sonnet-4-6 error direction -- optimistic, pessimistic or symmetric
     against the sonnet-4-20250514 baseline, on paired rows.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))
sys.path.insert(0, str(SCRIPT_DIR))

import sweep_cadence_and_session_model as S          # noqa: E402
from analysis.simulator.data import PriceLookup      # noqa: E402

START, END, INITIAL = S.START, S.C, S.INITIAL
# Must match analyst_sensitivity_harness.CELL exactly -- note `cadence` is a
# STRING and the kwargs are funding_mode / execution_order, not funding/exec_order.
CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)


def maxdd(vals):
    if not vals:
        return 0.0
    peak, m = vals[0], 0.0
    for v in vals:
        if v > peak:
            peak = v
        if peak > 0:
            m = max(m, (peak - v) / peak)
    return m


def daily_nav_path(snaps, prices):
    """Between session dates share counts are constant (trades happen only at
    sessions), so daily NAV = cash_at_session + sum(shares_t * price_t(day)).
    Shares recovered as position_value / price_on(session_date).
    Pure post-processing of the existing snapshot stream -- no allocator change."""
    out = []
    for i, s in enumerate(snaps):
        shares = {}
        for t, val in (s.position_values or {}).items():
            p = prices.price_on(t, s.date)
            if p and p > 0 and val > 0:
                shares[t] = val / p
        nxt = snaps[i + 1].date if i + 1 < len(snaps) else END + timedelta(days=1)
        d = s.date
        while d < nxt and d <= END:
            tot = s.cash_total
            for t, sh in shares.items():
                p = prices.price_on(t, d)
                if p:
                    tot += sh * p
            out.append((d, tot))
            d += timedelta(days=1)
    return out


def bh_path(prices, ticker, dates):
    sp = prices.price_on(ticker, START)
    if not sp:
        return []
    sh = INITIAL / sp
    vals = []
    for d in dates:
        p = prices.price_on(ticker, d)
        if p:
            vals.append(sh * p)
    return vals


# ---------------------------------------------------------------- A
def check_A(events, prices, type_fn, driver_fn, tier_fn):
    print("\n" + "=" * 78)
    print("A. DRAWDOWN GRANULARITY -- session-sampled vs daily-marked")
    print("=" * 78)
    alldates = [START + timedelta(days=i) for i in range((END - START).days + 1)]

    sess_dd, daily_dd, finals = [], [], []
    print(f"\n{'phase':>5} {'final':>12} {'dd_session':>11} {'dd_daily':>10} "
          f"{'understated_by':>15} {'n_sess':>7} {'n_days':>7}")
    for ph in (0, 10, 20):
        r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                     phase_offset=ph, seed=0, **CELL)
        snaps = r["daily_snapshots"]
        dp = daily_nav_path(snaps, prices)
        dd_d = maxdd([v for _, v in dp])
        sess_dd.append(r["max_dd"]); daily_dd.append(dd_d); finals.append(r["final_value"])
        print(f"{ph:>5} {r['final_value']:>12,.0f} {r['max_dd']*100:>10.2f}% "
              f"{dd_d*100:>9.2f}% {(dd_d-r['max_dd'])*100:>14.2f}pp "
              f"{len(snaps):>7} {len(dp):>7}")

    pa_f, pa_s, pa_d = (sum(finals)/3, sum(sess_dd)/3, sum(daily_dd)/3)
    print(f"\n  phase-averaged final      : ${pa_f:,.0f}      (published $184,819)")
    print(f"  phase-averaged dd SESSION : {pa_s*100:.2f}%        (published 17.32%)")
    print(f"  phase-averaged dd DAILY   : {pa_d*100:.2f}%        <-- like-for-like")

    print(f"\n  BENCHMARKS (buy-and-hold from {START}):")
    print(f"  {'tkr':5} {'daily dd':>9} {'K30 ph0':>9} {'K30 ph10':>9} {'K30 ph20':>9} {'ph-avg':>9}")
    for t in ("SPY", "QQQ", "TMFC"):
        d_dd = maxdd(bh_path(prices, t, alldates))
        phs = []
        for ph in (0, 10, 20):
            sess = [START + timedelta(days=ph + 30*i) for i in range((END-START).days//30 + 2)]
            sess = [x for x in sess if x <= END]
            phs.append(maxdd(bh_path(prices, t, sess)))
        print(f"  {t:5} {d_dd*100:>8.2f}% {phs[0]*100:>8.2f}% {phs[1]*100:>8.2f}% "
              f"{phs[2]*100:>8.2f}% {sum(phs)/3*100:>8.2f}%")
    print("\n  Published §2 figures: SPY 25.36%  QQQ 35.25%  TMFC 32.99%")
    print("  If those match the DAILY column and the portfolio's 17.32% matches the")
    print("  SESSION column, the published comparison is not like-for-like.")


# ---------------------------------------------------------------- B
def check_B(events, prices, type_fn, driver_fn, tier_fn):
    print("\n" + "=" * 78)
    print("B. SPWR -- analyst rejection, or mechanical absence?")
    print("=" * 78)
    spwr = [e for e in events if e.ticker == "SPWR"]
    print(f"\n  SPWR events in the loaded corpus ({len(events)} total events): {len(spwr)}")
    for e in spwr:
        print(f"    {e.call_date}  per_call_rec={e.per_call_rec!r:8} final_action={e.final_action!r:8} "
              f"conf={e.final_confidence!r:10} size={e.recommended_size}")
    if not spwr:
        print("    --> SPWR has NO scored event in the window. Its absence is a")
        print("        CORPUS GAP, not a decision. §5.1's 'only genuine rejection'")
        print("        claim does not survive.")

    r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                 phase_offset=0, seed=0, **CELL)
    txn = [t for t in r["portfolio"].transaction_log if t.ticker == "SPWR"]
    print(f"\n  SPWR trades executed in the settled cell (phase 0): {len(txn)}")
    for t in txn[:10]:
        print(f"    {t.trade_date} {t.side:4} {t.shares:12.4f} @ {t.price:8.2f}  {t.reason}")
    skipped = [s for s in r["skipped_events"] if "SPWR" in str(s)]
    print(f"  SPWR skipped_events: {len(skipped)}  {skipped[:5]}")
    tcl = [x for x in r["target_cap_log"] if x["ticker"] == "SPWR"]
    print(f"  SPWR target_cap_log (starter/add legs queued): {len(tcl)}  {tcl[:5]}")
    fl = [f for f in r["funding_log"] if f["ticker"] == "SPWR"]
    print(f"  SPWR funding_log entries: {len(fl)}  {fl[:5]}")

    ever = {t.ticker for t in r["portfolio"].transaction_log}
    end_held = {t for acc in r["portfolio"].accounts.values() for t in acc.lots
                if any(l.shares > 1e-9 for l in acc.lots[t])}
    print(f"\n  tickers EVER traded : {len(ever)}  {sorted(ever)}")
    print(f"  tickers held AT END : {len(end_held)}  {sorted(end_held)}")
    print("  NOTE: `distinct_tickers` in the sweep result is the AT END set. A count")
    print("        of 15 does not mean a name was never bought.")


# ---------------------------------------------------------------- C
def check_C(events, prices, type_fn, driver_fn, tier_fn):
    print("\n" + "=" * 78)
    print("C. TIE-BREAK SEED -- why 15 draws are bit-identical")
    print("=" * 78)
    by_date = defaultdict(list)
    for e in events:
        by_date[e.call_date].append(e.ticker)
    shared = {d: v for d, v in by_date.items() if len(v) > 1}
    print("\n  C1. same-call-date buckets the seed shuffle can act on:")
    print(f"      distinct call dates          : {len(by_date)}")
    print(f"      dates with >1 event          : {len(shared)}")
    print(f"      events sitting in such dates : {sum(len(v) for v in shared.values())}")
    for d in sorted(shared)[:8]:
        print(f"        {d}  {sorted(shared[d])}")
    print("      --> if >0, the wrap-up's stated cause ('no two events share a")
    print("          date') is FALSE and the shuffle has material to act on.")

    print("\n  C2. does the random 4th sort key ever bind?")
    print("      rank_key = (confidence, -days_since_call, gap). `gap` is a")
    print("      continuous float ratio, so exact 3-tuple ties should be rare.")
    orig = S.rank_key
    seen = defaultdict(list)

    def recording_rank_key(ticker, state_entry, portfolio, prices_today, session_date):
        k = orig(ticker, state_entry, portfolio, prices_today, session_date)
        seen[session_date].append(k)
        return k

    S.rank_key = recording_rank_key
    try:
        S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                 phase_offset=0, seed=0, **CELL)
    finally:
        S.rank_key = orig

    sessions_with_ties = 0
    tied_pairs = 0
    total_keys = 0
    for sd, keys in seen.items():
        total_keys += len(keys)
        c = Counter(keys)
        dups = {k: n for k, n in c.items() if n > 1}
        if dups:
            sessions_with_ties += 1
            for k, n in dups.items():
                tied_pairs += n * (n - 1) // 2
                print(f"      TIE  {sd}  key={k}  x{n}")
    print(f"      rank_key evaluations           : {total_keys}")
    print(f"      sessions containing an exact tie: {sessions_with_ties} / {len(seen)}")
    print(f"      tied candidate pairs            : {tied_pairs}")
    print("      --> 0 tied pairs means the seeded random 4th key NEVER binds,")
    print("          so ordering is fully determined by the continuous gap ratio.")

    finals = set()
    for sd in range(15):
        rr = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                      phase_offset=0, seed=sd, **CELL)
        finals.add(round(rr["final_value"], 6))
    print(f"\n      distinct final values across 15 tie-break seeds: {len(finals)}")
    print(f"      values: {sorted(finals)}")


# ---------------------------------------------------------------- E
def check_E(events, prices):
    print("\n" + "=" * 78)
    print("E. GATE SCOPE -- is the ledger's -7.44pp evidence about THIS portfolio?")
    print("=" * 78)
    from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH
    from analyst_sensitivity_lift import lift_for_events
    pc = PriceCache(PRICE_CACHE_PATH)

    LEDGER = ["ENPH", "TTD", "AMPX", "ENVX", "EOSE", "QS", "SPWR"]
    EST = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
    SPEC = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
    BIG4 = ["AVGO", "NVDA", "ORCL", "TTD"]

    scopes = [
        ("ledger entry-1 scope", LEDGER),
        ("ALL16", S.ALL16),
        ("ALL16 established", EST),
        ("ALL16 speculative", SPEC),
        ("the 4 names = ~73% of portfolio", BIG4),
    ]
    print(f"\n  {'scope':34} {'lift_pp':>9} {'n':>5}")
    for name, tks in scopes:
        sub = [e for e in events if e.ticker in tks]
        lift, n = lift_for_events(sub, pc)
        print(f"  {name:34} {lift*100:>8.2f}pp {n:>5}")
    print("\n  Ledger entry 1: champion 4.94pp (n=81), challenger -2.50pp (n=80),")
    print("  delta -7.44pp vs noise floor 4.2pp, holdout n=0 both arms.")
    print("  NOTE the lift baseline is 'always predict bullish' -- in a rising")
    print("  window that is a strong baseline, which is worth stating when")
    print("  interpreting any negative lift figure.")


# ---------------------------------------------------------------- D
def check_D():
    print("\n" + "=" * 78)
    print("D. sonnet-4-6 ERROR DIRECTION vs sonnet-4-20250514")
    print("=" * 78)
    from dotenv import load_dotenv
    import os, psycopg2, psycopg2.extras
    load_dotenv(SCRIPT_DIR.parent / ".env")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    ORD = {"Add": 0, "Hold": 1, "Trim": 2, "Exit": 3}
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT a."modelVersion" AS model, a.recommendation AS rec,
                   a."thesisHealth" AS health, COUNT(*) AS n
            FROM "Analysis" a
            WHERE a."modelVersion" IS NOT NULL
            GROUP BY 1,2,3 ORDER BY 1,2,3
        """)
        rows = cur.fetchall()
    dist = defaultdict(Counter)
    for r in rows:
        dist[r["model"]][r["rec"]] += r["n"]
    print("\n  Recommendation distribution by model (all stamped rows):")
    for m, c in dist.items():
        tot = sum(c.values())
        mean_ord = sum(ORD.get(k, 1) * v for k, v in c.items()) / tot if tot else 0
        print(f"    {m:28} n={tot:4}  " +
              "  ".join(f"{k}={c.get(k,0)}" for k in ("Add", "Hold", "Trim", "Exit")) +
              f"   mean_ordinal={mean_ord:.3f}")
    print("\n  mean_ordinal: 0=all Add, 3=all Exit. HIGHER than the champion means")
    print("  the challenger skews PESSIMISTIC (harness cost ~$42,700 at -7.44pp);")
    print("  LOWER means OPTIMISTIC (harness cost ~$0); equal means symmetric noise")
    print("  (harness cost ~$24,886). Small n -- treat as directional, not decisive.")

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT tk.symbol AS ticker, t."callDate"::date AS call_date,
                   a."modelVersion" AS model, a.recommendation AS rec
            FROM "Analysis" a
            JOIN "Transcript" t ON a."transcriptId" = t.id
            JOIN "Ticker" tk ON t."tickerId" = tk.id
            WHERE a."modelVersion" IS NOT NULL
            ORDER BY 1,2,3
        """)
        rows = cur.fetchall()
    paired = defaultdict(dict)
    for r in rows:
        paired[(r["ticker"], r["call_date"])][r["model"]] = r["rec"]
    both = {k: v for k, v in paired.items() if len(v) > 1}
    print(f"\n  Paired rows (same ticker+callDate scored by >1 model): {len(both)}")
    deltas = []
    for k, v in sorted(both.items()):
        ms = sorted(v)
        a, b = v[ms[0]], v[ms[-1]]
        d = ORD.get(b, 1) - ORD.get(a, 1)
        deltas.append(d)
        print(f"    {k[0]:6} {k[1]}  {ms[0][:18]}={a:5} -> {ms[-1][:18]}={b:5}  delta={d:+d}")
    if deltas:
        print(f"\n    mean paired delta = {sum(deltas)/len(deltas):+.3f}  "
              f"(positive = challenger more pessimistic)")
    conn.close()


def main():
    which = (sys.argv[1].upper() if len(sys.argv) > 1 else "ABCDE")
    if "D" in which and which == "D":
        check_D(); return
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(SCRIPT_DIR / "data" / "price_cache.json")
    print(f"corpus loaded: {len(events)} events, "
          f"{len({e.ticker for e in events})} tickers")
    if "A" in which: check_A(events, prices, type_fn, driver_fn, tier_fn)
    if "B" in which: check_B(events, prices, type_fn, driver_fn, tier_fn)
    if "C" in which: check_C(events, prices, type_fn, driver_fn, tier_fn)
    if "E" in which: check_E(events, prices)
    if "D" in which: check_D()


if __name__ == "__main__":
    main()
