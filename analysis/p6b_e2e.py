#!/usr/bin/env python3
"""
p6b_e2e.py -- prompts/P6B-end-to-end-check.md (run_id p6b-end-to-end-check)

Does the minimal prompt's score translate to portfolio dollars under the settled allocator configuration?
Reuses (by import, unmodified): sweep_cadence_and_session_model (load_events_dedup_on, run_session_sweep_cell),
resolve_open_four (CELL, daily_nav_path, maxdd), p3_guidance_ledger_driver (batch submit/poll), p6_output_format_driver (B prompt path,
model, max_tokens, sysblock). The overlay lives in p6b_overlay.py. The DB is read with SELECT only; nothing is written to it.

Commands:
  repro                  Step 0: reproduce the reference R (hard stop) -- $0
  events                 event list + transcript ids/hashes from the DB, cross-check against analysis/data/transcripts -- $0
  guards                 record the two version-guard assertions
  submit-b / submit-noise / poll-b / poll-noise      scoring (the only spend)
  cells                  run R, A0, B3, B2, N (+ seeds 1,2 on B3 and A0), resumable via cells.jsonl -- $0
  summary                phase-averaged tables, diagnostics, decision-stream diff -> summary.json / summary.md -- $0
"""
import sys, os, json, gzip, hashlib, subprocess, random, statistics
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis"))
import sweep_cadence_and_session_model as S            # noqa: E402
import resolve_open_four as R4                          # noqa: E402
import p3_guidance_ledger_driver as p3                  # noqa: E402
import p6_output_format_driver as p6                    # noqa: E402
import p6b_overlay as OV                                # noqa: E402
from analysis.simulator.data import PriceLookup         # noqa: E402
from analysis.simulator import accounts as ACC          # noqa: E402

RUN_ID = "p6b-end-to-end-check"
STATE = REPO / "analysis/data/run_state" / RUN_ID
PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
CELLS = STATE / "cells.jsonl"
LOGS = STATE / "logs"
DRIVER_FILE = "analysis/p6b_e2e.py"
PRICE_CACHE = REPO / "analysis/data/price_cache.json"
FUND_CACHE = REPO / "analysis/data/fundamentals_cache.json"
TYPE_JSON = REPO / "analysis/data/type_classifications.json"
CAP_USD = 15.0
EST_B, EST_N = 0.0236, 0.0402
NOISE_N = 100
MODEL, MAX_TOKENS = p6.MODEL, p6.MAX_TOKENS
PHASES = (0, 10, 20)
CELL = R4.CELL                                           # the settled configuration, exactly as check_A runs it
REF = {"final_avg": 184_819.0, "dd_session_avg": 17.32, "dd_daily_avg": 23.46,
       "finals": [179_945.0, 189_914.0, 184_599.0]}
REF_KEYS = ("1a-phase0", "1a-phase10", "1a-phase20")   # analysis/data/run_state/resolve-open-four/cells.jsonl

# point the imported p3 batch machinery at THIS run
p3.STATE, p3.PROGRESS, p3.FINDINGS = STATE, PROGRESS, FINDINGS


def now():
    return p3.now()


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*a):
    return subprocess.check_output(["git", *a], cwd=REPO).decode().strip()


def load_progress():
    return json.loads(PROGRESS.read_text())


def save_progress(p):
    PROGRESS.write_text(json.dumps(p, indent=1, default=str))


def finding(t):
    p3.finding(t)


def step(name, status, next_action=None, note=None):
    p = load_progress()
    p["steps"][name] = status
    if next_action:
        p["next_action"] = next_action
    if note:
        p["notes"].append(note)
    save_progress(p)


