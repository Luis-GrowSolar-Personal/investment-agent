#!/usr/bin/env python3
"""
p3_guidance_ledger_driver.py -- prompts/P3-guidance-ledger.md (run_id p3-guidance-ledger)

Phase 1: Pass A extraction -> fidelity check -> ledger -> $0 diagnostics -> pre-flight.
Phase 2 (Pass B) is NOT wired to run without a recorded go in progress.json.

Commands (see main()):
  check0f            alias resolution asserts (Step 0f)
  sample             choose the validation / eyeball sample
  extract-sync       synchronous extraction on the sample (validation, real spend)
  fidelity           mechanical fidelity check on an extractions jsonl
  submit-a / poll-a  Pass A batch
  build-ledger       join promises to actuals ($0)
  diag               5d / 5e diagnostics ($0)
  preflight-select / preflight-submit / preflight-poll / preflight-report
Batch helpers here are local (baseline_v6_tune_batch_driver's are hard-bound to
the tune split's state dir and eval cache); the request shape is copied from it.
"""
import os, sys, json, re, glob, hashlib, datetime, random, unicodedata
from pathlib import Path
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO))

RUN_ID = "p3-guidance-ledger"
STATE = REPO / "analysis/data/run_state" / RUN_ID
PROGRESS = STATE / "progress.json"
FINDINGS = STATE / "findings.md"
C2 = REPO / "analysis/data/corpus_v2"
TRANSCRIPTS = C2 / "transcripts"
SPLIT = C2 / "SPLIT_V7_RESERVE_REPLACEMENTS.json"
ALIASES = C2 / "TICKER_ALIASES.json"
V6_EVAL_DIR = REPO / "analysis/data/evals/v6_claude-sonnet-4-6"
PRICE_CACHE = "analysis/data/corpus_v2/scorer_price_cache_v1.json"
EXTRACTION_PROMPT = REPO / "docs/prompts/candidates/EXTRACTION_PROMPT_P3A.md"
CAND_PROMPT = REPO / "docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md"
V6_PROMPT = REPO / "docs/EVALUATION_PROMPT.md"
LEDGER_DIR = C2 / "ledger"
JOINED = REPO / "analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv"

MODEL = "claude-sonnet-4-6"
EXTRACT_MAX_TOKENS = 6000
SCORE_MAX_TOKENS = 4096
EXCLUDE = {"WOLF", "SPWR"}

# Sonnet 4.6 published rates, $/MTok. Batch = 50%.
P_IN, P_OUT, P_CR, P_CW = 3.0, 15.0, 0.30, 3.75


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_progress():
    return json.loads(PROGRESS.read_text())


def save_progress(p):
    PROGRESS.write_text(json.dumps(p, indent=2, default=str))


def finding(text):
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write(f"\n- {now()}: {text}\n")


def cost_of(usage, batch):
    c = (usage.get("input_tokens", 0) * P_IN + usage.get("output_tokens", 0) * P_OUT
         + usage.get("cache_read_input_tokens", 0) * P_CR
         + usage.get("cache_creation_input_tokens", 0) * P_CW) / 1e6
    return c * (0.5 if batch else 1.0)


# --------------------------------------------------------------------------- 0f
def alias_map():
    raw = json.loads(ALIASES.read_text())
    return {e["original_symbol"]: e["working_symbol"] for e in raw["entries"] if e.get("working_symbol")}


def resolved_train():
    """[(original, working)] for the 57 train companies, alias-resolved."""
    amap = alias_map()
    sp = json.loads(SPLIT.read_text())
    return [(t, amap.get(t, t)) for t in sp["train"]]


def train_calls():
    """{working: [ {date, path, year, quarter} sorted by date ]} -- only companies with files."""
    out = {}
    for orig, w in resolved_train():
        if w in EXCLUDE or orig in EXCLUDE:
            continue
        fs = sorted(glob.glob(str(TRANSCRIPTS / w / "*.json")))
        if not fs:
            continue
        rows = []
        for f in fs:
            d = json.loads(Path(f).read_text())
            rows.append({"date": Path(f).stem, "path": f, "year": d["year"], "quarter": d["quarter"]})
        out[w] = rows
    return out


