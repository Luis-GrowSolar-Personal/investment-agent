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
    "P7": REPO / "docs/prompts/candidates/EVALUATION_PROMPT_P7_three_voices.md",
    "P9": REPO / "docs/prompts/candidates/EVALUATION_PROMPT_P9_expected_return.md",
}
CAND_NAME = {"B": "P6B-minimal", "C": "P6C-score", "P7": "P7-three-voices", "P9": "P9-expected-return"}
EVAL_DIR = {a: REPO / f"analysis/data/evals/{n}_claude-sonnet-4-6" for a, n in CAND_NAME.items()}
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
EXCLUDE = {"WOLF", "SPWR", "PARA"}
CAP_USD = 130.0
EST_PER_CALL = 0.0380          # measured batch $/call, prompt header
PREFLIGHT_N = 100
NOISE_N = 120
THRESHOLDS = {"bearish_lte": -2, "bullish_gte": 2, "neutral": [-1, 0, 1]}

# --split tune (prompts/P6B-tune-confirmation.md): same driver, tune companies, arm B + a larger noise arm only.
SPLIT_NAME = "train"
if "--split" in sys.argv:
    _i = sys.argv.index("--split")
    SPLIT_NAME = sys.argv[_i + 1]
    del sys.argv[_i:_i + 2]
assert SPLIT_NAME in ("train", "tune"), SPLIT_NAME
TUNE = SPLIT_NAME == "tune"

# --rerun (prompts/B-champion-and-noise-floor.md): arm B on the same 1,217 train calls, a second time.
# Same prompt, model, max_tokens, request construction; custom ids suffixed __r1; outputs never touch the originals.
RERUN = "--rerun" in sys.argv
if RERUN:
    sys.argv.remove("--rerun")
    assert not TUNE, "--rerun is train only"
    RUN_ID = "b-champion-and-noise-floor"
    STATE = REPO / "analysis/data/run_state" / RUN_ID
    PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
    EVAL_DIR = {"B": REPO / "analysis/data/evals/P6B-minimal_claude-sonnet-4-6_rerun1"}
    CAP_USD, PREFLIGHT_N = 35.0, 30
    EST_PER_CALL = 0.0236
    RERUN_SUFFIX = "__r1"
    ORIGINAL_STATE = REPO / "analysis/data/run_state/p6-output-format-round"
if TUNE:
    RUN_ID = "p6b-tune-confirmation"
    STATE = REPO / "analysis/data/run_state" / RUN_ID
    PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
    V6_EVAL_DIR = REPO / "analysis/data/evals/v6_claude-sonnet-4-6_tune"
    EVAL_DIR = {"B": REPO / "analysis/data/evals/P6B-minimal_claude-sonnet-4-6_tune"}
    EXCLUDE = {"WOLF", "SPWR"}
    CAP_USD, PREFLIGHT_N, NOISE_N = 60.0, 50, 250
    EST_PER_CALL = 0.0236
    NOISE_PER_CALL = 0.0402       # train noise arm measured: $4.82 / 120
    THRESHOLDS = {"bearish_lte": -2, "bullish_gte": 3, "neutral": [-1, 0, 1, 2],
                  "train_run_original_mapping_labelled": {"bullish_gte": 2, "neutral": [-1, 0, 1]}}

    def _tune_resolved():
        amap = p3.alias_map()
        return [(t, amap.get(t, t)) for t in json.loads(p3.SPLIT.read_text())["tune"]]

    def _tune_strata():
        amap = p3.alias_map()
        m = {}
        for st, dd in json.loads(p3.SPLIT.read_text())["per_stratum"].items():
            for t in dd["tune"]:
                m[amap.get(t, t)] = st
        return m
    p3.resolved_train = _tune_resolved
    p3.stratum_map = _tune_strata
    p3.V6_EVAL_DIR = V6_EVAL_DIR

# --p7 (prompts/P7-three-voices.md): candidate P7 on the same 1,217 train calls. Same request construction as B, prompt text differs only.
P7 = "--p7" in sys.argv
if P7:
    sys.argv.remove("--p7")
    assert not TUNE and not RERUN
    RUN_ID = "p7-three-voices-train"
    STATE = REPO / "analysis/data/run_state" / RUN_ID
    PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
    CAP_USD, PREFLIGHT_N = 45.0, 150
    EST_PER_CALL = 0.027
    ORIGINAL_STATE = REPO / "analysis/data/run_state/p6-output-format-round"
    P7_SHA = "0a34f5a926f6be89400a8191cac5455f0b5cd11d2bef8a51d3a6b97510b2bcaf"
    ORIGINAL_STATE_B2 = REPO / "analysis/data/run_state/b-champion-and-noise-floor"

# --p9 (prompts/P9-expected-return.md): candidate P9 on the same 1,217 train calls. Same request construction as B.
P9R = "--p9r" in sys.argv          # second P9 draw (prompts/P9-second-draw.md): same as --p9, custom ids __r1, outputs isolated
if P9R:
    sys.argv[sys.argv.index("--p9r")] = "--p9"
P9 = "--p9" in sys.argv
if P9:
    sys.argv.remove("--p9")
    assert not TUNE and not RERUN and not P7
    RUN_ID = "p9-expected-return-train"
    STATE = REPO / "analysis/data/run_state" / RUN_ID
    PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
    CAP_USD, PREFLIGHT_N = 40.0, 150
    EST_PER_CALL = 0.0245
    ORIGINAL_STATE = REPO / "analysis/data/run_state/p6-output-format-round"
    ORIGINAL_STATE_B2 = REPO / "analysis/data/run_state/b-champion-and-noise-floor"
    P9_SHA = "a752e6b1b2a00b755396a526bfe3007e788ebfb6a93b32076754cd0e078c06a5"
    if P9R:
        RUN_ID = "p9-second-draw"
        STATE = REPO / "analysis/data/run_state" / RUN_ID
        PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
        CAP_USD = 36.0
        EST_PER_CALL = 0.0248
        EVAL_DIR = {"P9": REPO / "analysis/data/evals/P9-expected-return_claude-sonnet-4-6_rerun1"}
        RERUN_SUFFIX = "__r1"

# --winners (prompts/winners-missed-analysis.md): READ-text classifier over B draw 1's READs, plus (step 3) contrastive pairs. Not a candidate.
WV3 = "--wv3" in sys.argv          # winners-missed-v3: classifier v3 (v2 minus `discounted`), own state, cap 4
if WV3:
    sys.argv[sys.argv.index("--wv3")] = "--winners"
WV2 = "--wv2" in sys.argv          # winners-missed-v2: classifier v2, own state, cap 8
if WV2:
    sys.argv[sys.argv.index("--wv2")] = "--winners"
