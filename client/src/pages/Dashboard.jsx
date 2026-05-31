/**
 * Dashboard.jsx — Portfolio Analyst / Allocator view
 *
 * One collapsible card per owner. Each card shows:
 *   - Portfolio total vs investment goal (enough number) with progress bar
 *   - Per-ticker allocator output: weight, cap status, health, recommendation,
 *     trend, ratchet tranche, flags
 *   - Tax-aware trim routing for any Trim/Exit recommendation
 *   - 48-hour hold flags for positions > 30%
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';

// ---------------------------------------------------------------------------
// Style tokens (per UI_SPEC.md)
// ---------------------------------------------------------------------------
const HEALTH_COLORS = {
  Strengthening: '#34d399',
  Intact:        '#60a5fa',
  Weakening:     '#f59e0b',
  Broken:        '#ef4444',
};
const REC_COLORS = {
  Add:  '#34d399',
  Hold: '#60a5fa',
  Trim: '#f59e0b',
  Exit: '#ef4444',
};
const TRAJ_COLORS = {
  improving:    '#34d399',
  stable:       '#60a5fa',
  flattening:   '#94a3b8',
  softening:    '#f59e0b',
  deteriorating:'#ef4444',
  unknown:      '#475569',
};
const FLAG_COLORS = {
  red:    { bg: '#450a0a22', border: '#991b1b55', text: '#f87171' },
  amber:  { bg: '#78350f22', border: '#d9770655', text: '#fbbf24' },
  yellow: { bg: '#71300022', border: '#ca8a0455', text: '#fde68a' },
  slate:  { bg: '#1e2330',   border: '#334155',   text: '#94a3b8' },
};

function badge(label, color) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 7px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
      background: color + '1a',
      border: `1px solid ${color}33`,
      color,
      whiteSpace: 'nowrap',
    }}>{label}</span>
  );
}

function flagPill(flag) {
  const c = FLAG_COLORS[flag.severity] ?? FLAG_COLORS.slate;
  return (
    <span key={flag.type} style={{
      display: 'inline-block',
      padding: '1px 7px',
      borderRadius: 4,
      fontSize: 10,
      fontWeight: 600,
      background: c.bg,
      border: `1px solid ${c.border}`,
      color: c.text,
      whiteSpace: 'nowrap',
    }}>{flag.label}</span>
  );
}

function pct(n, decimals = 1) {
  if (n == null) return '—';
  return n.toFixed(decimals) + '%';
}
function money(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

// ---------------------------------------------------------------------------
// Trim routing detail (collapsed by default)
// ---------------------------------------------------------------------------
function TrimRouting({ routes }) {
  const [open, setOpen] = useState(false);
  if (!routes || routes.length === 0) return null;

  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: 'none', color: '#60a5fa', fontSize: 12, cursor: 'pointer', padding: 0 }}
      >
        {open ? '▼' : '▶'} Tax routing
      </button>
      {open && (
        <table style={{ marginTop: 8, width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ color: '#475569' }}>
              <th style={th}>Account</th>
              <th style={th}>Type</th>
              <th style={th}>Shares</th>
              <th style={th}>Mkt Value</th>
              <th style={th}>Tax cost</th>
              <th style={th}>LT gain</th>
              <th style={th}>ST gain</th>
            </tr>
          </thead>
          <tbody>
            {routes.map((r, i) => (
              <tr key={i} style={{ borderTop: '1px solid #1e2330' }}>
                <td style={td}>{r.accountName}</td>
                <td style={td}>
                  {r.isTaxAdvantaged
                    ? <span style={{ color: '#34d399', fontSize: 10, fontWeight: 600 }}>TAX-FREE</span>
                    : r.accountType.toUpperCase()}
                </td>
                <td style={td}>{r.shares.toFixed(3)}</td>
                <td style={td}>{money(r.marketValue)}</td>
                <td style={{ ...td, color: r.taxCost > 0 ? '#f59e0b' : '#34d399' }}>
                  {r.isTaxAdvantaged ? '$0' : money(r.taxCost)}
                </td>
                <td style={td}>{r.ltGain > 0 ? money(r.ltGain) : '—'}</td>
                <td style={td}>{r.stGain > 0 ? money(r.stGain) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ticker row
// ---------------------------------------------------------------------------
function TickerRow({ t }) {
  const [open, setOpen] = useState(false);
  const hasTrimData = t.trimRouting && t.trimRouting.length > 0;
  const hasFlags    = t.flags && t.flags.length > 0;

  const rowBg = t.overCap ? '#450a0a18'
    : t.ratchetTranche >= 1 ? '#78350f18'
    : 'transparent';

  return (
    <>
      <tr
        style={{ borderTop: '1px solid #1e2330', background: rowBg, cursor: hasTrimData ? 'pointer' : 'default' }}
        onClick={() => hasTrimData && setOpen(o => !o)}
      >
        {/* Drill triangle */}
        <td style={{ ...td, width: 20, color: '#475569' }}>
          {hasTrimData ? (open ? '▼' : '▶') : ''}
        </td>

        {/* Symbol + tier chip */}
        <td style={td}>
          <span style={{ fontWeight: 700, color: '#f1f5f9', fontSize: 13 }}>{t.symbol}</span>
          {t.tier && (
            <span style={{
              marginLeft: 6,
              fontSize: 10,
              fontWeight: 700,
              padding: '1px 5px',
              borderRadius: 3,
              border: `1px solid ${t.tier === 'established' ? '#33415555' : '#78350f55'}`,
              color: t.tier === 'established' ? '#64748b' : '#f59e0b',
              background: t.tier === 'established' ? '#1e2330' : '#78350f22',
              letterSpacing: '0.06em',
            }}>
              {t.tier === 'established' ? 'EST' : 'SPEC'}
            </span>
          )}
        </td>

        {/* Type */}
        <td style={{ ...td, color: '#94a3b8' }}>{t.type ?? '—'}</td>

        {/* Weight vs cap */}
        <td style={td}>
          <span style={{ color: t.overCap ? '#f87171' : t.approachCap ? '#fbbf24' : '#f1f5f9', fontWeight: 600 }}>
            {pct(t.currentPct)}
          </span>
          <span style={{ color: '#475569', fontSize: 11 }}> / {pct(t.hardCapPct, 0)}</span>
        </td>

        {/* Market value */}
        <td style={{ ...td, color: '#94a3b8' }}>{money(t.totalMktValue)}</td>

        {/* Thesis health */}
        <td style={td}>
          {t.thesisHealth !== '—'
            ? badge(t.thesisHealth, HEALTH_COLORS[t.thesisHealth] ?? '#94a3b8')
            : <span style={{ color: '#334155' }}>—</span>}
        </td>

        {/* Recommendation / final action */}
        <td style={td}>
          {t.finalAction !== '—'
            ? badge(t.finalAction, REC_COLORS[t.finalAction] ?? '#94a3b8')
            : <span style={{ color: '#334155' }}>—</span>}
        </td>

        {/* Trend trajectory */}
        <td style={td}>
          {t.trajectory
            ? <span style={{ fontSize: 11, fontWeight: 600, color: TRAJ_COLORS[t.trajectory] ?? '#94a3b8' }}>
                {t.trajectory}
              </span>
            : <span style={{ color: '#334155' }}>—</span>}
        </td>

        {/* Flags */}
        <td style={{ ...td, minWidth: 140 }}>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {hasFlags ? t.flags.map(f => flagPill(f)) : null}
          </div>
        </td>
      </tr>

      {/* Expanded trim routing */}
      {open && hasTrimData && (
        <tr style={{ background: '#0d1018' }}>
          <td colSpan={9} style={{ padding: '8px 20px 14px 36px' }}>
            <TrimRouting routes={t.trimRouting} />
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Owner dashboard card
// ---------------------------------------------------------------------------
function OwnerCard({ owner }) {
  const { getToken } = useAuth();
  const [open, setOpen]     = useState(true);
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr]       = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setErr('');
    try {
      const token = await getToken();
      const r = await fetch(`/api/dashboard/${encodeURIComponent(owner)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Load failed');
      setData(d);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [owner, getToken]);

  useEffect(() => { load(); }, [load]);

  const displayName = data?.displayName || owner;
  const enoughPct   = data?.enoughPct != null ? data.enoughPct * 100 : null;
  const goalColor   = enoughPct == null ? '#3b82f6' : enoughPct >= 100 ? '#4ade80' : enoughPct >= 60 ? '#fbbf24' : '#3b82f6';

  // Counts for header summary chips
  const flagCounts = !data ? {} : data.tickers.reduce((acc, t) => {
    t.flags.forEach(f => { acc[f.severity] = (acc[f.severity] ?? 0) + 1; });
    return acc;
  }, {});

  return (
    <div style={{ border: '1px solid #1e2330', borderRadius: 10, marginBottom: 20, overflow: 'hidden' }}>
      {/* Card header */}
      <div
        style={{ background: '#0f1117', padding: '14px 20px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}
        onClick={() => setOpen(o => !o)}
      >
        <span style={{ color: '#94a3b8', fontSize: 13 }}>{open ? '▼' : '▶'}</span>
        <span style={{ fontWeight: 700, fontSize: 15, color: '#f1f5f9' }}>{displayName}</span>

        {data && (
          <>
            <span style={{ fontSize: 13, color: '#94a3b8' }}>
              Portfolio: <strong style={{ color: '#f1f5f9' }}>{money(data.totalPortfolioValue)}</strong>
            </span>

            {/* Enough number progress */}
            {data.enoughNumber && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: '#64748b' }}>Goal: {money(data.enoughNumber)}</span>
                <div style={{ width: 100, height: 4, background: '#1e2330', borderRadius: 2 }}>
                  <div style={{ width: `${Math.min(100, enoughPct ?? 0)}%`, height: '100%', background: goalColor, borderRadius: 2 }} />
                </div>
                <span style={{ fontSize: 11, color: goalColor, fontWeight: 600 }}>
                  {enoughPct != null ? enoughPct.toFixed(0) + '%' : ''}
                </span>
                {data.enoughReached && (
                  <span style={{ fontSize: 11, color: '#4ade80', fontWeight: 700 }}>✓ REACHED</span>
                )}
              </div>
            )}
            {!data.enoughNumber && (
              <span style={{ fontSize: 12, color: '#334155', fontStyle: 'italic' }}>No goal set</span>
            )}

            {/* Flag summary chips */}
            {flagCounts.red    > 0 && <span style={{ fontSize: 11, color: '#f87171', fontWeight: 700 }}>⚑ {flagCounts.red} critical</span>}
            {flagCounts.amber  > 0 && <span style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700 }}>⚑ {flagCounts.amber} warning</span>}
          </>
        )}

        <button
          onClick={e => { e.stopPropagation(); load(); }}
          title="Refresh"
          style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#475569', cursor: 'pointer', fontSize: 15 }}
        >⟳</button>
      </div>

      {/* Card body */}
      {open && (
        <div style={{ background: '#0d1018' }}>
          {loading && (
            <div style={{ padding: 32, textAlign: 'center', color: '#475569', fontSize: 13 }}>Loading…</div>
          )}
          {err && (
            <div style={{ padding: 16, color: '#f87171', fontSize: 13 }}>{err}</div>
          )}
          {data && !loading && (
            <>
              {/* Enough number alert */}
              {data.enoughReached && (
                <div style={{ margin: 16, padding: '10px 16px', background: '#14532d22', border: '1px solid #16a34a55', borderRadius: 8, color: '#4ade80', fontSize: 13 }}>
                  🎯 Investment goal reached ({money(data.totalPortfolioValue)} / {money(data.enoughNumber)}). Consider transitioning to passive S&P 500 allocation.
                </div>
              )}

              {data.tickers.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center', color: '#475569', fontSize: 13 }}>
                  No active positions.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: '#0f1117' }}>
                        <th style={th}></th>
                        <th style={{ ...th, textAlign: 'left' }}>SYMBOL</th>
                        <th style={th}>TYPE</th>
                        <th style={th}>WEIGHT / CAP</th>
                        <th style={th}>VALUE</th>
                        <th style={th}>THESIS HEALTH</th>
                        <th style={th}>ACTION</th>
                        <th style={th}>TREND</th>
                        <th style={{ ...th, textAlign: 'left' }}>FLAGS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.tickers.map(t => (
                        <TickerRow key={t.tickerId} t={t} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Account summary footer */}
              <div style={{ padding: '10px 20px', borderTop: '1px solid #1e2330', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {data.accountSummary.map(a => (
                  <span key={a.id} style={{ fontSize: 11, color: '#475569' }}>
                    {a.name}
                    {a.cashBalance != null && <span style={{ color: '#334155' }}> · cash {money(a.cashBalance)}</span>}
                    {a.marginBalance > 0 && <span style={{ color: '#f87171' }}> · margin {money(a.marginBalance)}</span>}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page — fetches owner list, renders one card per owner
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const { getToken } = useAuth();
  const [owners, setOwners]   = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        const r = await fetch('/api/dashboard', { headers: { Authorization: `Bearer ${token}` } });
        const data = await r.json();
        if (r.ok) setOwners(data.map(d => d.owner));
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken]);

  return (
    <div style={{ maxWidth: 1100, margin: '32px auto', padding: '0 24px' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>Dashboard</h1>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
          Allocator view — concentration caps, tax-aware trim routing, ratchet status.
        </p>
      </div>

      {loading ? (
        <div style={{ color: '#475569', fontSize: 13 }}>Loading…</div>
      ) : owners.length === 0 ? (
        <div style={{ color: '#475569', fontSize: 13 }}>
          No owners found. Add owners in the <strong style={{ color: '#94a3b8' }}>Users</strong> tab.
        </div>
      ) : (
        owners.map(owner => <OwnerCard key={owner} owner={owner} />)
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Table style tokens
// ---------------------------------------------------------------------------
const th = {
  padding: '8px 12px',
  fontSize: 10,
  fontWeight: 700,
  color: '#475569',
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  textAlign: 'center',
  whiteSpace: 'nowrap',
  borderBottom: '1px solid #1e2330',
};
const td = {
  padding: '9px 12px',
  verticalAlign: 'middle',
  color: '#94a3b8',
  textAlign: 'center',
};