def cmd_check0f():
    sp = json.loads(SPLIT.read_text())
    rt = resolved_train()
    calls = train_calls()
    n_files = sum(len(v) for v in calls.values())
    n_comp = len(calls)
    missing = [w for _, w in rt if w not in calls]
    evs = sorted(glob.glob(str(V6_EVAL_DIR / "*.txt")))
    ev_tk = {Path(e).stem.rsplit("_", 1)[0] for e in evs}
    rset = {w for _, w in rt}
    unmapped = sorted(ev_tk - rset)
    pred = n_files - n_comp
    # unresolved counts, for the record
    unres = sum(len(glob.glob(str(TRANSCRIPTS / t / "*.json"))) for t in sp["train"])
    res = {
        "train_symbols": len(sp["train"]), "resolved_files": n_files, "resolved_companies": n_comp,
        "unresolved_files": unres, "no_files_symbols": missing, "eval_files": len(evs),
        "eval_unmapped_symbols": unmapped, "predecessor_bearing": pred,
        "disjoint_tune": not (set(sp["train"]) & set(sp["tune"])),
        "disjoint_holdout": not (set(sp["train"]) & set(sp["holdout"])),
        "wolf_spwr_in_train": sorted((set(sp["train"]) | rset) & EXCLUDE),
    }
    ok = (n_files == 1240 and n_comp == 56 and len(evs) == 1240 and not unmapped
          and pred == 1184 and set(missing) <= {"MAXNQ"} and res["disjoint_tune"] and res["disjoint_holdout"])
    res["asserts_pass"] = ok
    print(json.dumps(res, indent=1))
    (STATE / "step0f_alias_asserts.json").write_text(json.dumps(res, indent=1))
    if not ok:
        raise SystemExit("0f HARD STOP: alias/count assertion failed")


# --------------------------------------------------------------------------- normalisation / fidelity
_DASH = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_QUOTE = {ord("‘"): "'", ord("’"): "'", ord("“"): '"', ord("”"): '"', ord(" "): " "}


def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.translate(_QUOTE).translate(_DASH).lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_quote(s):
    return norm(s).strip(" .,;:!?\"'")


_SCALE = {"trillion": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mm": 1e6, "m": 1e6,
          "thousand": 1e3, "k": 1e3}


def parse_written(s):
    """Return (number, scale_word_or_None, is_percent) from an as-written string, or None."""
    t = norm(s)
    m = re.search(r"(-|\()?\$?\s*(\d[\d,]*\.?\d*|\.\d+)\s*(trillion|billion|million|thousand|bn|mm|k|b|m)?\b", t)
    if not m:
        return None
    try:
        num = float(m.group(2).replace(",", ""))
    except ValueError:
        return None
    return num, m.group(3), ("%" in t or "percent" in t or "basis point" in t or "bps" in t)


def plausible(value, written, sibling_written=None):
    """Does `value` agree with the parse of `written`? unit and scale must agree.
    Returns True / False / None (unverifiable: spelled-out number etc.)."""
    if value is None:
        return True
    p = parse_written(written)
    if p is None:
        return None
    num, sc, pct = p
    scales = [sc]
    if sibling_written:
        q = parse_written(sibling_written)
        if q and q[1]:
            scales.append(q[1])
    cands = set()
    for s in scales:
        mult = _SCALE.get(s, 1.0) if s else 1.0
        cands.add(num * mult)
    cands.add(num)  # a stated-unit value (e.g. 1.2 with unit 'billion' recorded unscaled) is not accepted below
    av = abs(float(value))
    for c in cands:
        if c == 0 and av == 0:
            return True
        if c and abs(av - c) / abs(c) < 0.011:
            # bare-number acceptance only when no scale word was written at all
            if c == num and any(_SCALE.get(s) for s in scales if s):
                continue
            return True
    # basis points written, percent recorded
    if "basis point" in norm(written) or "bps" in norm(written):
        if abs(av - num / 100) / max(num / 100, 1e-9) < 0.011:
            return True
    return False