WIN = "--winners" in sys.argv
if WIN:
    sys.argv.remove("--winners")
    assert not (TUNE or RERUN or P7 or P9)
    RUN_ID = "winners-missed"
    STATE = REPO / "analysis/data/run_state" / RUN_ID
    PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
    CAP_USD, PREFLIGHT_N = 12.0, 60
    CLASSIFIER = REPO / "docs/prompts/diagnostics/READ_CLASSIFIER_v1.md"
    CLASSIFIER_MAX_TOKENS = 400
    W_EST = 0.006
    if WV2:
        RUN_ID = "winners-missed-v2"
        STATE = REPO / "analysis/data/run_state" / RUN_ID
        PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
        CAP_USD, PREFLIGHT_N = 8.0, 60
        CLASSIFIER = REPO / "docs/prompts/diagnostics/READ_CLASSIFIER_v2.md"
        W_EST = 0.004
    if WV3:
        RUN_ID = "winners-missed-v3"
        STATE = REPO / "analysis/data/run_state" / RUN_ID
        PROGRESS, FINDINGS = STATE / "progress.json", STATE / "findings.md"
        CAP_USD = 4.0
        CLASSIFIER = REPO / "docs/prompts/diagnostics/READ_CLASSIFIER_v3.md"
        W_EST = 0.00167          # v2 pre-flight measured $/call (same reads, near-identical prompt)

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
    if TUNE:
        return _check0f_tune()
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
    text = regp.read_text()
    reg = json.loads(text)
    have = {c["version"] for c in reg["artifacts"]["evaluation_prompt"]["candidates"]}
    date = "2026-09-23"
    spec = {"P6B-minimal": ("B", "none", "Arm B, the control: no rubric; objective, constraint, -5..+5 score with noRead, 3-5 sentence read. Not a v6 derivative."),
            "P6C-score": ("C", "v6", "Arm C: v6 with only the RECOMMENDATION section replaced by a SCORE section; recommendation replaced by score/noRead/wrongIf in the structured block.")}
    lines = []
    for v, (arm, parent, detail) in spec.items():
        if v in have:
            continue
        entry = {"version": v, "status": "candidate", "parent": parent, "registered": date,
                 "path": str(PROMPTS[arm].relative_to(REPO)), "sha256": sha(PROMPTS[arm]),
                 "detail": detail + " prompts/P6-output-format-round.md. Not gated, not promoted. "
                           "version_guard checks the candidate NAME only; the driver asserts the sha256 itself."}
        lines.append("        " + json.dumps(entry))
    if lines:
        # textual insert after the last candidate line: keeps the file's hand-formatted layout (no re-dump)
        m = re.search(r'(\{"version": "v6\+P3a".*\})\n(\s*\]\n)', text)
        assert m, "anchor for insertion not found"
        text = text[:m.end(1)] + ",\n" + ",\n".join(lines) + "\n" + text[m.start(2):]
        json.loads(text)
        regp.write_text(text)
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
    for arm in (("P7",) if P7 else ("P9",) if P9 else ("B",) if (TUNE or RERUN) else ("B", "C")):
        t = PROMPTS[arm].read_text()
        rs = next(c["sha256"] for c in reg["candidates"] if c["version"] == CAND_NAME[arm])
        assert hashlib.sha256(t.encode()).hexdigest() == rs, f"arm {arm} hash != registry"
        out[arm] = assert_prompt_hash(t, candidate=CAND_NAME[arm])
    out["A_noise"] = assert_prompt_hash(PROMPTS["A"].read_text())
    assert out["A_noise"]["candidate_used"] is None
    return out


