#!/usr/bin/env python3
"""
p6_output_format_driver.py -- prompts/P6-output-format-round.md (run_id p6-output-format-round)

Setup, guard, batch submission and collection for the P6 output-format round.
Batch machinery, alias resolution and stratum_map() are IMPORTED from
p3_guidance_ledger_driver (its module-level STATE/PROGRESS/FINDINGS/EXCLUDE are
re-pointed at this run; nothing is rewritten). The analysis lives in
p6_output_format_analysis.py ($0, no model calls).

Commands:
  check0f            alias/count asserts (Step 0f), plus the PARA-excluded counts
  register           register P6B-minimal / P6C-score as candidates + run the guard (Step 0d)
  protocol           write SCORING_PROTOCOL_P6.json (Step 0e)
  select             pre-flight (100 transcripts) and noise-arm (120) selections, fixed seeds
  preflight-submit / preflight-poll / preflight-report
  submit-b / submit-c   full arms (C batch carries the 21a noise arm)
  poll-b / poll-c
Real spend: submit-* and preflight-submit only. Everything else is $0.
"""
import sys, json, re, glob, hashlib, random, datetime, subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO))
import p3_guidance_ledger_driver as p3  # noqa: E402

RUN_ID = "p6-output-format-round"
STATE = REPO / "analysis/data/run_state" / RUN_ID
PROGRESS = STATE / "progress.json"
FINDINGS = STATE / "findings.md"
C2 = REPO / "analysis/data/corpus_v2"
PRICE_CACHE_REL = "analysis/data/corpus_v2/scorer_price_cache_v1.json"
V6_EVAL_DIR = p3.V6_EVAL_DIR
PROMPTS = {
    "A": REPO / "docs/EVALUATION_PROMPT.md",
    "B": REPO / "docs/prompts/candidates/EVALUATION_PROMPT_P6B_minimal.md",
    "C": REPO / "docs/prompts/candidates/EVALUATION_PROMPT_P6C_score.md",
}
CAND_NAME = {"B": "P6B-minimal", "C": "P6C-score"}
EVAL_DIR = {a: REPO / f"analysis/data/evals/{n}_claude-sonnet-4-6" for a, n in CAND_NAME.items()}
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
EXCLUDE = {"WOLF", "SPWR", "PARA"}
CAP_USD = 130.0
EST_PER_CALL = 0.0380          # measured batch $/call, prompt header
PREFLIGHT_N = 100
NOISE_N = 120
THRESHOLDS = {"bearish_lte": -2, "bullish_gte": 2, "neutral": [-1, 0, 1]}

# re-point the imported machinery at THIS run
p3.STATE, p3.PROGRESS, p3.FINDINGS = STATE, PROGRESS, FINDINGS
p3.EXCLUDE = set(EXCLUDE)


def now():
    return p3.now()


def load_progress():
    return json.loads(PROGRESS.read_text())


def save_progress(p):
    PROGRESS.write_text(json.dumps(p, indent=2, default=str))


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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*a):
    return subprocess.check_output(["git", *a], cwd=REPO).decode().strip()


