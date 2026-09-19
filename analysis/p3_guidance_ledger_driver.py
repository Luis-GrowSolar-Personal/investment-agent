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
    if re.search(r"\bcents?\b", t[m.end():m.end() + 8]) and not m.group(3):
        num = num / 100.0
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
                    if val is None:
                        continue
                    # a value may pair with either written bound (loss/burn ranges flip order); abs compared
                    rs_ = [plausible(val, x, y) for x, y in ((lw, hw), (hw, lw)) if x is not None]
                    r = True if True in rs_ else (None if None in rs_ else False)
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


# --------------------------------------------------------------------------- ledger (Step 1c, $0)
METRICS = ["revenue", "gross_margin_pct", "operating_margin_pct", "operating_income", "eps", "free_cash_flow",
           "capex", "backlog", "unit_shipments", "customer_count", "cash_balance", "other"]
LOWER_IS_BETTER = {"capex"}
SYNONYMS = {
    "revenue": ["revenue", "revenues", "net sales", "sales", "top line", "top-line"],
    "gross_margin_pct": ["gross margin", "gross profit margin"],
    "operating_margin_pct": ["operating margin", "operating profit margin", "ebit margin"],
    "operating_income": ["operating income", "operating profit", "ebit"],
    "eps": ["eps", "earnings per share", "per diluted share", "per share"],
    "free_cash_flow": ["free cash flow", "fcf"],
    "capex": ["capex", "capital expenditure", "capital expenditures", "capital spending"],
    "backlog": ["backlog", "remaining performance obligation", "rpo"],
    "unit_shipments": ["shipments", "units shipped", "deliveries", "megawatts shipped"],
    "customer_count": ["customers", "customer count", "subscribers", "members"],
    "cash_balance": ["cash balance", "cash and cash equivalents", "cash and equivalents", "cash position"],
}
PER_LABEL = re.compile(r"^(?:Q([1-4])\s*)?FY\s*(\d{4})$|^Q([1-4])\s*(\d{4})$", re.I)


def period_key(label):
    """-> ('Q', year, q) | ('FY', year, None) | None"""
    if not label:
        return None
    t = str(label).strip().upper().replace(",", "")
    m = re.match(r"^Q([1-4])\s*FY\s*(\d{4})$", t) or re.match(r"^Q([1-4])\s*(\d{4})$", t)
    if m:
        return ("Q", int(m.group(2)), int(m.group(1)))
    m = re.match(r"^(?:FY|F)\s*(\d{4})$", t) or re.match(r"^(\d{4})\s*FY$", t)
    if m:
        return ("FY", int(m.group(1)), None)
    return None


def qidx(y, q):
    return y * 4 + q


def load_extraction_kept():
    """{custom_id: kept_extraction} from extractions.jsonl, after the fidelity filter."""
    out = {}
    stats = {"parsed": 0, "unparseable": []}
    for r in read_jsonl(STATE / "extractions.jsonl"):
        ex = parse_json_obj(r["content"])
        if ex is None:
            stats["unparseable"].append(r["custom_id"])
            continue
        tp = TRANSCRIPTS / r["ticker"] / f"{r['date']}.json"
        text = json.loads(tp.read_text())["text"]
        kept, st, drops = fidelity_filter(ex, text)
        out[r["custom_id"]] = {"kept": kept, "stats": st, "n_drops": len(drops), "stop_reason": r.get("stop_reason")}
        stats["parsed"] += 1
    return out, stats


def mid(g):
    lo, hi = g.get("low"), g.get("high")
    if lo is None:
        return hi
    if hi is None:
        return lo
    return (lo + hi) / 2


def basis_conflict(a, b):
    a, b = (a or "unspecified"), (b or "unspecified")
    return "unspecified" not in (a, b) and a.lower() != b.lower()


def mentioned_with_number(metric, text_norm):
    for syn in SYNONYMS.get(metric, []):
        for m in re.finditer(r"\b" + re.escape(syn) + r"\b", text_norm):
            window = text_norm[m.end(): m.end() + 100] + " " + text_norm[max(0, m.start() - 60): m.start()]
            if re.search(r"\d", window):
                return True
    return False