# ------------------------------------------------------------------------------------------ manifests (section 10b)
def assert_clean():
    # code state only: this run's own output directory is excluded (results being produced are not "dirty code")
    dirty = bool(git("status", "--porcelain", "--", ".", f":(exclude)analysis/data/run_state/{RUN_ID}"))
    commit = git("rev-parse", "HEAD")
    if dirty:
        raise SystemExit(f"HARD STOP: git_dirty is true at {commit[:12]}; a manifest may not be written.")
    if subprocess.run(["git", "cat-file", "-e", f"{commit}:{DRIVER_FILE}"], cwd=REPO).returncode != 0:
        raise SystemExit(f"HARD STOP: HEAD {commit[:12]} does not contain {DRIVER_FILE}")
    return commit


def write_manifest(name, params, results, corpus=None):
    commit = assert_clean()
    m = {"run_id": RUN_ID, "manifest": name, "timestamp_utc": now(), "git_commit": commit, "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
         "git_dirty": False, "driver_file": DRIVER_FILE, "driver_contains_file_at_commit": True,
         "corpus": corpus, "checksums": {"type_classifications.json": sha256_file(TYPE_JSON), "price_cache.json": sha256_file(PRICE_CACHE),
                                          "fundamentals_cache.json": sha256_file(FUND_CACHE)},
         "params": params, "results": results}
    (STATE / f"manifest_{name}.json").write_text(json.dumps(m, indent=1, default=str))
    return m


# ------------------------------------------------------------------------------------------ events and transcripts
def connect():
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.set_session(readonly=True)                       # SELECT only, enforced by the connection
    return conn


