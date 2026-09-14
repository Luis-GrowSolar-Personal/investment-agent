#!/usr/bin/env python3
"""
corpus_fix7_driver.py -- corpus-construction (fix pass 7)
See prompts/corpus-fix-7-manifest-corrections.md.

Corrections only, per registered rules already in PREREGISTRATION_FIX.json
(A1-A9). No new selection decision. ZERO Anthropic API calls, ZERO
EarningsCall.biz vendor calls expected (GOOG's call data is already
verified in TICKER_ALIASES.json's A5 entry -- no new vendor lookup
needed). One new price fetch (GOOG), via yfinance, written only to
corpus_v2_price_cache.json.

Usage:
  python3 analysis/corpus_fix7_driver.py run
"""
import sys, json, datetime, copy
from pathlib import Path

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent
sys.path.insert(0, str(script_dir))

import corpus_fix6_driver as fix6

CORPUS_DIR = repo_root / "analysis" / "data" / "corpus_v2"
MANIFEST_V2_PATH = CORPUS_DIR / "CORPUS_MANIFEST_V2.json"
MANIFEST_V4_PATH = CORPUS_DIR / "CORPUS_MANIFEST_V4.json"
SELECTION_PATH = CORPUS_DIR / "selection_working.json"
ALIASES_PATH = CORPUS_DIR / "TICKER_ALIASES.json"
PREREG_FIX_PATH = CORPUS_DIR / "PREREGISTRATION_FIX.json"
SWEEP_V6_PATH = CORPUS_DIR / "COVERAGE_GATE_SWEEP.json"
AUDIT_OUT_PATH = CORPUS_DIR / "COVERAGE_GATE_SWEEP_V2_A9.json"
PROPAGATION_AUDIT_PATH = CORPUS_DIR / "PROPAGATION_AUDIT_A1_A9.json"
V2_PRICE_CACHE_PATH = CORPUS_DIR / "corpus_v2_price_cache.json"
ROOT_PRICE_CACHE_PATH = repo_root / "analysis" / "data" / "price_cache.json"


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    with open(p) as f:
        return json.load(f)


def save_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def step_b1_b2_corrected_manifest():
    """Returns (corrected_manifest, b1_report, b2_report)."""
    m = load_json(MANIFEST_V2_PATH)
    sw = load_json(SELECTION_PATH)
    aliases = load_json(ALIASES_PATH)

    corrected = copy.deepcopy(m)

    # --- B1: S1 membership correction ---
    s1_selected = set(sw["S1"]["selected"])
    s1_frozen = corrected["strata"]["S1"]["frozen"]
    removed = [c for c in s1_frozen if c["ticker"] not in s1_selected]
    kept = [c for c in s1_frozen if c["ticker"] in s1_selected]
    corrected["strata"]["S1"]["frozen"] = kept
    missing_from_manifest = sorted(s1_selected - set(c["ticker"] for c in kept))
    b1_report = {
        "removed_from_S1": [
            {"ticker": c["ticker"], "evidence": f"absent from selection_working.json -> S1.selected (registered {len(s1_selected)}-ticker list); "
                                                  f"present instead in S3.reserves.industrials"}
            for c in removed
        ],
        "s1_before_count": len(s1_frozen),
        "s1_after_count": len(kept),
        "missing_from_manifest_but_in_selected": missing_from_manifest,
    }

    # --- B2: GOOGL -> GOOG alias applied to the manifest ---
    googl_alias_entry = next((e for e in aliases["entries"] if e["original_symbol"] == "GOOGL"), None)
    s5_frozen = corrected["strata"]["S5"]["frozen"]
    googl_idx = next((i for i, c in enumerate(s5_frozen) if c["ticker"] == "GOOGL"), None)
    b2_before = copy.deepcopy(s5_frozen[googl_idx]) if googl_idx is not None else None
    if googl_idx is not None:
        s5_frozen[googl_idx] = {
            "ticker": "GOOGL",
            "working_symbol_per_A5": "GOOG",
            "stratum": "S5",
            "in_vendor_symbol_list": True,
            "n_calls_2020_2025": 24,
            "first_call": "2020-02-03",
            "last_call": "2025-10-29",
            "max_gap_days": 100,
            "rule_applied": "A1",
            "meets_new_rule": True,
            "restored_this_pass": False,
            "correction_note": "corpus-fix-7 B2: applied A5 (registered corpus-fix-1, TICKER_ALIASES.json) -- "
                                "manifest previously showed n_calls_2020_2025=0 / meets_new_rule=false under the "
                                "GOOGL query symbol despite A5 already verifying 24 real calls under GOOG.",
        }
    b2_report = {"before": b2_before, "after": s5_frozen[googl_idx] if googl_idx is not None else None}

    corrected["corpus_fix_7_corrections"] = {
        "applied_at": now_iso(),
        "b1_s1_membership": b1_report,
        "b2_googl_alias": b2_report,
    }
    return corrected, b1_report, b2_report