def grade_one(g, actual, metric):
    """g: guided entry; actual: number in the same framing. Returns dict grade fields."""
    lo, hi = g.get("low"), g.get("high")
    one = g.get("one_sided")
    lib = metric in LOWER_IS_BETTER
    out = {"range_width_pct": None}
    if one is None and lo is not None and hi is not None:
        out["range_width_pct"] = 0.0 if hi == lo else round((hi - lo) / abs(lo), 6) if lo else None
    if one == "floor" or (lo is not None and hi is None):
        bound, kind = lo, "floor"
    elif one == "ceiling" or (hi is not None and lo is None):
        bound, kind = hi, "ceiling"
    else:
        bound, kind = None, None
    if kind == "floor":
        if actual >= bound:
            out.update(grade="met")
        else:
            out.update(grade="missed", miss_pct=round((bound - actual) / abs(bound), 6) if bound else None)
        return out
    if kind == "ceiling":
        if actual <= bound:
            out.update(grade="met")
        else:
            out.update(grade="missed", miss_pct=round((actual - bound) / abs(bound), 6) if bound else None)
        return out
    if lo <= actual <= hi:
        out.update(grade="met")
    elif actual < lo:
        if lib:
            out.update(grade="beat", beat_pct=round((lo - actual) / abs(lo), 6) if lo else None)
        else:
            out.update(grade="missed", miss_pct=round((lo - actual) / abs(lo), 6) if lo else None)
    else:
        if lib:
            out.update(grade="missed", miss_pct=round((actual - hi) / abs(hi), 6) if hi else None)
        else:
            out.update(grade="beat", beat_pct=round((actual - hi) / abs(hi), 6) if hi else None)
    return out


