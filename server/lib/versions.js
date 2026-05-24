/**
 * versions.js — Single source of truth for the active prompt and model versions.
 *
 * These constants stamp every Analysis row written to the DB, making analyst
 * drift auditable forever instead of reconstructed from deploy history.
 *
 * PROMPT_VERSION: matches the "Version: vN" header in docs/EVALUATION_PROMPT.md.
 *   Update this whenever the prompt changes materially enough to warrant a gate run.
 *
 * MODEL_VERSION: the exact Claude model string passed to the Anthropic API.
 *   Must be a dated snapshot (claude-sonnet-4-YYYYMMDD) for gate runs to be
 *   reproducible. Reverted to claude-sonnet-4-20250514 on 2026-05-23 after the
 *   first Promotion Gate run: sonnet-4-6 regressed by 7.4pp (noise floor 4.2pp),
 *   verdict HOLD. See data/gate_ledger.json entry 1 and PROMOTION_GATE.md §10.
 */

const PROMPT_VERSION = 'v6';
const MODEL_VERSION  = 'claude-sonnet-4-20250514';

module.exports = { PROMPT_VERSION, MODEL_VERSION };