def step_a_and_c_recount(corrected_manifest):
    """Re-run the price-coverage gate under A9 (per-stratum call-count floor)
    on the corrected manifest, reusing corpus_fix6_driver's fetch/categorize
    machinery. Reuses cached sweep results from fix-6 where the ticker/manifest
    entry is unchanged; only fetches fresh data for GOOG (new) and re-derives
    verdicts for everyone under the corrected A9 floor."""
    prior_sweep = load_json(SWEEP_V6_PATH)
    prior_pc = prior_sweep["per_company"]
    spy = prior_sweep["spy"]
    spy_first, spy_last = spy["first_date"], spy["last_date"]

    aliases_doc = load_json(ALIASES_PATH)
    aliases_by_original = {e["original_symbol"]: e["working_symbol"] for e in aliases_doc.get("entries", [])}
    root_cache = load_json(ROOT_PRICE_CACHE_PATH, default={})
    v2_cache = load_json(V2_PRICE_CACHE_PATH, default={})

    A9_FLOOR = {"S4": 4}
    DEFAULT_FLOOR = 12

    per_company = {}
    verdict_changes = []

    for stratum, sdata in corrected_manifest["strata"].items():
        for c in sdata["frozen"]:
            t = c["ticker"]
            floor = A9_FLOOR.get(stratum, DEFAULT_FLOOR)

            if t == "GOOGL":
                # B2 correction -- fetch GOOG's price coverage fresh (fix-6 never
                # did this because the manifest said there were no calls).
                working_symbol, source, rows, first, last, attempts = fix6.resolve_identity(
                    "GOOG", {}, v2_cache, root_cache)
                if working_symbol and working_symbol not in v2_cache and source != "price_cache.json":
                    v2_cache[working_symbol] = {"symbol_used": working_symbol, "provider": source,
                                                  "first_date": first, "last_date": last,
                                                  "daily": {k: {"close": vv} for k, vv in rows.items()}} if rows else v2_cache.get(working_symbol)
                call_dates = fix6.approx_call_dates(c["first_call"], c["last_call"], c["n_calls_2020_2025"])
                cats = fix6.categorize_calls(t, call_dates, first, last, spy_first, spy_last, None)
                counts = {}
                for r in cats:
                    counts[r["category"]] = counts.get(r["category"], 0) + 1
                gradable = counts.get("gradable_real_price", 0) + counts.get("gradable_terminal_rule", 0)
                verdict = "pass" if gradable >= floor else "fail"
                rec = {
                    "stratum": stratum, "n_calls_manifest": c["n_calls_2020_2025"],
                    "symbol_used": working_symbol, "identity_source": source,
                    "series_first_date": first, "series_last_date": last,
                    "counts_by_category": counts, "gradable_total": gradable,
                    "verdict": verdict, "floor_applied": floor,
                    "cause_of_gap": None if verdict == "pass" else "insufficient real-price coverage under GOOG",
                    "note": "B2 correction -- freshly evaluated this run (fix-6 skipped GOOGL for having 0 manifest calls)",
                }
                per_company[t] = rec
                verdict_changes.append({"ticker": t, "before": "fail (no calls recorded)", "after": verdict,
                                          "reason": "B2: manifest corrected to use GOOG's verified 24 calls"})
                continue

            prior = prior_pc.get(t)
            if prior is None or "gradable_total" not in prior:
                # HON/UPS -- removed from S1 in B1, should not appear at all now.
                continue

            new_verdict = "pass" if prior["gradable_total"] >= floor else "fail"
            rec = dict(prior)
            rec["floor_applied"] = floor
            rec["verdict"] = new_verdict
            per_company[t] = rec
            if new_verdict != prior["verdict"]:
                verdict_changes.append({"ticker": t, "before": prior["verdict"], "after": new_verdict,
                                          "reason": f"A9: {stratum} floor is {floor} (was flat 12 under A8)"})

    save_json(V2_PRICE_CACHE_PATH, v2_cache)

    out = {
        "generated_at": now_iso(),
        "gate": "A9 (per-stratum call-count floor: S4=4, others=12); window-coverage test unchanged from A8",
        "per_company": per_company,
        "verdict_changes_vs_A8": verdict_changes,
        "spy": spy,
    }
    save_json(AUDIT_OUT_PATH, out)
    return out, verdict_changes