def build_company_ledgers(w, rows, ext, texts_norm):
    """rows sorted by date; ext: custom_id -> kept. Returns list of ledger dicts (one per call with predecessor)
    plus the first-call empty ledger."""
    out = []
    # promise store: (metric, framing, period_key) -> list of (call_idx_in_rows, guided_entry)
    for i, r in enumerate(rows):
        c = cid(w, r["date"])
        tgt_key = ("Q", r["year"], r["quarter"])
        rec = {"ticker": w, "call_date": r["date"], "custom_id": c, "fiscal": [r["year"], r["quarter"]],
               "has_predecessor": i > 0, "gap": False, "rows": [], "pending_fy": [], "intents": [],
               "retractions": [], "counts": {}, "extraction_present": c in ext}
        if i == 0:
            out.append(rec)
            continue
        prev = rows[i - 1]
        gap = qidx(r["year"], r["quarter"]) - qidx(prev["year"], prev["quarter"])
        rec["gap"] = gap != 1
        rec["gap_quarters"] = gap
        tgt = ext.get(c)
        if tgt is None:
            rec["extraction_missing"] = True
            out.append(rec)
            continue
        reported = tgt["kept"]["reported"]
        retr = tgt["kept"]["retractions"]
        # collect promises from calls before this one whose period covers this call
        # (quarterly for this quarter; FY for this fiscal year -> pending unless this is the Q4 call)
        promises = {}
        for j in range(i):
            cj = ext.get(cid(w, rows[j]["date"]))
            if not cj:
                continue
            if rec["gap"] and j < i - 1:
                # gap ledgers carry only guidance whose period still covers N+1; that is the same test below
                pass
            for g in cj["kept"]["guided"]:
                pk = period_key(g.get("fiscal_period"))
                if pk is None:
                    continue
                m = g.get("metric") or "other"
                key = (m, g.get("framing"), pk)
                promises.setdefault(key, []).append((j, g))
        fy_year = r["year"]
        is_fy_end = r["quarter"] == 4
        for (m, framing, pk), lst in promises.items():
            lst.sort(key=lambda t: t[0])
            orig, latest = lst[0][1], lst[-1][1]
            if pk[0] == "Q":
                if (pk[1], pk[2]) != (r["year"], r["quarter"]):
                    continue
            else:
                if pk[1] != fy_year:
                    continue
                if not is_fy_end:
                    down = (m not in LOWER_IS_BETTER and mid(latest) is not None and mid(orig) is not None
                            and mid(latest) < mid(orig))
                    rec["pending_fy"].append({"metric": m, "framing": framing, "original": {k: orig.get(k) for k in ("low", "high", "low_as_written", "high_as_written")},
                                              "latest_revision": {k: latest.get(k) for k in ("low", "high", "low_as_written", "high_as_written")},
                                              "revised_down": bool(down), "n_revisions": len(lst)})
                    continue
            # find matching reported
            want_period = pk
            cands = []
            for e in reported:
                if (e.get("metric") or "other") != m:
                    continue
                epk = period_key(e.get("fiscal_period"))
                if epk is not None and epk != want_period:
                    continue
                cands.append(e)
            row = {"metric": m, "framing": framing, "period": list(pk), "basis": orig.get("basis"),
                   "original": {k: orig.get(k) for k in ("low", "high", "low_as_written", "high_as_written", "one_sided")},
                   "latest_revision": {k: latest.get(k) for k in ("low", "high", "low_as_written", "high_as_written", "one_sided")},
                   "n_revisions": len(lst), "quote": orig.get("quote"), "one_sided": orig.get("one_sided")}
            same_frame = [e for e in cands if e.get("framing") == framing]
            if same_frame:
                cands_used = same_frame
                conv = False
            else:
                cands_used = []
                conv = None
            ok_basis = [e for e in cands_used if not basis_conflict(orig.get("basis"), e.get("basis"))]
            if len(cands_used) > 1:
                row["multi_candidate"] = len(cands_used)
            if ok_basis:
                act = ok_basis[0]
                row["actual"] = act.get("value")
                row["actual_as_written"] = act.get("value_as_written")
                gr_o = grade_one(orig, act["value"], m)
                gr_l = grade_one(latest, act["value"], m)
                row.update(gr_o)
                row["grade_vs_latest"] = gr_l["grade"]
                row["revised"] = (orig.get("low"), orig.get("high")) != (latest.get("low"), latest.get("high"))
            elif cands_used:
                row.update(grade="basis_mismatch", basis_conflict=[orig.get("basis"), cands_used[0].get("basis")],
                           range_width_pct=None)
            elif cands:
                # present in another numeric framing: convert only if the prior-year base is in the ledger
                row["actual_framing"] = cands[0].get("framing")
                row.update(grade="basis_mismatch", framing_mismatch=True, range_width_pct=None)
            else:
                retracted = any((x.get("metric_or_all") or "").lower() in ("all", m, m.replace("_", " "))
                                or (x.get("metric_or_all") or "").lower() in SYNONYMS.get(m, []) for x in retr)
                if retracted:
                    row.update(grade="withdrawn", range_width_pct=None)
                else:
                    present = mentioned_with_number(m, texts_norm(w, r["date"]))
                    row["searched_transcript"] = True
                    if present:
                        row.update(grade="ungradable_present", range_width_pct=None)  # present but not extracted
                    else:
                        row.update(grade="unreported", range_width_pct=None)
            rec["rows"].append(row)
        # stated intents from previous call due by this one
        pc = ext.get(cid(w, prev["date"]))
        if pc:
            tn = texts_norm(w, r["date"])
            for it in pc["kept"].get("stated_intents", []):
                pk = period_key(it.get("by_fiscal_period"))
                if pk and pk[0] == "Q" and (pk[1], pk[2]) == (r["year"], r["quarter"]):
                    toks = [t for t in re.findall(r"[a-z]{5,}", norm(it.get("intent", "")))][:6]
                    hit = sum(1 for t in toks if t in tn)
                    rec["intents"].append({"intent": it.get("intent"), "mentioned_now": bool(toks and hit / len(toks) >= 0.5)})
        rec["retractions"] = [x.get("metric_or_all") for x in retr]
        # grades tallies
        cnt = {}
        for x in rec["rows"]:
            cnt[x["grade"]] = cnt.get(x["grade"], 0) + 1
        rec["counts"] = cnt
        rec["revised_down_count"] = sum(1 for x in rec["pending_fy"] if x["revised_down"])
        out.append(rec)
    return out


_TXT_CACHE = {}


def texts_norm(w, date):
    k = (w, date)
    if k not in _TXT_CACHE:
        _TXT_CACHE[k] = norm(json.loads((TRANSCRIPTS / w / f"{date}.json").read_text())["text"])
    return _TXT_CACHE[k]


GRADES6 = ["met", "missed", "beat", "unreported", "withdrawn", "basis_mismatch"]


