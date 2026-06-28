/**
 * DecisionAnalytics.jsx — Track Record tab
 *
 * Shows every decision made on move-card recommendations, grouped by ticker.
 * The key use case: "You declined to trim SPWR at $24, again at $20, again
 * at $16. SPWR is now at $X." — makes cognitive biases visible.
 *
 * Data source: GET /api/decisions (owner-scoped)
 * Price at decision: pulled from systemSnapshot.pricePerShare
 * Current price: placeholder (—) until Polygon.io is wired up
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';

const API_URL = import.meta.env.VITE_API_URL || '';

// ── Color helpers ─────────────────────────────────────────────────────────────

const DECISION_COLOR = {
  accepted: '#22c55e',
  declined: '#f87171',
  deferred: '#f59e0b',
};

const MOVETYPE_COLOR = {
  EXIT:         '#ef4444',
  TRIM_CAP:     '#f59e0b',
  TRIM_RATCHET: '#f59e0b',
  TRIM_MODEL:   '#f59e0b',
  ADD:          '#22c55e',
  INITIATE:     '#60a5fa',
};

function decisionColor(d) { return DECISION_COLOR[d] ?? '#64748b'; }
function moveColor(m)     { return MOVETYPE_COLOR[m] ?? '#64748b'; }

function moveLabel(moveType) {
  return moveType.replace(/_/g, ' ');
}

function money(n) {
  if (n == null) return '—';
  return '$' + Math.round(n).toLocaleString();
}

function price(n) {
  if (n == null || n === 0) return '—';
  return '$' + (+n).toFixed(2);
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

// ── Shared table styles ───────────────────────────────────────────────────────

const th = {
  textAlign: 'left',
  padding: '9px 12px',
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: '#475569',
  borderBottom: '1px solid #1e2330',
};

const td = {
  padding: '10px 12px',
  fontSize: 12,
  color: '#cbd5e1',
  borderBottom: '1px solid #131720',
  verticalAlign: 'top',
};

// ── Badge ─────────────────────────────────────────────────────────────────────

function Badge({ label, color }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 7px',
      borderRadius: 4,
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.05em',
      color,
      background: color + '18',
      border: `1px solid ${color}40`,
    }}>
      {label}
    </span>
  );
}

// ── Bias Summary bar ──────────────────────────────────────────────────────────

function BiasBar({ decisions }) {
  const total = decisions.length;
  if (total === 0) return null;

  const byDecision = { accepted: 0, declined: 0, deferred: 0 };
  const trimDecisions   = { accepted: 0, declined: 0, deferred: 0 };
  const addDecisions    = { accepted: 0, declined: 0, deferred: 0 };
  const reasonFreq      = {};

  for (const d of decisions) {
    byDecision[d.decision] = (byDecision[d.decision] ?? 0) + 1;

    const isTrim = ['EXIT', 'TRIM_CAP', 'TRIM_RATCHET', 'TRIM_MODEL'].includes(d.moveType);
    const isAdd  = ['ADD', 'INITIATE'].includes(d.moveType);
    if (isTrim) trimDecisions[d.decision] = (trimDecisions[d.decision] ?? 0) + 1;
    if (isAdd)  addDecisions[d.decision]  = (addDecisions[d.decision]  ?? 0) + 1;

    if (d.declinedReason) {
      const r = d.declinedReason.trim();
      reasonFreq[r] = (reasonFreq[r] ?? 0) + 1;
    }
  }

  const trimTotal      = Object.values(trimDecisions).reduce((s, n) => s + n, 0);
  const trimDeclineRate = trimTotal > 0
    ? Math.round((trimDecisions.declined + trimDecisions.deferred) / trimTotal * 100)
    : null;

  const addTotal       = Object.values(addDecisions).reduce((s, n) => s + n, 0);
  const addAcceptRate  = addTotal > 0
    ? Math.round(addDecisions.accepted / addTotal * 100)
    : null;

  const topReasons = Object.entries(reasonFreq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  return (
    <div style={{
      display: 'flex',
      gap: 16,
      marginBottom: 20,
      flexWrap: 'wrap',
    }}>
      {/* Total decisions */}
      <StatCard label="Total decisions" value={total}>
        <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
          {['accepted', 'declined', 'deferred'].map(d => (
            byDecision[d] > 0 && (
              <span key={d} style={{ fontSize: 11, color: decisionColor(d) }}>
                {byDecision[d]} {d}
              </span>
            )
          ))}
        </div>
      </StatCard>

      {/* Trim avoidance */}
      {trimTotal > 0 && (
        <StatCard
          label="Trim / Exit avoidance"
          value={trimDeclineRate != null ? `${trimDeclineRate}%` : '—'}
          valueColor={trimDeclineRate > 60 ? '#f87171' : trimDeclineRate > 30 ? '#f59e0b' : '#22c55e'}
        >
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
            of {trimTotal} trim recommendation{trimTotal !== 1 ? 's' : ''} not acted on
          </div>
        </StatCard>
      )}

      {/* Add acceptance */}
      {addTotal > 0 && (
        <StatCard
          label="Add acceptance rate"
          value={addAcceptRate != null ? `${addAcceptRate}%` : '—'}
          valueColor={addAcceptRate > 70 ? '#22c55e' : '#f59e0b'}
        >
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
            of {addTotal} add recommendation{addTotal !== 1 ? 's' : ''}
          </div>
        </StatCard>
      )}

      {/* Top decline reasons */}
      {topReasons.length > 0 && (
        <StatCard label="Top decline reasons" value={null}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
            {topReasons.map(([reason, count]) => (
              <div key={reason} style={{ fontSize: 11, color: '#94a3b8', display: 'flex', gap: 6, alignItems: 'baseline' }}>
                <span style={{ color: '#475569', flexShrink: 0 }}>{count}×</span>
                <span style={{ fontStyle: 'italic' }}>"{reason}"</span>
              </div>
            ))}
          </div>
        </StatCard>
      )}
    </div>
  );
}