def fidelity_filter(ex, transcript_text):
    """Mechanical fidelity check on one extraction. Returns (kept_ex, stats, drops)."""
    tn = norm(transcript_text)
    stats = {"entries": 0, "kept": 0, "quote_miss": 0, "written_miss": 0, "mis_parse": 0, "unverifiable": 0,
             "no_quote": 0}
    drops = []
    kept = {"reported": [], "guided": [], "stated_intents": ex.get("stated_intents", []) or [],
            "retractions": []}
    for kind in ("reported", "guided", "retractions"):
        for e in ex.get(kind, []) or []:
            stats["entries"] += 1
            q = e.get("quote")
            if not q or not str(q).strip():
                stats["no_quote"] += 1
                stats["quote_miss"] += 1
                drops.append((kind, "no_quote", e))
                continue
            qn = norm_quote(q)
            if qn not in tn:
                stats["quote_miss"] += 1
                drops.append((kind, "quote_not_verbatim", e))
                continue
            if kind == "retractions":
                stats["kept"] += 1
                kept[kind].append(e)
                continue
            keys = ["value_as_written"] if kind == "reported" else ["low_as_written", "high_as_written"]
            bad = False
            for k in keys:
                w = e.get(k)
                if w is None:
                    continue
                if norm_quote(str(w)) not in qn:
                    bad = True
            if bad:
                stats["written_miss"] += 1
                stats["quote_miss"] += 1
                drops.append((kind, "as_written_not_in_quote", e))
                continue
            mis = False
            unv = False
            if kind == "reported":
                r = plausible(e.get("value"), e.get("value_as_written"))
                mis, unv = (r is False), (r is None)
            else:
                lw, hw = e.get("low_as_written"), e.get("high_as_written")
                for val, w, sib in ((e.get("low"), lw, hw), (e.get("high"), hw, lw)):
                    if w is None:
                        continue
                    r = plausible(val, w, sib)
                    mis = mis or (r is False)
                    unv = unv or (r is None)
            if mis:
                stats["mis_parse"] += 1
                drops.append((kind, "mis_parse", e))
                continue
            if unv:
                stats["unverifiable"] += 1
            stats["kept"] += 1
            kept[kind].append(e)
    return kept, stats, drops


# --------------------------------------------------------------------------- extraction request shape
def ex_system():
    return [{"type": "text", "text": EXTRACTION_PROMPT.read_text(), "cache_control": {"type": "ephemeral"}}]


def ex_user(rec):
    d = json.loads(Path(rec["path"]).read_text())
    return f"CALL LABEL: Q{d['quarter']} {d['year']}\n\n{d['text']}"


def cid(w, date):
    c = f"{w}_{date}"
    assert re.match(r"^[a-zA-Z0-9_-]{1,64}$", c), c
    return c


def parse_json_obj(txt):
    t = txt.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def read_jsonl(p):
    p = Path(p)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def append_jsonl(p, rec):
    with Path(p).open("a") as f:
        f.write(json.dumps(rec) + "\n")
        f.flush()


def all_train_records():
    out = []
    for w, rows in train_calls().items():
        for r in rows:
            out.append({"ticker": w, **r})
    return out


# --------------------------------------------------------------------------- sample for validation / eyeball
def stratum_map():
    sp = json.loads(SPLIT.read_text())
    amap = alias_map()
    m = {}
    for s, d in sp["per_stratum"].items():
        for t in d["train"]:
            m[amap.get(t, t)] = s
    return m


def guidance_keyword_score(text):
    t = norm(text)
    return len(re.findall(r"\b(guidance|outlook|we expect|we anticipate|expect (?:revenue|to)|range of)\b", t))