def cmd_build_ledger():
    ext, st = load_extraction_kept()
    calls = train_calls()
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    flat = []
    n_pred = n_nonempty = n_gap = n_missing_ext = 0
    for w, rows in calls.items():
        ledgers = build_company_ledgers(w, rows, ext, texts_norm)
        for L in ledgers:
            d = LEDGER_DIR / w
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{L['call_date']}.json").write_text(json.dumps(L, indent=1))
            if L["has_predecessor"]:
                n_pred += 1
                n_gap += 1 if L["gap"] else 0
                n_missing_ext += 1 if L.get("extraction_missing") else 0
                if any(x["grade"] in GRADES6 for x in L["rows"]):
                    n_nonempty += 1
            for x in L["rows"]:
                flat.append({"ticker": w, "call_date": L["call_date"], "year": L["fiscal"][0], "quarter": L["fiscal"][1],
                             "metric": x["metric"], "framing": x["framing"], "period": "/".join(map(str, x["period"])),
                             "grade": x["grade"], "miss_pct": x.get("miss_pct"), "beat_pct": x.get("beat_pct"),
                             "range_width_pct": x.get("range_width_pct"), "gap_call": L["gap"],
                             "framing_mismatch": x.get("framing_mismatch", False),
                             "revised": x.get("revised", False)})
    import csv
    with (C2 / "ledger_summary.csv").open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(flat[0].keys()) if flat else ["ticker"])
        wr.writeheader()
        wr.writerows(flat)
    print(f"ledger files written; predecessor-bearing={n_pred} non-empty={n_nonempty} gap={n_gap} "
          f"extraction_missing={n_missing_ext} promises={len(flat)} unparseable_json={len(st['unparseable'])}")


# --------------------------------------------------------------------------- v6 cache + outcomes
def v6_directions():
    from analyst_direct_scorer import parse_structured, direction_from_score
    out = {}
    for f in sorted(glob.glob(str(V6_EVAL_DIR / "*.txt"))):
        stem = Path(f).stem
        tk, dt = stem.rsplit("_", 1)
        sc = parse_structured(Path(f).read_text())
        out[(tk, dt)] = {"dir": direction_from_score(sc), "rec": sc.get("recommendation"), "health": sc.get("thesisHealth")}
    return out


def outcomes():
    import csv
    out = {}
    with JOINED.open() as f:
        for r in csv.DictReader(f):
            if r["split"] != "train":
                continue
            out[(r["ticker"], r["call_date"])] = {"gt": r["ground_truth"], "rel": float(r["benchmark_rel_return_pct"]),
                                                    "pred": r["predicted"]}
    return out


BAD = {"missed", "unreported", "withdrawn"}


def flags(L):
    g = [x["grade"] for x in L["rows"]]
    graded = [x for x in g if x in GRADES6]
    return {"graded": len(graded), "bad": any(x in BAD for x in g),
            "clean": bool(graded) and not any(x in BAD for x in g) and any(x in ("met", "beat") for x in g),
            "clean_beat": ("beat" in g) and not any(x in BAD for x in g)}


def load_ledgers():
    out = {}
    for f in sorted(glob.glob(str(LEDGER_DIR / "*" / "*.json"))):
        L = json.loads(Path(f).read_text())
        out[(L["ticker"], L["call_date"])] = L
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** 0.5) / den
    return (100 * (c - h), 100 * (c + h))


def block_boot_share(rows, key_fn, ticker_fn, B=2000, seed=11):
    """Ticker-block bootstrap 95% range for the share of rows with key_fn true."""
    rng = random.Random(seed)
    by = {}
    for r in rows:
        by.setdefault(ticker_fn(r), []).append(1 if key_fn(r) else 0)
    tks = list(by)
    if not tks:
        return (float("nan"), float("nan"))
    vals = []
    for _ in range(B):
        k = n = 0
        for t in (rng.choice(tks) for _ in tks):
            k += sum(by[t]); n += len(by[t])
        if n:
            vals.append(100 * k / n)
    vals.sort()
    return (vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1])


