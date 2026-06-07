/**
 * InvestmentIdeas.jsx — Wrapper for the three research sub-tabs.
 *
 * Each sub-tab has its own URL so right-click → "Open in New Tab" works
 * on all three — useful for opening multiple Analyst tabs in parallel.
 *
 *   /ideas       — Stock Radar (watchlist + scores)
 *   /analyst     — Stock Analyst (transcript evaluator)
 *   /commentary  — Advisory Feed
 *
 * App.jsx keeps this component mounted for all three paths, so all three
 * sub-components stay alive (display:none) and state survives tab switches.
 */

import { useLocation } from 'react-router-dom';
import Radar from './Radar.jsx';
import Evaluator from './Evaluator.jsx';
import AdvisoryFeed from './AdvisoryFeed.jsx';

const TABS = [
  { id: 'ideas',      label: 'Ideas',       href: '/ideas' },
  { id: 'analyst',    label: 'Analyst',     href: '/analyst' },
  { id: 'commentary', label: 'Commentary',  href: '/commentary' },
];

function tabStyle(isActive) {
  return {
    background: 'none',
    border: 'none',
    borderBottom: isActive ? '2px solid #3b82f6' : '2px solid transparent',
    color: isActive ? '#f1f5f9' : '#475569',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: isActive ? 600 : 400,
    marginBottom: -1,
    padding: '10px 16px',
    transition: 'color 0.15s',
    textDecoration: 'none',
    display: 'inline-block',
  };
}

export default function InvestmentIdeas() {
  const { pathname } = useLocation();

  // Derive active sub-tab from URL
  const active = pathname === '/analyst'    ? 'analyst'
               : pathname === '/commentary' ? 'commentary'
               : 'ideas';

  return (
    <div>
      {/* Sub-tab bar — all tabs are <a> links so right-click works on each */}
      <div style={{
        display: 'flex',
        gap: 0,
        borderBottom: '1px solid #1e2330',
        padding: '0 24px',
        background: '#0a0d13',
      }}>
        {TABS.map(t => (
          <a key={t.id} href={t.href} style={tabStyle(active === t.id)}>
            {t.label}
          </a>
        ))}
      </div>

      {/* Sub-pages — all mounted, toggled with display */}
      <div style={{ display: active === 'ideas'      ? 'block' : 'none' }}><Radar /></div>
      <div style={{ display: active === 'analyst'    ? 'block' : 'none' }}><Evaluator /></div>
      <div style={{ display: active === 'commentary' ? 'block' : 'none' }}><AdvisoryFeed /></div>
    </div>
  );
}
