#!/usr/bin/env python3
"""
corpus_construction_split_v2.py -- Fix-pass Step E of corpus-construction.

Three-way company-level split (train/tune/holdout) of CORPUS_MANIFEST_V2.json's
78 companies, stratified so every stratum (S1-S5, including S4) carries a
proportional share. Method identical to the first pass's own registered
Step 5 method (analysis/data/corpus_v2/PREREGISTRATION.json ->
outcome_holdout_split): "Python random.shuffle per stratum with the fixed
seed, then round-robin assignment train/tune/holdout to preserve
proportionality within rounding." Seed 20201231 (same fixed seed used
throughout this run's other randomization steps).

Split is by COMPANY, never by call.
"""
import json, random, hashlib, datetime
from pathlib import Path

REPO = Path(__file__).parent.parent
MANIFEST_V2 = REPO / "analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json"
SEED = 20201231


def split_stratum(tickers, rnd):
    t = list(tickers)
    rnd.shuffle(t)
    out = {"train": [], "tune": [], "holdout": []}
    buckets = ["train", "tune", "holdout"]
    for i, tk in enumerate(t):
        out[buckets[i % 3]].append(tk)
    return out


def main():
    manifest = json.loads(MANIFEST_V2.read_text())
    rnd = random.Random(SEED)

    split = {"train": [], "tune": [], "holdout": []}
    per_stratum = {}
    for stratum in ["S1", "S2", "S3", "S4", "S5"]:
        tickers = [r["ticker"] for r in manifest["strata"][stratum]["frozen"]]
        s = split_stratum(tickers, rnd)
        per_stratum[stratum] = {k: sorted(v) for k, v in s.items()}
        for k in split:
            split[k].extend(s[k])

    for k in split:
        split[k] = sorted(split[k])

    holdout_str = json.dumps(split["holdout"], sort_keys=True)
    holdout_sha256 = hashlib.sha256(holdout_str.encode()).hexdigest()

    result = {
        "run_id": "corpus-construction",
        "pass": "fix (second pass), Step E",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "method": "random.shuffle per stratum with fixed seed, then round-robin train/tune/holdout assignment -- same method registered in PREREGISTRATION.json's outcome_holdout_split, applied here to the V2 (78-company) corpus.",
        "seed": SEED,
        "manifest_source": "analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json",
        "counts": {k: len(v) for k, v in split.items()},
        "per_stratum_counts": {s: {k: len(v) for k, v in per_stratum[s].items()} for s in per_stratum},
        "per_stratum": per_stratum,
        "train": split["train"],
        "tune": split["tune"],
        "holdout": split["holdout"],
        "holdout_sha256": holdout_sha256,
    }
    result["old_holdout_sha256_78_companies_rmo_included"] = "d4e40fe0b5f1234b34c3fe7ccd5e704afff4e5aaf4e17dbc0e53c2223e412a23"
    result["new_holdout_sha256_77_companies_rmo_removed"] = result["holdout_sha256"]
    out_path = REPO / "analysis/data/corpus_v2/SPLIT_V3_RMO_REMOVED.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ("per_stratum",)}, indent=2))


if __name__ == "__main__":
    main()
