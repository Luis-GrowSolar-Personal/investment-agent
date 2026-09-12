"""
version_guard.py -- the harness-side counterpart to server/lib/versionGuard.js.

Built 2026-09-12 (prompts/version-registry-and-drift-guards.md). This is the
guard that would have caught the $48 / ~10M token spend from
docs/handoffs/2026-09-03-prompt-version-drift.md: Test 4 and Test 6 both
scored v10+auto1 -- a prompt used in neither production nor the corpus --
because nothing checked the prompt hash before spending money on it.

Every driver that makes scoring (Claude API) calls must call
`assert_prompt_hash(...)` before its FIRST API call, not after. On failure it
raises immediately -- no calls are made downstream of a raised exception in
correctly-structured driver code (see each driver's own placement, verified
in the wrap-up for this run).

Usage:
    from analysis.version_guard import assert_prompt_hash
    prompt_text = PROMPT_PATH.read_text()
    assert_prompt_hash(prompt_text)   # raises SystemExit on mismatch

A registered candidate may be declared explicitly:
    assert_prompt_hash(prompt_text, candidate="v10+auto1")
This does not silently pass -- it prints a loud warning naming the candidate,
because every row the caller writes downstream must stamp that candidate
version, not the promoted one. That stamping is the caller's responsibility;
this module only decides whether the run may proceed at all.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "VERSION_REGISTRY.json"


def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text())


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _current_branch() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def _diverges_from_dev(path_in_repo: str) -> str:
    """Best-effort: does the branch's committed version of `path_in_repo`
    differ from dev's? Returns a human-readable status string; never raises
    -- this is diagnostic context for a failure message, not itself a gate."""
    try:
        branch = _current_branch()
        if not branch or branch == "dev":
            return "on dev, N/A"
        mine = subprocess.run(
            ["git", "show", f"HEAD:{path_in_repo}"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        theirs = subprocess.run(
            ["git", "show", f"dev:{path_in_repo}"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        if mine.returncode != 0 or theirs.returncode != 0:
            return "could not compare (path missing on one side or not committed)"
        return "MATCHES dev" if mine.stdout == theirs.stdout else "DIVERGES from dev"
    except Exception as e:
        return f"could not compare ({e})"


class PromptVersionMismatch(SystemExit):
    pass


def assert_prompt_hash(
    prompt_text: str,
    artifact_key: str = "evaluation_prompt",
    candidate: str | None = None,
    path_in_repo: str = "docs/EVALUATION_PROMPT.md",
) -> dict:
    """Hard-fails (raises SystemExit, so the caller cannot swallow it and
    continue by accident) unless prompt_text's hash matches the registry's
    promoted hash for `artifact_key`, OR `candidate` names a registered
    candidate for that artifact.

    Returns a dict describing the check on success, for the caller to log
    or fold into a manifest.
    """
    registry = _load_registry()
    artifact = registry["artifacts"].get(artifact_key)
    if artifact is None:
        raise PromptVersionMismatch(
            f"version_guard: no registry entry for artifact '{artifact_key}' "
            f"in {REGISTRY_PATH}"
        )

    actual_hash = _sha256(prompt_text)
    promoted_hash = artifact.get("promoted_sha256")
    branch = _current_branch()
    divergence = _diverges_from_dev(path_in_repo)

    if actual_hash == promoted_hash:
        return {
            "ok": True, "promoted_hash": promoted_hash, "actual_hash": actual_hash,
            "candidate_used": None, "branch": branch,
        }

    if candidate:
        registered = next(
            (c for c in artifact.get("candidates", []) if c.get("version") == candidate),
            None,
        )
        if registered is not None:
            print(
                f"[version_guard] WARNING: running against PROMPT_CANDIDATE='{candidate}' "
                f"for '{artifact_key}' -- NOT the promoted version. Every result this run "
                f"produces must be recorded/stamped under the candidate version, never the "
                f"promoted one."
            )
            return {
                "ok": True, "promoted_hash": promoted_hash, "actual_hash": actual_hash,
                "candidate_used": candidate, "branch": branch,
            }
        raise PromptVersionMismatch(
            f"version_guard: PROMPT_CANDIDATE='{candidate}' is not a registered candidate "
            f"for artifact '{artifact_key}'. Registered candidates: "
            f"{[c.get('version') for c in artifact.get('candidates', [])]}"
        )

    raise PromptVersionMismatch(
        "\n"
        f"version_guard: HARD-FAIL before any API call.\n"
        f"  artifact:        {artifact_key} ({path_in_repo})\n"
        f"  promoted sha256: {promoted_hash}\n"
        f"  actual sha256:   {actual_hash}\n"
        f"  current branch:  {branch}\n"
        f"  vs dev:          {divergence}\n"
        f"  No API call was made. Either restore the promoted content, or pass an explicit\n"
        f"  candidate= naming a version registered in VERSION_REGISTRY.json's\n"
        f"  artifacts.{artifact_key}.candidates list."
    )
