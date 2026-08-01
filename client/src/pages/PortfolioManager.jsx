/**
 * PortfolioManager.jsx — Recommended Moves engine
 *
 * Actionable rebalancing plan per owner:
 *   - Portfolio summary bar (value, cash, barbell status)
 *   - Action-required moves (exits, trims, adds) with tax routing
 *   - Capital flow plan (freed → uses)
 *   - Watchlist promotion candidates ranked by signal quality
 *   - Holds (no action needed) and structural warnings
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';

// ─── Style tokens ─────────────────────────────────────────────────────────────

const C = {
  bg:      '#090c12',
  card:    '#0d1018',
  border:  '#1e2330',
  border2: '#252d3e',
  text:    '#f1f5f9',
  muted:   '#94a3b8',
  dim:     '#475569',
  faint:   '#334155',
  green:   '#34d399',
  blue:    '#60a5fa',
  amber:   '#f59e0b',
  red:     '#ef4444',
  purple:  '#a78bfa',
  slate:   '#64748b',
};

const MOVE_META = {
  EXIT:          { label: 'EXIT',     color: C.red    },
  TRIM_CAP:      { label: 'TRIM ⚑',  color: C.red    },
  TRIM_RATCHET:  { label: 'TRIM',     color: C.amber  },
  TRIM_SIGNAL:   { label: 'TRIM',     color: '#fbbf24'},
  TRIM_MODEL:    { label: 'TRIM',     color: C.amber  },
  ADD:           { label: 'ADD',      color: C.green  },
  HOLD:          { label: 'HOLD',     color: C.blue   },
  HOLD_ADVISORY: { label: 'ADVISORY', color: C.slate  },
};

const HEALTH_COLORS = {
  Strengthening: C.green,
  Intact:        C.blue,
  Weakening:     C.amber,
  Broken:        C.red,
};
const TRAJ_COLORS = {
  improving:     C.green,
  stable:        C.blue,
  flattening:    C.muted,
  softening:     C.amber,
  deteriorating: C.red,
  unknown:       C.faint,
};

// ─── Formatting ───────────────────────────────────────────────────────────────

function timeAgo(ts) {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function money(n) {
  if (n == null) return '—';
  const abs  = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  return sign + '$' + abs.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function pct(n, d = 1) {
  if (n == null) return '—';
  return n.toFixed(d) + '%';
}
function TaxLabel({ n }) {
  if (n == null) return '—';
  if (n === 0)   return <span style={{ color: C.green }}>$0 tax</span>;
  if (n < 0)     return <span style={{ color: C.green }}>+{money(-n)} harvest</span>;
  return <span style={{ color: C.amber }}>{money(n)} tax</span>;
}

// ─── Small UI atoms ───────────────────────────────────────────────────────────

function Badge({ label, color }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 7px',
      borderRadius: 4,
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
      background: color + '1a',
      border: `1px solid ${color}33`,
      color,
      whiteSpace: 'nowrap',
    }}>{label}</span>
  );
}

function TierChip({ tier }) {
  if (!tier) return null;
  const est = tier === 'established';
  return (
    <span style={{
      fontSize: 9,
      fontWeight: 700,
      padding: '1px 5px',
      borderRadius: 3,
      border: `1px solid ${est ? '#33415555' : '#78350f55'}`,
      color: est ? C.dim : C.amber,
      background: est ? C.border : '#78350f22',
      letterSpacing: '0.06em',
      marginLeft: 5,
    }}>
      {est ? 'EST' : 'SPEC'}
    </span>
  );
}

function SectionHeader({ title, count, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
      <span style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', color: color ?? C.muted }}>
        {title}
      </span>
      {count != null && (
        <span style={{
          fontSize: 10, fontWeight: 700,
          padding: '1px 6px', borderRadius: 10,
          background: (color ?? C.muted) + '22',
          color: color ?? C.muted,
        }}>{count}</span>
      )}
    </div>
  );
}

// ─── Tax routing detail (collapsible) ────────────────────────────────────────

function TaxRoutingDetail({ accounts }) {
  if (!accounts || accounts.length === 0) return null;
  return (
    <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${C.border}` }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: C.dim, letterSpacing: '0.06em', marginBottom: 6 }}>TAX ROUTING</div>
      {accounts.map((a, i) => (
        <div key={i} style={{
          display: 'flex', gap: 12, alignItems: 'center',
          padding: '5px 0',
          borderTop: i > 0 ? `1px solid ${C.border}` : 'none',
          fontSize: 12, flexWrap: 'wrap',
        }}>
          <span style={{ color: C.muted, minWidth: 150 }}>{a.accountName}</span>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
            color: a.isTaxAdvantaged ? C.green : C.dim,
            background: a.isTaxAdvantaged ? C.green + '15' : C.border,
          }}>
            {a.isTaxAdvantaged ? 'TAX-FREE' : a.accountType.toUpperCase()}
          </span>
          <span style={{ color: C.dim }}>{a.sharesToSell.toFixed(3)} shares</span>
          <span style={{ color: C.muted, fontWeight: 600 }}>{money(a.dollarAmount)}</span>
          <span style={{ marginLeft: 'auto' }}><TaxLabel n={a.taxCost} /></span>
          {!a.isTaxAdvantaged && (a.ltGain !== 0 || a.stGain !== 0) && (
            <span style={{ fontSize: 10, color: C.dim }}>
              LT {money(a.ltGain)} · ST {money(a.stGain)}
            </span>
          )}
          {a.roundedToWhole && (
            <span style={{ fontSize: 10, color: C.dim, width: '100%', marginTop: 2 }}>
              rounded to whole shares (fractional trading not enabled)
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Add routing detail (collapsible, mirrors TaxRoutingDetail for buys) ─────

function AddRoutingDetail({ accounts }) {
  if (!accounts || accounts.length === 0) return null;
  return (
    <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${C.border}` }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: C.dim, letterSpacing: '0.06em', marginBottom: 6 }}>BUY ROUTING</div>
      {accounts.map((a, i) => (
        <div key={i} style={{
          display: 'flex', gap: 12, alignItems: 'center',
          padding: '5px 0',
          borderTop: i > 0 ? `1px solid ${C.border}` : 'none',
          fontSize: 12, flexWrap: 'wrap',
        }}>
          <span style={{ color: C.muted, minWidth: 150 }}>{a.accountName}</span>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
            color: a.isTaxAdvantaged ? C.green : C.dim,
            background: a.isTaxAdvantaged ? C.green + '15' : C.border,
          }}>
            {a.isTaxAdvantaged ? 'TAX-SHELTERED' : a.accountType.toUpperCase()}
          </span>
          <span style={{ color: C.dim }}>{a.sharesToBuy.toFixed(3)} shares</span>
          <span style={{ color: C.muted, fontWeight: 600 }}>{money(a.dollarAmount)}</span>
          {a.insufficientCash && (
            <span style={{ marginLeft: 'auto', fontSize: 10, color: C.amber, fontWeight: 700 }}>
              ⚠ fund account first
            </span>
          )}
          {a.roundedToWhole && (
            <span style={{ fontSize: 10, color: C.dim, width: '100%', marginTop: 2 }}>
              rounded to whole shares (fractional trading not enabled)
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Allocation tab ───────────────────────────────────────────────────────────
// Current vs. target across the six buckets the engine already models
// (bucketOverride: etf/crypto/commodity, plus established/speculative equity
// tiers, plus cash). Data comes from `data.allocation` in the /api/moves
// payload — see server/routes/moves.js.

const BUCKET_COLORS = {
  established: C.blue,
  speculative: C.amber,
  etf:         C.purple,
  crypto:      C.green,
  commodity:   '#2dd4bf',
  cash:        C.slate,
};

function AllocationBar({ title, segments }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: C.dim, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
        {title}
      </div>
      <div style={{ display: 'flex', height: 40, borderRadius: 8, overflow: 'hidden', border: `1px solid ${C.border}`, background: C.bg }}>
        {segments.map(s => (
          <div
            key={s.key}
            title={`${s.label}: ${pct(s.pct)} · ${money(s.value)}`}
            style={{
              width: `${Math.max(s.pct, 0.6)}%`,
              background: s.color + '33',
              borderRight: `1px solid ${C.bg}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              overflow: 'hidden',
            }}
          >
            {s.pct > 8 && (
              <span style={{ fontSize: 10, fontWeight: 700, color: s.color, whiteSpace: 'nowrap' }}>
                {pct(s.pct, 0)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function AllocationView({ data }) {
  const alloc = data?.allocation;
  if (!alloc) return null;
  const total = data.totalPortfolioValue || 0;
  const accountSummaries = data.accountSummaries ?? [];

  const rows = alloc.buckets.map(b => {
    const currentPct  = total > 0 ? (b.currentValue / total) * 100 : 0;
    const targetValue = total * (b.targetPct / 100);
    return {
      ...b,
      color: BUCKET_COLORS[b.key] ?? C.muted,
      currentPct,
      targetValue,
      deltaPct: currentPct - b.targetPct,
    };
  });

  const gridCols = '18px 18px 1fr 110px 90px 110px 90px 90px';
  const holdingsByBucket = {};
  for (const h of alloc.holdings ?? []) {
    (holdingsByBucket[h.bucketKey] ??= []).push(h);
  }

  return (
    <div style={{ marginBottom: 24 }}>
      <AllocationBar title="Current allocation" segments={rows.map(r => ({ key: r.key, label: r.label, pct: r.currentPct, value: r.currentValue, color: r.color }))} />
      <AllocationBar title="Target allocation"  segments={rows.map(r => ({ key: r.key, label: r.label, pct: r.targetPct,  value: r.targetValue,  color: r.color }))} />

      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden', marginTop: 14 }}>
        <div style={{ display: 'grid', gridTemplateColumns: gridCols, padding: '9px 14px', borderBottom: `1px solid ${C.border}`, fontSize: 10, fontWeight: 700, color: C.dim, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          <div /><div />
          <div>Bucket</div>
          <div style={{ textAlign: 'right' }}>Current $</div>
          <div style={{ textAlign: 'right' }}>Current %</div>
          <div style={{ textAlign: 'right' }}>Target $</div>
          <div style={{ textAlign: 'right' }}>Target %</div>
          <div style={{ textAlign: 'right' }}>Δ</div>
        </div>
        {rows.map((r, i) => (
          <AllocationBucketRow
            key={r.key}
            row={r}
            idx={i}
            gridCols={gridCols}
            holdings={r.key === 'cash' ? null : (holdingsByBucket[r.key] ?? [])}
            accountSummaries={r.key === 'cash' ? accountSummaries : null}
          />
        ))}
      </div>

      <div style={{ fontSize: 11, color: C.faint, marginTop: 8 }}>
        Cash target reflects the {pct(alloc.cashReservePct, 0)} reserve floor — the other five buckets' targets are
        scaled down so all six sum to 100% of total portfolio value. See the Moves tab for the specific trades that
        close these gaps.
      </div>
    </div>
  );
}

function AllocationBucketRow({ row: r, idx, gridCols, holdings, accountSummaries }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = (holdings && holdings.length > 0) || (accountSummaries && accountSummaries.length > 0);

  return (
    <>
      <div
        onClick={() => hasDetail && setExpanded(e => !e)}
        style={{
          display: 'grid', gridTemplateColumns: gridCols, padding: '9px 14px', alignItems: 'center',
          fontSize: 12.5, borderTop: idx > 0 ? `1px solid ${C.border}` : 'none',
          background: idx % 2 ? C.bg + '60' : 'transparent',
          cursor: hasDetail ? 'pointer' : 'default',
        }}
      >
        <span style={{ color: C.faint, fontSize: 10 }}>{hasDetail ? (expanded ? '▼' : '▶') : ''}</span>
        <div style={{ width: 10, height: 10, borderRadius: 3, background: r.color }} />
        <div style={{ color: C.text, fontWeight: 600 }}>{r.label}</div>
        <div style={{ textAlign: 'right', color: C.muted }}>{money(r.currentValue)}</div>
        <div style={{ textAlign: 'right', color: C.muted }}>{pct(r.currentPct)}</div>
        <div style={{ textAlign: 'right', color: C.text }}>{money(r.targetValue)}</div>
        <div style={{ textAlign: 'right', color: C.text }}>{pct(r.targetPct)}</div>
        <div style={{
          textAlign: 'right', fontWeight: 700,
          color: Math.abs(r.deltaPct) <= 2 ? C.green : r.deltaPct > 0 ? C.amber : C.blue,
        }}>
          {r.deltaPct > 0 ? '+' : ''}{r.deltaPct.toFixed(1)}%
        </div>
      </div>

      {expanded && holdings && (
        <div style={{ gridColumn: '1 / -1', background: C.bg + '80', borderTop: `1px dashed ${C.border}`, padding: '8px 14px 10px 40px' }}>
          {holdings.map(h => (
            <div key={h.symbol} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '4px 0', fontSize: 12 }}>
              <span style={{ fontWeight: 700, color: C.text, minWidth: 60 }}>{h.symbol}</span>
              <span style={{ color: C.faint, flex: 1 }}>{h.shortName}</span>
              <span style={{ color: C.dim }}>{h.shares.toLocaleString(undefined, { maximumFractionDigits: 2 })} sh</span>
              <span style={{ color: C.muted, minWidth: 80, textAlign: 'right' }}>{money(h.mktValue)}</span>
              <span style={{ color: C.faint, minWidth: 50, textAlign: 'right' }}>{pct(h.currentPct)}</span>
            </div>
          ))}
        </div>
      )}

      {expanded && accountSummaries && (
        <div style={{ gridColumn: '1 / -1', background: C.bg + '80', borderTop: `1px dashed ${C.border}`, padding: '8px 14px 10px 40px' }}>
          {accountSummaries.filter(a => a.cashBalance > 0).map(a => (
            <div key={a.id} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '4px 0', fontSize: 12 }}>
              <span style={{ fontWeight: 700, color: C.text, flex: 1 }}>{a.name}</span>
              <span style={{ color: C.faint }}>{a.type}</span>
              <span style={{ color: C.muted, minWidth: 80, textAlign: 'right' }}>{money(a.cashBalance)}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

// ─── Move card ────────────────────────────────────────────────────────────────

// Diff table for Action Required — one grid track shared by the header and
// every row so columns line up. Each MoveRow returns a Fragment of direct
// grid children (no wrapping <div>) so CSS Grid lays multi-line rows
// (main line + optional full-width detail line) into the same column set.
const MOVE_GRID_COLS = '18px minmax(150px,1.4fr) 100px 100px 100px 90px 34px 200px';

function MoveTableHeader() {
  const th = { fontSize: 10, fontWeight: 700, color: C.dim, textTransform: 'uppercase', letterSpacing: '0.06em', padding: '0 4px 8px 4px' };
  return (
    <div style={{ gridColumn: '1 / -1', display: 'grid', gridTemplateColumns: MOVE_GRID_COLS, alignItems: 'end', borderBottom: `1px solid ${C.border}`, marginBottom: 4 }}>
      <div />
      <div style={th}>Ticker</div>
      <div style={{ ...th, textAlign: 'right' }}>Current</div>
      <div style={{ ...th, textAlign: 'right' }}>Target</div>
      <div style={{ ...th, textAlign: 'right' }}>Amount</div>
      <div style={{ ...th, textAlign: 'right' }}>Tax</div>
      <div />
      <div style={th}>Decision</div>
    </div>
  );
}

function MoveRow({ move, idx, decision, onAccept, onDecline }) {
  const [expanded,      setExpanded]      = useState(false);
  const [pendingAction, setPendingAction] = useState(null); // null | 'accept' | 'decline'
  const [inputAmount,   setInputAmount]   = useState('');
  const [inputReason,   setInputReason]   = useState('');
  const [submitting,    setSubmitting]    = useState(false);

  const meta      = MOVE_META[move.moveType] ?? MOVE_META.HOLD;
  const hasAccts  = move.accounts && move.accounts.length > 0;
  const isDecided = !!decision;
  const isEditing = pendingAction !== null;
  // Detail (signal badges / routing / decide-form) opens either because the
  // row was clicked to expand, or because Accept/Decline/Change was clicked.
  const showDetail = expanded || isEditing;

  async function confirmAccept() {
    setSubmitting(true);
    const amount = parseFloat(inputAmount) || move.dollarAmount;
    await onAccept(move, amount);
    setSubmitting(false);
    setPendingAction(null);
  }

  async function confirmDecline() {
    if (!inputReason.trim()) return;
    setSubmitting(true);
    await onDecline(move, inputReason.trim());
    setSubmitting(false);
    setPendingAction(null);
  }

  const rowBg = idx % 2 === 0 ? 'transparent' : C.card + '80';
  const cellBase = { padding: '9px 4px', borderTop: `1px solid ${C.border}`, background: rowBg, fontSize: 12.5 };

  return (
    <>
      {/* Main line */}
      <div
        style={{ ...cellBase, cursor: 'pointer', display: 'flex', alignItems: 'center' }}
        onClick={() => setExpanded(e => !e)}
      >
        <span style={{ color: C.faint, fontSize: 10 }}>{showDetail ? '▼' : '▶'}</span>
      </div>
      <div style={{ ...cellBase, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', cursor: 'pointer' }}
           onClick={() => setExpanded(e => !e)}>
        <Badge label={meta.label} color={meta.color} />
        <span style={{ fontWeight: 800, color: C.text }}>{move.symbol}</span>
        <TierChip tier={move.tier} />
        {move.isNewPosition && (
          <span title="Not currently held — opening a new position" style={{ fontSize: 9, fontWeight: 700, color: C.purple, border: `1px solid ${C.purple}55`, background: C.purple + '15', borderRadius: 3, padding: '1px 5px' }}>
            NEW
          </span>
        )}
      </div>
      <div style={{ ...cellBase, textAlign: 'right', color: C.muted }}>
        {move.currentShares != null ? move.currentShares.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—'}
      </div>
      <div style={{ ...cellBase, textAlign: 'right', color: C.text, fontWeight: 600 }}>
        {move.targetShares != null ? move.targetShares.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—'}
      </div>
      <div style={{ ...cellBase, textAlign: 'right', color: C.text, fontWeight: 600 }}>
        {money(move.dollarAmount)}
      </div>
      <div style={{ ...cellBase, textAlign: 'right' }}>
        <TaxLabel n={move.taxCost} />
      </div>
      <div style={{ ...cellBase, textAlign: 'center' }}>
        {move.requires48h && (
          <span title="48-hour waiting period (position above 30%)" style={{ fontSize: 9, color: '#fde68a', fontWeight: 700, background: '#71300015', border: '1px solid #ca8a0433', borderRadius: 4, padding: '1px 4px' }}>
            48h
          </span>
        )}
      </div>
      <div style={{ ...cellBase, display: 'flex', alignItems: 'center', gap: 6 }} onClick={e => e.stopPropagation()}>
        {isDecided && !isEditing ? (
          <>
            {decision.status === 'accepted' ? (
              <span style={{ color: C.green, fontWeight: 700, fontSize: 11 }}>✓ Accepted {money(decision.acceptedAmount)}</span>
            ) : (
              <span style={{ color: C.muted, fontWeight: 700, fontSize: 11 }}>✗ Declined</span>
            )}
            <button
              onClick={() => {
                setPendingAction(decision.status === 'accepted' ? 'accept' : 'decline');
                setInputAmount((decision.acceptedAmount ?? move.dollarAmount).toFixed(0));
                setInputReason(decision.declinedReason ?? '');
                setExpanded(true);
              }}
              style={{ background: 'none', border: 'none', color: C.faint, fontSize: 10, textDecoration: 'underline', cursor: 'pointer', padding: 0 }}
            >change</button>
          </>
        ) : !isEditing ? (
          <>
            <button
              onClick={() => { setPendingAction('accept'); setInputAmount(move.dollarAmount.toFixed(0)); setExpanded(true); }}
              style={{ padding: '3px 10px', borderRadius: 5, border: `1px solid ${C.green}55`, background: C.green + '15', color: C.green, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
            >✓ Accept</button>
            <button
              onClick={() => { setPendingAction('decline'); setInputReason(''); setExpanded(true); }}
              style={{ padding: '3px 10px', borderRadius: 5, border: `1px solid ${C.border2}`, background: 'transparent', color: C.muted, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
            >✗ Decline</button>
          </>
        ) : (
          <span style={{ fontSize: 11, color: C.dim }}>editing below…</span>
        )}
      </div>

      {/* Expanded detail — spans the full row width */}
      {showDetail && (
        <div style={{ gridColumn: '1 / -1', background: rowBg, borderTop: `1px dashed ${C.border}`, padding: '4px 4px 12px 34px' }}
             onClick={e => e.stopPropagation()}>

          {/* Signal detail */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 11, color: C.faint }}>{move.reason}</span>
            {move.thesisHealth && move.thesisHealth !== '—' && (
              <Badge label={move.thesisHealth} color={HEALTH_COLORS[move.thesisHealth] ?? C.muted} />
            )}
            {move.trajectory && (
              <span style={{ fontSize: 11, fontWeight: 600, color: TRAJ_COLORS[move.trajectory] ?? C.dim }}>{move.trajectory}</span>
            )}
            {move.ratchetTranche > 0 && (
              <span style={{ fontSize: 11, color: C.amber }}>ratchet {move.ratchetTranche}</span>
            )}
            {move.currentPct != null && (
              <span style={{ fontSize: 11, color: C.dim }}>
                {pct(move.currentPct)} current / {move.moveType === 'TRIM_MODEL' || move.moveType === 'ADD'
                  ? <>{pct(move.targetPct, 1)} model</> : <>{pct(move.hardCapPct, 0)} cap</>}
              </span>
            )}
          </div>

          {/* Prior decision note (only relevant if we're re-deciding and it differs from what's shown above) */}
          {move.priorDecision && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <span style={{ fontSize: 10, color: C.amber, fontWeight: 700 }}>
                LAST DECISION: {move.priorDecision.decision.toUpperCase()}
              </span>
              {move.priorDecision.reason && (
                <span style={{ fontSize: 11, color: C.faint, fontStyle: 'italic' }}>"{move.priorDecision.reason}"</span>
              )}
              <span style={{ fontSize: 10, color: C.dim }}>· {timeAgo(move.priorDecision.decidedAt)}</span>
            </div>
          )}

          {/* Account routing */}
          {hasAccts && (
            move.moveType === 'ADD'
              ? <AddRoutingDetail accounts={move.accounts} />
              : <TaxRoutingDetail accounts={move.accounts} />
          )}

          {/* Decide / revise forms */}
          {pendingAction === 'accept' && (
            <div style={{ paddingTop: 10 }}>
              <div style={{ fontSize: 11, color: C.dim, marginBottom: 6 }}>Amount to execute (edit to partially accept):</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 13, color: C.muted }}>$</span>
                <input
                  type="number"
                  value={inputAmount}
                  onChange={e => setInputAmount(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && confirmAccept()}
                  autoFocus
                  style={{ background: C.border, border: `1px solid ${C.border2}`, borderRadius: 4, color: C.text, fontSize: 13, padding: '4px 8px', width: 100 }}
                />
                <button onClick={confirmAccept} disabled={submitting}
                  style={{ padding: '4px 14px', borderRadius: 5, border: 'none', background: C.green, color: '#000', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
                >{submitting ? '…' : 'Confirm'}</button>
                <button onClick={() => setPendingAction(null)}
                  style={{ padding: '4px 10px', borderRadius: 5, border: `1px solid ${C.border2}`, background: 'transparent', color: C.dim, fontSize: 12, cursor: 'pointer' }}
                >Cancel</button>
              </div>
            </div>
          )}

          {pendingAction === 'decline' && (
            <div style={{ paddingTop: 10 }}>
              <div style={{ fontSize: 11, color: C.dim, marginBottom: 6 }}>Reason for declining:</div>
              <input
                type="text"
                value={inputReason}
                onChange={e => setInputReason(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && inputReason.trim() && confirmDecline()}
                placeholder="e.g. I think it will turn the corner next quarter"
                autoFocus
                style={{ background: C.border, border: `1px solid ${C.border2}`, borderRadius: 4, color: C.text, fontSize: 12, padding: '5px 10px', width: '100%', boxSizing: 'border-box', marginBottom: 8 }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={confirmDecline} disabled={submitting || !inputReason.trim()}
                  style={{ padding: '4px 14px', borderRadius: 5, border: `1px solid ${C.amber}55`, background: C.amber + '15', color: C.amber, fontSize: 12, fontWeight: 700, cursor: inputReason.trim() ? 'pointer' : 'not-allowed', opacity: inputReason.trim() ? 1 : 0.5 }}
                >{submitting ? '…' : 'Confirm Decline'}</button>
                <button onClick={() => setPendingAction(null)}
                  style={{ padding: '4px 10px', borderRadius: 5, border: `1px solid ${C.border2}`, background: 'transparent', color: C.dim, fontSize: 12, cursor: 'pointer' }}
                >Cancel</button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

// ─── Account buckets ──────────────────────────────────────────────────────────

const ACCT_TYPE_LABEL = {
  roth:      'ROTH IRA',
  ira:       'IRA',
  taxable:   'Taxable',
  custodial: 'Custodial',
};

function BucketBadge({ label, count, color }) {
  if (!count) return null;
  return (
    <span style={{
      fontSize: 11, fontWeight: 700,
      padding: '3px 8px', borderRadius: 4,
      background: color + '18',
      border: `1px solid ${color}33`,
      color,
    }}>
      {label} {count}
    </span>
  );
}

function AccountBuckets({ accountSummaries, moves, selected, onSelect }) {
  if (!accountSummaries || accountSummaries.length === 0) return null;

  // Group accounts by type (sum cash + mktValue across same-type accounts)
  const byType = {};
  for (const acct of accountSummaries) {
    if (!byType[acct.type]) byType[acct.type] = { cashBalance: 0, marketValue: 0 };
    byType[acct.type].cashBalance += acct.cashBalance;
    byType[acct.type].marketValue += acct.marketValue;
  }

  // Count actionable moves per account type.
  // ADD only counted if the account type has at least one routing row with cash.
  const countsByType = {};
  for (const move of moves) {
    const accountTypes = new Set((move.accounts || []).map(a => a.accountType));
    for (const type of accountTypes) {
      if (!countsByType[type]) countsByType[type] = { exit: 0, trim: 0, add: 0 };
      const rows = (move.accounts || []).filter(a => a.accountType === type);
      if (move.moveType === 'EXIT')              countsByType[type].exit++;
      else if (move.moveType.startsWith('TRIM')) countsByType[type].trim++;
      else if (move.moveType === 'ADD' && rows.some(a => !a.insufficientCash))
                                                 countsByType[type].add++;
    }
  }

  const types = Object.keys(byType);

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
      {types.map(type => {
        const info   = byType[type];
        const counts = countsByType[type] ?? { exit: 0, trim: 0, add: 0 };
        const isSel  = selected === type;
        const hasAction = counts.exit + counts.trim + counts.add > 0;

        return (
          <div
            key={type}
            onClick={() => onSelect(isSel ? null : type)}
            style={{
              flex: '1 1 170px',
              background: C.card,
              border: `1px solid ${isSel ? C.blue : C.border}`,
              borderRadius: 10,
              padding: '14px 16px',
              cursor: 'pointer',
              transition: 'border-color 0.15s',
            }}
          >
            <div style={{
              fontSize: 11, fontWeight: 800, letterSpacing: '0.08em',
              color: isSel ? C.blue : C.muted, marginBottom: 10,
            }}>
              {ACCT_TYPE_LABEL[type] ?? type.toUpperCase()}
            </div>

            <div style={{ display: 'flex', gap: 20, marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 9, color: C.faint, fontWeight: 700, letterSpacing: '0.06em', marginBottom: 2 }}>POSITIONS</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>{money(info.marketValue)}</div>
              </div>
              <div>
                <div style={{ fontSize: 9, color: C.faint, fontWeight: 700, letterSpacing: '0.06em', marginBottom: 2 }}>CASH</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>{money(info.cashBalance)}</div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <BucketBadge label="Exit" count={counts.exit} color={C.red}   />
              <BucketBadge label="Trim" count={counts.trim} color={C.amber} />
              <BucketBadge label="Add"  count={counts.add}  color={C.green} />
              {!hasAction && (
                <span style={{ fontSize: 11, color: C.faint }}>No action needed</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Capital flow (funded now / queue split) ──────────────────────────────────

function UseRow({ use, color }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '5px 0', borderBottom: `1px solid ${C.border}`, fontSize: 12,
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ color: C.muted }}>{use.label}</span>
        {use.status === 'partial' && (
          <span style={{ fontSize: 9, fontWeight: 700, color: C.amber, background: C.amber + '15',
            border: `1px solid ${C.amber}33`, borderRadius: 3, padding: '0 4px' }}>PARTIAL</span>
        )}
      </div>
      <div style={{ textAlign: 'right' }}>
        <span style={{ color: color ?? C.text, fontWeight: 600 }}>
          {use.status === 'partial' ? money(use.partialAmount) : money(use.dollarNeeded)}
        </span>
        {use.status === 'partial' && (
          <div style={{ fontSize: 10, color: C.dim }}>of {money(use.dollarNeeded)}</div>
        )}
      </div>
    </div>
  );
}

function CapitalFlow({ flow }) {
  if (!flow) return null;
  const hasSources  = flow.sources?.length > 0;
  const hasFunded   = flow.fundedNow?.length > 0;
  const hasQueued   = flow.queue?.length > 0;
  if (!hasSources && flow.freeCash <= 0 && !hasFunded && !hasQueued) return null;

  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: '18px 20px' }}>
      <SectionHeader title="Capital Flow" color={C.blue} />

      {/* Summary bar */}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 20 }}>
        <Metric label="FROM TRIMS"       value={money(flow.totalNetFreed)}  sub="net after tax" />
        <Metric label="FREE CASH"        value={money(flow.freeCash)}       sub="above reserve" />
        <div style={{ width: 1, background: C.border, alignSelf: 'stretch' }} />
        <Metric label="TOTAL DEPLOYABLE" value={money(flow.totalAvailable)} color={C.blue}
          sub={flow.freeCash <= 0 && flow.totalNetFreed > 0 ? 'after executing trims'
             : flow.freeCash > 0  && flow.totalNetFreed > 0 ? 'trims + free cash'
             : null} />
        {hasFunded && (
          <Metric label="DEPLOYED NOW"   value={money(flow.fundedNow.reduce((s, u) => s + (u.partialAmount ?? u.dollarNeeded), 0))}
            color={C.green} />
        )}
        {flow.surplusAfterFunded > 0 && (
          <Metric label="SURPLUS"        value={money(flow.surplusAfterFunded)} color={C.slate} />
        )}
        {hasQueued && (
          <Metric label="QUEUED"         value={money(flow.queueTotalNeeded)}
            color={C.amber} sub="needs new contribution" />
        )}
      </div>

      {/* 3-column layout: sources | funded now | queued */}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        {hasSources && (
          <div style={{ flex: 1, minWidth: 160 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: C.dim, letterSpacing: '0.06em', marginBottom: 8 }}>SOURCES</div>
            {flow.sources.map((s, i) => (
              <FlowRow key={i} label={s.label} amount={s.netFreed}
                sub={s.taxCost > 0 ? `−${money(s.taxCost)} tax` : s.taxCost < 0 ? `+${money(-s.taxCost)} harvest` : null}
                subColor={s.taxCost > 0 ? C.amber : C.green}
              />
            ))}
            {flow.freeCash > 0 && <FlowRow label="Free cash" amount={flow.freeCash} />}
          </div>
        )}

        {hasSources && (hasFunded || hasQueued) && (
          <div style={{ display: 'flex', alignItems: 'center', color: C.faint, fontSize: 18 }}>→</div>
        )}

        {hasFunded && (
          <div style={{ flex: 1, minWidth: 160 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: C.green, letterSpacing: '0.06em', marginBottom: 8 }}>
              FUNDED NOW
            </div>
            {flow.fundedNow.map((u, i) => (
              <UseRow key={i} use={u} color={C.green} />
            ))}
          </div>
        )}

        {hasQueued && (
          <div style={{ flex: 1, minWidth: 160 }}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: C.amber, letterSpacing: '0.06em' }}>QUEUE</div>
              <span style={{ fontSize: 9, color: C.dim }}>needs new capital</span>
            </div>
            {flow.queue.map((u, i) => (
              <UseRow key={i} use={u} color={C.dim} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, sub, color }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: C.dim, fontWeight: 700, letterSpacing: '0.07em', marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color ?? C.text }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: C.dim }}>{sub}</div>}
    </div>
  );
}

function FlowRow({ label, amount, sub, subColor }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: `1px solid ${C.border}`, fontSize: 12 }}>
      <div>
        <span style={{ color: C.muted }}>{label}</span>
        {sub && <span style={{ fontSize: 10, color: subColor ?? C.dim, marginLeft: 6 }}>{sub}</span>}
      </div>
      <span style={{ color: C.text, fontWeight: 600 }}>{money(amount)}</span>
    </div>
  );
}

// ─── Watchlist candidates ─────────────────────────────────────────────────────

// Watchlist candidates no longer render as a separate read-only section —
// they're folded directly into Action Required as real ADD moves (see
// server/routes/moves.js `openMoves`). A position moves from watchlist to
// portfolio as a *result* of accepting a move here, not as a prerequisite
// for the engine recommending it.

// ─── Holds ────────────────────────────────────────────────────────────────────

function HoldsList({ holds }) {
  if (!holds || holds.length === 0) return null;
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: '16px 20px' }}>
      <SectionHeader title="No Action Needed" count={holds.length} color={C.dim} />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {holds.map(h => (
          <div key={h.symbol} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: C.border, borderRadius: 6,
            padding: '5px 10px', fontSize: 12,
          }}>
            <span style={{ fontWeight: 700, color: C.text }}>{h.symbol}</span>
            <TierChip tier={h.tier} />
            {h.thesisHealth && h.thesisHealth !== '—' && (
              <span style={{ fontSize: 10, color: HEALTH_COLORS[h.thesisHealth] ?? C.dim }}>
                {h.thesisHealth}
              </span>
            )}
            {h.trajectory && (
              <span style={{ fontSize: 10, color: TRAJ_COLORS[h.trajectory] ?? C.dim }}>· {h.trajectory}</span>
            )}
            <span style={{ fontSize: 11, color: C.dim }}>{pct(h.currentPct)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Warnings ─────────────────────────────────────────────────────────────────

function WarningsList({ warnings, onAcceptWarning }) {
  if (!warnings || warnings.length === 0) return null;
  const SEV = {
    red:    { bg: '#450a0a22', border: '#991b1b55', text: '#f87171',  icon: '⚑' },
    amber:  { bg: '#78350f22', border: '#d9770655', text: '#fbbf24',  icon: '⚠' },
    yellow: { bg: '#71300022', border: '#ca8a0455', text: '#fde68a',  icon: '◎' },
    slate:  { bg: C.border,   border: C.border2,   text: C.muted,    icon: '○' },
  };
  return (
    <div>
      <SectionHeader title="Structural Flags" count={warnings.length} color={C.amber} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {warnings.map((w, i) => {
          const s = SEV[w.severity] ?? SEV.slate;
          const isActionable = w.actionType === 'update_position_target' && onAcceptWarning;
          return (
            <div key={i} style={{
              display: 'flex', gap: 10, padding: '10px 14px',
              background: s.bg, border: `1px solid ${s.border}`,
              borderRadius: 8, fontSize: 13, alignItems: 'center', flexWrap: 'wrap',
            }}>
              <span style={{ color: s.text, flexShrink: 0 }}>{s.icon}</span>
              <span style={{ color: s.text, flex: 1 }}>{w.message}</span>
              {isActionable && (
                <button
                  onClick={() => onAcceptWarning(w)}
                  style={{
                    padding: '4px 12px', borderRadius: 5, flexShrink: 0,
                    border: `1px solid ${C.green}55`, background: C.green + '15',
                    color: C.green, fontSize: 11, fontWeight: 700, cursor: 'pointer',
                  }}
                >
                  ✓ Set target to {w.suggestedTarget}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Portfolio summary bar ────────────────────────────────────────────────────

function PortfolioSummaryBar({ data }) {
  const bb = data.barbellStatus;
  return (
    <div style={{
      background: C.card,
      border: `1px solid ${C.border}`,
      borderRadius: 10,
      padding: '16px 24px',
      display: 'flex', gap: 28, alignItems: 'center', flexWrap: 'wrap',
      marginBottom: 24,
    }}>
      <div>
        <div style={{ fontSize: 10, color: C.dim, fontWeight: 700, letterSpacing: '0.07em', marginBottom: 3 }}>PORTFOLIO</div>
        <div style={{ fontSize: 22, fontWeight: 800, color: C.text }}>{money(data.totalPortfolioValue)}</div>
      </div>

      <div style={{ width: 1, height: 36, background: C.border }} />

      <div>
        <div style={{ fontSize: 10, color: C.dim, fontWeight: 700, letterSpacing: '0.07em', marginBottom: 3 }}>CASH</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: C.text }}>{money(data.totalCash)}</div>
        <div style={{ fontSize: 10, marginTop: 2 }}>
          <span style={{ color: C.amber }}>{money(data.cashReserveFloor)} floor</span>
          <span style={{ color: C.faint }}> · </span>
          <span style={{ color: data.freeCash > 0 ? C.green : C.dim }}>{money(data.freeCash)} available</span>
        </div>
      </div>

      <div style={{ width: 1, height: 36, background: C.border }} />

      <div>
        <div style={{ fontSize: 10, color: C.dim, fontWeight: 700, letterSpacing: '0.07em', marginBottom: 3 }}>POSITIONS</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: C.text }}>
          {data.positionCount}
          <span style={{ fontSize: 12, color: C.dim, fontWeight: 400 }}> / {data.maxPositions}</span>
        </div>
      </div>

      <div style={{ width: 1, height: 36, background: C.border }} />

      {bb.estPct != null && bb.specPct != null ? (
        <div>
          <div style={{ fontSize: 10, color: C.dim, fontWeight: 700, letterSpacing: '0.07em', marginBottom: 4 }}>
            BARBELL&nbsp;
            <span style={{ color: bb.inBalance ? C.green : C.amber }}>{bb.inBalance ? '✓' : '⚠'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, color: C.dim }}>EST {bb.estPct.toFixed(0)}%</span>
            <div style={{ position: 'relative', width: 110, height: 6, background: C.border, borderRadius: 3 }}>
              <div style={{ position: 'absolute', left: 0, top: 0, width: `${Math.min(100, bb.estPct)}%`, height: '100%', background: C.blue, borderRadius: 3 }} />
              <div style={{ position: 'absolute', top: -2, left: `${bb.estTarget}%`, width: 2, height: 10, background: C.dim, borderRadius: 1 }} />
            </div>
            <span style={{ fontSize: 11, color: bb.inBalance ? C.dim : C.amber }}>SPEC {bb.specPct.toFixed(0)}%</span>
          </div>
          <div style={{ fontSize: 10, color: C.faint, marginTop: 2 }}>
            target {bb.estTarget}/{bb.specTarget} · pool {bb.estPoolPct?.toFixed(0)}%/{bb.specPoolPct?.toFixed(0)}% avail
          </div>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: C.faint, fontStyle: 'italic' }}>barbell: tier data pending</div>
      )}
    </div>
  );
}

// ─── Deployable capital bar ───────────────────────────────────────────────────

function DeployableBar({ freeCash, cashReserveFloor, availableNow, decisions, moves }) {
  const acceptedCount = Object.values(decisions).filter(d => d.status === 'accepted').length;
  const declinedCount = Object.values(decisions).filter(d => d.status === 'declined').length;
  const decidedCount  = acceptedCount + declinedCount;

  return (
    <div style={{
      background: C.card, border: `1px solid ${C.border}`, borderRadius: 10,
      padding: '14px 24px', display: 'flex', gap: 24, alignItems: 'center',
      flexWrap: 'wrap', marginBottom: 16,
    }}>
      <div>
        <div style={{ fontSize: 10, color: C.dim, fontWeight: 700, letterSpacing: '0.07em', marginBottom: 3 }}>
          AVAILABLE TO DEPLOY
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: availableNow >= 0 ? C.green : C.red }}>
          {money(availableNow)}
        </div>
        <div style={{ fontSize: 10, color: C.faint }}>
          {money(freeCash)} free cash
          {acceptedCount > 0 && ` + accepted proceeds`}
        </div>
      </div>

      <div style={{ width: 1, height: 36, background: C.border }} />

      <div>
        <div style={{ fontSize: 10, color: C.dim, fontWeight: 700, letterSpacing: '0.07em', marginBottom: 3 }}>
          5% RESERVE
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: C.amber }}>{money(cashReserveFloor)}</div>
        <div style={{ fontSize: 10, color: C.faint }}>cash floor · do not deploy</div>
      </div>

      {decidedCount > 0 && (
        <>
          <div style={{ width: 1, height: 36, background: C.border }} />
          <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
            {acceptedCount > 0 && (
              <span style={{ fontSize: 12, color: C.green, fontWeight: 600 }}>✓ {acceptedCount} accepted</span>
            )}
            {declinedCount > 0 && (
              <span style={{ fontSize: 12, color: C.muted, fontWeight: 600 }}>✗ {declinedCount} declined</span>
            )}
            {moves.length - decidedCount > 0 && (
              <span style={{ fontSize: 12, color: C.faint }}>{moves.length - decidedCount} pending</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Owner selector ───────────────────────────────────────────────────────────

function OwnerSelector({ owners, selected, onSelect }) {
  if (owners.length <= 1) return null;
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
      {owners.map(o => (
        <button
          key={o.owner}
          onClick={() => onSelect(o.owner)}
          style={{
            padding: '6px 14px', borderRadius: 20,
            border: `1px solid ${selected === o.owner ? C.blue : C.border}`,
            background: selected === o.owner ? C.blue + '1a' : 'transparent',
            color: selected === o.owner ? C.blue : C.muted,
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}
        >
          {o.displayName}
        </button>
      ))}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function PortfolioManager() {
  const { getToken } = useAuth();

  const [owners,        setOwners]        = useState([]);
  const [selected,      setSelected]      = useState(null);
  const [data,          setData]          = useState(null);
  const [loading,       setLoading]       = useState(false);
  const [refreshing,    setRefreshing]    = useState(false);
  const [err,           setErr]           = useState('');
  const [selectedBucket, setSelectedBucket] = useState(null);
  const [view, setView] = useState('allocation'); // 'allocation' | 'moves'
  // Session decisions: key = `${symbol}-${moveType}` → { status, acceptedAmount?, declinedReason? }
  const [decisions, setDecisions] = useState({});

  // Reset decisions when the owner changes
  useEffect(() => { setDecisions({}); }, [selected]);

  // Load owner list once
  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        const r     = await fetch('/api/moves', { headers: { Authorization: `Bearer ${token}` } });
        const list  = await r.json();
        if (r.ok && list.length > 0) {
          setOwners(list);
          setSelected(list[0].owner);
        }
      } catch {
        setErr('Could not load owner list');
      }
    })();
  }, [getToken]);

  // Rebuild the `decisions` map from each move's `priorDecision` (server-side,
  // sourced from OwnerDecision — the actual DB record, not local-only state).
  // This is what makes accept/decline persist across page visits: the row
  // shows up already checked/unchecked with its reason on load, instead of
  // resetting to "undecided" and asking you to re-click through everything
  // you already decided last time.
  function hydrateDecisions(moves) {
    const next = {};
    for (const m of moves ?? []) {
      if (!m.priorDecision) continue;
      const key = `${m.symbol}-${m.moveType}`;
      next[key] = m.priorDecision.decision === 'accepted'
        ? { status: 'accepted', acceptedAmount: m.priorDecision.acceptedAmount ?? m.dollarAmount }
        : { status: 'declined', declinedReason: m.priorDecision.reason };
    }
    return next;
  }

  // Load moves for selected owner — serves from cache instantly
  const loadMoves = useCallback(async () => {
    if (!selected) return;
    setLoading(true);
    setErr('');
    try {
      const token = await getToken();
      const r     = await fetch(`/api/moves/${encodeURIComponent(selected)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Load failed');
      setData(d);
      setDecisions(hydrateDecisions(d.moves));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [selected, getToken]);

  // Force recompute — hits POST /:owner/refresh, replaces stale cache
  const forceRefresh = useCallback(async () => {
    if (!selected || refreshing) return;
    setRefreshing(true);
    setErr('');
    try {
      const token = await getToken();
      const r     = await fetch(`/api/moves/${encodeURIComponent(selected)}/refresh`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Refresh failed');
      setData(d);
      // Rehydrate from the DB record rather than blanking — a recompute
      // changes the move's numbers, not your prior decision on it.
      setDecisions(hydrateDecisions(d.moves));
    } catch (e) {
      setErr(e.message);
    } finally {
      setRefreshing(false);
    }
  }, [selected, refreshing, getToken]);

  // ── Decision handlers ──────────────────────────────────────────────────────

  const handleAccept = useCallback(async (move, amount) => {
    const key = `${move.symbol}-${move.moveType}`;
    try {
      const token = await getToken();
      await fetch('/api/decisions', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          symbol:        move.symbol,
          moveType:      move.moveType,
          decision:      'accepted',
          acceptedAmount: amount,
          systemSnapshot: {
            thesisHealth:    move.thesisHealth,
            trajectory:      move.trajectory,
            ratchetTranche:  move.ratchetTranche,
            currentPct:      move.currentPct,
            dollarAmount:    move.dollarAmount,
            pricePerShare:   move.pricePerShare ?? null,
          },
        }),
      });
    } catch (e) {
      console.error('Accept failed:', e);
    }
    setDecisions(prev => ({ ...prev, [key]: { status: 'accepted', acceptedAmount: amount } }));
  }, [getToken]);

  const handleDecline = useCallback(async (move, reason) => {
    const key = `${move.symbol}-${move.moveType}`;
    try {
      const token = await getToken();
      await fetch('/api/decisions', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          symbol:        move.symbol,
          moveType:      move.moveType,
          decision:      'declined',
          declinedReason: reason,
          systemSnapshot: {
            thesisHealth:    move.thesisHealth,
            trajectory:      move.trajectory,
            ratchetTranche:  move.ratchetTranche,
            currentPct:      move.currentPct,
            dollarAmount:    move.dollarAmount,
            pricePerShare:   move.pricePerShare ?? null,
          },
        }),
      });
    } catch (e) {
      console.error('Decline failed:', e);
    }
    setDecisions(prev => ({ ...prev, [key]: { status: 'declined', declinedReason: reason } }));
  }, [getToken]);

  const handleAcceptWarning = useCallback(async (warning) => {
    // Optimistically remove the warning from local state — no recompute needed.
    // Accepting a position target only creates/updates AccountPositionConfig to
    // suppress the warning; it doesn't affect move recommendations.
    setData(prev => prev ? {
      ...prev,
      warnings: (prev.warnings ?? []).filter(w =>
        !(w.type === warning.type && w.accountId === warning.accountId)
      ),
    } : prev);
    try {
      const token = await getToken();
      await fetch(`/api/moves/${encodeURIComponent(selected)}/account-config`, {
        method:  'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body:    JSON.stringify(warning.actionPayload),
      });
      // Server cache is invalidated by the PATCH — next hard refresh will reflect suppression.
    } catch (e) {
      console.error('Accept warning failed:', e);
    }
  }, [getToken, selected]);

  useEffect(() => { loadMoves(); }, [loadMoves]);

  const actionMoves = data?.moves ?? [];

  // ── Running totals (update as decisions are made) ──────────────────────────
  const IS_TRIM_OR_EXIT = new Set(['EXIT','TRIM_CAP','TRIM_RATCHET','TRIM_SIGNAL','TRIM_MODEL']);

  const acceptedProceedsTotal = actionMoves
    .filter(m => decisions[`${m.symbol}-${m.moveType}`]?.status === 'accepted' && IS_TRIM_OR_EXIT.has(m.moveType))
    .reduce((s, m) => {
      const d        = decisions[`${m.symbol}-${m.moveType}`];
      const accepted = d.acceptedAmount ?? m.dollarAmount;
      const ratio    = m.dollarAmount > 0 ? accepted / m.dollarAmount : 1;
      return s + (m.netProceeds * ratio);
    }, 0);

  const acceptedSpendTotal = actionMoves
    .filter(m => decisions[`${m.symbol}-${m.moveType}`]?.status === 'accepted' && m.moveType === 'ADD')
    .reduce((s, m) => {
      const d = decisions[`${m.symbol}-${m.moveType}`];
      return s + (d.acceptedAmount ?? m.dollarAmount);
    }, 0);

  const availableNow = (data?.freeCash ?? 0) + acceptedProceedsTotal - acceptedSpendTotal;

  // Returns true if a move is actionable in a given account type.
  // ADD moves require at least one routing row with actual cash (insufficientCash !== true).
  // TRIM/EXIT moves just need to touch that account type.
  function moveAppliesToBucket(move, accountType) {
    const rows = (move.accounts || []).filter(a => a.accountType === accountType);
    if (rows.length === 0) return false;
    if (move.moveType === 'ADD') return rows.some(a => !a.insufficientCash);
    return true;
  }

  // Filter moves to selected bucket; null = show all
  const displayMoves = selectedBucket
    ? actionMoves.filter(m => moveAppliesToBucket(m, selectedBucket))
    : actionMoves;

  return (
    <div style={{ maxWidth: 1000, margin: '32px auto', padding: '0 24px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: C.text }}>Portfolio Manager</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
            <p style={{ margin: 0, fontSize: 13, color: C.dim }}>
              Specific buy/sell amounts, tax routing, capital flow. Click any move to see account-level detail.
            </p>
            {data?.computedAt && (
              <span style={{ fontSize: 11, color: C.faint, whiteSpace: 'nowrap' }}>
                {data.fromCache ? 'cached' : 'fresh'} · {timeAgo(data.computedAt)}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={forceRefresh}
          disabled={refreshing || loading}
          title="Recompute recommendations"
          style={{ background: 'none', border: `1px solid ${C.border}`, color: refreshing ? C.green : C.dim, cursor: 'pointer', fontSize: 16, borderRadius: 6, padding: '6px 10px' }}
        >{refreshing ? '⟳' : '⟳'}</button>
      </div>

      <OwnerSelector owners={owners} selected={selected} onSelect={setSelected} />

      {loading && (
        <div style={{ color: C.dim, fontSize: 13, padding: '48px 0', textAlign: 'center' }}>Computing moves…</div>
      )}
      {err && !loading && (
        <div style={{ color: C.red, fontSize: 13 }}>{err}</div>
      )}

      {data && !loading && (
        <>
          <PortfolioSummaryBar data={data} />

          {/* Allocation / Moves tab switcher */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20, borderBottom: `1px solid ${C.border}` }}>
            {[
              { key: 'allocation', label: 'Allocation' },
              { key: 'moves',      label: `Recommended Moves${actionMoves.length ? ` (${actionMoves.length})` : ''}` },
            ].map(t => (
              <button
                key={t.key}
                onClick={() => setView(t.key)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  padding: '8px 4px 10px 4px', marginRight: 16,
                  fontSize: 13, fontWeight: 700,
                  color: view === t.key ? C.text : C.dim,
                  borderBottom: view === t.key ? `2px solid ${C.blue}` : '2px solid transparent',
                }}
              >{t.label}</button>
            ))}
          </div>

          {view === 'allocation' && <AllocationView data={data} />}

          {view === 'moves' && (
            <>
          {/* Structural flags — actionable/move-related only; the barbell-drift
              warning was retired since the Allocation tab shows that directly */}
          {data.warnings?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <WarningsList warnings={data.warnings} onAcceptWarning={handleAcceptWarning} />
            </div>
          )}

          {/* Deployable capital running total */}
          <DeployableBar
            freeCash={data.freeCash}
            cashReserveFloor={data.cashReserveFloor}
            availableNow={availableNow}
            decisions={decisions}
            moves={actionMoves}
          />

          {/* Account buckets */}
          <AccountBuckets
            accountSummaries={data.accountSummaries}
            moves={actionMoves}
            selected={selectedBucket}
            onSelect={setSelectedBucket}
          />

          {/* Actions — filtered by selected bucket when one is active */}
          <div style={{ marginBottom: 24 }}>
            <SectionHeader
              title={selectedBucket
                ? `${ACCT_TYPE_LABEL[selectedBucket] ?? selectedBucket} — Action Required`
                : 'Action Required'}
              count={displayMoves.length || undefined}
              color={
                displayMoves.some(m => m.moveType === 'EXIT')         ? C.red   :
                displayMoves.some(m => m.moveType.startsWith('TRIM')) ? C.amber :
                displayMoves.length > 0                               ? C.green :
                C.dim
              }
            />
            {displayMoves.length > 0
              ? (
                <div style={{ display: 'grid', gridTemplateColumns: MOVE_GRID_COLS, background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: '10px 12px 4px 12px' }}>
                  <MoveTableHeader />
                  {displayMoves.map((m, i) => (
                    <MoveRow
                      key={`${m.symbol}-${m.moveType}-${i}`}
                      move={m}
                      idx={i}
                      decision={decisions[`${m.symbol}-${m.moveType}`] ?? null}
                      onAccept={handleAccept}
                      onDecline={handleDecline}
                    />
                  ))}
                </div>
              )
              : (
                <div style={{
                  textAlign: 'center', padding: '22px 0',
                  background: C.card, border: `1px solid ${C.border}`, borderRadius: 10,
                  color: C.green, fontSize: 14, fontWeight: 600,
                }}>
                  ✓ No action required{selectedBucket ? ` in ${ACCT_TYPE_LABEL[selectedBucket] ?? selectedBucket}` : ''}
                </div>
              )
            }
          </div>

          {/* Advisories (HOLD_ADVISORY — winners running) */}
          {data.advisories?.length > 0 && (
            <div style={{ marginBottom: 24, padding: '14px 16px', background: C.card,
              border: `1px solid ${C.slate}44`, borderRadius: 10 }}>
              <SectionHeader title="Let Run" count={data.advisories.length} color={C.slate} />
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {data.advisories.map(a => (
                  <div key={a.symbol} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    background: C.border, borderRadius: 6, padding: '5px 10px', fontSize: 12,
                  }}>
                    <span style={{ fontWeight: 700, color: C.text }}>{a.symbol}</span>
                    <TierChip tier={a.tier} />
                    <span style={{ fontSize: 11, color: C.green }}>{pct(a.currentPct)}</span>
                    <span style={{ fontSize: 10, color: C.dim }}>→ cap {pct(a.hardCapPct, 0)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Holds */}
          {data.holds?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <HoldsList holds={data.holds} />
            </div>
          )}
            </>
          )}

          <div style={{ textAlign: 'right', fontSize: 11, color: C.faint }}>
            Generated {new Date().toLocaleTimeString()}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Table tokens ─────────────────────────────────────────────────────────────

const thSt = {
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
const tdSt = {
  padding: '10px 12px',
  verticalAlign: 'middle',
  color: '#94a3b8',
  textAlign: 'center',
};
