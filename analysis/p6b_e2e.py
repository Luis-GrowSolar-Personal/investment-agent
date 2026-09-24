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

# --run confound (prompts/P6B-confound-and-concentration.md): same driver, extended. B and noise scores are READ from the
# end-to-end run's committed files; new outputs go to this run's own state directory.
RUN_MODE = "e2e"
if "--run" in sys.argv:
    _i = sys.argv.index("--run")
    RUN_MODE = sys.argv[_i + 1]
    del sys.argv[_i:_i + 2]
CONFOUND = RUN_MODE == "confound"
PRIOR_ID = "p6b-end-to-end-check"
PRIOR = REPO / "analysis/data/run_state" / PRIOR_ID
RUN_ID = "p6b-confound-and-concentration" if CONFOUND else PRIOR_ID
STATE = REPO / "analysis/data/run_state" / RUN_ID
PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
CELLS = STATE / "cells.jsonl"
LOGS = STATE / "logs"
DRIVER_FILE = "analysis/p6b_e2e.py"
PRICE_CACHE = REPO / "analysis/data/price_cache.json"
FUND_CACHE = REPO / "analysis/data/fundamentals_cache.json"
TYPE_JSON = REPO / "analysis/data/type_classifications.json"
CAP_USD = 12.0 if CONFOUND else 15.0
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
    prompt = p6.PROMPTS["B" if arm == "B" else "A"].read_text()      # N and V both run unmodified v6
    c = f"{arm}__{key[0]}_{key[1].isoformat()}"
    assert len(c) <= 64
    return Request(custom_id=c, params=MessageCreateParamsNonStreaming(
        model=MODEL, max_tokens=MAX_TOKENS, system=sysblock(prompt), messages=[{"role": "user", "content": text}]))


def scores_path(arm):
    base = PRIOR if CONFOUND else STATE           # B and the noise arm are read from the end-to-end run in confound mode
    if arm == "V":
        return STATE / "scores_v6_sonnet46_all16.jsonl"      # merged 195 rows (reused noise rows + new rows)
    return base / {"B": "scores_b_all16.jsonl", "N": "scores_noise_all16.jsonl"}[arm]


def new_rows_path():
    return STATE / "scores_v6_sonnet46_new_rows.jsonl"


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


def guards_v6():
    """Confound run: only the promoted v6 hash is asserted (no candidate); B is not re-scored."""
    from analysis.version_guard import assert_prompt_hash
    g = assert_prompt_hash(p6.PROMPTS["A"].read_text())
    assert g["candidate_used"] is None
    return {"A_promoted_v6": g}


def cmd_guards():
    print(json.dumps(guards_v6() if CONFOUND else guards(), indent=1))


def cmd_submit_b():
    submit("B", "batch_id_arm_b", EST_B)


def cmd_submit_noise():
    submit("N", "batch_id_noise", EST_N)


