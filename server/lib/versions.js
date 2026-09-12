/**
 * versions.js — thin re-export of VERSION_REGISTRY.json's promoted versions.
 *
 * Built 2026-09-12 (prompts/version-registry-and-drift-guards.md). This used
 * to be a hand-maintained constant, which is exactly how the app drifted
 * silently to v10+auto1 for five weeks while this file kept claiming 'v6'
 * (docs/handoffs/2026-09-03-prompt-version-drift.md) -- nothing forced the
 * two to agree. Deleting the bug class rather than guarding it: there is now
 * exactly one place version truth lives (VERSION_REGISTRY.json), and this
 * file just reads it.
 *
 * PROMPT_VERSION / MODEL_VERSION names are preserved so callers
 * (server/routes/evaluate.js) are unchanged.
 *
 * Note this exports the PROMOTED version string, not necessarily what
 * evaluate.js ends up stamping on a given row -- a PROMPT_CANDIDATE
 * override at request time stamps the candidate's version instead. See
 * server/lib/versionGuard.js and evaluate.js's `effectivePromptVersion`.
 *
 * Fail SAFE, not fail dead (2026-09-12 follow-up,
 * prompts/drift-guards-followup.md). A missing/malformed registry file, a
 * changed relative path in a deployed layout, or a renamed registry key
 * used to throw at require() time -- meaning `require('./versions')`
 * failing took the whole server down on a file-read problem, not a version
 * mismatch. That is the exact boot-refusal failure mode
 * version-registry-and-drift-guards-out.md's §2 deliberately rejected for
 * the guard, reintroduced accidentally here. The scoring route's hash
 * check (evaluate.js) remains the actual enforcement point and already
 * fails closed -- that is where refusal belongs, not at import. So: on any
 * read/parse/lookup failure here, log loudly and export a clearly-marked
 * sentinel instead of throwing.
 */

const fs = require('fs');
const path = require('path');

const REGISTRY_PATH = path.resolve(__dirname, '../../docs/architecture/VERSION_REGISTRY.json');
const UNKNOWN_SENTINEL = 'UNKNOWN-REGISTRY-UNREADABLE';

let PROMPT_VERSION = UNKNOWN_SENTINEL;
let MODEL_VERSION = UNKNOWN_SENTINEL;

try {
  const registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
  if (!registry.artifacts || !registry.artifacts.evaluation_prompt || !registry.artifacts.model) {
    throw new Error('registry loaded but is missing artifacts.evaluation_prompt or artifacts.model');
  }
  PROMPT_VERSION = registry.artifacts.evaluation_prompt.promoted_version;
  MODEL_VERSION = registry.artifacts.model.promoted_version;
} catch (err) {
  console.error(
    `[versions.js] FAILED TO LOAD VERSION_REGISTRY.json at ${REGISTRY_PATH}: ${err.message}\n` +
    `  Exporting PROMPT_VERSION=MODEL_VERSION='${UNKNOWN_SENTINEL}' so the server can still start.\n` +
    `  The scoring route's own hash check (server/routes/evaluate.js) will refuse to score with an\n` +
    `  unreadable registry -- this file's job is only to not take the whole app down over it.`
  );
}

module.exports = { PROMPT_VERSION, MODEL_VERSION };