# --------------------------------------------------------------------------- 0e
def cmd_protocol():
    if TUNE:
        return _protocol_tune()
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
    rng = random.Random("p6b-tune-preflight-11" if TUNE else "p6-preflight-11")
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
    rng2 = random.Random("p6b-tune-noise-11" if TUNE else "p6-noise-11")
    noise = []
    for s in sorted(nalloc):
        noise += [(r["ticker"], r["date"]) for r in rng2.sample(sorted(pn[s], key=lambda r: (r["ticker"], r["date"])), nalloc[s])]
    out = {"preflight": [list(k) for k in pre], "preflight_alloc": alloc, "noise": [list(k) for k in noise],
           "noise_alloc": nalloc, "universe_counts": counts, "seeds": ["p6-preflight-11", "p6-noise-11"]}
    (STATE / "selection.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("preflight", "noise")}), len(pre), len(noise))


# --------------------------------------------------------------------------- requests
def cid(arm, w, d):
    c = f"{arm}__{w}_{d}" + (RERUN_SUFFIX if (RERUN or P9R) else "")
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
    sfx = "_tune" if TUNE else ""
    if P7:
        return STATE / {"P7": "scores_p7.jsonl"}[arm]
    if P9:
        return STATE / {"P9": "scores_p9_rerun1.jsonl" if P9R else "scores_p9.jsonl"}[arm]
    if RERUN:
        return STATE / {"B": "scores_b_rerun1.jsonl"}[arm]
    return STATE / {"B": f"scores_b{sfx}.jsonl", "C": f"scores_c{sfx}.jsonl", "N": f"scores_noise{sfx}.jsonl"}[arm]


def have_ids(arm):
    return {(r["ticker"], r["date"]) for r in p3.read_jsonl(scores_path(arm))}


def committed_usd(p):
    return sum(v for k, v in p.get("committed_usd_by_batch", {}).items())


def commit_spend(key, n, per_call):
    p = load_progress()
    est = round(n * per_call, 2)
    total = committed_usd({"committed_usd_by_batch": {k: v for k, v in p.get("committed_usd_by_batch", {}).items() if k != key}}) + est
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
    arms = ("P7",) if P7 else ("P9",) if P9 else ("B",) if (TUNE or RERUN) else ("B", "C")
    reqs = [make_request(a, w, d) for w, d in sel["preflight"] for a in arms]
    assert len(reqs) == len(arms) * PREFLIGHT_N
    submit("batch_id_preflight", reqs, EST_PER_CALL)
    step("5a", "in_progress", "poll preflight batch")


def route(raw_path, default_arm=None):
    """Split raw batch rows by custom_id prefix into scores_{b,c,noise}.jsonl and write eval-cache .txt files."""
    n = 0
    for r in p3.read_jsonl(raw_path):
        c = r["custom_id"]
        if RERUN or P9R:
            assert c.endswith(RERUN_SUFFIX), c
            c = c[:-len(RERUN_SUFFIX)]
        arm, rest = c.split("__", 1)
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
    ARMS = ("B",) if (TUNE or RERUN) else ("B", "C")
    for arm in ARMS:
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
    for arm in ARMS:
        res[arm]["projected_full_arm_usd"] = round(res[arm]["cost_per_call"] * n_full, 2)
    lim = 32 if (TUNE or RERUN) else 55
    res["stop_projection_over_55"] = any(res[a]["projected_full_arm_usd"] > lim for a in ARMS)
    res["projection_limit_usd"] = lim
    res["control_defaulting_to_abstention"] = res["B"]["noRead_share_pct"] > 100 / 3
    (STATE / "preflight_report.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    ok = all(res[a]["unparseable"] == 0 and res[a]["bad_score"] == 0 and res[a]["bad_noRead"] == 0
             and res[a]["stop_max_tokens"] == 0 for a in ARMS)
    print("PREFLIGHT FORMAT CHECKS", "PASS" if ok else "FAIL -- stop and report")
    print("PROJECTION", f"STOP (>${lim})" if res["stop_projection_over_55"] else "ok")


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


# --------------------------------------------------------------------------- tune-side (P6B-tune-confirmation)
def _check0f_tune():
    """Tune-side alias hard stop: every tune symbol resolved; every file in the v6 tune cache maps to a resolved symbol."""
    sp = json.loads(p3.SPLIT.read_text())
    amap = p3.alias_map()
    rt = p3.resolved_train()                      # patched: tune list
    resolved = {w for _, w in rt}
    files_all = {w: sorted(glob.glob(str(p3.TRANSCRIPTS / w / "*.json"))) for _, w in rt}
    n_files_all = sum(len(v) for v in files_all.values())
    unresolved_files = sum(len(glob.glob(str(p3.TRANSCRIPTS / t / "*.json"))) for t in sp["tune"])
    evs = sorted(glob.glob(str(V6_EVAL_DIR / "*.txt")))
    ev_tk = {Path(e).stem.rsplit("_", 1)[0] for e in evs}
    unmapped = sorted(ev_tk - resolved)
    recs = p3.all_train_records()                 # WOLF/SPWR excluded
    kept_cos = {r["ticker"] for r in recs}
    no_files = [w for w, v in files_all.items() if not v]
    out = {"tune_symbols": len(sp["tune"]), "resolved_files_incl_excluded": n_files_all,
           "unresolved_files": unresolved_files, "aliases_applied": {t: amap[t] for t in sp["tune"] if t in amap},
           "v6_tune_eval_files": len(evs), "eval_unmapped_symbols": unmapped, "symbols_with_no_files": no_files,
           "excluded": sorted(EXCLUDE), "calls_after_exclusion": len(recs), "companies_after_exclusion": len(kept_cos),
           "disjoint_train": not (set(sp["tune"]) & set(sp["train"])), "disjoint_holdout": not (set(sp["tune"]) & set(sp["holdout"]))}
    ok = (len(evs) == n_files_all and not unmapped and out["disjoint_train"] and out["disjoint_holdout"]
          and not (set(no_files) - EXCLUDE - {"BNY"}))      # BK->BNY: 0 transcripts, documented vendor gap (baseline-v6-tune-batch-out.md s2); expected, recorded
    out["expected_empty"] = {"BNY": "BK/BNY pre-rebrand history not carried by the vendor; 0 transcripts; analogue of MAXN on train"}
    out["asserts_pass"] = ok
    (STATE / "step0f_tune_alias_asserts.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    if not ok:
        raise SystemExit("0f HARD STOP (tune): alias/count assertion failed")


def _protocol_tune():
    sp = json.loads(p3.SPLIT.read_text())
    proto = {
        "run_id": RUN_ID, "registered_at": now(), "split_scored": "tune",
        "company_list_original": sp["tune"], "company_list_resolved": [w for _, w in p3.resolved_train()],
        "aliases_applied": {t: p3.alias_map()[t] for t in sp["tune"] if t in p3.alias_map()},
        "excluded_entirely": sorted(EXCLUDE), "excluded_note": "WOLF, SPWR ungradable (2026-09-19 state of play s6); every call excluded, not only unscoreable ones",
        "manifest_source": "analysis/data/corpus_v2/CORPUS_MANIFEST_V7.json", "manifest_sha256": sha(C2 / "CORPUS_MANIFEST_V7.json"),
        "split_source": "analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json", "split_sha256": sha(p3.SPLIT),
        "prompts": {a: {"path": str(PROMPTS[a].relative_to(REPO)), "sha256": sha(PROMPTS[a])} for a in "AB"},
        "candidate": "P6B-minimal (registered in VERSION_REGISTRY.json; not a promotion)",
        "model_version_pinned": MODEL, "model_matches_baselines": True,
        "price_cache_path": PRICE_CACHE_REL,
        "entry_for_money": "rel_ret arm B (first close strictly after the call date), 182 days, SPY",
        "thresholds_fixed_before_any_result": {
            "primary_pre_registered_2026-09-24": {"bearish": "score <= -2", "bullish": "score >= +3", "neutral": "-1, 0, +1, +2"},
            "train_run_original_mapping_reported_alongside": {"bearish": "score <= -2", "bullish": "score >= +2", "neutral": "-1, 0, +1"}},
        "request_caps": {"preflight": PREFLIGHT_N, "arm_b": 1300, "noise": NOISE_N},
        "spend_caps_usd": {"total": CAP_USD, "full_arm_projection_stop": 32},
        "max_tokens_scoring": MAX_TOKENS, "eval_cache": str(EVAL_DIR["B"].relative_to(REPO)) + "/",
        "seeds": {"preflight": "random.Random('p6b-tune-preflight-11')", "noise": "random.Random('p6b-tune-noise-11')"},
        "disjointness": {"tune_train": not (set(sp["tune"]) & set(sp["train"])), "tune_holdout": not (set(sp["tune"]) & set(sp["holdout"]))},
        "holdout": "untouched",
    }
    assert proto["disjointness"]["tune_train"] and proto["disjointness"]["tune_holdout"]
    assert PRICE_CACHE_REL == str(p3.PRICE_CACHE)
    (C2 / "SCORING_PROTOCOL_P6B_TUNE.json").write_text(json.dumps(proto, indent=1))
    print("wrote", C2 / "SCORING_PROTOCOL_P6B_TUNE.json")


def cmd_submit_noise():
    sel = json.loads((STATE / "selection.json").read_text())
    done = have_ids("N")
    reqs = [make_request("N", w, d) for w, d in sel["noise"] if (w, d) not in done]
    assert len(reqs) <= NOISE_N
    submit("batch_id_noise", reqs, NOISE_PER_CALL)
    step("4b", "in_progress", "poll-noise")


def cmd_poll_noise():
    poll("batch_id_noise", "raw_noise.jsonl")


# --------------------------------------------------------------------------- rerun-side (prompts/B-champion-and-noise-floor.md)
def cmd_rerun_select():
    """30 stratified train calls for the pre-flight, fixed seed (all strata present in train, via stratum_map())."""
    assert RERUN
    smap = p3.stratum_map()
    by_s = {}
    for r in universe():
        by_s.setdefault(smap.get(r["ticker"], "?"), []).append(r)
    assert "?" not in by_s, "unmapped stratum"
    counts = {s: len(v) for s, v in by_s.items()}
    alloc = p3.stratum_alloc(PREFLIGHT_N, counts)
    if alloc.get("S4", 0) == 0:          # prompt 2a: stratified across the strata; proportional gives S4 zero, so take one from the largest
        big = max(alloc, key=alloc.get)
        alloc[big] -= 1
        alloc["S4"] = 1
    rng = random.Random("b-rerun-preflight-11")
    pre = []
    for s in sorted(alloc):
        pre += [(r["ticker"], r["date"]) for r in rng.sample(sorted(by_s[s], key=lambda r: (r["ticker"], r["date"])), alloc[s])]
    assert len(pre) == PREFLIGHT_N
    (STATE / "selection.json").write_text(json.dumps({"preflight": [list(k) for k in pre], "preflight_alloc": alloc,
                                                      "universe_counts": counts, "seed": "b-rerun-preflight-11"}, indent=1))
    print(json.dumps({"alloc": alloc, "counts": counts, "n_universe": sum(counts.values())}))


def cmd_rerun_check():
    """Request-shape equality with the original run, and the 1,217-call universe assert. $0."""
    assert RERUN
    from analysis.version_guard import assert_prompt_hash  # noqa: F401 (guards() below runs it)
    recs = universe()
    orig = {(r["ticker"], r["date"]) for r in p3.read_jsonl(ORIGINAL_STATE / "scores_b.jsonl")}
    assert len(recs) == 1217 == len(orig), (len(recs), len(orig))
    assert {(r["ticker"], r["date"]) for r in recs} == orig, "universe != original scores_b.jsonl"
    B_SHA = "d1fa5e53fd743412503a0ba316d21b49a061e1ccf3e2064478bb83dfe9b430ab"
    assert sha(PROMPTS["B"]) == B_SHA
    rng = random.Random("b-rerun-shape-11")
    sample = rng.sample(sorted(orig), 25)
    raw_ids = {r["custom_id"] for f in ("raw_arm_b.jsonl", "raw_preflight.jsonl") for r in p3.read_jsonl(ORIGINAL_STATE / f)
               if r["custom_id"].startswith("B__")}
    for w, d in sample:
        req = make_request("B", w, d)
        prm = req["params"] if isinstance(req, dict) else req.params
        prm = dict(prm)
        assert prm["model"] == MODEL == "claude-sonnet-4-6" and prm["max_tokens"] == 4096 == MAX_TOKENS
        assert "temperature" not in prm and set(prm) == {"model", "max_tokens", "system", "messages"}, sorted(prm)
        sysb = prm["system"]
        assert len(sysb) == 1 and sysb[0]["text"] == PROMPTS["B"].read_text() and sysb[0]["cache_control"] == {"type": "ephemeral"}
        assert prm["messages"] == [{"role": "user", "content": transcript(w, d)}]
        cidv = req["custom_id"] if isinstance(req, dict) else req.custom_id
        assert cidv == f"B__{w}_{d}__r1"
        assert f"B__{w}_{d}" in raw_ids, f"original raw_arm_b/raw_preflight has no row for {w} {d}"
    rep = {"universe": len(recs), "equal_to_original_scores_b": True, "prompt_sha": B_SHA, "model": MODEL,
           "max_tokens": MAX_TOKENS, "temperature_param": "absent", "sample_checked": len(sample),
           "note": "raw_arm_b.jsonl stores responses, not request params; shape is asserted against the unchanged make_request() "
                   "code path, prompt sha, and presence of each sampled call's original custom_id in raw_arm_b.jsonl or raw_preflight.jsonl"}
    (STATE / "request_shape_check.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


def cmd_submit_rerun():
    assert RERUN
    reqs = [make_request("B", r["ticker"], r["date"]) for r in pending("B")]
    print("pending (after pre-flight reuse):", len(reqs))
    assert len(reqs) + len(have_ids("B")) == 1217
    submit("batch_id_rerun", reqs, per_call("B"))
    step("2b", "in_progress", "poll-rerun")


def cmd_poll_rerun():
    poll("batch_id_rerun", "raw_rerun.jsonl")


# --------------------------------------------------------------------------- winners-side (prompts/winners-missed-analysis.md)
def w_read_text(content):
    """B's READ paragraph only: strip the SCORE section (score, rationale, wrongIf) and the structured block."""
    m = re.search(r"## READ\s*(.*?)\s*(?:## SCORE|---STRUCTURED---|$)", content, re.S)
    assert m and m.group(1).strip(), "no READ section"
    return m.group(1).strip()


def w_request(tk, d, read):
    from anthropic.types.messages.batch_create_params import Request
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    return Request(custom_id=f"W__{tk}_{d}", params=MessageCreateParamsNonStreaming(
        model=MODEL, max_tokens=CLASSIFIER_MAX_TOKENS, system=sysblock(CLASSIFIER.read_text()),
        messages=[{"role": "user", "content": read}]))


def w_reads():
    b = {(r["ticker"], r["date"]): r for r in p3.read_jsonl(REPO / "analysis/data/run_state/p6-output-format-round/scores_b.jsonl")}
    recs = universe()
    assert len(recs) == 1217
    return {(r["ticker"], r["date"]): w_read_text(b[(r["ticker"], r["date"])]["content"]) for r in recs}


def w_scores_path():
    return STATE / ("read_labels_v3.jsonl" if WV3 else "read_labels_v2.jsonl" if WV2 else "read_labels.jsonl")


def w_have():
    return {(r["ticker"], r["date"]) for r in p3.read_jsonl(w_scores_path())}


def cmd_w_check():
    assert WIN
    reads = w_reads()
    bad = [k for k, v in reads.items() if re.search(r"\*\*[+-]?\d\*\*|---STRUCTURED", v)]
    assert not bad, f"score or structured block leaked into READ text for {bad[:3]}"
    p = load_progress(); p["classifier_sha256"] = sha(CLASSIFIER); p["classifier_path"] = str(CLASSIFIER.relative_to(REPO)); save_progress(p)
    k = next(iter(reads)); req = w_request(*k, reads[k]); prm = dict(req["params"] if isinstance(req, dict) else req.params)
    assert prm["model"] == MODEL and prm["max_tokens"] == 400 and "temperature" not in prm
    print(json.dumps({"reads": len(reads), "classifier_sha256": p["classifier_sha256"], "median_read_chars": sorted(len(v) for v in reads.values())[len(reads) // 2]}))


def cmd_w_select():
    assert WIN
    if WV2:                                     # the same 60 as v1's pre-flight
        v1 = json.loads((REPO / "analysis/data/run_state/winners-missed/selection.json").read_text())
        (STATE / "selection.json").write_text(json.dumps(v1, indent=1)); print("copied v1 selection", v1["alloc"]); return
    smap = p3.stratum_map(); by_s = {}
    for r in universe(): by_s.setdefault(smap[r["ticker"]], []).append(r)
    counts = {s_: len(v) for s_, v in by_s.items()}
    alloc = p3.stratum_alloc(PREFLIGHT_N, counts)
    if alloc.get("S4", 0) == 0:
        big = max(alloc, key=alloc.get); alloc[big] -= 1; alloc["S4"] = 1
    rng = random.Random("winners-preflight-11"); pre = []
    for s_ in sorted(alloc):
        pre += [(r["ticker"], r["date"]) for r in rng.sample(sorted(by_s[s_], key=lambda r: (r["ticker"], r["date"])), alloc[s_])]
    rng.shuffle(pre)
    (STATE / "selection.json").write_text(json.dumps({"preflight": [list(k) for k in pre], "alloc": alloc}, indent=1)); print(alloc)


def w_submit(key, keys, per):
    p = load_progress()
    if p.get(key):
        print(key, "already recorded", p[key]); return
    reads = w_reads()
    assert p.get("classifier_sha256") == sha(CLASSIFIER), "classifier sha not recorded / changed"
    reqs = [w_request(tk, d, reads[(tk, d)]) for tk, d in keys]
    commit_spend(key, len(reqs), per)
    p3.submit_batch(reqs, key)


def w_route(raw):
    from analyst_direct_scorer import parse_structured
    have, n = w_have(), 0
    for r in p3.read_jsonl(STATE / raw):
        tk, d = r["custom_id"][3:].rsplit("_", 1)
        if (tk, d) in have: continue
        p3.append_jsonl(w_scores_path(), {"ticker": tk, "date": d, "content": r["content"], "parsed": parse_structured(r["content"]),
                                          "usage": r["usage"], "stop_reason": r["stop_reason"], "cost_usd": r["cost_usd"], "batch_id": r["batch_id"]})
        n += 1
    print("routed", n, "new rows")


def cmd_w_preflight_submit():
    assert WIN
    sel = json.loads((STATE / "selection.json").read_text())
    w_submit("batch_id_preflight", [tuple(x) for x in sel["preflight"]], W_EST)
    step("2b", "in_progress", "w-preflight-poll")


def cmd_w_preflight_poll():
    if p3.poll_batch("batch_id_preflight", "raw_preflight.jsonl", "batch_id_preflight"):
        w_route("raw_preflight.jsonl")


W_ALLOWED = ({"balance": {"outweighs", "balanced", "outweighed"}, "raised": {"yes", "no"}, "beat": {"yes", "no"}} if WV3 else
             {"balance": {"outweighs", "balanced", "outweighed"}, "raised": {"yes", "no"}, "beat": {"yes", "no"}, "discounted": {"yes", "no"}} if WV2 else
             {"positive": {"none", "weak", "strong"}, "negative": {"none", "weak", "strong"}, "forwardPositive": {"yes", "no"}, "discounted": {"yes", "no"}})


def cmd_w_preflight_report():
    sel = json.loads((STATE / "selection.json").read_text()); want = {tuple(x) for x in sel["preflight"]}
    rows = [r for r in p3.read_jsonl(w_scores_path()) if (r["ticker"], r["date"]) in want]
    bad = sum(1 for r in rows if not r["parsed"] or any(r["parsed"].get(f) not in v for f, v in W_ALLOWED.items()))
    mt = sum(r["stop_reason"] == "max_tokens" for r in rows)
    dist = {f: {v: sum(1 for r in rows if r["parsed"].get(f) == v) for v in vals} for f, vals in W_ALLOWED.items()}
    single = {f: round(100 * max(d.values()) / max(len(rows), 1), 1) for f, d in dist.items()}
    cost = sum(r["cost_usd"] for r in rows); per = cost / max(len(rows), 1)
    rep = {"n": len(rows), "unparseable_or_out_of_set": bad, "max_tokens": mt, "distribution": dist, "max_single_value_share_pct": single,
           "stop_single_value_gt85": [f for f, v in single.items() if v > 85], "cost_usd": round(cost, 4), "cost_per_call": round(per, 5),
           "projected_full_usd": round(per * 1217, 2)}
    if WV2:
        v1r = {(r["ticker"], r["date"]): r for r in p3.read_jsonl(REPO / "analysis/data/run_state/winners-missed/read_labels.jsonl")}
        v1d = [v1r[(r["ticker"], r["date"])]["parsed"].get("discounted") for r in rows if (r["ticker"], r["date"]) in v1r]
        rep["v1_discounted_same_60"] = {"yes": v1d.count("yes"), "no": v1d.count("no"), "n": len(v1d)}
        rep["predictions"] = {"raised_yes_pct": dist["raised"]["yes"] / max(len(rows), 1) * 100, "beat_yes_pct": dist["beat"]["yes"] / max(len(rows), 1) * 100,
                              "balance_max_share_pct": single["balance"]}
    rep["STOP"] = bool(bad or mt or rep["stop_single_value_gt85"] or rep["projected_full_usd"] > 8)
    (STATE / "preflight_report.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


def cmd_w_submit_full():
    assert WIN
    have = w_have()
    keys = [k for k in w_reads() if k not in have]
    random.Random(11).shuffle(keys)
    per = W_EST if WV3 else json.loads((STATE / "preflight_report.json").read_text())["cost_per_call"]
    w_submit("batch_id_full", keys, per)
    step("2c", "in_progress", "w-poll-full")


def cmd_w_poll_full():
    if p3.poll_batch("batch_id_full", "raw_full.jsonl", "batch_id_full"):
        w_route("raw_full.jsonl")


# ---- winners step 3: same-company contrastive pairs (prompts/winners-missed-analysis.md Step 3, run by winners-missed-v2)
PAIR_SYSTEM = """You will be shown two earnings call transcripts from the same company, labelled Call A and Call B. The company name, ticker and dates have been removed where possible.

One of the two calls was followed by a much better six months for the stock than the other (more than 20 points better than the S&P 500). Neither the date order nor the outcome is given. Do not say which company this is, and do not rely on anything you remember about how this company's stock did. If your reason is something you can only recall rather than something you can point to in the two transcripts, say so.

Decide which call you think was followed by the much better six months. Then state the ONE concrete difference between the two transcripts that drove your pick, as a mechanism a person could check by reading them. Example of the right kind of answer: "Call A raised full-year guidance while Call B only reaffirmed it."

Return only this block:

---STRUCTURED---
{
  "pick": "",
  "mechanism": "",
  "kind": "",
  "raiseOrBeat": ""
}
---END STRUCTURED---

- pick: "A" or "B".
- mechanism: one sentence, the single checkable difference.
- kind: exactly one of "guidance", "results_vs_expectations", "margins", "demand_or_bookings", "product_or_launch", "balance_sheet_or_cash", "management_tone_or_qna", "external_or_macro", "recall_not_in_text", "other".
- raiseOrBeat: "raise" if the mechanism is that one call raised guidance or outlook and the other did not; "beat" if it is that one call's results beat the company's own prior guidance or targets and the other's did not; "both" if it is both; "neither" otherwise.
"""
_MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"


W3_ALIASES = {
    "AEP": ["American Electric Power", "AEP"], "AIG": ["American International Group", "AIG"],
    "AMPX": ["Amprius Technologies", "Amperius Technologies", "Ambrius Technologie", "Amprius", "Amperius", "Ambrius", "AMPX"],
    "BOX": ["Box, Inc.", "Box Inc", "Box"], "CMCSA": ["Comcast", "NBCUniversal"], "CMI": ["Cummins"], "COF": ["Capital One"],
    "COST": ["Costco"], "DIOD": ["Diodes Incorporated", "Diodes", "Diode's", "Diode"], "EOSE": ["Eos Energy", "EOS Energy", "Eos", "EOS"],
    "IBM": ["International Business Machines", "IBM"], "INTC": ["Intel"], "JKS": ["JinkoSolar", "Jinko Solar", "Jinko"],
    "JPM": ["JPMorgan Chase", "JPMorgan", "JP Morgan", "Chase"], "LLY": ["Eli Lilly", "Lilly"], "MRK": ["Merck"],
    "MS": ["Morgan Stanley"], "MU": ["Micron"], "NEM": ["Newmont"], "NXPI": ["NXP Semiconductors", "NXP Semiconductor", "NXP"],
    "PH": ["Parker Hannifin", "Parker"], "PSX": ["Phillips 66"], "QCOM": ["Qualcomm"], "QS": ["QuantumScape"],
    "SLAB": ["Silicon Laboratories", "Silicon Labs", "Silicon Lab"], "TEAM": ["Atlassian"], "TFC": ["Truist Financial", "Truist"],
    "TTD": ["The Trade Desk", "Trade Desk"], "UPS": ["United Parcel Service", "UPS"], "WMB": ["Williams Companies", "Williams"],
}


def w3_strip(text, ticker):
    """Mechanical redaction: company names (fixed alias list per ticker, case-sensitive whole words), ticker, years and months. Returns (text, info)."""
    names = sorted(set(W3_ALIASES.get(ticker, []) + [ticker]), key=len, reverse=True)
    out = text
    for nm in names:
        out = re.sub(r"(?<![A-Za-z])" + re.escape(nm) + r"(?:[\u2019']s)?(?![A-Za-z])", "[COMPANY]", out)
    out = re.sub(r"\b(?:19|20)\d{2}\b", "[YEAR]", out)
    out = re.sub(r"\b" + _MONTHS + r"\b\.?(?:\s+\d{1,2}(?:st|nd|rd|th)?)?", "[MONTH]", out)
    residual = [nm for nm in names if re.search(r"(?<![A-Za-z])" + re.escape(nm) + r"(?![A-Za-z])", out)]
    return out, {"aliases_used": names, "name_removed": ticker in W3_ALIASES, "ticker_residual": ticker in residual, "name_residual": bool(set(residual) - {ticker}),
                 "n_replaced": len(re.findall(r"\[COMPANY\]", out))}


def cmd_w3_build():
    """Seeded selection of up to 30 same-company pairs (one big-winner call, that company's nearest middle call), redacted transcripts, A/B order seeded."""
    assert WIN
    import csv as _csv
    from datetime import date as _date
    rows = list(_csv.DictReader(open(REPO / "analysis/data/run_state/p6-output-format-round/calls.csv")))
    by = {}
    for r in rows:
        if r["fwd_rel_ret_tradeable"] == "": continue
        v = float(r["fwd_rel_ret_tradeable"])
        cls = "winner" if v >= 20 else "loser" if v <= -20 else "middle"
        by.setdefault(r["ticker"], []).append({"ticker": r["ticker"], "date": r["call_date"], "ret": v, "cls": cls})
    elig = sorted(t for t, xs in by.items() if any(x["cls"] == "winner" for x in xs) and any(x["cls"] == "middle" for x in xs))
    rng = random.Random("winners-pairs-11")
    pick = rng.sample(elig, min(30, len(elig)))
    pairs, i = [], 0
    for t in sorted(pick):
        xs = by[t]; w = rng.choice(sorted([x for x in xs if x["cls"] == "winner"], key=lambda x: x["date"]))
        d0 = _date.fromisoformat(w["date"])
        m = min([x for x in xs if x["cls"] == "middle"], key=lambda x: (abs((_date.fromisoformat(x["date"]) - d0).days), x["date"]))
        a_is_winner = rng.random() < 0.5
        wt, wi = w3_strip(transcript(t, w["date"]), t); mt, mi = w3_strip(transcript(t, m["date"]), t)
        pairs.append({"pair": i, "ticker": t, "winner": w, "middle": m, "days_apart": abs((_date.fromisoformat(m["date"]) - d0).days),
                      "A_is_winner": a_is_winner, "A_text": wt if a_is_winner else mt, "B_text": mt if a_is_winner else wt,
                      "redaction": {"winner": wi, "middle": mi}})
        i += 1
    TX = REPO / "analysis/data/evals/winners-missed-v2_pairs"; TX.mkdir(parents=True, exist_ok=True)      # redacted texts: gitignored, rebuildable from the seed
    (TX / "pairs_texts.json").write_text(json.dumps({p["pair"]: {"A": p["A_text"], "B": p["B_text"]} for p in pairs}))
    meta = [{k: v for k, v in p.items() if k not in ("A_text", "B_text")} for p in pairs]
    (STATE / "pairs.json").write_text(json.dumps({"eligible_companies": len(elig), "seed": "winners-pairs-11", "pairs": meta}, indent=1))
    leak = sum(1 for p in pairs for k in ("winner", "middle") if p["redaction"][k]["ticker_residual"] or p["redaction"][k]["name_residual"] or not p["redaction"][k]["name_removed"])
    print(json.dumps({"eligible_companies": len(elig), "pairs": len(pairs), "transcripts_with_leak_or_no_name_extracted": leak, "of": 2 * len(pairs),
                      "median_chars": sorted(len(p["A_text"]) for p in pairs)[len(pairs) // 2]}))


def cmd_w3_submit():
    assert WIN
    from anthropic.types.messages.batch_create_params import Request
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    P = json.loads((STATE / "pairs.json").read_text())["pairs"]
    TXT = json.loads((REPO / "analysis/data/evals/winners-missed-v2_pairs/pairs_texts.json").read_text())
    for p in P: p["A_text"], p["B_text"] = TXT[str(p["pair"])]["A"], TXT[str(p["pair"])]["B"]
    pr = load_progress()
    if pr.get("batch_id_pairs"):
        print("already", pr["batch_id_pairs"]); return
    reqs = [Request(custom_id=f"PAIR__{p['pair']:02d}", params=MessageCreateParamsNonStreaming(
        model=MODEL, max_tokens=500, system=[{"type": "text", "text": PAIR_SYSTEM}],
        messages=[{"role": "user", "content": f"=== Call A ===\n{p['A_text']}\n\n=== Call B ===\n{p['B_text']}"}])) for p in P]
    pr["pair_system_sha256"] = hashlib.sha256(PAIR_SYSTEM.encode()).hexdigest(); save_progress(pr)
    commit_spend("batch_id_pairs", len(reqs), 0.075)
    p3.submit_batch(reqs, "batch_id_pairs")


def cmd_w3_retry():
    """The 4 pairs whose first pass stopped at max_tokens=500 before finishing the block: same request, max_tokens 2000."""
    assert WIN
    from anthropic.types.messages.batch_create_params import Request
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from analyst_direct_scorer import parse_structured
    P = json.loads((STATE / "pairs.json").read_text())["pairs"]
    TXT = json.loads((REPO / "analysis/data/evals/winners-missed-v2_pairs/pairs_texts.json").read_text())
    failed = sorted(int(r["custom_id"].split("__")[1]) for r in p3.read_jsonl(STATE / "raw_pairs.jsonl") if not parse_structured(r["content"]).get("pick"))
    pr = load_progress()
    if pr.get("batch_id_pairs_retry"):
        print("already", pr["batch_id_pairs_retry"]); return
    reqs = [Request(custom_id=f"PAIR__{i:02d}", params=MessageCreateParamsNonStreaming(
        model=MODEL, max_tokens=2000, system=[{"type": "text", "text": PAIR_SYSTEM}],
        messages=[{"role": "user", "content": f"=== Call A ===\n{TXT[str(i)]['A']}\n\n=== Call B ===\n{TXT[str(i)]['B']}"}])) for i in failed]
    pr["retry_pairs"] = failed; save_progress(pr)
    commit_spend("batch_id_pairs_retry", len(reqs), 0.09)
    p3.submit_batch(reqs, "batch_id_pairs_retry")


def cmd_w3_retry_poll():
    if p3.poll_batch("batch_id_pairs_retry", "raw_pairs_retry.jsonl", "batch_id_pairs_retry"):
        print("retry collected")


def cmd_w3_poll():
    if p3.poll_batch("batch_id_pairs", "raw_pairs.jsonl", "batch_id_pairs"):
        print("pairs collected")


# --------------------------------------------------------------------------- P9-side (prompts/P9-expected-return.md)
def cmd_p9_select():
    """150 train calls, proportional across S1-S5, at least one S4 call, fixed seed."""
    assert P9
    smap = p3.stratum_map()
    by_s = {}
    for r in universe():
        by_s.setdefault(smap.get(r["ticker"], "?"), []).append(r)
    assert "?" not in by_s
    counts = {s_: len(v) for s_, v in by_s.items()}
    alloc = p3.stratum_alloc(PREFLIGHT_N, counts)
    if alloc.get("S4", 0) == 0:
        big = max(alloc, key=alloc.get); alloc[big] -= 1; alloc["S4"] = 1
    rng = random.Random("p9-preflight-11")
    pre = []
    for s_ in sorted(alloc):
        pre += [(r["ticker"], r["date"]) for r in rng.sample(sorted(by_s[s_], key=lambda r: (r["ticker"], r["date"])), alloc[s_])]
    assert len(pre) == PREFLIGHT_N and len(set(pre)) == PREFLIGHT_N
    (STATE / "selection.json").write_text(json.dumps({"preflight": [list(k) for k in pre], "preflight_alloc": alloc,
                                                      "universe_counts": counts, "seed": "p9-preflight-11"}, indent=1))
    print(json.dumps({"alloc": alloc, "counts": counts}))


def cmd_p9_check():
    assert P9
    recs = universe()
    orig = {(r["ticker"], r["date"]) for r in p3.read_jsonl(ORIGINAL_STATE / "scores_b.jsonl")}
    assert len(recs) == 1217 == len(orig) and {(r["ticker"], r["date"]) for r in recs} == orig
    assert sha(PROMPTS["P9"]) == P9_SHA, "P9 candidate sha != registered"
    reg = json.loads((REPO / "docs/architecture/VERSION_REGISTRY.json").read_text())["artifacts"]["evaluation_prompt"]["candidates"]
    assert next(c["sha256"] for c in reg if c["version"] == "P9-expected-return") == P9_SHA
    rng = random.Random("p9-shape-11")
    for w, d in rng.sample(sorted(orig), 25):
        a, b = dict(make_request("P9", w, d)["params"]), dict(make_request("B", w, d)["params"])
        assert set(a) == set(b) == {"model", "max_tokens", "system", "messages"} and "temperature" not in a
        assert a["model"] == b["model"] == MODEL and a["max_tokens"] == b["max_tokens"] == 4096
        assert a["messages"] == b["messages"]
        assert a["system"][0]["cache_control"] == b["system"][0]["cache_control"] and len(a["system"]) == len(b["system"]) == 1
        assert a["system"][0]["text"] == PROMPTS["P9"].read_text() and b["system"][0]["text"] == PROMPTS["B"].read_text()
        assert make_request("P9", w, d)["custom_id"] == f"P9__{w}_{d}" + ("__r1" if P9R else "")
    rep = {"universe": 1217, "p9_sha": P9_SHA, "shape": "identical to B make_request() except system text", "sample": 25}
    (STATE / "request_shape_check.json").write_text(json.dumps(rep, indent=1)); print(rep)


def _num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def cmd_p9_preflight_report():
    """Every section 4 stop figure. $0."""
    assert P9
    from analyst_direct_scorer import parse_structured
    sel = json.loads((STATE / "selection.json").read_text())
    want = {tuple(x) for x in sel["preflight"]}
    rows = [r for r in p3.read_jsonl(scores_path("P9")) if (r["ticker"], r["date"]) in want]
    bad = {"unparseable": 0, "non_numeric": 0, "max_tokens": 0, "bad_noRead": 0}
    er, order_broken, nr, cost, toks = [], 0, 0, 0.0, []
    for r in rows:
        st = parse_structured(r["content"]); cost += r["cost_usd"]; toks.append(r["usage"]["output_tokens"])
        if r["stop_reason"] == "max_tokens": bad["max_tokens"] += 1
        if not st: bad["unparseable"] += 1; continue
        e, lo, hi = _num(st.get("expectedReturn")), _num(st.get("rangeLow")), _num(st.get("rangeHigh"))
        if None in (e, lo, hi): bad["non_numeric"] += 1; continue
        er.append(e)
        if not (lo <= e <= hi): order_broken += 1
        if not isinstance(st.get("noRead"), bool): bad["bad_noRead"] += 1
        elif st["noRead"]: nr += 1
    import numpy as _np
    n = max(len(er), 1)
    q1, med_, q3 = (float(_np.percentile(er, q)) for q in (25, 50, 75)) if er else (0, 0, 0)
    pos, neg = sum(e > 0 for e in er), sum(e < 0 for e in er)
    per = cost / max(len(rows), 1)
    rep = {"n": len(rows), **bad, "range_order_broken": order_broken, "distinct_values": len(set(er)),
           "median": med_, "middle_half": [q1, q3], "middle_half_span": q3 - q1,
           "share_positive_pct": round(100 * pos / n, 1), "share_negative_pct": round(100 * neg / n, 1),
           "share_same_side_max_pct": round(100 * max(pos, neg) / n, 1),
           "noRead_pct": round(100 * nr / max(len(rows), 1), 1), "cost_usd": round(cost, 4), "cost_per_call": round(per, 5),
           "projected_full_usd": round(per * 1217, 2), "median_completion_tokens": sorted(toks)[len(toks) // 2] if toks else None}
    stops = {"parse_or_max_tokens_or_nonnumeric": any(bad.values()), "range_order_broken_gt3": order_broken > 3,
             "bunched": (q3 - q1) < 4 or len(set(er)) < 8, "one_sided_gt85": max(pos, neg) / n > 0.85,
             "noRead_gt10": rep["noRead_pct"] > 10, "cost_gt36": rep["projected_full_usd"] > 36}
    rep["stop_rules"] = stops; rep["STOP"] = any(stops.values())
    (STATE / "preflight_report.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


def cmd_submit_p9():
    assert P9
    reqs = [make_request("P9", r["ticker"], r["date"]) for r in pending("P9")]
    print("pending after pre-flight reuse:", len(reqs))
    assert len(reqs) + len(have_ids("P9")) == 1217
    submit("batch_id_full", reqs, EST_PER_CALL if P9R else per_call_p7())
    step("5b", "in_progress", "poll-p9")


def cmd_poll_p9():
    poll("batch_id_full", "raw_full.jsonl")


# --------------------------------------------------------------------------- P7-side (prompts/P7-three-voices.md)
GAP_OK, PRESSURE_OK = {"numbers_ahead", "aligned", "claims_ahead"}, {"answered", "avoided", "none"}


def _b_dir(s):
    return None if s is None else "bearish" if s <= -2 else "bullish" if s >= 3 else "neutral"


def cmd_p7_select():
    """150 train calls, proportional across S1-S5, at least one S4 call, fixed seed."""
    assert P7
    smap = p3.stratum_map()
    by_s = {}
    for r in universe():
        by_s.setdefault(smap.get(r["ticker"], "?"), []).append(r)
    assert "?" not in by_s
    counts = {s: len(v) for s, v in by_s.items()}
    alloc = p3.stratum_alloc(PREFLIGHT_N, counts)
    if alloc.get("S4", 0) == 0:
        big = max(alloc, key=alloc.get); alloc[big] -= 1; alloc["S4"] = 1
    rng = random.Random("p7-preflight-11")
    pre = []
    for s in sorted(alloc):
        pre += [(r["ticker"], r["date"]) for r in rng.sample(sorted(by_s[s], key=lambda r: (r["ticker"], r["date"])), alloc[s])]
    assert len(pre) == PREFLIGHT_N and len(set(pre)) == PREFLIGHT_N
    (STATE / "selection.json").write_text(json.dumps({"preflight": [list(k) for k in pre], "preflight_alloc": alloc,
                                                      "universe_counts": counts, "seed": "p7-preflight-11"}, indent=1))
    print(json.dumps({"alloc": alloc, "counts": counts}))


def cmd_p7_check():
    """Universe equals B's; prompt sha; request shape identical to B's make_request() except the system text. $0."""
    assert P7
    recs = universe()
    orig = {(r["ticker"], r["date"]) for r in p3.read_jsonl(ORIGINAL_STATE / "scores_b.jsonl")}
    assert len(recs) == 1217 == len(orig) and {(r["ticker"], r["date"]) for r in recs} == orig
    assert sha(PROMPTS["P7"]) == P7_SHA, "P7 candidate sha != registered"
    reg = json.loads((REPO / "docs/architecture/VERSION_REGISTRY.json").read_text())["artifacts"]["evaluation_prompt"]["candidates"]
    assert next(c["sha256"] for c in reg if c["version"] == "P7-three-voices") == P7_SHA
    rng = random.Random("p7-shape-11")
    for w, d in rng.sample(sorted(orig), 25):
        a, b = dict(make_request("P7", w, d)["params"]), dict(make_request("B", w, d)["params"])
        assert set(a) == set(b) == {"model", "max_tokens", "system", "messages"} and "temperature" not in a
        assert a["model"] == b["model"] == MODEL and a["max_tokens"] == b["max_tokens"] == 4096
        assert a["messages"] == b["messages"]
        assert a["system"][0]["cache_control"] == b["system"][0]["cache_control"] and len(a["system"]) == len(b["system"]) == 1
        assert a["system"][0]["text"] == PROMPTS["P7"].read_text() and b["system"][0]["text"] == PROMPTS["B"].read_text()
        assert make_request("P7", w, d)["custom_id"] == f"P7__{w}_{d}"
    rep = {"universe": 1217, "p7_sha": P7_SHA, "shape": "identical to B make_request() except system text", "sample": 25}
    (STATE / "request_shape_check.json").write_text(json.dumps(rep, indent=1)); print(rep)


def cmd_p7_preflight_report():
    """Stop-rule figures first: direction disagreement vs B draw 1 (and draw 2 for reference), parse/enum/max_tokens, cost projection."""
    assert P7
    from analyst_direct_scorer import parse_structured
    sel = json.loads((STATE / "selection.json").read_text())
    want = {tuple(x) for x in sel["preflight"]}
    b1 = {(r["ticker"], r["date"]): r for r in p3.read_jsonl(ORIGINAL_STATE / "scores_b.jsonl")}
    b2 = {(r["ticker"], r["date"]): r for r in p3.read_jsonl(ORIGINAL_STATE_B2 / "scores_b_rerun1.jsonl")}
    rows = [r for r in p3.read_jsonl(scores_path("P7")) if (r["ticker"], r["date"]) in want]

    def sc(r):
        s = parse_structured(r["content"]).get("score")
        return s if isinstance(s, int) and not isinstance(s, bool) and -5 <= s <= 5 else None
    bad = {"unparseable": 0, "bad_score": 0, "bad_noRead": 0, "bad_gap": 0, "bad_pressure": 0, "max_tokens": 0}
    dis1 = dis2 = n = 0
    gaps, press, cost, toks = {}, {}, 0.0, []
    for r in rows:
        st = parse_structured(r["content"]); cost += r["cost_usd"]; toks.append(r["usage"]["output_tokens"])
        if r["stop_reason"] == "max_tokens": bad["max_tokens"] += 1
        if not st: bad["unparseable"] += 1; continue
        s = sc(r)
        if s is None: bad["bad_score"] += 1
        if not isinstance(st.get("noRead"), bool): bad["bad_noRead"] += 1
        g, pr = st.get("gap"), st.get("pressure")
        if g not in GAP_OK: bad["bad_gap"] += 1
        if pr not in PRESSURE_OK: bad["bad_pressure"] += 1
        gaps[g] = gaps.get(g, 0) + 1; press[pr] = press.get(pr, 0) + 1
        k = (r["ticker"], r["date"])
        sb1 = parse_structured(json.dumps({}) if False else b1[k]["content"]).get("score") if k in b1 else None
        sb2 = parse_structured(b2[k]["content"]).get("score") if k in b2 else None
        if s is not None and sb1 is not None:
            n += 1
            dis1 += _b_dir(s) != _b_dir(sb1)
            dis2 += (sb2 is not None and _b_dir(s) != _b_dir(sb2))
    per = cost / max(len(rows), 1)
    rep = {"n": len(rows), "disagree_vs_B_draw1": dis1, "disagree_vs_B_draw1_pct": round(100 * dis1 / max(n, 1), 1),
           "disagree_vs_B_draw2_pct": round(100 * dis2 / max(n, 1), 1), "stop_threshold_pct": 20.0, **bad,
           "gap_counts": gaps, "pressure_counts": press, "cost_usd": round(cost, 4), "cost_per_call": round(per, 5),
           "projected_full_usd": round(per * 1217, 2), "median_completion_tokens": sorted(toks)[len(toks) // 2] if toks else None}
    rep["STOP"] = (100 * dis1 / max(n, 1) < 20.0 or any(bad.values()) or rep["projected_full_usd"] > 40)
    (STATE / "preflight_report.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


def cmd_submit_p7():
    assert P7
    reqs = [make_request("P7", r["ticker"], r["date"]) for r in pending("P7")]
    print("pending after pre-flight reuse:", len(reqs))
    assert len(reqs) + len(have_ids("P7")) == 1217
    submit("batch_id_full", reqs, per_call_p7())
    step("5b", "in_progress", "poll-p7")


def per_call_p7():
    return json.loads((STATE / "preflight_report.json").read_text())["cost_per_call"]


def cmd_poll_p7():
    poll("batch_id_full", "raw_full.jsonl")


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "").replace("-", "_")
    fn = globals().get("cmd_" + cmd)
    if fn:
        fn(*sys.argv[2:])
    else:
        print(__doc__)