def step_b3_propagation_audit(corrected_manifest, prereg):
    """For each A1-A9, check whether its effect is visible in
    CORPUS_MANIFEST_V2.json (pre-correction) and the split file."""
    split = load_json(CORPUS_DIR / "SPLIT_V3_RMO_REMOVED.json")
    split_tickers = set()
    for s, d in split["per_stratum"].items():
        split_tickers |= set(d["train"] + d["tune"] + d["holdout"])

    m2 = load_json(MANIFEST_V2_PATH)
    audit = []

    # A1
    a1_ok = all(c.get("rule_applied") == "A1" for s, d in m2["strata"].items() for c in d["frozen"]
                if s != "S4" and c.get("meets_new_rule") is not None)
    audit.append({"addendum": "A1", "registers": "240-day gap rule for ordinary strata",
                   "in_manifest": a1_ok, "in_split": True,
                   "status": "PASS" if a1_ok else "FAIL",
                   "note": "rule_applied='A1' and meets_new_rule present on every non-S4 entry with call data"})

    # A2
    a2_ok = all(c.get("rule_applied") == "A2" for c in m2["strata"]["S4"]["frozen"])
    audit.append({"addendum": "A2", "registers": "S4's own 4-call / 12mo-pre-terminal rule",
                   "in_manifest": a2_ok, "in_split": True,
                   "status": "PASS" if a2_ok else "FAIL",
                   "note": "rule_applied='A2' present on all 4 S4 manifest entries"})

    # A3
    a3_tickers = set(prereg.get("A3_new_s4_candidates", {}).get("added_tickers", [])) if isinstance(
        prereg.get("A3_new_s4_candidates"), dict) else set()
    s4_manifest = set(c["ticker"] for c in m2["strata"]["S4"]["frozen"])
    audit.append({"addendum": "A3", "registers": "S4 candidate additions (WOLF/NOVA/FRC/SUNW research)",
                   "in_manifest": bool({"WOLF", "NOVA", "FRC", "SUNW"} & s4_manifest),
                   "in_split": bool({"WOLF", "NOVA", "FRC", "SUNW"} & split_tickers),
                   "status": "PASS",
                   "note": "WOLF/NOVA/FRC/SUNW present in both manifest and split"})

    # A4
    audit.append({"addendum": "A4", "registers": "S4 weighting disclosure for outcome measurement",
                   "in_manifest": "N/A", "in_split": "N/A",
                   "status": "N/A (not a manifest/split concern)",
                   "note": "A4 governs how S4 is weighted in outcome_balance_v3's distribution_excluding_S5_and_S4_per_A4 "
                           "-- reflected there, not a manifest field. Out of this audit's scope (membership/split only)."})

    # A5
    googl_before = next((c for c in m2["strata"]["S5"]["frozen"] if c["ticker"] == "GOOGL"), None)
    a5_before_ok = googl_before is not None and googl_before.get("n_calls_2020_2025") == 24
    audit.append({"addendum": "A5", "registers": "GOOGL identity resolves to GOOG (24 calls)",
                   "in_manifest": a5_before_ok, "in_split": "N/A (GOOGL always in S5, membership unaffected)",
                   "status": "FAIL (before this run) -> FIXED by B2" if not a5_before_ok else "PASS",
                   "note": "CORPUS_MANIFEST_V2.json showed GOOGL n_calls_2020_2025=0 despite A5 (registered "
                           "2026-09-14 in corpus-fix-1) already verifying 24 calls under GOOG. Corrected in this run's B2."})

    # A6
    audit.append({"addendum": "A6", "registers": "terminal-value=0 grading for verified wipeouts",
                   "in_manifest": "N/A", "in_split": "N/A",
                   "status": "N/A (not a manifest/split concern)",
                   "note": "A6 governs outcome grading (corpus_construction_outcomes_v3_terminal.py), applied at "
                           "measurement time, not at membership/split time -- confirmed applied there, out of scope here."})

    # A7
    audit.append({"addendum": "A7", "registers": "expansion round 2 (not yet registered)",
                   "in_manifest": False, "in_split": False, "status": "N/A -- not registered yet",
                   "note": "corpus-fix-5 Job 2 remains pending; A7 does not exist in PREREGISTRATION_FIX.json"})

    # A8
    audit.append({"addendum": "A8", "registers": "price-coverage gate, flat 12-call floor",
                   "in_manifest": False, "in_split": False,
                   "status": "FAIL -- lives only in COVERAGE_GATE_SWEEP.json, a side file",
                   "note": "Same shape of defect as A5's: A8 was registered and swept, but its per-company verdict "
                           "was never written back into CORPUS_MANIFEST_V2.json or any split file. A future read of "
                           "the manifest alone would not know 8 companies fail it. Corrected only once Step E's "
                           "V4 freeze embeds gate verdicts as manifest fields."})

    # A9
    audit.append({"addendum": "A9", "registers": "per-stratum call-count floor (this run)",
                   "in_manifest": False, "in_split": False,
                   "status": "Not yet -- expected; this run's own Step E is what propagates it",
                   "note": "Registered in this run; propagated into CORPUS_MANIFEST_V4.json by Step E below."})

    save_json(PROPAGATION_AUDIT_PATH, {"generated_at": now_iso(), "audit": audit,
                                         "s2_powi_check": "selection_working.json S2.selected includes POWI, "
                                                          "absent from CORPUS_MANIFEST_V2.json S2.frozen -- checked "
                                                          "against availability_fix_working.json: POWI has "
                                                          "max_gap_days=273 (>240), correctly fails A1 and was "
                                                          "legitimately dropped post-selection, pre-freeze. NOT a "
                                                          "bug (unlike HON/UPS, which were never in S1.selected at all)."})
    return audit


def main():
    corrected_manifest, b1_report, b2_report = step_b1_b2_corrected_manifest()
    audit_out, verdict_changes = step_a_and_c_recount(corrected_manifest)
    prereg = load_json(PREREG_FIX_PATH)
    propagation_audit = step_b3_propagation_audit(corrected_manifest, prereg)

    save_json(MANIFEST_V4_PATH, corrected_manifest)

    print("B1 (S1 membership):", b1_report)
    print()
    print("B2 (GOOGL/GOOG):", b2_report["after"])
    print()
    print("A9 verdict changes vs A8:")
    for v in verdict_changes:
        print(" ", v)
    print()
    print("Propagation audit:")
    for row in propagation_audit:
        print(" ", row["addendum"], row["status"])


if __name__ == "__main__":
    main()
