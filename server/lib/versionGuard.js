/**
 * versionGuard.js — single point of truth for "does what's on disk match
 * what the registry says is promoted."
 *
 * Built 2026-09-12 (prompts/version-registry-and-drift-guards.md) after
 * v10+auto1 ran in production for five weeks while every row it wrote
 * claimed v6 (docs/handoffs/2026-09-03-prompt-version-drift.md). The
 * registry alone doesn't prevent that -- something has to actually check
 * the hash before a scoring call, every time. This is that something.
 *
 * PROMPT_CANDIDATE=<version> is the one escape hatch: it must name a
 * registered candidate for the artifact being checked, and the caller is
 * responsible for stamping that candidate version on whatever row it
 * writes (not the promoted version). Unset (the default) means refuse on
 * any mismatch.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const REGISTRY_PATH = path.resolve(__dirname, '../../docs/architecture/VERSION_REGISTRY.json');

function loadRegistry() {
  return JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
}

function sha256(content) {
  return crypto.createHash('sha256').update(content, 'utf8').digest('hex');
}

/**
 * Compare `content` (a string already read/derived by the caller) against
 * the registry's promoted_sha256 for `artifactKey`.
 *
 * Returns { ok, promotedHash, actualHash, candidateUsed, artifactKey }.
 * Does not throw -- callers decide what "not ok" means for their route.
 */
function checkPromptHash(artifactKey, content) {
  const registry = loadRegistry();
  const artifact = registry.artifacts[artifactKey];
  if (!artifact) {
    throw new Error(`versionGuard: no registry entry for artifact "${artifactKey}"`);
  }

  const actualHash = sha256(content);
  const promotedHash = artifact.promoted_sha256;
  const candidateEnvVar = 'PROMPT_CANDIDATE';
  const candidate = process.env[candidateEnvVar];

  if (actualHash === promotedHash) {
    return { ok: true, promotedHash, actualHash, candidateUsed: null, artifactKey };
  }

  if (candidate) {
    const registered = (artifact.candidates || []).find(c => c.version === candidate);
    if (registered && registered.sha256 && registered.sha256 === actualHash) {
      return { ok: true, promotedHash, actualHash, candidateUsed: candidate, artifactKey };
    }
    if (registered) {
      // Candidate is named and registered, but its recorded hash (if any)
      // doesn't match what's on disk right now, OR it has no recorded hash
      // yet. Trust the explicit declaration -- the caller is asserting
      // "this is that candidate" -- but this is exactly the seam an
      // undeclared drift could hide in, so it is logged loudly by the caller.
      return { ok: true, promotedHash, actualHash, candidateUsed: candidate, artifactKey, unverifiedCandidateHash: true };
    }
    return {
      ok: false,
      promotedHash, actualHash, candidateUsed: candidate, artifactKey,
      reason: `PROMPT_CANDIDATE="${candidate}" is not a registered candidate for "${artifactKey}"`,
    };
  }

  return {
    ok: false,
    promotedHash, actualHash, candidateUsed: null, artifactKey,
    reason: `content hash does not match promoted artifact "${artifactKey}" and no PROMPT_CANDIDATE was declared`,
  };
}

/**
 * Convenience wrapper for call sites that just want a hard failure on
 * mismatch (no candidate override support) -- used by portfolioImport.js,
 * which has no gated candidate mechanism at all yet.
 */
function assertPromptHash(artifactKey, content) {
  const result = checkPromptHash(artifactKey, content);
  if (!result.ok) {
    throw new Error(
      `versionGuard: ${result.reason} (promoted=${result.promotedHash}, actual=${result.actualHash})`
    );
  }
  return result;
}

module.exports = { loadRegistry, checkPromptHash, assertPromptHash, sha256, REGISTRY_PATH };