def cmd_sample():
    """15 eyeball transcripts by corpus stratum (3 S1, 3 S2, 2 S3, 3 S5, 2 S4 failures, 2 no numeric guidance) + 5 random. Seed 11."""
    smap = stratum_map()
    recs = all_train_records()
    rng = random.Random(11)
    by_s = {}
    for r in recs:
        by_s.setdefault(smap.get(r["ticker"], "?"), []).append(r)
    pick = []

    def take(pool, n, tag):
        pool = [r for r in pool if all(r["path"] != p["path"] for p in pick)]
        for r in rng.sample(pool, min(n, len(pool))):
            pick.append({**r, "tag": tag})

    # Corpus strata (PREREGISTRATION.json): S1 large cap, S2 in-scope mixed cap, S3 other, S4 failures, S5 ALL16.
    # The prompt's established/speculative/pre-revenue labels are tier (a separate classifier), not stratum;
    # the eyeball set is drawn by stratum and labelled as such.
    take(by_s.get("S1", []), 3, "S1_large_cap")
    take(by_s.get("S2", []), 3, "S2_mixed_cap")
    take(by_s.get("S3", []), 2, "S3")
    take(by_s.get("S5", []), 3, "S5_ALL16")
    take(by_s.get("S4", []), 2, "S4_failures")
    # two with no numeric guidance: lowest guidance keyword count among a random 300 transcripts
    pool = rng.sample(recs, 300)
    scored = sorted(pool, key=lambda r: guidance_keyword_score(json.loads(Path(r["path"]).read_text())["text"]))
    take(scored[:6], 2, "no_numeric_guidance")
    take(recs, 5, "random")
    out = [{"ticker": r["ticker"], "date": r["date"], "path": r["path"], "tag": r["tag"],
            "stratum": smap.get(r["ticker"])} for r in pick]
    (STATE / "validation_sample.json").write_text(json.dumps(out, indent=1))
    for o in out:
        print(o["tag"], o["ticker"], o["date"], o["stratum"])


# --------------------------------------------------------------------------- sync extraction (validation)
def client():
    import anthropic
    return anthropic.Anthropic()


def extract_one_sync(cl, rec):
    msg = cl.messages.create(model=MODEL, max_tokens=EXTRACT_MAX_TOKENS, system=ex_system(),
                             messages=[{"role": "user", "content": ex_user(rec)}])
    txt = "".join(b.text for b in msg.content if b.type == "text")
    u = msg.usage
    usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
             "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
             "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0}
    return txt, usage, msg.stop_reason


def cmd_extract_sync(path="validation_extractions.jsonl"):
    cl = client()
    sample = json.loads((STATE / "validation_sample.json").read_text())
    outp = STATE / path
    done = {r["custom_id"] for r in read_jsonl(outp)}
    spent = sum(r["cost_usd"] for r in read_jsonl(outp))
    for s in sample:
        c = cid(s["ticker"], s["date"])
        if c in done:
            continue
        if spent > 6.0:
            raise SystemExit("validation spend cap ($6) reached")
        txt, usage, stop = extract_one_sync(cl, s)
        cost = cost_of(usage, batch=False)
        spent += cost
        append_jsonl(outp, {"custom_id": c, "ticker": s["ticker"], "date": s["date"], "tag": s["tag"],
                            "content": txt, "usage": usage, "stop_reason": stop, "cost_usd": round(cost, 5),
                            "source": "sync_validation", "extraction_prompt_sha256": sha256_file(EXTRACTION_PROMPT),
                            "fetched_at": now()})
        print(c, s["tag"], f"${cost:.4f}", stop)
    print(f"validation spend so far ${spent:.4f}")


def fidelity_report(records, label):
    tot = {"entries": 0, "kept": 0, "quote_miss": 0, "written_miss": 0, "mis_parse": 0, "unverifiable": 0,
           "no_quote": 0}
    per_tk = {}
    unparsed = 0
    empty = 0
    for r in records:
        ex = parse_json_obj(r["content"])
        if ex is None:
            unparsed += 1
            continue
        tp = TRANSCRIPTS / r["ticker"] / f"{r['date']}.json"
        text = json.loads(tp.read_text())["text"]
        kept, st, drops = fidelity_filter(ex, text)
        if st["entries"] == 0:
            empty += 1
        for k in tot:
            tot[k] += st[k]
            per_tk.setdefault(r["ticker"], {kk: 0 for kk in tot})[k] += st[k]
    n = max(tot["entries"], 1)
    print(f"[{label}] calls={len(records)} unparseable_json={unparsed} empty_extractions={empty}")
    print(f"  entries={tot['entries']} kept={tot['kept']} quote_miss={tot['quote_miss']} "
          f"({100*tot['quote_miss']/n:.2f}%) [of which as_written_not_in_quote={tot['written_miss']}] "
          f"mis_parse={tot['mis_parse']} ({100*tot['mis_parse']/n:.2f}%) unverifiable_kept={tot['unverifiable']}")
    drop_rate = (tot["quote_miss"] + tot["mis_parse"]) / n
    print(f"  combined drop rate {100*drop_rate:.2f}%")
    return {"totals": tot, "per_ticker": per_tk, "drop_rate": drop_rate, "unparseable": unparsed, "empty": empty}