def cmd_diag():
    """5c reports, 5d, 5e -- all $0."""
    L = load_ledgers()
    v6 = v6_directions()
    oc = outcomes()
    pred_bearing = {k: v for k, v in L.items() if v["has_predecessor"]}
    fl = {k: flags(v) for k, v in pred_bearing.items()}
    n = len(pred_bearing)
    cov = sum(1 for k in pred_bearing if fl[k]["graded"] > 0)
    print(f"predecessor-bearing calls: {n}; with >=1 graded promise (coverage): {cov} ({100*cov/n:.1f}%)")
    print("gap-marked:", sum(1 for v in pred_bearing.values() if v["gap"]),
          "| extraction missing:", sum(1 for v in pred_bearing.values() if v.get("extraction_missing")))
    # grade tallies overall and by year
    import collections
    tot = collections.Counter(); by_year = collections.defaultdict(collections.Counter)
    nprom = []
    for k, v in pred_bearing.items():
        nprom.append(sum(1 for x in v["rows"] if x["grade"] in GRADES6))
        for x in v["rows"]:
            tot[x["grade"]] += 1
            by_year[k[1][:4]][x["grade"]] += 1
    tp = sum(tot.values())
    print("grade shares (all promises):", {g: f"{tot[g]} ({100*tot[g]/tp:.1f}%)" for g in tot})
    import statistics
    nz = [x for x in nprom if x]
    if nz:
        print(f"promises per non-empty call: median {statistics.median(nz)}, range {min(nz)}-{max(nz)}")
    print("grade-by-year:")
    for y in sorted(by_year):
        print(" ", y, dict(by_year[y]))
    fm = sum(1 for v in pred_bearing.values() for x in v["rows"] if x.get("framing_mismatch"))
    print("framing mismatches (graded basis_mismatch, framing_mismatch=True):", fm, "| framing conversions: 0 (not implemented; see wrap-up)")
    # 5d
    def split_stats(name, member, target_gt, base, year=None):
        rows = []
        for k in pred_bearing:
            if k not in oc or not member(fl[k]):
                continue
            if year is not None and (k[1][:4] == "2020") != year:
                continue
            rows.append(k)
        kk = sum(1 for k in rows if oc[k]["gt"] == target_gt)
        lo, hi = wilson(kk, len(rows))
        bl, bh = block_boot_share([(k,) for k in rows], lambda r: oc[r[0]]["gt"] == target_gt, lambda r: r[0][0])
        print(f"  {name}: n={len(rows)} {target_gt}-outcome share {100*kk/max(len(rows),1):.1f}% "
              f"(Wilson {lo:.1f}-{hi:.1f}; ticker-block {bl:.1f}-{bh:.1f}) vs base {base}%")
    print("5d-i (miss/unreported/withdrawn -> underperformed S&P by >5pts, base 46.6%):")
    split_stats("all years", lambda f: f["bad"], "bearish", 46.6)
    split_stats("2020 only", lambda f: f["bad"], "bearish", 46.6, year=True)
    split_stats("excl 2020", lambda f: f["bad"], "bearish", 46.6, year=False)
    print("5d-ii (clean beats, no miss -> outperformed S&P by >5pts, base 32.8%):")
    split_stats("all years", lambda f: f["clean_beat"], "bullish", 32.8)
    split_stats("2020 only", lambda f: f["clean_beat"], "bullish", 32.8, year=True)
    split_stats("excl 2020", lambda f: f["clean_beat"], "bullish", 32.8, year=False)
    # 5e populations
    def vd(k):
        return (v6.get(k) or {}).get("dir")
    n_elig = [k for k in pred_bearing if fl[k]["bad"] and vd(k) != "bearish"]
    n_bull = [k for k in pred_bearing if fl[k]["clean_beat"] and vd(k) != "bullish"]
    n_reas = [k for k in pred_bearing if fl[k]["clean"] and vd(k) == "bearish"]
    n_nomiss = [k for k in pred_bearing if fl[k]["graded"] > 0 and not fl[k]["bad"] and vd(k) != "bearish"]
    print(f"5e: N_eligible={len(n_elig)} (gate >=150) | N_eligible_bull={len(n_bull)} | N_reassure={len(n_reas)} | no-miss ledger-bearing v6-not-bearish={len(n_nomiss)}")
    res = {"n": n, "coverage": cov, "N_eligible": len(n_elig), "N_eligible_bull": len(n_bull), "N_reassure": len(n_reas),
           "n_nomiss_pool": len(n_nomiss)}
    (STATE / "diag_5cde.json").write_text(json.dumps(res, indent=1))
    if len(n_elig) < 150:
        print("*** GATE: N_eligible < 150 -- STOP before pre-flight and report ***")
    return res


# --------------------------------------------------------------------------- ledger text for the analyst
def fmt_guide(g):
    lo, hi = g.get("low_as_written"), g.get("high_as_written")
    one = g.get("one_sided")
    if one == "floor":
        return f"at least {lo}"
    if one == "ceiling":
        return f"up to {hi}"
    if lo and hi and lo != hi:
        return f"{lo} to {hi}"
    return lo or hi or "n/a"


def pct(x):
    return "" if x is None else f"{100*x:.1f}%"