function StatCard({ label, value, valueColor = '#f1f5f9', children }) {
  return (
    <div style={{
      background: '#0f1117',
      border: '1px solid #1e2330',
      borderRadius: 8,
      padding: '12px 16px',
      minWidth: 160,
      flex: '0 0 auto',
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: '#475569', marginBottom: 4 }}>
        {label}
      </div>
      {value != null && (
        <div style={{ fontSize: 22, fontWeight: 700, color: valueColor, lineHeight: 1.1 }}>
          {value}
        </div>
      )}
      {children}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DecisionAnalytics() {
  const { getToken } = useAuth();
  const [decisions, setDecisions] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);
  const [expanded,  setExpanded]  = useState(new Set());  // expanded ticker symbols
  const [filter,    setFilter]    = useState('all');       // all | declined | accepted | deferred

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/decisions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setDecisions(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => { load(); }, [load]);

  // Group decisions by ticker symbol, newest first within each group
  const groups = (() => {
    const map = new Map();
    for (const d of decisions) {
      if (!map.has(d.ticker.symbol)) map.set(d.ticker.symbol, []);
      map.get(d.ticker.symbol).push(d);
    }
    const result = [];
    for (const [symbol, rows] of map.entries()) {
      rows.sort((a, b) => new Date(b.decidedAt) - new Date(a.decidedAt));
      // Apply filter — if all rows are filtered out, skip the group entirely
      const filtered = filter === 'all' ? rows : rows.filter(r => r.decision === filter);
      if (filtered.length === 0) continue;
      result.push({ symbol, name: rows[0].ticker.name, rows: filtered, allRows: rows });
    }
    // Sort groups by most recent decision
    result.sort((a, b) => new Date(b.rows[0].decidedAt) - new Date(a.rows[0].decidedAt));
    return result;
  })();

  function toggleExpand(symbol) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  }

  const filteredDecisions = filter === 'all'
    ? decisions
    : decisions.filter(d => d.decision === filter);

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
          Track Record
        </h1>
        <span style={{ fontSize: 12, color: '#64748b' }}>
          {decisions.length} decision{decisions.length !== 1 ? 's' : ''} logged
        </span>
      </div>
      <p style={{ fontSize: 12, color: '#64748b', margin: '4px 0 20px', maxWidth: 700, lineHeight: 1.5 }}>
        Every recommendation acted on (or passed on) — with the price at decision time.
        Once a current-price feed is wired up, each row will show the P&amp;L impact of that call.
      </p>

      {/* Bias bar */}
      {!loading && !error && <BiasBar decisions={filteredDecisions} />}

      {/* Filter pills */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {['all', 'declined', 'accepted', 'deferred'].map(opt => (
          <button
            key={opt}
            onClick={() => setFilter(opt)}
            style={{
              background: filter === opt ? '#1e3a5f' : 'transparent',
              border: `1px solid ${filter === opt ? '#3b82f6' : '#2d3748'}`,
              borderRadius: 5,
              color: filter === opt ? '#93c5fd' : '#64748b',
              fontSize: 11, fontWeight: 600,
              padding: '4px 12px',
              cursor: 'pointer',
              textTransform: 'capitalize',
              letterSpacing: '0.04em',
            }}
          >
            {opt}
          </button>
        ))}
      </div>

      {loading && <div style={{ color: '#475569', fontSize: 13 }}>Loading…</div>}
      {error   && <div style={{ color: '#fca5a5', fontSize: 13 }}>Error: {error}</div>}

      {!loading && !error && groups.length === 0 && (
        <div style={{ color: '#475569', fontSize: 13, padding: '24px 0' }}>
          No decisions recorded yet. Accept or decline a recommendation in the Portfolio Manager to start building your track record.
        </div>
      )}

      {/* Per-ticker decision history */}
      {!loading && !error && groups.map(group => (
        <TickerGroup
          key={group.symbol}
          group={group}
          isExpanded={expanded.has(group.symbol)}
          onToggle={() => toggleExpand(group.symbol)}
        />
      ))}
    </div>
  );
}

