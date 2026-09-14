#!/usr/bin/env python3
"""
corpus_construction_split_v7_reserve_replacements.py -- corpus-fix-8-followup2.

Identical method to split_v3 through v6 (same fixed seed 20201231, same
random.shuffle-per-stratum + round-robin train/tune/holdout assignment),
applied to CORPUS_MANIFEST_V7.json (BLK/WEC/SIRI added as reserve
replacements for SCHW/ED/IPG).

Split is by COMPANY, never by call.
"""
import json, random, hashlib, datetime
from pathlib import Path

REPO = Path(__file__).parent.parent
MANIFEST_V7 = REPO / "analysis/data/corpus_v2/CORPUS_MANIFEST_V7.json"
PRIOR_SPLIT = REPO / "analysis/data/corpus_v2/SPLIT_V6_BK_MAXN_FOLLOWUP.json"
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
    manifest = json.loads(MANIFEST_V7.read_text())
    prior = json.loads(PRIOR_SPLIT.read_text())
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
        "pass": "corpus-fix-8-followup2",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "method": "Identical to split_v3 through v6: random.shuffle per stratum with the fixed seed, "
                  "then round-robin train/tune/holdout assignment.",
        "seed": SEED,
        "manifest_source": "analysis/data/corpus_v2/CORPUS_MANIFEST_V7.json (corpus-fix-8-followup2: "
                            "BLK/WEC/SIRI added as reserve replacements for SCHW/ED/IPG)",
        "counts": {k: len(v) for k, v in split.items()},
        "per_stratum_counts": {s: {k: len(v) for k, v in per_stratum[s].items()} for s in per_stratum},
        "per_stratum": per_stratum,
        "train": split["train"],
        "tune": split["tune"],
        "holdout": split["holdout"],
        "holdout_sha256": holdout_sha256,
        "old_holdout_sha256_v6_161_companies": prior["holdout_sha256"],
        "new_holdout_sha256_v7_164_companies": holdout_sha256,
    }
    out_path = REPO / "analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "per_stratum"}, indent=2))


if __name__ == "__main__":
    main()