def ledger_text(L):
    if not L["has_predecessor"]:
        return "---PRIOR-CALL LEDGER---\nNo prior call on record.\n---END LEDGER---"
    lines = ["---PRIOR-CALL LEDGER---",
             "metric | original guide | latest revision | actual | grade | miss_pct | range_width_pct | quote"]
    if L.get("gap"):
        lines.insert(1, f"(note: the prior call on record is {L.get('gap_quarters')} quarters earlier; only guidance whose period covers this quarter is shown)")
    shown = 0
    for x in L["rows"]:
        if x["grade"] not in GRADES6:
            continue
        shown += 1
        mp = x.get("miss_pct") if x["grade"] == "missed" else x.get("beat_pct") if x["grade"] == "beat" else None
        rw = x.get("range_width_pct")
        rwt = "one-sided" if x.get("one_sided") else ("" if rw is None else f"{100*rw:.1f}%")
        act = x.get("actual_as_written") or ("" if x["grade"] != "basis_mismatch" else "different basis/framing")
        q = (x.get("quote") or "").replace("|", "/")[:140]
        lines.append(f"{x['metric']} ({x['framing']}, {x['basis'] or 'basis unspecified'}, "
                     f"{'Q'+str(x['period'][2])+' ' if x['period'][0]=='Q' else ''}FY{x['period'][1]}) | {fmt_guide(x['original'])} | "
                     f"{fmt_guide(x['latest_revision']) if x.get('revised') else 'unchanged'} | {act} | {x['grade']} | "
                     f"{pct(mp) if x['grade'] in ('missed','beat') else ''} | {rwt} | {q}")
    if shown == 0:
        lines.append("(no gradable promises from the prior call)")
    lines.append("(derived lines)")
    lines.append("none computed")
    lines.append("(full-year promises, pending)")
    if L["pending_fy"]:
        for x in L["pending_fy"]:
            lines.append(f"{x['metric']} FY: original {fmt_guide(x['original'])}; latest {fmt_guide(x['latest_revision'])}; "
                         f"revised down: {'yes' if x['revised_down'] else 'no'}")
    else:
        lines.append("none")
    lines.append("(stated intents due this quarter)")
    if L["intents"]:
        for it in L["intents"]:
            lines.append(f"{it['intent']} (mentioned in this call: {'yes' if it['mentioned_now'] else 'no'})")
    else:
        lines.append("none")
    lines.append("(retractions this quarter)")
    lines.append("; ".join(L["retractions"]) if L["retractions"] else "none")
    lines.append("---END LEDGER---")
    return "\n".join(lines)


def cand_user(w, date, L):
    text = json.loads((TRANSCRIPTS / w / f"{date}.json").read_text())["text"]
    return ledger_text(L) + "\n\n" + text


# --------------------------------------------------------------------------- pre-flight
ARM_PREFIX = {"elig": "E1", "nomiss": "N1", "noise": "A21a", "instr": "B21b"}


def stratum_alloc(n_total, counts):
    tot = sum(counts.values())
    raw = {k: n_total * v / tot for k, v in counts.items()}
    base = {k: int(v) for k, v in raw.items()}
    rem = n_total - sum(base.values())
    for k in sorted(raw, key=lambda k: raw[k] - base[k], reverse=True)[:rem]:
        base[k] += 1
    return base


def cmd_preflight_select():
    L = load_ledgers()
    v6 = v6_directions()
    smap = stratum_map()
    rng = random.Random(11)
    pb = {k: v for k, v in L.items() if v["has_predecessor"]}
    fl = {k: flags(v) for k, v in pb.items()}
    vd = lambda k: (v6.get(k) or {}).get("dir")
    elig = sorted(k for k in pb if fl[k]["bad"] and vd(k) != "bearish")
    nomiss = sorted(k for k in pb if fl[k]["graded"] > 0 and not fl[k]["bad"] and vd(k) != "bearish")
    a = rng.sample(elig, min(125, len(elig)))
    b = rng.sample(nomiss, min(75, len(nomiss)))
    allk = sorted(v6.keys())
    allk = [k for k in allk if k[0] in smap]
    by_s = {}
    for k in allk:
        by_s.setdefault(smap[k[0]], []).append(k)
    alloc = stratum_alloc(120, {s: len(v) for s, v in by_s.items()})
    c = []
    for st, n in sorted(alloc.items()):
        c += rng.sample(by_s[st], n)
    d = sorted(k for k, v in L.items() if not v["has_predecessor"])
    sel = {"elig": a, "nomiss": b, "noise": c, "instr": d}
    out = {arm: [list(k) for k in ks] for arm, ks in sel.items()}
    out["_alloc_21a"] = alloc
    out["_seed"] = 11
    (STATE / "preflight_selection.json").write_text(json.dumps(out, indent=1))
    print({arm: len(ks) for arm, ks in sel.items()}, alloc)