// ── TickerGroup ───────────────────────────────────────────────────────────────

function TickerGroup({ group, isExpanded, onToggle }) {
  const latest = group.rows[0];
  const declinedCount = group.allRows.filter(r => r.decision === 'declined' || r.decision === 'deferred').length;
  const allDeclined   = group.allRows.length > 1 && declinedCount === group.allRows.length;

  return (
    <div style={{
      marginBottom: 8,
      background: '#0f1117',
      border: '1px solid #1e2330',
      borderRadius: 8,
      overflow: 'hidden',
    }}>
      {/* Ticker header row */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          cursor: 'pointer',
          background: isExpanded ? '#0d1120' : 'transparent',
          userSelect: 'none',
        }}
      >
        <span style={{ fontSize: 12, color: '#475569' }}>{isExpanded ? '▼' : '▶'}</span>
        <span style={{ color: '#93c5fd', fontWeight: 700, fontSize: 14, minWidth: 60 }}>
          {group.symbol}
        </span>
        <span style={{ fontSize: 11, color: '#64748b' }}>{group.name}</span>
        <span style={{ fontSize: 11, color: '#475569', marginLeft: 4 }}>
          {group.rows.length} decision{group.rows.length !== 1 ? 's' : ''}
        </span>
        {/* Alert: repeated non-actions on same ticker */}
        {allDeclined && (
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
            color: '#f87171', background: '#f8717118', border: '1px solid #f8717140',
            borderRadius: 4, padding: '2px 7px', marginLeft: 4,
          }}>
            ALL PASSED
          </span>
        )}
        {/* Latest decision summary */}
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Badge label={latest.decision.toUpperCase()} color={decisionColor(latest.decision)} />
          <span style={{ fontSize: 11, color: '#64748b' }}>{moveLabel(latest.moveType)}</span>
          {latest.systemSnapshot?.pricePerShare && (
            <span style={{ fontSize: 11, color: '#94a3b8' }}>
              @ {price(latest.systemSnapshot.pricePerShare)}
            </span>
          )}
          <span style={{ fontSize: 11, color: '#475569' }}>{fmtDate(latest.decidedAt)}</span>
        </span>
      </div>

      {/* Expanded decision table */}
      {isExpanded && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#090b11' }}>
              <th style={th}>Date</th>
              <th style={th}>Move</th>
              <th style={th}>Decision</th>
              <th style={{ ...th, textAlign: 'right' }}>$ Rec</th>
              <th style={{ ...th, textAlign: 'right' }}>Price at decision</th>
              <th style={{ ...th, textAlign: 'right' }}>Current price</th>
              <th style={{ ...th, textAlign: 'right' }}>Δ since decision</th>
              <th style={th}>Context</th>
              <th style={th}>Reason / notes</th>
            </tr>
          </thead>
          <tbody>
            {group.rows.map(d => (
              <DecisionRow key={d.id} d={d} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── DecisionRow ───────────────────────────────────────────────────────────────

function DecisionRow({ d }) {
  const snap     = d.systemSnapshot ?? {};
  const decPrice = snap.pricePerShare;
  // Current price: placeholder until Polygon.io is wired up
  const curPrice = null;

  const pctChange = decPrice && curPrice
    ? ((curPrice - decPrice) / decPrice) * 100
    : null;

  // For TRIM/EXIT: if user passed and price fell — that was a missed opportunity cost.
  // For ADD: if user passed and price rose — also missed.
  const isTrim      = ['EXIT', 'TRIM_CAP', 'TRIM_RATCHET', 'TRIM_MODEL'].includes(d.moveType);
  const passed      = d.decision === 'declined' || d.decision === 'deferred';
  const priceWentDown = pctChange != null && pctChange < 0;
  const priceWentUp   = pctChange != null && pctChange > 0;

  // Outcome: was the recommendation validated by subsequent price?
  // Trim declined + price fell = recommendation was right, user was wrong
  // Add declined  + price rose = recommendation was right, user was wrong
  const recWasRight = passed && (
    (isTrim && priceWentDown) || (!isTrim && priceWentUp)
  );
  const recWasWrong = passed && (
    (isTrim && priceWentUp) || (!isTrim && priceWentDown)
  );

  const deltaColor = pctChange == null ? '#64748b'
                   : recWasRight ? '#f87171'   // right rec, user was wrong — highlight red
                   : recWasWrong ? '#22c55e'   // rec was wrong — green (dodged)
                   : pctChange >= 0 ? '#22c55e'
                   : '#f87171';

  return (
    <tr style={{ background: '#0c0e18' }}>
      {/* Date */}
      <td style={{ ...td, color: '#94a3b8', whiteSpace: 'nowrap' }}>
        {fmtDate(d.decidedAt)}
      </td>
      {/* Move type */}
      <td style={td}>
        <Badge label={moveLabel(d.moveType)} color={moveColor(d.moveType)} />
      </td>
      {/* Decision */}
      <td style={td}>
        <Badge label={d.decision.toUpperCase()} color={decisionColor(d.decision)} />
      </td>
      {/* Recommended $ amount */}
      <td style={{ ...td, textAlign: 'right', color: '#64748b' }}>
        {snap.dollarAmount != null ? money(snap.dollarAmount) : '—'}
        {d.acceptedAmount != null && d.acceptedAmount !== snap.dollarAmount && (
          <div style={{ fontSize: 10, color: '#475569' }}>
            acted: {money(d.acceptedAmount)}
          </div>
        )}
      </td>
      {/* Price at decision */}
      <td style={{ ...td, textAlign: 'right', fontFamily: 'monospace', color: '#94a3b8' }}>
        {price(decPrice)}
      </td>
      {/* Current price (placeholder) */}
      <td style={{ ...td, textAlign: 'right', color: '#334155', fontStyle: 'italic', fontSize: 11 }}>
        —
      </td>
      {/* Δ */}
      <td style={{ ...td, textAlign: 'right', color: deltaColor, fontFamily: 'monospace' }}>
        {pctChange != null
          ? `${pctChange >= 0 ? '+' : ''}${pctChange.toFixed(1)}%`
          : <span style={{ color: '#334155', fontSize: 10, fontStyle: 'italic' }}>awaiting price feed</span>
        }
      </td>
      {/* Context from systemSnapshot */}
      <td style={td}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {snap.thesisHealth && (
            <span style={{ fontSize: 10, color: '#64748b' }}>
              thesis: <span style={{ color: '#94a3b8' }}>{snap.thesisHealth}</span>
            </span>
          )}
          {snap.trajectory && (
            <span style={{ fontSize: 10, color: '#64748b' }}>
              traj: <span style={{ color: '#94a3b8' }}>{snap.trajectory}</span>
            </span>
          )}
          {snap.currentPct != null && (
            <span style={{ fontSize: 10, color: '#64748b' }}>
              position: <span style={{ color: '#94a3b8' }}>{snap.currentPct.toFixed(1)}%</span>
            </span>
          )}
        </div>
      </td>
      {/* Decline reason / notes */}
      <td style={{ ...td, maxWidth: 240 }}>
        {d.declinedReason
          ? <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: 11 }}>"{d.declinedReason}"</span>
          : <span style={{ color: '#334155', fontSize: 11 }}>—</span>
        }
      </td>
    </tr>
  );
}
