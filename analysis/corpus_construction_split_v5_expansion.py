#!/usr/bin/env python3
"""
corpus_construction_split_v5_expansion.py -- corpus-fix-8, Step E.

Identical method to split_v3/v4 (same fixed seed 20201231, same
random.shuffle-per-stratum + round-robin train/tune/holdout assignment),
applied to CORPUS_MANIFEST_V5.json (corpus-fix-8's ~150-company expansion).

Split is by COMPANY, never by call.
"""
import json, random, hashlib, datetime
from pathlib import Path

REPO = Path(__file__).parent.parent
MANIFEST_V5 = REPO / "analysis/data/corpus_v2/CORPUS_MANIFEST_V5.json"
PRIOR_SPLIT = REPO / "analysis/data/corpus_v2/SPLIT_V4_MANIFEST_CORRECTIONS.json"
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
    manifest = json.loads(MANIFEST_V5.read_text())
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
        "pass": "corpus-fix-8, Step E",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "method": "Identical to split_v3/v4: random.shuffle per stratum with the fixed seed, "
                  "then round-robin train/tune/holdout assignment.",
        "seed": SEED,
        "manifest_source": "analysis/data/corpus_v2/CORPUS_MANIFEST_V5.json (corpus-fix-8 expansion "
                            "to ~150 companies)",
        "counts": {k: len(v) for k, v in split.items()},
        "per_stratum_counts": {s: {k: len(v) for k, v in per_stratum[s].items()} for s in per_stratum},
        "per_stratum": per_stratum,
        "train": split["train"],
        "tune": split["tune"],
        "holdout": split["holdout"],
        "holdout_sha256": holdout_sha256,
        "old_holdout_sha256_v4_75_companies": prior["holdout_sha256"],
        "new_holdout_sha256_v5_expanded": holdout_sha256,
    }
    out_path = REPO / "analysis/data/corpus_v2/SPLIT_V5_EXPANSION.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "per_stratum"}, indent=2))


if __name__ == "__main__":
    main()