def preflight_requests():
    from anthropic.types.messages.batch_create_params import Request
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from analysis.version_guard import assert_prompt_hash, sha256_text as vsha
    sel = json.loads((STATE / "preflight_selection.json").read_text())
    L = load_ledgers()
    cand = CAND_PROMPT.read_text()
    v6t = V6_PROMPT.read_text()
    reg = json.loads((REPO / "docs/architecture/VERSION_REGISTRY.json").read_text())
    regsha = next(c["sha256"] for c in reg["artifacts"]["evaluation_prompt"]["candidates"] if c["version"] == "v6+P3a")
    assert vsha(cand) == regsha, "candidate hash != registry"
    g1 = assert_prompt_hash(cand, candidate="v6+P3a")          # candidate arms
    g2 = assert_prompt_hash(v6t)                                # 21a arm: promoted v6
    assert g2["candidate_used"] is None
    sys_c = [{"type": "text", "text": cand, "cache_control": {"type": "ephemeral"}}]
    sys_6 = [{"type": "text", "text": v6t, "cache_control": {"type": "ephemeral"}}]
    reqs = []
    for arm in ("elig", "nomiss", "noise", "instr"):
        for w, dt in sel[arm]:
            c = f"{ARM_PREFIX[arm]}__{w}_{dt}"
            assert re.match(r"^[a-zA-Z0-9_-]{1,64}$", c), c
            if arm == "noise":
                user = json.loads((TRANSCRIPTS / w / f"{dt}.json").read_text())["text"]
                system = sys_6
            else:
                user = cand_user(w, dt, L[(w, dt)])
                system = sys_c
            reqs.append(Request(custom_id=c, params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=SCORE_MAX_TOKENS, system=system,
                messages=[{"role": "user", "content": user}])))
    return reqs, {"candidate_guard": g1, "v6_guard": g2}


def cmd_preflight_submit():
    p = load_progress()
    assert p["spend_approval"]["approved_by"] == "Luis" and p["phase"] == 1
    reqs, guards = preflight_requests()
    est = len(reqs) * 0.045
    print(f"pre-flight requests {len(reqs)}; projected cost ~${est:.2f} (cap $20); guards {json.dumps(guards)}")
    if est > 20:
        raise SystemExit("projected pre-flight over $20 -- stop and report")
    p["preflight_guards"] = guards
    save_progress(p)
    submit_batch(reqs, "batch_id_preflight")


def cmd_preflight_poll():
    poll_batch("batch_id_preflight", "preflight_scores.jsonl", "preflight")


