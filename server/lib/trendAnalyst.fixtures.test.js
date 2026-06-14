#!/usr/bin/env node
/**
 * trendAnalyst.fixtures.test.js — Parity test runner (Node side).
 *
 * Runs analysis/data/trend_verdict_fixtures.json through
 * server/lib/trendAnalyst.js's computeTrendVerdict / applyMatrix /
 * computeFinalConfidence.
 *
 * The Python counterpart (analysis/test_trend_fixtures.py) runs the same
 * fixtures through analysis/trend_analyst.py. Both must pass — this is the
 * regression bar for any change to the trend-verdict/matrix/confidence rules
 * in either language (see trendAnalyst.js's file header).
 *
 * Usage:
 *   node server/lib/trendAnalyst.fixtures.test.js
 */

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const { computeTrendVerdict, applyMatrix, computeFinalConfidence } = require('./trendAnalyst');

const fixturesPath = path.join(__dirname, '..', '..', 'analysis', 'data', 'trend_verdict_fixtures.json');
const fixtures = JSON.parse(fs.readFileSync(fixturesPath, 'utf8'));

const defaults = fixtures.verdict_defaults;
const failures = [];

// --- verdict cases ---------------------------------------------------------
for (const c of fixtures.verdict_cases) {
  const history = c.history.map(entry => ({ ...defaults, ...entry }));
  const verdict = computeTrendVerdict(history, c.tier || 'established');
  const expected = c.expected;

  if (expected === null) {
    if (verdict !== null) {
      failures.push(`[verdict] ${c.name}: got ${JSON.stringify(verdict)}, want null`);
    }
    continue;
  }

  if (verdict === null) {
    failures.push(`[verdict] ${c.name}: got null, want ${JSON.stringify(expected)}`);
    continue;
  }

  const got = [verdict.trajectory, verdict.suggested_override];
  const want = [expected.trajectory, expected.suggested_override];
  if (got[0] !== want[0] || got[1] !== want[1]) {
    failures.push(`[verdict] ${c.name}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
  }
}

// --- matrix cases ------------------------------------------------------------
for (const c of fixtures.matrix_cases) {
  const [action] = applyMatrix(c.per_call_rec, c.verdict, c.layer3_rotation_target || false);
  if (action !== c.expected_action) {
    failures.push(`[matrix] ${c.name}: got ${JSON.stringify(action)}, want ${JSON.stringify(c.expected_action)}`);
  }
}

// --- confidence cases ----------------------------------------------------------
for (const c of fixtures.confidence_cases) {
  const got = computeFinalConfidence(c.verdict, c.per_call_rec, c.final_action);
  if (got !== c.expected) {
    failures.push(`[confidence] ${c.name}: got ${JSON.stringify(got)}, want ${JSON.stringify(c.expected)}`);
  }
}

if (failures.length) {
  console.log('FIXTURE FAILURES (Node):');
  for (const f of failures) console.log(`  - ${f}`);
  process.exit(1);
}

const total = fixtures.verdict_cases.length + fixtures.matrix_cases.length + fixtures.confidence_cases.length;
console.log(`All ${total} fixture cases passed (Node).`);
assert.strictEqual(failures.length, 0);
