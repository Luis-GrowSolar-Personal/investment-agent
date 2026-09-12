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
 */

const fs = require('fs');
const path = require('path');

const REGISTRY_PATH = path.resolve(__dirname, '../../docs/architecture/VERSION_REGISTRY.json');
const registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));

const PROMPT_VERSION = registry.artifacts.evaluation_prompt.promoted_version;
const MODEL_VERSION  = registry.artifacts.model.promoted_version;

module.exports = { PROMPT_VERSION, MODEL_VERSION };