def cmd_fidelity(path="validation_extractions.jsonl"):
    recs = read_jsonl(STATE / path)
    res = fidelity_report(recs, path)
    (STATE / (Path(path).stem + "_fidelity.json")).write_text(json.dumps(res, indent=1))
    return res


# --------------------------------------------------------------------------- batch helpers
def submit_batch(requests, key):
    p = load_progress()
    if p.get(key):
        print(f"{key} already recorded: {p[key]} -- NOT submitting again")
        return p[key]
    cl = client()
    b = cl.messages.batches.create(requests=requests)
    p[key] = b.id
    p[key + "_submitted_at"] = now()
    p[key + "_requests"] = len(requests)
    save_progress(p)
    print(f"SUBMITTED {key}={b.id} n={len(requests)} -- COMMIT progress.json NOW")
    return b.id


def poll_batch(key, out_jsonl, prompt_tag):
    cl = client()
    p = load_progress()
    bid = p.get(key)
    if not bid:
        print(f"no {key}")
        return
    b = cl.messages.batches.retrieve(bid)
    print(f"{bid}: {b.processing_status} {b.request_counts}")
    if b.processing_status != "ended":
        return False
    outp = STATE / out_jsonl
    have = {r["custom_id"] for r in read_jsonl(outp)}
    n = err = exp = 0
    for e in cl.messages.batches.results(bid):
        if e.custom_id in have:
            continue
        if e.result.type == "succeeded":
            m = e.result.message
            u = m.usage
            usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                     "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                     "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0}
            tk, dt = e.custom_id.rsplit("_", 1)
            append_jsonl(outp, {"custom_id": e.custom_id, "ticker": tk, "date": dt,
                                "content": "".join(b_.text for b_ in m.content if b_.type == "text"),
                                "usage": usage, "stop_reason": m.stop_reason,
                                "cost_usd": round(cost_of(usage, batch=True), 5), "source": "batch",
                                "batch_id": bid, "tag": prompt_tag, "fetched_at": now()})
            n += 1
        elif e.result.type == "errored":
            finding(f"{key} errored: {e.custom_id}: {e.result.error}")
            err += 1
        else:
            finding(f"{key} {e.result.type}: {e.custom_id}")
            exp += 1
    print(f"collected {n} errored={err} other={exp}")
    return True


def cmd_submit_a():
    from anthropic.types.messages.batch_create_params import Request
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    p = load_progress()
    assert p["spend_approval"]["approved_by"] == "Luis" and p["phase"] == 1
    have = {r["custom_id"] for r in read_jsonl(STATE / "extractions.jsonl")}
    reqs = []
    sysm = ex_system()
    for r in all_train_records():
        c = cid(r["ticker"], r["date"])
        if c in have:
            continue
        reqs.append(Request(custom_id=c, params=MessageCreateParamsNonStreaming(
            model=MODEL, max_tokens=EXTRACT_MAX_TOKENS, system=sysm,
            messages=[{"role": "user", "content": ex_user(r)}])))
    print(f"Pass A requests: {len(reqs)}")
    if len(reqs) > 1300:
        raise SystemExit("cap")
    est = p.get("passA_cost_estimate_usd")
    if est is None or est > 45:
        raise SystemExit(f"projected Pass A cost {est} missing or over $45 -- stop and report")
    submit_batch(reqs, "batch_id_pass_a")


def cmd_poll_a():
    poll_batch("batch_id_pass_a", "extractions.jsonl", "passA")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"check0f": cmd_check0f, "sample": cmd_sample, "extract-sync": cmd_extract_sync,
          "fidelity": cmd_fidelity, "submit-a": cmd_submit_a, "poll-a": cmd_poll_a}.get(cmd)
    if fn:
        fn(*sys.argv[2:])
    else:
        print(__doc__)
