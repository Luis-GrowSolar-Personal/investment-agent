/**
 * InvestmentIdeas.jsx — Wrapper for the three research sub-tabs:
 *
 *   Ideas       — Stock Radar (watchlist + scores)
 *   Analyst     — Stock Analyst (transcript evaluator)
 *   Commentary  — Advisory Feed
 *
 * All three sub-components stay mounted (display:none) so in-flight
 * fetches and form state survive tab switches.
 */

import { useState } from 'react';
import Radar from './Radar.jsx';
import Evaluator from './Evaluator.jsx';
import AdvisoryFeed from './AdvisoryFeed.jsx';

const TABS = [
  { id: 'ideas',      label: 'Ideas' },
  { id: 'analyst',    label: 'Analyst' },
  { id: 'commentary', label: 'Commentary' },
];

export default function InvestmentIdeas() {
  const [active, setActive] = useState('ideas');

  return (
    <div>
      {/* Sub-tab selector */}
      <div style={{
        display: 'flex',
        gap: 0,
        borderBottom: '1px solid #1e2330',
        padding: '0 24px',
        background: '#0a0d13',
      }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: active === t.id ? '2px solid #3b82f6' : '2px solid transparent',
              color: active === t.id ? '#f1f5f9' : '#475569',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: active === t.id ? 600 : 400,
              marginBottom: -1,
              padding: '10px 16px',
              transition: 'color 0.15s',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Sub-pages — all mounted, toggled with display */}
      <div style={{ display: active === 'ideas'      ? 'block' : 'none' }}><Radar /></div>
      <div style={{ display: active === 'analyst'    ? 'block' : 'none' }}><Evaluator /></div>
      <div style={{ display: active === 'commentary' ? 'block' : 'none' }}><AdvisoryFeed /></div>
    </div>
  );
}