def route(raw):
    n = 0
    for r in p3.read_jsonl(raw):
        arm, rest = r["custom_id"].split("__", 1)
        tk, dt = rest.rsplit("_", 1)
        dest = new_rows_path() if arm == "V" else scores_path(arm)
        if (tk, dt) in {(x["ticker"], x["date"]) for x in p3.read_jsonl(dest)}:
            continue
        p3.append_jsonl(dest, {"custom_id": r["custom_id"], "arm": arm, "ticker": tk, "date": dt, "content": r["content"], "usage": r["usage"],
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


# ------------------------------------------------------------------------------------------ confound run: v6 on claude-sonnet-4-6
def cmd_submit_v6():
    p = load_progress()
    if p.get("batch_id_v6"):
        print(f"batch_id_v6 already recorded: {p['batch_id_v6']} -- NOT submitting")
        return
    g = guards_v6()
    events = S.load_events_dedup_on()[0]
    tr = fetch_transcripts(with_text=True)
    have = {(r["ticker"], date.fromisoformat(r["date"])) for r in p3.read_jsonl(scores_path("N"))}       # reused verbatim
    keys = sorted((e.ticker, e.call_date) for e in events)
    assert len(keys) == 195 and have <= set(keys)
    rest = [k for k in keys if k not in have]
    reqs = [make_request("V", k, tr[k]["raw_text"]) for k in rest]
    est = round(len(reqs) * EST_N, 2)
    print(f"batch_id_v6: {len(reqs)} requests (reusing {len(have)} noise-arm rows) x ${EST_N:.4f} = ${est:.2f} (cap ${CAP_USD})")
    if est > CAP_USD:
        raise SystemExit("HARD CAP reached. Stop and report.")
    p["guards"] = g
    p["committed_usd_by_batch"] = {"batch_id_v6": est}
    save_progress(p)
    p3.submit_batch(reqs, "batch_id_v6")
    print("COMMIT progress.json NOW (batch id written)")


def cmd_poll_v6():
    poll("batch_id_v6", "raw_v6.jsonl")


def cmd_merge_v6():
    """195 rows: the noise arm's 100 rows verbatim + the new rows. Asserts full coverage and reports parse / stop-reason status."""
    from analyst_direct_scorer import parse_structured
    events = S.load_events_dedup_on()[0]
    keys = {(e.ticker, e.call_date.isoformat()) for e in events}
    rows = {}
    for r in p3.read_jsonl(scores_path("N")):
        rows[(r["ticker"], r["date"])] = {**r, "source": "noise_arm_reused_verbatim"}
    for r in p3.read_jsonl(new_rows_path()):
        rows[(r["ticker"], r["date"])] = {**r, "source": "this_run"}
    assert set(rows) == keys and len(rows) == 195, f"coverage: {len(rows)} rows, missing {sorted(keys - set(rows))[:5]}, extra {sorted(set(rows) - keys)[:5]}"
    out = scores_path("V")
    out.write_text("")
    bad, stops = [], Counter()
    for k in sorted(rows):
        r = rows[k]
        rec = (parse_structured(r["content"]).get("recommendation") or "").strip().title()
        stops[r["stop_reason"]] += 1
        if rec not in ("Hold", "Add", "Trim", "Exit"):
            bad.append({"key": list(k), "stop_reason": r["stop_reason"], "recommendation": rec})
        p3.append_jsonl(out, r)
    res = {"rows": len(rows), "from_noise_arm": sum(r["source"].startswith("noise") for r in rows.values()), "new": sum(r["source"] == "this_run" for r in rows.values()),
           "unparsed_or_no_direction": bad, "stop_reasons": dict(stops), "cost_new_usd": round(sum(r["cost_usd"] for r in rows.values() if r["source"] == "this_run"), 4)}
    (STATE / "merge_v6_report.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


# ------------------------------------------------------------------------------------------ confound run: cells
LOO_TICKERS = S.ALL16


def _cell_events(name, events, scores_b, fresh):
    if name == "A0p":
        return OV.overlay_a0(events, rec_override=fresh), []
    return cell_events(name, events, scores_b, fresh)


def cmd_full():
    """R, A0, A0' (fresh v6 on claude-sonnet-4-6, all 195), B3: full universe, seed 0, phases 0/10/20. Logs kept for the decision-stream diff."""
    commit = assert_clean()
    world = load_world()
    events = world[0]
    scores_b, _ = parse_scores("B")
    fresh, bad = parse_scores("V")
    assert len(fresh) + len(bad) == 195
    LOGS.mkdir(exist_ok=True)
    have = {json.loads(l)["config_hash"] for l in CELLS.read_text().splitlines()} if CELLS.exists() else set()
    for name in ("A0p", "A0", "B3"):
        evs, dropped = _cell_events(name, events, scores_b, fresh)
        osha = overlay_sha(evs)
        for ph in PHASES:
            params = {"cell": name, "seed": 0, "phase": ph, "universe": "full", **CELL}
            ch = hashlib.sha256((commit + json.dumps(params, sort_keys=True) + osha).encode()).hexdigest()[:16]
            if ch in have:
                print("reuse", name, ph)
                continue
            res, logs = run_one(evs, world, ph, 0)
            res.update({"rec_counts_fed": rec_counts(evs), "n_events_fed": len(evs), "n_dropped_no_score": len(dropped)})
            with gzip.open(LOGS / f"{name}-s0-ph{ph}.json.gz", "wt") as f:
                json.dump(logs, f, default=str)
            p3.append_jsonl(CELLS, {"cell_key": f"{name}-full-s0-ph{ph}", "params": params, "config_hash": ch, "driver_commit": commit, "overlay_sha256": osha, "results": res})
            have.add(ch)
            print(f"{name} phase {ph}: final ${res['final']:,.0f} dd session {100*res['dd_session']:.2f}% daily {100*res['dd_daily']:.2f}% adds {res['add_total']}")


def cmd_loo():
    """Leave-one-ticker-out: drop each name's events entirely (no starter, no Adds, no donor role) from A0, A0' and B3; seed 0, three phases."""
    commit = assert_clean()
    world = load_world()
    events = world[0]
    scores_b, _ = parse_scores("B")
    fresh, _ = parse_scores("V")
    have = {json.loads(l)["config_hash"] for l in CELLS.read_text().splitlines()} if CELLS.exists() else set()
    base = {name: _cell_events(name, events, scores_b, fresh)[0] for name in ("A0", "A0p", "B3")}
    n_new = 0
    for tk in LOO_TICKERS:
        for name in ("A0", "A0p", "B3"):
            evs = [e for e in base[name] if e.ticker != tk]
            osha = overlay_sha(evs)
            for ph in PHASES:
                params = {"cell": name, "seed": 0, "phase": ph, "universe": f"minus_{tk}", **CELL}
                ch = hashlib.sha256((commit + json.dumps(params, sort_keys=True) + osha).encode()).hexdigest()[:16]
                if ch in have:
                    continue
                res, _ = run_one(evs, world, ph, 0)
                keep = {k: res[k] for k in ("final", "dd_session", "dd_daily", "add_total", "n_events", "distinct_tickers", "skipped_events")}
                keep["n_events_fed"] = len(evs)
                p3.append_jsonl(CELLS, {"cell_key": f"LOO-{tk}-{name}-s0-ph{ph}", "params": params, "config_hash": ch, "driver_commit": commit, "overlay_sha256": osha, "results": keep})
                have.add(ch)
                n_new += 1
    print("LOO runs written:", n_new)


def _full(cells, name):
    rs = sorted([c for c in cells if c["params"].get("universe") == "full" and c["params"]["cell"] == name], key=lambda c: c["params"]["phase"])
    if len(rs) != 3:
        return None
    f = [c["results"]["final"] for c in rs]
    return {"finals": f, "final_avg": sum(f) / 3, "phase_min": min(f), "phase_max": max(f), "spread": max(f) - min(f),
            "dd_daily_avg": 100 * sum(c["results"]["dd_daily"] for c in rs) / 3, "dd_session_avg": 100 * sum(c["results"]["dd_session"] for c in rs) / 3,
            "dd_daily_by_phase": [100 * c["results"]["dd_daily"] for c in rs], "runs": [c["results"] for c in rs]}


def _ending_dollars(runs, final_avg):
    tks = sorted({t for r in runs for t in r["ending_weights"]})
    return {t: final_avg * sum(r["ending_weights"].get(t, 0.0) for r in runs) / len(runs) for t in tks}


def cmd_summary_confound():
    cells = load_cells()
    prior = [json.loads(l) for l in (PRIOR / "cells.jsonl").read_text().splitlines()]
    events = S.load_events_dedup_on()[0]
    scores_b, _ = parse_scores("B")
    fresh, bad = parse_scores("V")
    out = {"cells": {}}
    for name in ("A0", "A0p", "B3"):
        out["cells"][name] = _full(cells, name)
    # R (from the reproduction) and the prior run's R / B2 / N for the side-by-side table
    rep = json.loads((STATE / "repro.json").read_text())
    out["R_reproduction"] = {"phase_avg_final": rep["phase_avg_final"], "dd_daily_avg_pct": rep["dd_daily_avg_pct"], "match": rep["match"]}
    pa = lambda nm: agg(prior, nm, 0)
    out["prior"] = {nm: pa(nm) for nm in ("R", "A0", "B3", "B2", "N")}
    out["consistency_vs_prior_run"] = {nm: {"final_diff_usd": out["cells"][nm]["final_avg"] - out["prior"][nm]["final_avg"],
                                            "dd_daily_diff_pts": out["cells"][nm]["dd_daily_avg"] - out["prior"][nm]["dd_daily_avg"]} for nm in ("A0", "B3")}
    a0, a0p, b3 = out["cells"]["A0"], out["cells"]["A0p"], out["cells"]["B3"]
    model_share, prompt_share = a0p["final_avg"] - a0["final_avg"], b3["final_avg"] - a0p["final_avg"]
    if b3["final_avg"] > a0p["phase_max"] and b3["phase_min"] > a0p["phase_max"]:
        branch = "B3 ABOVE A0' phase range -> the prompt is the cause"
    elif a0p["final_avg"] >= b3["phase_min"]:
        branch = "A0' RISES INTO OR ABOVE B3's phase range -> the model is the cause"
    else:
        branch = "IN BETWEEN -> report both contributions"
    out["reading"] = {"A0p_final": a0p["final_avg"], "A0p_phase_range": [a0p["phase_min"], a0p["phase_max"]], "A0p_dd_daily": a0p["dd_daily_avg"],
                      "model_share_A0p_minus_A0": model_share, "prompt_share_B3_minus_A0p": prompt_share, "total_B3_minus_A0": b3["final_avg"] - a0["final_avg"],
                      "branch": branch, "B3_phase_range": [b3["phase_min"], b3["phase_max"]],
                      "B3_lowest_phase_minus_A0p_highest_phase": b3["phase_min"] - a0p["phase_max"]}
    # verdict mix and agreement, all 195
    arch = {(e.ticker, e.call_date): e.per_call_rec for e in events}
    mix_a, mix_f = Counter(arch.values()), Counter(fresh.get(k) for k in arch)
    ct = Counter((arch[k], fresh[k]) for k in arch)
    srcs = {(r["ticker"], date.fromisoformat(r["date"])): r["source"] for r in p3.read_jsonl(scores_path("V"))}
    out["verdict_mix"] = {"archived_v6": dict(mix_a), "fresh_v6_sonnet46": dict(mix_f), "crosstab_archived_to_fresh": {f"{a}->{b}": n for (a, b), n in sorted(ct.items())},
                          "agreement_n": sum(n for (a, b), n in ct.items() if a == b), "n": len(arch),
                          "by_source": {src: {"archived": dict(Counter(arch[k] for k in arch if srcs[k] == src)), "fresh": dict(Counter(fresh[k] for k in arch if srcs[k] == src))}
                                        for src in sorted(set(srcs.values()))},
                          "unparsed": bad}
    # the four carrying names: archived v6 vs fresh v6 vs B, event by event
    out["carriers"] = [{"ticker": e.ticker, "call_date": e.call_date.isoformat(), "archived_v6": e.per_call_rec, "fresh_v6": fresh[(e.ticker, e.call_date)],
                        "B_score": scores_b[(e.ticker, e.call_date)], "B3": OV.map_score(scores_b[(e.ticker, e.call_date)], 3)}
                       for e in sorted(events, key=lambda e: (e.ticker, e.call_date)) if e.ticker in CARRIERS]
    # ending value by stock, A0' beside R / A0 / B3 / B2 (phase-averaged, seed 0)
    ed = {}
    for nm, src in (("R", out["prior"]["R"]), ("A0", a0), ("A0p", a0p), ("B3", b3), ("B2", out["prior"]["B2"])):
        runs = src["runs"]
        ed[nm] = _ending_dollars(runs, src["final_avg"])
    out["ending_dollars"] = ed
    # decision-stream diff A0 -> A0'
    diffs = []
    for ph in PHASES:
        la = [tuple(x) for x in json.load(gzip.open(LOGS / f"A0-s0-ph{ph}.json.gz", "rt"))["trades"]]
        lb = [tuple(x) for x in json.load(gzip.open(LOGS / f"A0p-s0-ph{ph}.json.gz", "rt"))["trades"]]
        i = first_divergence(la, lb)
        diffs.append({"phase": ph, "n_A0": len(la), "n_A0p": len(lb), "first_divergence_index": i, "matched_before_divergence": i,
                      "first_A0": la[i] if i is not None and i < len(la) else None, "first_A0p": lb[i] if i is not None and i < len(lb) else None,
                      "n_identical_rows": len(set(la) & set(lb)), "share_of_A0_rows_also_in_A0p": len(set(la) & set(lb)) / len(set(la))})
    out["decision_stream_diff_A0_vs_A0p"] = diffs
    # leave-one-out
    loo = {}
    for c in cells:
        u = c["params"].get("universe", "")
        if u.startswith("minus_"):
            loo.setdefault(u[6:], {}).setdefault(c["params"]["cell"], []).append(c["results"])
    rows = []
    for tk, d in loo.items():
        if not all(len(d.get(n, [])) == 3 for n in ("A0", "A0p", "B3")):
            continue
        av = lambda n, k: sum(r[k] for r in d[n]) / 3
        rows.append({"dropped": tk, "A0": av("A0", "final"), "A0p": av("A0p", "final"), "B3": av("B3", "final"), "gap": av("B3", "final") - av("A0p", "final"),
                     "gap_pct_of_A0p": 100 * (av("B3", "final") - av("A0p", "final")) / av("A0p", "final"), "gap_vs_A0": av("B3", "final") - av("A0", "final"),
                     "B3_dd_daily": 100 * av("B3", "dd_daily"), "A0p_dd_daily": 100 * av("A0p", "dd_daily"), "A0_dd_daily": 100 * av("A0", "dd_daily"),
                     "B3_phase_min": min(r["final"] for r in d["B3"]), "A0p_phase_max": max(r["final"] for r in d["A0p"])})
    order = ["NVDA"] + [r["dropped"] for r in sorted([r for r in rows if r["dropped"] != "NVDA"], key=lambda r: r["gap"])]
    rows = sorted(rows, key=lambda r: order.index(r["dropped"]))
    ref = {"dropped": "none (full universe)", "A0": a0["final_avg"], "A0p": a0p["final_avg"], "B3": b3["final_avg"], "gap": prompt_share,
           "gap_pct_of_A0p": 100 * prompt_share / a0p["final_avg"], "gap_vs_A0": b3["final_avg"] - a0["final_avg"], "B3_dd_daily": b3["dd_daily_avg"],
           "A0p_dd_daily": a0p["dd_daily_avg"], "A0_dd_daily": a0["dd_daily_avg"], "B3_phase_min": b3["phase_min"], "A0p_phase_max": a0p["phase_max"]}
    out["loo"] = {"reference": ref, "rows": rows, "n_rows": len(rows),
                  "gap_positive_in": sum(r["gap"] > 0 for r in rows), "gap_flips_on": [r["dropped"] for r in rows if r["gap"] <= 0],
                  "smallest_gap": min((r["gap"], r["dropped"]) for r in rows) if rows else None,
                  "gap_without_NVDA": next((r["gap"] for r in rows if r["dropped"] == "NVDA"), None),
                  "B3_dd_better_than_A0p_in": sum(r["B3_dd_daily"] < r["A0p_dd_daily"] for r in rows), "B3_dd_worse_rows": [r["dropped"] for r in rows if r["B3_dd_daily"] >= r["A0p_dd_daily"]],
                  "B3_lowest_phase_above_A0p_highest_in": sum(r["B3_phase_min"] > r["A0p_phase_max"] for r in rows)}
    (STATE / "summary.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("reading", "verdict_mix", "consistency_vs_prior_run", "decision_stream_diff_A0_vs_A0p")}, indent=1, default=str))
    print("LOO", json.dumps({k: v for k, v in out["loo"].items() if k != "rows"}, default=str))
    for r in [out["loo"]["reference"]] + out["loo"]["rows"]:
        print(f"{r['dropped']:20} A0 {r['A0']:>9,.0f}  A0' {r['A0p']:>9,.0f}  B3 {r['B3']:>9,.0f}  gap {r['gap']:>9,.0f} ({r['gap_pct_of_A0p']:5.1f}%)  dd B3 {r['B3_dd_daily']:5.2f} A0' {r['A0p_dd_daily']:5.2f}")

if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "").replace("-", "_")
    fn = globals().get("cmd_" + cmd)
    if fn:
        fn(*sys.argv[2:])
    else:
        print(__doc__)
