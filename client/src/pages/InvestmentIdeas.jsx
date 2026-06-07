/**
 * InvestmentIdeas.jsx — Wrapper for the three research sub-tabs:
 *
 *   Ideas       — Stock Radar (watchlist + scores)
 *   Analyst     — Stock Analyst (transcript evaluator)  ← <a> tag so
 *                 right-click → "Open in New Tab" works for parallel uploads.
 *                 Single-click navigates to /analyst (same result, standalone).
 *   Commentary  — Advisory Feed
 *
 * Ideas and Commentary stay mounted (display:none) for state persistence.
 * Analyst lives at /analyst — not rendered here to avoid a double-mount.
 */

import { useState } from 'react';
import Radar from './Radar.jsx';
import AdvisoryFeed from './AdvisoryFeed.jsx';

const tabBase = {
  background: 'none',
  border: 'none',
  borderBottom: '2px solid transparent',
  color: '#475569',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 400,
  marginBottom: -1,
  padding: '10px 16px',
  transition: 'color 0.15s',
  textDecoration: 'none',
  display: 'inline-block',
};

const tabActive = {
  ...tabBase,
  borderBottom: '2px solid #3b82f6',
  color: '#f1f5f9',
  fontWeight: 600,
};

export default function InvestmentIdeas() {
  const [active, setActive] = useState('ideas');

  return (
    <div>
      {/* Sub-tab bar */}
      <div style={{
        display: 'flex',
        gap: 0,
        borderBottom: '1px solid #1e2330',
        padding: '0 24px',
        background: '#0a0d13',
      }}>
        {/* Ideas — button (state-based) */}
        <button
          onClick={() => setActive('ideas')}
          style={active === 'ideas' ? tabActive : tabBase}
        >
          Ideas
        </button>

        {/* Analyst — anchor so right-click → "Open in New Tab" works.
            Single-click navigates to /analyst (standalone, no sub-tab chrome). */}
        <a href="/analyst" style={tabBase}>
          Analyst
        </a>

        {/* Commentary — button (state-based) */}
        <button
          onClick={() => setActive('commentary')}
          style={active === 'commentary' ? tabActive : tabBase}
        >
          Commentary
        </button>
      </div>

      {/* Sub-pages — mounted, toggled with display */}
      <div style={{ display: active === 'ideas'      ? 'block' : 'none' }}><Radar /></div>
      <div style={{ display: active === 'commentary' ? 'block' : 'none' }}><AdvisoryFeed /></div>
    </div>
  );
}
