#!/usr/bin/env python3
"""
whats_live.py -- the one-command answer to "what version is X."

Built 2026-09-12 (prompts/version-registry-and-drift-guards.md), so the next
session does not have to open an investigation the way
docs/handoffs/2026-09-03-prompt-version-drift.md did. Read-only: hashes
files on disk, reads git, prints. No API calls, no DB writes.

Exit code: 0 if every registered artifact's on-disk hash matches its
promoted_sha256; 1 otherwise (so this can gate CI later, per the prompt).
Artifacts with promoted_sha256 == null are informational and never affect
the exit code (there is nothing to mismatch against).

Usage:
    python3 analysis/whats_live.py
    python3 analysis/whats_live.py --registry-path /path/to/a/copy.json
        # For demonstrating/testing checker logic (e.g. staleness-on-model-
        # change) against a scratch COPY of the registry. Never point this
        # at anything other than a copy for a real check -- every scoring
        # driver treats the live VERSION_REGISTRY.json as a hard gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "VERSION_REGISTRY.json"


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git(*args) -> str:
    out = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def diverges_from_dev(rel_path: str) -> str:
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if not branch:
        return "unknown (not a git repo?)"
    if branch == "dev":
        return "on dev"
    mine = subprocess.run(["git", "show", f"HEAD:{rel_path}"], cwd=REPO_ROOT,
                           capture_output=True, text=True, timeout=10)
    theirs = subprocess.run(["git", "show", f"dev:{rel_path}"], cwd=REPO_ROOT,
                             capture_output=True, text=True, timeout=10)
    if mine.returncode != 0 or theirs.returncode != 0:
        return "cannot compare (path missing on one side, or uncommitted)"
    return "MATCHES dev" if mine.stdout == theirs.stdout else "DIVERGES from dev"


def extract_js_template_literal(js_path: Path, const_name: str) -> str | None:
    """Extract a `const NAME = \\`...\\`;` template literal body from a JS file,
    for artifacts registered by literal-hash rather than whole-file hash
    (currently: portfolio_import_prompt)."""
    import re
    if not js_path.exists():
        return None
    src = js_path.read_text()
    m = re.search(rf"const {re.escape(const_name)} = `([\s\S]*?)`;", src)
    return m.group(1) if m else None


def check_artifact(key: str, artifact: dict) -> dict:
    path_str = artifact.get("path", "")
    promoted = artifact.get("promoted_sha256")

    # Special-cased artifacts whose path field doesn't map 1:1 to a whole
    # file hash (documented, not hidden -- see the note in the registry).
    if key == "portfolio_import_prompt":
        content = extract_js_template_literal(
            REPO_ROOT / "server" / "lib" / "portfolioImport.js",
            "POSITIONS_CSV_PROMPT_TEMPLATE",
        )
        on_disk = sha256_text(content) if content is not None else None
    elif key == "allocator_simulator":
        hashes = artifact.get("hashes", {})
        rel = "analysis/simulator/allocator_v3.py"
        on_disk = sha256_file(REPO_ROOT / rel)
    elif key == "allocator_live":
        on_disk = sha256_file(REPO_ROOT / "server" / "routes" / "moves.js")
        return {
            "key": key, "promoted": None, "on_disk": on_disk, "match": None,
            "detail": f"informational only, not gated (accepted divergence -- see decisions.accepted_production_divergence). current sha256={on_disk}",
        }
    elif key == "trend_analyst":
        py_hash = sha256_file(REPO_ROOT / "analysis" / "trend_analyst.py")
        js_hash = sha256_file(REPO_ROOT / "server" / "lib" / "trendAnalyst.js")
        return {
            "key": key, "promoted": None, "on_disk": None, "match": None,
            "detail": f"python={py_hash}, js={js_hash} (two unreconciled implementations, no single promoted hash)",
        }
    elif key == "ticker_universe":
        return {"key": key, "promoted": None, "on_disk": None, "match": None,
                "detail": "canonical value check done separately (see ALL16 agreement note)"}
    else:
        # Ordinary case: a single file, path taken literally (allowing a
        # trailing ":line-line" annotation used only for human readability).
        clean_path = path_str.split(":")[0].split(",")[0].strip()
        on_disk = sha256_file(REPO_ROOT / clean_path) if clean_path and not clean_path.startswith("--") else None

    match = (on_disk == promoted) if (on_disk is not None and promoted is not None) else None
    return {"key": key, "promoted": promoted, "on_disk": on_disk, "match": match}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry-path", default=None,
                         help="Path to a VERSION_REGISTRY.json COPY to check instead of "
                              "the live one -- for demonstrating checker logic only.")
    args = parser.parse_args()
    registry_path = Path(args.registry_path) if args.registry_path else REGISTRY_PATH
    registry = json.loads(registry_path.read_text())
    exit_code = 0

    if registry_path != REGISTRY_PATH:
        print(f"NOTE: checking a non-live registry path: {registry_path}\n")

    print("=" * 78)
    print("whats_live.py -- version registry status")
    print(f"  registry seeded: {registry.get('seeded_at')} @ commit {registry.get('seeded_at_commit')}")
    print("=" * 78)

    print("\n[1] Registered artifacts\n")
    for key, artifact in registry["artifacts"].items():
        result = check_artifact(key, artifact)
        if result["match"] is None:
            status = "INFO" if result["promoted"] is None else "?"
            extra = f"  ({result.get('detail')})" if result.get("detail") else ""
            print(f"  {status:5} {key:28} {extra}")
            continue
        status = "MATCH" if result["match"] else "MISMATCH"
        if not result["match"]:
            exit_code = 1
        print(f"  {status:8} {key:28} promoted={result['promoted']}")
        if not result["match"]:
            print(f"           {'':28} on_disk ={result['on_disk']}")

    print("\n[2] Branch and drift vs dev\n")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    print(f"  current branch: {branch}")
    watched_paths = {
        "evaluation_prompt": "docs/EVALUATION_PROMPT.md",
        "model": "server/lib/versions.js",
        "allocator_live": "server/routes/moves.js",
    }
    for key, rel in watched_paths.items():
        print(f"  {rel:40} {diverges_from_dev(rel)}")

    print("\n[3] Settled allocator configuration (from the registry, not a docstring)\n")
    settled = registry["benchmarks"].get("settled_control", {})
    print(f"  final_value:            ${settled.get('figures', {}).get('final_value')}")
    print(f"  phase_averaged_median:  ${settled.get('figures', {}).get('phase_averaged_median')}")
    print(f"  corpus_window:          {settled.get('corpus_window')}")
    print(f"  allocator:              {settled.get('artifact_versions_and_hashes', {}).get('allocator_simulator')}")
    print(f"  quotable:               {settled.get('quotable')}")

    print("\n[4] Benchmark validity (three states, not a boolean)\n")
    print("  VALID: cite freely. SUPERSEDED: cite only within its own tuple")
    print("  (PROMOTION_GATE.md Sec11.1) -- reproducible, describes a retired")
    print("  configuration, NOT a defect and not something to go fix.")
    print("  UNREPRODUCIBLE: no known method ever produced it again -- this")
    print("  is the state that deserves attention.\n")

    promoted_model = registry["artifacts"].get("model", {}).get("promoted_version")

    def classify(bench):
        """Returns (state, value, note). VALID/SUPERSEDED is computed
        dynamically against the live promoted model (comparison-protocol
        rule 5, PROMOTION_GATE.md Sec11.5) or a pre-existing static `stale`
        flag (e.g. a prompt-version mismatch, which isn't a single
        hash-comparable field). UNREPRODUCIBLE is never computed -- it must
        be declared (Step 1's own instruction: the tool cannot infer
        reproducibility from hashes)."""
        declared = bench.get("reproducibility")
        value = bench.get("reproducibility_value")
        note = bench.get("reproducibility_note")
        if declared == "UNREPRODUCIBLE":
            return "UNREPRODUCIBLE", value, note
        if bench.get("stale"):
            return "SUPERSEDED", value, note or bench.get("stale_reason")
        record_model = bench.get("model")
        if record_model is not None and promoted_model is not None and record_model != promoted_model:
            return "SUPERSEDED", value, (note or "") + (
                f" [model axis: recorded under {record_model!r}, "
                f"currently promoted is {promoted_model!r}]"
            )
        return "VALID", value, note

    results = {key: classify(bench) for key, bench in registry["benchmarks"].items()}
    counts = {"VALID": 0, "SUPERSEDED": 0, "UNREPRODUCIBLE": 0}
    for state, _, _ in results.values():
        counts[state] += 1

    # UNREPRODUCIBLE first and unmissable -- it is the one state that
    # deserves attention; SUPERSEDED must not be allowed to bury it.
    unrepro = [k for k, (s, _, _) in results.items() if s == "UNREPRODUCIBLE"]
    if unrepro:
        print(f"  ** UNREPRODUCIBLE ({len(unrepro)}) -- needs attention, unlike the states below **")
        for key in unrepro:
            _, value, note = results[key]
            print(f"    {key}  [{value}]")
            print(f"      {note}")
        print()

    superseded = [k for k, (s, _, _) in results.items() if s == "SUPERSEDED"]
    if superseded:
        print(f"  SUPERSEDED ({len(superseded)}) -- reproducible, describes a retired "
              f"configuration. Cite ONLY within its own tuple; never extrapolate to "
              f"the current system.")
        for key in superseded:
            _, value, note = results[key]
            print(f"    {key}  [{value}]")
            print(f"      {note}")
        print()

    valid = [k for k, (s, _, _) in results.items() if s == "VALID"]
    if valid:
        print(f"  VALID ({len(valid)}) -- every valid_while artifact unchanged. Cite freely.")
        for key in valid:
            print(f"    {key}")
        print()

    print(f"  Counts: {counts['VALID']} VALID, {counts['SUPERSEDED']} SUPERSEDED, "
          f"{counts['UNREPRODUCIBLE']} UNREPRODUCIBLE")

    print("\n[5] Cache-age breaches\n")
    fc = registry["artifacts"].get("fundamentals_cache", {})
    latest = fc.get("latest_fetched_at")
    max_age = fc.get("max_age_days")
    if latest:
        try:
            fetched = datetime.fromisoformat(latest.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - fetched).days
            breach = age_days > max_age if max_age else None
            print(f"  fundamentals_cache: {age_days} days old (max_age_days={max_age}) "
                  f"{'-- BREACH' if breach else '-- within tolerance' if breach is not None else ''}")
            if breach:
                exit_code = exit_code or 0  # cache staleness is expected/frozen by design -- informational, not a gate failure
        except Exception as e:
            print(f"  fundamentals_cache: could not compute age ({e})")

    print("\n[6] Model retirement countdown\n")
    print("  Informational only -- never affects exit code (PROMOTION_GATE.md Sec8.1).")
    warning_threshold_days = 90
    any_retirement = False
    for key, artifact in registry["artifacts"].items():
        ret_date_str = artifact.get("retirement_date")
        if not ret_date_str:
            continue
        any_retirement = True
        try:
            ret_date = datetime.fromisoformat(ret_date_str).replace(tzinfo=timezone.utc)
            days_left = (ret_date - datetime.now(timezone.utc)).days
            flag = " -- WITHIN WARNING WINDOW" if days_left <= warning_threshold_days else ""
            print(f"  {key} ({artifact.get('promoted_version')}): "
                  f"retires {ret_date_str} -- {days_left} days left "
                  f"(warning threshold {warning_threshold_days}d){flag}")
            if days_left <= warning_threshold_days:
                print(f"           ACTION (PROMOTION_GATE.md Sec8.1 step 2): capture a paired bridge "
                      f"sample under BOTH the outgoing and incoming model before the retirement date. "
                      f"After retirement, pairing becomes impossible forever -- as already happened "
                      f"with the corpus scored by claude-sonnet-4-20250514.")
        except Exception as e:
            print(f"  {key}: could not compute retirement countdown from {ret_date_str!r} ({e})")
    if not any_retirement:
        print("  (no registered artifact carries a retirement_date)")

    print("\n[7] Accepted / settled divergences -- known, do not act\n")
    any_accepted = False
    for key, decision in registry["decisions"].items():
        if decision.get("disposition", "").startswith("ACCEPTED"):
            any_accepted = True
            print(f"  ACCEPTED  {key}")
            print(f"            reopening condition: {decision.get('reopening_condition')}")
            for item in decision.get("do_not", []):
                print(f"            do NOT: {item}")
    if not any_accepted:
        print("  (none)")

    print("\n[8] Open decisions\n")
    for key, decision in registry["decisions"].items():
        if decision.get("disposition", "").startswith(("OPEN", "GAP", "PENDING")):
            print(f"  {decision.get('disposition'):20} {key}")

    print("\n" + "=" * 78)
    print(f"Exit code: {exit_code} ({'all promoted artifacts match' if exit_code == 0 else 'one or more MISMATCHES above'})")
    print("=" * 78)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