def fetch_transcripts(keys=None, with_text=True):
    """Transcript rows for the harness events, using load_call_events' own filters; lowest id per (ticker, call_date)."""
    import psycopg2.extras
    conn = connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT t.id AS transcript_id, tk.symbol AS ticker, t."callDate"::date AS call_date{', t."rawText" AS raw_text' if with_text else ''}
                FROM "Analysis" a
                JOIN "Transcript" t ON a."transcriptId" = t.id
                JOIN "Ticker" tk ON t."tickerId" = tk.id
                JOIN (SELECT a2."transcriptId", MAX(a2."createdAt") AS latest FROM "Analysis" a2 GROUP BY a2."transcriptId") latest
                  ON latest."transcriptId" = a."transcriptId" AND latest.latest = a."createdAt"
                WHERE tk.symbol = ANY(%s) AND t."callDate" <= %s AND a."createdAt" < %s AND a."createdAt" >= %s
                ORDER BY t."callDate" ASC, tk.symbol ASC
            """, (S.ALL16, S.C, "2026-06-27 16:26:16-04", "2026-05-02 12:33:23-04"))
            rows = cur.fetchall()
    finally:
        conn.close()
    best = {}
    for r in rows:
        k = (r["ticker"], r["call_date"])
        if k not in best or r["transcript_id"] < best[k]["transcript_id"]:
            best[k] = r
    return best


def event_list_sha(events, tr):
    lst = sorted([e.ticker, e.call_date.isoformat(), tr[(e.ticker, e.call_date)]["transcript_id"]] for e in events)
    return hashlib.sha256(json.dumps(lst).encode()).hexdigest(), lst


def load_world():
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(PRICE_CACHE)
    return events, type_fn, driver_fn, tier_fn, prices


# ------------------------------------------------------------------------------------------ trade logging (wrappers, no harness edit)
TRADE_LOG = []
_orig_buy, _orig_sell = ACC.Portfolio.execute_buy, ACC.Portfolio.execute_sell


def _buy(self, trade):
    TRADE_LOG.append((trade.trade_date.isoformat(), trade.ticker, "buy", round(trade.shares, 6), trade.account))
    return _orig_buy(self, trade)


def _sell(self, trade):
    TRADE_LOG.append((trade.trade_date.isoformat(), trade.ticker, "sell", round(trade.shares, 6), trade.account))
    return _orig_sell(self, trade)


ACC.Portfolio.execute_buy, ACC.Portfolio.execute_sell = _buy, _sell


# ------------------------------------------------------------------------------------------ one run + diagnostics
def run_one(events, world, phase, seed):
    _, type_fn, driver_fn, tier_fn, prices = world
    TRADE_LOG.clear()
    r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn, phase_offset=phase, seed=seed, **CELL)
    snaps = r["daily_snapshots"]
    dp = R4.daily_nav_path(snaps, prices)
    dd_daily = R4.maxdd([v for _, v in dp])
    fl = r["funding_log"]
    last = snaps[-1]
    weights = {t: round(v / last.total_value, 5) for t, v in (last.position_values or {}).items() if v > 0}
    cash_pct = [100 * s.cash_total / s.total_value for s in snaps if s.total_value > 0]

    def first_below(th):
        for s in snaps:
            if s.total_value > 0 and s.cash_total / s.total_value < th / 100:
                return (s.date - S.START).days
        return None
    buys = [t for t in TRADE_LOG if t[2] == "buy"]
    sells = [t for t in TRADE_LOG if t[2] == "sell"]
    sale_dollars = sum(x.proceeds for x in r["portfolio"].realized_sales)
    buy_dollars = sum(f["actual_dollars"] for f in fl)
    avg_nav = statistics.mean(s.total_value for s in snaps)
    res = {"final": r["final_value"], "dd_session": r["max_dd"], "dd_daily": dd_daily, "n_sessions": r["n_sessions"], "n_events": r["n_events"],
           "add_total": r["add_total"], "fully_funded": r["fully_funded"], "partial": r["partial"], "unfunded": r["unfunded"],
           "total_shortfall": r["total_shortfall"], "binding_counts": dict(Counter(f["binding"] for f in fl)),
           "sessions_with_cash_bound": len({f["date"].isoformat() for f in fl if "cash" in str(f["binding"]).lower()}),
           "n_displacements": r["n_displacements"], "distinct_tickers": r["distinct_tickers"],
           "below_1pct_cash_sessions": r["below_1pct_days"], "avg_cash_pct_sessions": statistics.mean(cash_pct) if cash_pct else None,
           "days_to_cash_below_5pct": first_below(5), "days_to_cash_below_10pct": first_below(10),
           "ending_weights": weights, "ending_cash_pct": 100 * last.cash_total / last.total_value,
           "n_buy_trades": len(buys), "n_sell_trades": len(sells), "buy_dollars": buy_dollars, "sale_dollars": sale_dollars,
           "turnover_buys_plus_sells_over_avg_nav": (buy_dollars + sale_dollars) / avg_nav,
           "realized_gains": r["realized_gains"], "max_session_pp_change": r["max_session_pp_change"], "skipped_events": len(r["skipped_events"])}
    return res, {"funding_log": fl, "target_cap_log": r["target_cap_log"], "trades": list(TRADE_LOG)}


def rec_counts(events):
    return dict(Counter(e.per_call_rec for e in events))


# ------------------------------------------------------------------------------------------ Step 0
def cmd_repro():
    assert_clean()
    world = load_world()
    events = world[0]
    tr = fetch_transcripts(with_text=False)
    missing = [(e.ticker, e.call_date) for e in events if (e.ticker, e.call_date) not in tr]
    assert not missing, missing
    h, _ = event_list_sha(events, tr)
    ref = {}
    for l in (REPO / "analysis/data/run_state/resolve-open-four/cells.jsonl").read_text().splitlines():
        c = json.loads(l)
        if c["cell_key"] in REF_KEYS:
            ref[c["cell_key"]] = c["results"]
    rows = []
    for ph, key in zip(PHASES, REF_KEYS):
        res, _ = run_one(events, world, ph, 0)
        rows.append({"phase": ph, "res": res, "ref_key": key, "ref": ref[key]})
        print(f"phase {ph}: final {res['final']:,.2f} (ref {ref[key]['final']:,.2f}) session dd {100*res['dd_session']:.2f}% (ref {100*ref[key]['dd_session']:.2f}) "
              f"daily dd {100*res['dd_daily']:.2f}% (ref {100*ref[key]['dd_daily']:.2f})")
    fa = sum(r["res"]["final"] for r in rows) / 3
    sa = 100 * sum(r["res"]["dd_session"] for r in rows) / 3
    da = 100 * sum(r["res"]["dd_daily"] for r in rows) / 3
    print(f"phase-averaged: final ${fa:,.2f} (ref $184,819 +/- $1) | dd session {sa:.2f}% (ref 17.32 +/- 0.02) | dd daily {da:.2f}% (ref 23.46 +/- 0.02)")
    per_phase_ok = all(abs(r["res"]["final"] - REF["finals"][i]) <= 1.0 for i, r in enumerate(rows))
    ok = (abs(fa - REF["final_avg"]) <= 1.0 and abs(sa - REF["dd_session_avg"]) <= 0.02 and abs(da - REF["dd_daily_avg"]) <= 0.02 and per_phase_ok)
    exact = all(abs(r["res"]["final"] - r["ref"]["final"]) < 1e-6 for r in rows)
    out = {"match": ok, "bit_exact_vs_reference_cells": exact, "phase_avg_final": fa, "dd_session_avg_pct": sa, "dd_daily_avg_pct": da,
           "per_phase": [{"phase": r["phase"], "final": r["res"]["final"], "dd_session": r["res"]["dd_session"], "dd_daily": r["res"]["dd_daily"],
                          "reference_cell": r["ref_key"], "reference": r["ref"]} for r in rows],
           "reference_provenance": {"published": "docs/handoffs/2026-09-05-state-of-play.md s5.1 ($184,819 / 17.32% / 23.46%)",
                                    "cells": "analysis/data/run_state/resolve-open-four/cells.jsonl keys 1a-phase0/1a-phase10/1a-phase20 -> results.final, results.dd_session, results.dd_daily"},
           "n_events": len(events), "event_list_sha256": h, "trade_wrapper_active": True}
    (STATE / "repro.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "per_phase"}, indent=1, default=str))
    if not ok:
        raise SystemExit("HARD STOP (Step 0): the reference does not reproduce. Nothing else in this run means anything. Report.")
    write_manifest("repro", {"cell": CELL, "phases": list(PHASES), "seed": 0}, out,
                   corpus={"n_events": len(events), "tickers": sorted({e.ticker for e in events}), "event_list_sha256": h, "window": [S.START.isoformat(), S.C.isoformat()]})


# ------------------------------------------------------------------------------------------ events / transcripts
def cmd_events():
    events = S.load_events_dedup_on()[0]
    tr = fetch_transcripts(with_text=True)
    keys = [(e.ticker, e.call_date) for e in events]
    assert all(k in tr for k in keys)
    h, lst = event_list_sha(events, tr)
    disk = {}
    for k in keys:
        p = REPO / "analysis/data/transcripts" / f"{k[0]}_{k[1].isoformat()}.txt"
        if p.exists():
            a, b = " ".join(p.read_text().split()), " ".join((tr[k]["raw_text"] or "").split())
            disk[f"{k[0]}_{k[1]}"] = "identical" if a == b else f"differs (disk {len(a)} chars, db {len(b)})"
    empty = [f"{k[0]}_{k[1]}" for k in keys if not (tr[k]["raw_text"] or "").strip()]
    out = {"n_events": len(events), "event_list_sha256": h, "per_ticker": dict(Counter(e.ticker for e in events)),
           "transcripts": [{"ticker": t, "call_date": d, "transcript_id": i, "chars": len(tr[(t, date.fromisoformat(d))]["raw_text"] or ""),
                            "sha256": hashlib.sha256((tr[(t, date.fromisoformat(d))]["raw_text"] or "").encode()).hexdigest()} for t, d, i in lst],
           "on_disk_cross_check": {"n_on_disk": len(disk), "identical": sum(v == "identical" for v in disk.values()),
                                   "differs": {k: v for k, v in disk.items() if v != "identical"}},
           "empty_transcripts": empty}
    (STATE / "events_manifest.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "transcripts"}, indent=1))
    if empty:
        raise SystemExit(f"STOP: empty transcripts {empty}")


# ------------------------------------------------------------------------------------------ scoring
def guards():
    from analysis.version_guard import assert_prompt_hash
    reg = json.loads((REPO / "docs/architecture/VERSION_REGISTRY.json").read_text())["artifacts"]["evaluation_prompt"]
    b = p6.PROMPTS["B"].read_text()
    rs = next(c["sha256"] for c in reg["candidates"] if c["version"] == "P6B-minimal")
    assert hashlib.sha256(b.encode()).hexdigest() == rs, "arm B hash != registry"
    gb = assert_prompt_hash(b, candidate="P6B-minimal")
    ga = assert_prompt_hash(p6.PROMPTS["A"].read_text())
    assert ga["candidate_used"] is None
    return {"B": gb, "A_noise": ga}


def sysblock(text):
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def make_request(arm, key, text):
    from anthropic.types.messages.batch_create_params import Request
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    prompt = p6.PROMPTS["B" if arm == "B" else "A"].read_text()
    c = f"{arm}__{key[0]}_{key[1].isoformat()}"
    assert len(c) <= 64
    return Request(custom_id=c, params=MessageCreateParamsNonStreaming(
        model=MODEL, max_tokens=MAX_TOKENS, system=sysblock(prompt), messages=[{"role": "user", "content": text}]))


def scores_path(arm):
    return STATE / {"B": "scores_b_all16.jsonl", "N": "scores_noise_all16.jsonl"}[arm]


def noise_keys(events):
    keys = sorted((e.ticker, e.call_date) for e in events)
    return sorted(random.Random("p6b-e2e-noise-11").sample(keys, NOISE_N))


def committed(p):
    return sum(p.get("committed_usd_by_batch", {}).values())


def submit(arm, key_name, est_per_call):
    p = load_progress()
    if p.get(key_name):
        print(f"{key_name} already recorded: {p[key_name]} -- NOT submitting")
        return
    g = guards()
    events = S.load_events_dedup_on()[0]
    tr = fetch_transcripts(with_text=True)
    keys = sorted((e.ticker, e.call_date) for e in events) if arm == "B" else noise_keys(events)
    done = {(r["ticker"], date.fromisoformat(r["date"])) for r in p3.read_jsonl(scores_path(arm))}
    reqs = [make_request(arm, k, tr[k]["raw_text"]) for k in keys if k not in done]
    est = round(len(reqs) * est_per_call, 2)
    p = load_progress()
    others = sum(v for k, v in p.get("committed_usd_by_batch", {}).items() if k != key_name)
    print(f"{key_name}: {len(reqs)} requests x ${est_per_call:.4f} = ${est:.2f}; committed after = ${others + est:.2f} (cap ${CAP_USD})")
    if others + est > CAP_USD:
        raise SystemExit("HARD CAP reached. Stop and report.")
    p.setdefault("guards", {})[key_name] = g
    p.setdefault("committed_usd_by_batch", {})[key_name] = est
    save_progress(p)
    p3.submit_batch(reqs, key_name)
    print("COMMIT progress.json NOW (batch id written)")


def cmd_guards():
    print(json.dumps(guards(), indent=1))


def cmd_submit_b():
    submit("B", "batch_id_arm_b", EST_B)


def cmd_submit_noise():
    submit("N", "batch_id_noise", EST_N)


def route(raw):
    n = 0
    for r in p3.read_jsonl(raw):
        arm, rest = r["custom_id"].split("__", 1)
        tk, dt = rest.rsplit("_", 1)
        if (tk, dt) in {(x["ticker"], x["date"]) for x in p3.read_jsonl(scores_path(arm))}:
            continue
        p3.append_jsonl(scores_path(arm), {"custom_id": r["custom_id"], "arm": arm, "ticker": tk, "date": dt, "content": r["content"], "usage": r["usage"],
                                            "stop_reason": r["stop_reason"], "cost_usd": r["cost_usd"], "batch_id": r["batch_id"], "fetched_at": r["fetched_at"]})
        n += 1
    return n


def poll(key, raw_name):
    done = p3.poll_batch(key, raw_name, key)
    if done:
        print("routed", route(STATE / raw_name), "new rows")


def cmd_poll_b():
    poll("batch_id_arm_b", "raw_arm_b.jsonl")


def cmd_poll_noise():
    poll("batch_id_noise", "raw_noise.jsonl")


def parse_scores(arm):
    from analyst_direct_scorer import parse_structured
    out, bad = {}, []
    for r in p3.read_jsonl(scores_path(arm)):
        sc = parse_structured(r["content"])
        k = (r["ticker"], date.fromisoformat(r["date"]))
        if arm == "B":
            s = sc.get("score")
            if isinstance(s, int) and not isinstance(s, bool) and -5 <= s <= 5:
                out[k] = s
            else:
                bad.append((k, r["stop_reason"]))
        else:
            rec = (sc.get("recommendation") or "").strip().title()
            if rec in ("Hold", "Add", "Trim", "Exit"):
                out[k] = rec
            else:
                bad.append((k, r["stop_reason"]))
    return out, bad


# ------------------------------------------------------------------------------------------ cells
def cell_events(name, events, scores_b, fresh_v6):
    """Returns (events_for_cell, dropped)."""
    if name == "R":
        return events, []
    if name == "A0":
        return OV.overlay_a0(events), []
    if name == "N":
        return OV.overlay_a0(events, rec_override=fresh_v6), []
    if name == "B3":
        return OV.overlay_b(events, scores_b, add_cut=3)
    if name == "B2":
        return OV.overlay_b(events, scores_b, add_cut=2)
    raise ValueError(name)


def overlay_sha(evs):
    return hashlib.sha256(json.dumps([[e.ticker, e.call_date.isoformat(), e.per_call_rec, e.final_action, e.final_confidence, e.recommended_size, e.trajectory]
                                      for e in sorted(evs, key=lambda e: (e.ticker, e.call_date))]).encode()).hexdigest()


def cmd_cells(which=None):
    commit = assert_clean()
    world = load_world()
    events = world[0]
    scores_b, bad_b = parse_scores("B")
    fresh, bad_n = parse_scores("N")
    LOGS.mkdir(exist_ok=True)
    have = {json.loads(l)["config_hash"] for l in CELLS.read_text().splitlines()} if CELLS.exists() else set()
    plan = [("R", 0), ("A0", 0), ("B3", 0), ("B2", 0), ("N", 0), ("B3", 1), ("B3", 2), ("A0", 1), ("A0", 2)]
    if which:
        plan = [x for x in plan if x[0] in which.split(",")]
    for name, seed in plan:
        evs, dropped = cell_events(name, events, scores_b, fresh)
        osha = overlay_sha(evs)
        for ph in PHASES:
            params = {"cell": name, "seed": seed, "phase": ph, **{k: v for k, v in CELL.items()}}
            ch = hashlib.sha256((commit + json.dumps(params, sort_keys=True) + osha).encode()).hexdigest()[:16]
            if ch in have:
                print("reuse", name, seed, ph)
                continue
            res, logs = run_one(evs, world, ph, seed)
            res.update({"rec_counts_fed": rec_counts(evs), "n_events_fed": len(evs), "n_dropped_no_score": len(dropped), "dropped": [f"{t}_{d}" for t, d in dropped]})
            rec = {"cell_key": f"{name}-s{seed}-ph{ph}", "params": params, "config_hash": ch, "driver_commit": commit, "overlay_sha256": osha, "results": res}
            with gzip.open(LOGS / f"{name}-s{seed}-ph{ph}.json.gz", "wt") as f:
                json.dump(logs, f, default=str)
            p3.append_jsonl(CELLS, rec)
            have.add(ch)
            print(f"{name} seed {seed} phase {ph}: final ${res['final']:,.0f} dd session {100*res['dd_session']:.2f}% daily {100*res['dd_daily']:.2f}% adds {res['add_total']} dropped {len(dropped)}")


# ------------------------------------------------------------------------------------------ summary
def load_cells():
    return [json.loads(l) for l in CELLS.read_text().splitlines()]


def agg(cells, name, seed):
    rs = sorted([c for c in cells if c["params"]["cell"] == name and c["params"]["seed"] == seed], key=lambda c: c["params"]["phase"])
    if len(rs) != 3:
        return None
    f = [c["results"]["final"] for c in rs]
    return {"finals": f, "final_avg": sum(f) / 3, "phase_min": min(f), "phase_max": max(f), "phase_spread": max(f) - min(f),
            "dd_session_avg": 100 * sum(c["results"]["dd_session"] for c in rs) / 3, "dd_daily_avg": 100 * sum(c["results"]["dd_daily"] for c in rs) / 3,
            "dd_daily_by_phase": [100 * c["results"]["dd_daily"] for c in rs], "runs": [c["results"] for c in rs]}


def first_divergence(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n if len(a) != len(b) else None


CARRIERS = ("AVGO", "NVDA", "ORCL", "TTD")
SPECULATIVES = ("AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR")


def phase_mean(cells, name, seed, fn):
    rs = [c["results"] for c in cells if c["params"]["cell"] == name and c["params"]["seed"] == seed]
    vals = [fn(r) for r in rs]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def fwd_ret(prices, tk, d, days):
    p0, p1 = prices.price_on(tk, d), prices.price_on(tk, min(d + timedelta(days=days), S.C))
    return None if not p0 or not p1 else p1 / p0 - 1


def cmd_summary():
    cells = load_cells()
    events, _, _, _, prices = load_world()
    scores_b, _ = parse_scores("B")
    fresh, _ = parse_scores("N")
    S_ = {"cells": {}, "diag": {}}
    for name in ("R", "A0", "B3", "B2", "N"):
        a = agg(cells, name, 0)
        if a:
            S_["cells"][name] = a
    for name in ("B3", "A0"):
        for sd in (1, 2):
            a = agg(cells, name, sd)
            if a:
                S_["cells"][f"{name}_seed{sd}"] = a
    # draw spread: seeds 0/1/2 phase finals identical?
    S_["draw_spread"] = {n: max(abs(x - y) for x, y in zip(S_["cells"][n]["finals"], S_["cells"][f"{n}_seed{sd}"]["finals"]))
                         for n in ("B3", "A0") for sd in (1, 2) if f"{n}_seed{sd}" in S_["cells"]}
    # decision-stream diff B3 vs A0, per phase, seed 0
    diffs = []
    for ph in PHASES:
        la = [tuple(x) for x in json.load(gzip.open(LOGS / f"A0-s0-ph{ph}.json.gz", "rt"))["trades"]]
        lb = [tuple(x) for x in json.load(gzip.open(LOGS / f"B3-s0-ph{ph}.json.gz", "rt"))["trades"]]
        i = first_divergence(la, lb)
        diffs.append({"phase": ph, "n_A0": len(la), "n_B3": len(lb), "first_divergence_index": i, "matched_before_divergence": i,
                      "first_A0": la[i] if i is not None and i < len(la) else None, "first_B3": lb[i] if i is not None and i < len(lb) else None,
                      "n_identical_rows": len(set(la) & set(lb))})
    S_["decision_stream_diff_B3_vs_A0"] = diffs
    # per-cell diagnostics, phase-averaged (seed 0)
    keys = ["add_total", "fully_funded", "partial", "unfunded", "sessions_with_cash_bound", "n_displacements", "avg_cash_pct_sessions",
            "days_to_cash_below_5pct", "days_to_cash_below_10pct", "ending_cash_pct", "n_buy_trades", "n_sell_trades", "buy_dollars", "sale_dollars",
            "turnover_buys_plus_sells_over_avg_nav", "distinct_tickers", "realized_gains", "total_shortfall"]
    for name in ("R", "A0", "B3", "B2", "N"):
        S_["diag"][name] = {k: phase_mean(cells, name, 0, lambda r, k=k: r.get(k)) for k in keys}
        rc = [c["results"]["rec_counts_fed"] for c in cells if c["params"]["cell"] == name and c["params"]["seed"] == 0][0]
        S_["diag"][name]["rec_counts_fed"] = rc
        S_["diag"][name]["binding_counts_ph0"] = [c["results"]["binding_counts"] for c in cells if c["params"]["cell"] == name and c["params"]["seed"] == 0][0]
        tickers = sorted({t for c in cells if c["params"]["cell"] == name and c["params"]["seed"] == 0 for t in c["results"]["ending_weights"]})
        S_["diag"][name]["ending_weights_pct"] = {t: 100 * phase_mean(cells, name, 0, lambda r, t=t: r["ending_weights"].get(t, 0.0)) for t in tickers}
        w = S_["diag"][name]["ending_weights_pct"]
        S_["diag"][name]["carriers_share_pct"] = sum(w.get(t, 0) for t in CARRIERS)
        S_["diag"][name]["speculatives_share_pct"] = sum(w.get(t, 0) for t in SPECULATIVES)
        fin = sum(c["results"]["final"] for c in cells if c["params"]["cell"] == name and c["params"]["seed"] == 0) / 3
        S_["diag"][name]["ending_dollars"] = {t: fin * v / 100 for t, v in w.items()}
    # v6 archive rec -> B3 rec crosstab and Add-quality on the events themselves
    ct = Counter((e.per_call_rec, OV.map_score(scores_b[(e.ticker, e.call_date)], 3)) for e in events)
    S_["crosstab_v6_to_B3"] = {f"{a}->{b}": n for (a, b), n in sorted(ct.items())}
    qual = {}
    for label, recfn in (("v6 archive", lambda e: e.per_call_rec), ("B3", lambda e: OV.map_score(scores_b[(e.ticker, e.call_date)], 3)),
                         ("B2", lambda e: OV.map_score(scores_b[(e.ticker, e.call_date)], 2))):
        for grp, tks in (("all", None), ("carriers", CARRIERS), ("speculatives", SPECULATIVES)):
            for rec in ("Add", "Hold", "Trim", "Exit"):
                xs = [fwd_ret(prices, e.ticker, e.call_date, 182) for e in events if recfn(e) == rec and (tks is None or e.ticker in tks)]
                xs = [x for x in xs if x is not None]
                if xs:
                    qual[f"{label}|{grp}|{rec}"] = {"n": len(xs), "median_182d_raw_return_pct": 100 * statistics.median(xs), "mean_182d_raw_return_pct": 100 * statistics.mean(xs),
                                                    "share_up_pct": 100 * sum(x > 0 for x in xs) / len(xs)}
    S_["add_hold_trim_quality_182d"] = qual
    (STATE / "summary.json").write_text(json.dumps(S_, indent=1, default=str))
    for k, v in S_["cells"].items():
        print(f"{k:10} final ${v['final_avg']:,.0f} phases {[round(x) for x in v['finals']]} spread ${v['phase_spread']:,.0f} dd session {v['dd_session_avg']:.2f}% daily {v['dd_daily_avg']:.2f}%")
    print("draw spread (max abs $ diff of phase finals vs seed 0):", S_["draw_spread"])
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("ending_weights_pct", "ending_dollars", "binding_counts_ph0")} for k, v in S_["diag"].items()}, indent=1, default=str))
    print(json.dumps(diffs, indent=1, default=str))


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "").replace("-", "_")
    fn = globals().get("cmd_" + cmd)
    if fn:
        fn(*sys.argv[2:])
    else:
        print(__doc__)