def cmd_preflight_report():
    from analyst_direct_scorer import parse_structured, direction_from_score
    recs = read_jsonl(STATE / "preflight_scores.jsonl")
    v6 = v6_directions()
    oc = outcomes()
    L = load_ledgers()
    smap = stratum_map()
    arms = {}
    stops = {"max_tokens": 0}
    six = ["ledgerLoadBearingMetric", "ledgerLoadBearingOutcome", "ledgerMissCount", "ledgerMaxMissPct",
           "ledgerRevisedDownCount", "ledgerWithdrawnCount"]
    populated = {k: 0 for k in six}
    n_cand = 0
    cost = 0.0
    for r in recs:
        cost += r["cost_usd"]
        pre, rest = r["custom_id"].split("__", 1)
        w, dt = rest.rsplit("_", 1)
        arm = {v: k for k, v in ARM_PREFIX.items()}[pre]
        sc = parse_structured(r["content"])
        nd = direction_from_score(sc)
        if r.get("stop_reason") == "max_tokens":
            stops["max_tokens"] += 1
        if arm != "noise":
            n_cand += 1
            for k in six:
                if k in sc:
                    populated[k] += 1
        od = (v6.get((w, dt)) or {}).get("dir")
        arms.setdefault(arm, []).append({"k": (w, dt), "old": od, "new": nd, "stratum": smap.get(w)})
    print(f"pre-flight results: {len(recs)}; cost ${cost:.2f}; stop_reason=max_tokens: {stops['max_tokens']}")
    print(f"six new fields present in candidate outputs ({n_cand}): {populated}")
    res = {"cost": cost, "arms": {}}
    for arm, rows in arms.items():
        n = len(rows)
        flips = [x for x in rows if x["old"] and x["new"] and x["old"] != x["new"]]
        nonb = [x for x in rows if x["old"] != "bearish"]
        bflip = [x for x in nonb if x["new"] == "bearish"]
        nonbull = [x for x in rows if x["old"] != "bullish"]
        bullflip = [x for x in nonbull if x["new"] == "bullish"]
        reas = [x for x in rows if x["old"] == "bearish" and x["new"] in ("neutral", "bullish")]
        lo, hi = wilson(len(flips), n)
        blo, bhi = wilson(len(bflip), len(nonb))
        ulo, uhi = wilson(len(bullflip), len(nonbull))
        print(f"[{arm}] n={n} any-flip {len(flips)} ({100*len(flips)/n:.1f}%, {lo:.1f}-{hi:.1f}) | "
              f"bearish-direction flips {len(bflip)}/{len(nonb)} ({100*len(bflip)/max(len(nonb),1):.1f}%, {blo:.1f}-{bhi:.1f}) | "
              f"bullish-direction {len(bullflip)}/{len(nonbull)} ({100*len(bullflip)/max(len(nonbull),1):.1f}%, {ulo:.1f}-{uhi:.1f}) | "
              f"reassurance flips {len(reas)}")
        res["arms"][arm] = {"n": n, "flips": len(flips), "bear_flips": len(bflip), "bear_denom": len(nonb),
                            "bull_flips": len(bullflip), "bull_denom": len(nonbull), "reassure": len(reas)}
        if arm == "noise":
            by = {}
            for x in rows:
                by.setdefault(x["stratum"], []).append(x)
            for st, xs in sorted(by.items(), key=lambda t: str(t[0])):
                f = sum(1 for x in xs if x["old"] and x["new"] and x["old"] != x["new"])
                a, b = wilson(f, len(xs))
                print(f"     21a {st}: {f}/{len(xs)} ({100*f/len(xs):.1f}%, {a:.1f}-{b:.1f})")
    # stop rule + projection
    d = json.loads((STATE / "diag_5cde.json").read_text())
    e, nm, nz, ins = (res["arms"].get(k) for k in ("elig", "nomiss", "noise", "instr"))
    if e and nm:
        er = e["bear_flips"] / max(e["bear_denom"], 1)
        nr = nm["bear_flips"] / max(nm["bear_denom"], 1)
        print(f"MECHANISM-FAILURE TEST: no-miss bearish-direction flip rate {100*nr:.1f}% vs eligible {100*er:.1f}% -> "
              f"{'STOP (no-miss >= eligible)' if nr >= er else 'pass'}")
    if e and nz:
        noise_rate = nz["flips"] / nz["n"]
        er_any = e["flips"] / e["n"]
        net_rate = er_any - noise_rate
        print(f"eligible any-flip rate {100*er_any:.1f}% minus 21a noise {100*noise_rate:.1f}% = net {100*net_rate:.1f}%; "
              f"projected net flips on N_eligible={d['N_eligible']}: {net_rate*d['N_eligible']:.0f} "
              f"(raw {er_any*d['N_eligible']:.0f}); floor ~100")
    if ins and nz:
        print(f"21b instruction-effect flip rate {100*ins['flips']/ins['n']:.1f}% minus 21a {100*nz['flips']/nz['n']:.1f}% "
              f"= {100*(ins['flips']/ins['n']-nz['flips']/nz['n']):.1f} points (2020-clustering caveat applies)")
    (STATE / "preflight_report.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"check0f": cmd_check0f, "sample": cmd_sample, "extract-sync": cmd_extract_sync,
          "fidelity": cmd_fidelity, "submit-a": cmd_submit_a, "poll-a": cmd_poll_a,
          "build-ledger": cmd_build_ledger, "diag": cmd_diag,
          "preflight-select": cmd_preflight_select, "preflight-submit": cmd_preflight_submit,
          "preflight-poll": cmd_preflight_poll, "preflight-report": cmd_preflight_report}.get(cmd)
    if fn:
        fn(*sys.argv[2:])
    else:
        print(__doc__)
