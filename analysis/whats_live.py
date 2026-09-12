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
"""

from __future__ import annotations

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
    registry = json.loads(REGISTRY_PATH.read_text())
    exit_code = 0

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

    print("\n[4] Stale benchmarks (valid_while artifacts have moved)\n")
    any_stale = False
    for key, bench in registry["benchmarks"].items():
        if bench.get("stale"):
            any_stale = True
            print(f"  STALE  {key}")
            print(f"         reason: {bench.get('stale_reason')}")
    if not any_stale:
        print("  (none marked stale)")

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

    print("\n[6] Accepted / settled divergences -- known, do not act\n")
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

    print("\n[7] Open decisions\n")
    for key, decision in registry["decisions"].items():
        if decision.get("disposition", "").startswith(("OPEN", "GAP", "PENDING")):
            print(f"  {decision.get('disposition'):20} {key}")

    print("\n" + "=" * 78)
    print(f"Exit code: {exit_code} ({'all promoted artifacts match' if exit_code == 0 else 'one or more MISMATCHES above'})")
    print("=" * 78)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