# --------------------------------------------------------------------------- 0f
def cmd_check0f():
    """p3's assertions (1,240 files / 56 companies / 1,240 evals / 1,184 predecessor-bearing, MAXN empty),
    run with p3's own exclusion set (WOLF, SPWR); then the PARA-excluded population this run uses."""
    p3.EXCLUDE = {"WOLF", "SPWR"}
    try:
        p3.cmd_check0f()
    finally:
        p3.EXCLUDE = set(EXCLUDE)
    recs = p3.all_train_records()
    with_para = {"WOLF", "SPWR"}
    p3.EXCLUDE = with_para
    all_ = p3.all_train_records()
    p3.EXCLUDE = set(EXCLUDE)
    para = [r for r in all_ if r["ticker"] == "PARA"]
    out = {"resolved_files_with_PARA": len(all_), "para_files": len(para),
           "resolved_files_p6": len(recs), "companies_p6": len({r["ticker"] for r in recs}),
           "exclusion": sorted(EXCLUDE), "predecessor_bearing_p6": len(recs) - len({r["ticker"] for r in recs})}
    (STATE / "step0f_p6_counts.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


# --------------------------------------------------------------------------- 0d
def cmd_register():
    from analysis.version_guard import assert_prompt_hash
    regp = REPO / "docs/architecture/VERSION_REGISTRY.json"
    reg = json.loads(regp.read_text())
    cands = reg["artifacts"]["evaluation_prompt"]["candidates"]
    have = {c["version"] for c in cands}
    date = "2026-09-23"
    spec = {"P6B-minimal": ("B", "none", "Arm B, the control: no rubric; objective, constraint, -5..+5 score with noRead, 3-5 sentence read. Not a v6 derivative."),
            "P6C-score": ("C", "v6", "Arm C: v6 with only the RECOMMENDATION section replaced by a SCORE section; recommendation replaced by score/noRead/wrongIf in the structured block.")}
    for v, (arm, parent, detail) in spec.items():
        if v in have:
            continue
        cands.append({"version": v, "status": "candidate", "parent": parent, "registered": date,
                      "path": str(PROMPTS[arm].relative_to(REPO)), "sha256": sha(PROMPTS[arm]),
                      "detail": detail + " prompts/P6-output-format-round.md. Not gated, not promoted. "
                                "version_guard checks the candidate NAME only; the driver asserts the sha256 itself."})
    regp.write_text(json.dumps(reg, indent=2) + "\n")
    for arm in ("B", "C"):
        r = assert_prompt_hash(PROMPTS[arm].read_text(), candidate=CAND_NAME[arm], path_in_repo=str(PROMPTS[arm].relative_to(REPO)))
        print(arm, json.dumps(r))
    g = assert_prompt_hash(PROMPTS["A"].read_text())
    assert g["candidate_used"] is None
    print("A", json.dumps(g))


def guards():
    """Three assertions, all recorded: B vs candidate P6B-minimal, C vs P6C-score, v6 (noise) vs promoted hash."""
    from analysis.version_guard import assert_prompt_hash
    reg = json.loads((REPO / "docs/architecture/VERSION_REGISTRY.json").read_text())["artifacts"]["evaluation_prompt"]
    out = {}
    for arm in ("B", "C"):
        t = PROMPTS[arm].read_text()
        rs = next(c["sha256"] for c in reg["candidates"] if c["version"] == CAND_NAME[arm])
        assert hashlib.sha256(t.encode()).hexdigest() == rs, f"arm {arm} hash != registry"
        out[arm] = assert_prompt_hash(t, candidate=CAND_NAME[arm])
    out["A_noise"] = assert_prompt_hash(PROMPTS["A"].read_text())
    assert out["A_noise"]["candidate_used"] is None
    return out


# --------------------------------------------------------------------------- 0e
def cmd_protocol():
    sp = json.loads(p3.SPLIT.read_text())
    rt = p3.resolved_train()
    reg = json.loads((REPO / "docs/architecture/VERSION_REGISTRY.json").read_text())
    proto = {
        "run_id": RUN_ID, "registered_at": now(), "split_scored": "train",
        "company_list_original": sp["train"], "company_list_resolved": [w for _, w in rt],
        "excluded_entirely": sorted(EXCLUDE),
        "excluded_note": "WOLF, SPWR (no price data); PARA (corrupt price series, 2026-09-23 state of play 4.1)",
        "manifest_source": "analysis/data/corpus_v2/CORPUS_MANIFEST_V7.json",
        "manifest_sha256": sha(C2 / "CORPUS_MANIFEST_V7.json"),
        "split_source": "analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json", "split_sha256": sha(p3.SPLIT),
        "prompts": {a: {"path": str(PROMPTS[a].relative_to(REPO)), "sha256": sha(PROMPTS[a])} for a in "ABC"},
        "arm_roles": {"A": "v6 promoted, already scored on train (noise arm re-scores 120 with it)",
                      "B": "P6B-minimal, control", "C": "P6C-score, v6 with SCORE section replacing RECOMMENDATION"},
        "model_version_pinned": MODEL, "model_matches_baselines": True,
        "model_baseline_evidence": "SCORING_PROTOCOL_P3A.json -> model_version_pinned = claude-sonnet-4-6",
        "price_cache_path": PRICE_CACHE_REL,
        "entry_for_money": "rel_ret arm B (first close strictly after the call date), 182 days, SPY benchmark",
        "score_to_direction_thresholds_fixed_before_any_result": THRESHOLDS,
        "request_caps": {"preflight": 200, "arm_b": 1300, "arm_c": 1300, "noise": NOISE_N},
        "spend_caps_usd": {"total": CAP_USD, "per_full_arm_projection_stop": 55},
        "max_tokens_scoring": MAX_TOKENS,
        "eval_caches": {a: str(EVAL_DIR[a].relative_to(REPO)) + "/" for a in "BC"},
        "noise_arm_scores": f"analysis/data/run_state/{RUN_ID}/scores_noise.jsonl (v6 eval cache is NOT overwritten)",
        "disjointness": {"train_tune": not (set(sp["train"]) & set(sp["tune"])),
                         "train_holdout": not (set(sp["train"]) & set(sp["holdout"]))},
        "seeds": {"preflight": "random.Random('p6-preflight-11')", "noise": "random.Random('p6-noise-11')"},
    }
    assert proto["disjointness"]["train_tune"] and proto["disjointness"]["train_holdout"]
    assert PRICE_CACHE_REL == str(p3.PRICE_CACHE), (PRICE_CACHE_REL, p3.PRICE_CACHE)
    (C2 / "SCORING_PROTOCOL_P6.json").write_text(json.dumps(proto, indent=1))
    print("wrote", C2 / "SCORING_PROTOCOL_P6.json")


# --------------------------------------------------------------------------- selection
def universe():
    return p3.all_train_records()          # alias-resolved train, EXCLUDE (incl. PARA) applied


def cmd_select():
    smap = p3.stratum_map()
    recs = universe()
    by_s = {}
    for r in recs:
        by_s.setdefault(smap.get(r["ticker"], "?"), []).append(r)
    assert "?" not in by_s, "unmapped stratum"
    counts = {s: len(v) for s, v in by_s.items()}
    rng = random.Random("p6-preflight-11")
    alloc = p3.stratum_alloc(PREFLIGHT_N, counts)
    pre = []
    for s in sorted(alloc):
        pre += [(r["ticker"], r["date"]) for r in rng.sample(sorted(by_s[s], key=lambda r: (r["ticker"], r["date"])), alloc[s])]
    # noise arm: 120 calls already in the v6 cache, proportional to the S1-S5 train mix (P3 prompt 5f)
    v6 = {tuple(Path(f).stem.rsplit("_", 1)) for f in glob.glob(str(V6_EVAL_DIR / "*.txt"))}
    pool = [r for r in recs if (r["ticker"], r["date"]) in v6]
    pn = {}
    for r in pool:
        pn.setdefault(smap[r["ticker"]], []).append(r)
    nalloc = p3.stratum_alloc(NOISE_N, {s: len(v) for s, v in pn.items()})
    rng2 = random.Random("p6-noise-11")
    noise = []
    for s in sorted(nalloc):
        noise += [(r["ticker"], r["date"]) for r in rng2.sample(sorted(pn[s], key=lambda r: (r["ticker"], r["date"])), nalloc[s])]
    out = {"preflight": [list(k) for k in pre], "preflight_alloc": alloc, "noise": [list(k) for k in noise],
           "noise_alloc": nalloc, "universe_counts": counts, "seeds": ["p6-preflight-11", "p6-noise-11"]}
    (STATE / "selection.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("preflight", "noise")}), len(pre), len(noise))


# --------------------------------------------------------------------------- requests
def cid(arm, w, d):
    c = f"{arm}__{w}_{d}"
    assert re.match(r"^[a-zA-Z0-9_-]{1,64}$", c), c
    return c


def sysblock(text):
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def transcript(w, d):
    return json.loads((p3.TRANSCRIPTS / w / f"{d}.json").read_text())["text"]


def make_request(arm, w, d):
    from anthropic.types.messages.batch_create_params import Request
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    prompt = PROMPTS["A" if arm == "N" else arm].read_text()
    return Request(custom_id=cid(arm, w, d), params=MessageCreateParamsNonStreaming(
        model=MODEL, max_tokens=MAX_TOKENS, system=sysblock(prompt),
        messages=[{"role": "user", "content": transcript(w, d)}]))


def scores_path(arm):
    return STATE / {"B": "scores_b.jsonl", "C": "scores_c.jsonl", "N": "scores_noise.jsonl"}[arm]


def have_ids(arm):
    return {(r["ticker"], r["date"]) for r in p3.read_jsonl(scores_path(arm))}


def committed_usd(p):
    return sum(v for k, v in p.get("committed_usd_by_batch", {}).items())


def commit_spend(key, n, per_call):
    p = load_progress()
    est = round(n * per_call, 2)
    total = committed_usd(p) + est
    print(f"{key}: {n} requests x ${per_call:.4f} = ${est:.2f}; committed after = ${total:.2f} (cap ${CAP_USD})")
    if total > CAP_USD:
        raise SystemExit(f"HARD CAP: ${total:.2f} > ${CAP_USD}. Stop and report.")
    assert p["luis_approved_usd"] >= total
    p.setdefault("committed_usd_by_batch", {})[key] = est
    save_progress(p)


def submit(key, reqs, per_call):
    p = load_progress()
    if p.get(key):
        print(f"{key} already recorded: {p[key]} -- NOT submitting")
        return
    g = guards()
    p = load_progress()
    p.setdefault("guards", {})[key] = g
    save_progress(p)
    commit_spend(key, len(reqs), per_call)
    p3.submit_batch(reqs, key)
    print("COMMIT progress.json NOW (batch id written)")


# --------------------------------------------------------------------------- pre-flight
def cmd_preflight_submit():
    sel = json.loads((STATE / "selection.json").read_text())
    reqs = [make_request(a, w, d) for w, d in sel["preflight"] for a in ("B", "C")]
    assert len(reqs) == 2 * PREFLIGHT_N
    submit("batch_id_preflight", reqs, EST_PER_CALL)
    step("5a", "in_progress", "poll preflight batch")


def route(raw_path, default_arm=None):
    """Split raw batch rows by custom_id prefix into scores_{b,c,noise}.jsonl and write eval-cache .txt files."""
    n = 0
    for r in p3.read_jsonl(raw_path):
        arm, rest = r["custom_id"].split("__", 1)
        w, d = rest.rsplit("_", 1)
        if (w, d) in have_ids(arm):
            continue
        row = {"custom_id": r["custom_id"], "arm": arm, "ticker": w, "date": d, "content": r["content"],
               "usage": r["usage"], "stop_reason": r["stop_reason"], "cost_usd": r["cost_usd"],
               "batch_id": r["batch_id"], "fetched_at": r["fetched_at"]}
        p3.append_jsonl(scores_path(arm), row)
        if arm in EVAL_DIR:
            EVAL_DIR[arm].mkdir(parents=True, exist_ok=True)
            (EVAL_DIR[arm] / f"{w}_{d}.txt").write_text(r["content"])
        n += 1
    return n


def poll(key, raw_name):
    done = p3.poll_batch(key, raw_name, key)
    if done:
        print("routed", route(STATE / raw_name), "new rows")
    return done


def cmd_preflight_poll():
    if poll("batch_id_preflight", "raw_preflight.jsonl"):
        step("5a", "in_progress", "run preflight-report")


def cmd_preflight_report():
    from analyst_direct_scorer import parse_structured
    sel = json.loads((STATE / "selection.json").read_text())
    want = {tuple(x) for x in sel["preflight"]}
    res = {}
    for arm in ("B", "C"):
        rows = [r for r in p3.read_jsonl(scores_path(arm)) if (r["ticker"], r["date"]) in want]
        bad_parse = bad_score = bad_nr = maxtok = nr_true = 0
        cost = 0.0
        toks = []
        for r in rows:
            sc = parse_structured(r["content"])
            cost += r["cost_usd"]
            toks.append(r["usage"]["output_tokens"])
            if r["stop_reason"] == "max_tokens":
                maxtok += 1
            if not sc:
                bad_parse += 1
                continue
            s = sc.get("score")
            if not (isinstance(s, int) and not isinstance(s, bool) and -5 <= s <= 5):
                bad_score += 1
            if not isinstance(sc.get("noRead"), bool):
                bad_nr += 1
            elif sc["noRead"]:
                nr_true += 1
        n = max(len(rows), 1)
        per = cost / n
        res[arm] = {"n": len(rows), "unparseable": bad_parse, "bad_score": bad_score, "bad_noRead": bad_nr,
                    "stop_max_tokens": maxtok, "noRead_true": nr_true, "noRead_share_pct": round(100 * nr_true / n, 1),
                    "cost_usd": round(cost, 4), "cost_per_call": round(per, 5),
                    "median_completion_tokens": sorted(toks)[len(toks) // 2] if toks else None}
    n_full = len(universe())
    for arm in ("B", "C"):
        res[arm]["projected_full_arm_usd"] = round(res[arm]["cost_per_call"] * n_full, 2)
    res["stop_projection_over_55"] = any(res[a]["projected_full_arm_usd"] > 55 for a in "BC")
    res["control_defaulting_to_abstention"] = res["B"]["noRead_share_pct"] > 100 / 3
    (STATE / "preflight_report.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    ok = all(res[a]["unparseable"] == 0 and res[a]["bad_score"] == 0 and res[a]["bad_noRead"] == 0
             and res[a]["stop_max_tokens"] == 0 for a in "BC")
    print("PREFLIGHT FORMAT CHECKS", "PASS" if ok else "FAIL -- stop and report")
    print("PROJECTION", "STOP (>$55)" if res["stop_projection_over_55"] else "ok")


# --------------------------------------------------------------------------- full arms
def pending(arm):
    done = have_ids(arm)
    return [r for r in universe() if (r["ticker"], r["date"]) not in done]


def per_call(arm):
    rep = json.loads((STATE / "preflight_report.json").read_text())
    return rep[arm]["cost_per_call"]


def cmd_submit_b():
    reqs = [make_request("B", r["ticker"], r["date"]) for r in pending("B")]
    submit("batch_id_arm_b", reqs, per_call("B"))
    step("5c", "in_progress", "poll-b; then submit-c")


def cmd_submit_c():
    p = load_progress()
    assert p.get("batch_id_arm_b"), "submit B first"
    sel = json.loads((STATE / "selection.json").read_text())
    reqs = [make_request("C", r["ticker"], r["date"]) for r in pending("C")]
    reqs += [make_request("N", w, d) for w, d in sel["noise"]]
    submit("batch_id_arm_c", reqs, per_call("C"))
    step("5c", "in_progress", "poll-c")


def cmd_poll_b():
    poll("batch_id_arm_b", "raw_arm_b.jsonl")


def cmd_poll_c():
    poll("batch_id_arm_c", "raw_arm_c.jsonl")


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "").replace("-", "_")
    fn = globals().get("cmd_" + cmd)
    if fn:
        fn(*sys.argv[2:])
    else:
        print(__doc__)
