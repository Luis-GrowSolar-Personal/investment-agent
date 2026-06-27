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

// ─── Move card ────────────────────────────────────────────────────────────────

function MoveCard({ move, idx }) {
  const [expanded, setExpanded] = useState(false);
  const meta       = MOVE_META[move.moveType] ?? MOVE_META.HOLD;
  const hasAccts   = move.accounts && move.accounts.length > 0;

  return (
    <div style={{
      border: `1px solid ${meta.color}33`,
      borderLeft: `3px solid ${meta.color}`,
      borderRadius: 8,
      background: meta.color + '08',
      marginBottom: 10,
      overflow: 'hidden',
    }}>
      {/* Main row */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', cursor: hasAccts ? 'pointer' : 'default', flexWrap: 'wrap' }}
        onClick={() => hasAccts && setExpanded(e => !e)}
      >
        <span style={{ color: C.faint, fontSize: 11, flexShrink: 0, minWidth: 10 }}>
          {hasAccts ? (expanded ? '▼' : '▶') : ' '}
        </span>
        <span style={{ fontSize: 11, color: C.faint, minWidth: 18, textAlign: 'right', flexShrink: 0 }}>{idx + 1}.</span>
        <div style={{ flexShrink: 0 }}><Badge label={meta.label} color={meta.color} /></div>
        <span style={{ fontWeight: 800, fontSize: 14, color: C.text, flexShrink: 0 }}>{move.symbol}</span>
        <TierChip tier={move.tier} />
        <span style={{ fontSize: 12, color: C.muted, flex: 1, minWidth: 120 }}>{move.reason}</span>
        <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 'auto' }}>
          <span style={{ fontWeight: 700, fontSize: 15, color: C.text }}>{money(move.dollarAmount)}</span>
          {move.sharesApprox > 0 && (
            <div style={{ fontSize: 10, color: C.dim }}>~{move.sharesApprox.toFixed(2)} sh</div>
          )}
        </div>
        <div style={{ textAlign: 'right', minWidth: 80, flexShrink: 0 }}>
          <TaxLabel n={move.taxCost} />
        </div>
        {move.requires48h && (
          <span style={{ fontSize: 10, color: '#fde68a', fontWeight: 700, background: '#71300015', border: '1px solid #ca8a0433', borderRadius: 4, padding: '1px 6px', flexShrink: 0 }}>
            48h
          </span>
        )}
      </div>

      {/* Signal detail row */}
      <div style={{ display: 'flex', gap: 8, padding: '0 16px 10px 68px', flexWrap: 'wrap', alignItems: 'center' }}>
        {move.thesisHealth && move.thesisHealth !== '—' && (
          <Badge label={move.thesisHealth} color={HEALTH_COLORS[move.thesisHealth] ?? C.muted} />
        )}
        {move.trajectory && (
          <span style={{ fontSize: 11, fontWeight: 600, color: TRAJ_COLORS[move.trajectory] ?? C.dim }}>
            {move.trajectory}
          </span>
        )}
        {move.ratchetTranche > 0 && (
          <span style={{ fontSize: 11, color: C.amber }}>ratchet {move.ratchetTranche}</span>
        )}
        {move.currentPct != null && (
          <span style={{ fontSize: 11, color: C.dim }}>
            {pct(move.currentPct)} current
            {' / '}
            {move.moveType === 'TRIM_MODEL' || move.moveType === 'ADD'
              ? <>{pct(move.targetPct, 1)} model</>
              : <>{pct(move.hardCapPct, 0)} cap</>
            }
          </span>
        )}
      </div>

      {/* Expanded routing detail */}
      {expanded && hasAccts && (
        <div style={{ padding: '0 16px 14px 16px' }}>
          {move.moveType === 'ADD'
            ? <AddRoutingDetail accounts={move.accounts} />
            : <TaxRoutingDetail accounts={move.accounts} />
          }
        </div>
      )}
    </div>
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

  // Count moves per account type from routing
  const countsByType = {};
  for (const move of moves) {
    const types = new Set((move.accounts || []).map(a => a.accountType));
    for (const type of types) {
      if (!countsByType[type]) countsByType[type] = { exit: 0, trim: 0, add: 0 };
      if (move.moveType === 'EXIT')              countsByType[type].exit++;
      else if (move.moveType.startsWith('TRIM')) countsByType[type].trim++;
      else if (move.moveType === 'ADD')          countsByType[type].add++;
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

function WatchlistCandidates({ candidates }) {
  if (!candidates || candidates.length === 0) return null;

  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ padding: '18px 20px 12px' }}>
        <SectionHeader title="Watchlist Candidates" count={candidates.length} color={C.purple} />
        <div style={{ fontSize: 12, color: C.dim, marginTop: -6, marginBottom: 4 }}>
          Ranked by signal quality (trajectory + health + type + action)
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ background: '#0b0f18' }}>
              {['#', 'SYMBOL', 'TYPE', 'HEALTH', 'ACTION', 'TREND', 'SUGGESTED', 'SCORE'].map(h => (
                <th key={h} style={thSt}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {candidates.map((c, i) => (
              <tr key={c.tickerId} style={{ borderTop: `1px solid ${C.border}` }}>
                <td style={{ ...tdSt, color: C.faint }}>#{i + 1}</td>
                <td style={tdSt}>
                  <span style={{ fontWeight: 700, color: C.text }}>{c.symbol}</span>
                  <TierChip tier={c.tier} />
                </td>
                <td style={{ ...tdSt, color: C.dim }}>{c.type}</td>
                <td style={tdSt}>
                  {c.thesisHealth && c.thesisHealth !== '—'
                    ? <Badge label={c.thesisHealth} color={HEALTH_COLORS[c.thesisHealth] ?? C.muted} />
                    : <span style={{ color: C.faint }}>—</span>}
                </td>
                <td style={tdSt}>
                  <Badge label={c.finalAction} color={c.finalAction === 'Add' ? C.green : C.blue} />
                </td>
                <td style={tdSt}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: TRAJ_COLORS[c.trajectory] ?? C.dim }}>
                    {c.trajectory ?? '—'}
                  </span>
                </td>
                <td style={{ ...tdSt, textAlign: 'right' }}>
                  <div style={{ fontWeight: 600, color: C.text }}>{money(c.suggestedDollar)}</div>
                  <div style={{ fontSize: 10, color: C.dim }}>{pct(c.suggestedPct, 0)} of portfolio</div>
                </td>
                <td style={{ ...tdSt, textAlign: 'center' }}>
                  <span style={{
                    fontSize: 12, fontWeight: 700,
                    color: c.rankScore >= 12 ? C.green : c.rankScore >= 8 ? C.blue : C.dim,
                  }}>
                    {c.rankScore}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

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

function WarningsList({ warnings }) {
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
          return (
            <div key={i} style={{
              display: 'flex', gap: 10, padding: '10px 14px',
              background: s.bg, border: `1px solid ${s.border}`,
              borderRadius: 8, fontSize: 13,
            }}>
              <span style={{ color: s.text, flexShrink: 0 }}>{s.icon}</span>
              <span style={{ color: s.text }}>{w.message}</span>
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
    } catch (e) {
      setErr(e.message);
    } finally {
      setRefreshing(false);
    }
  }, [selected, refreshing, getToken]);

  useEffect(() => { loadMoves(); }, [loadMoves]);

  const actionMoves = data?.moves ?? [];

  // Filter moves to selected bucket; null = show all
  const displayMoves = selectedBucket
    ? actionMoves.filter(m => m.accounts?.some(a => a.accountType === selectedBucket))
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
              ? displayMoves.map((m, i) => (
                  <MoveCard key={`${m.symbol}-${m.moveType}-${i}`} move={m} idx={i} />
                ))
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

          {/* Capital flow */}
          {(data.capitalFlow?.sources?.length > 0 ||
            data.capitalFlow?.fundedNow?.length > 0 ||
            data.capitalFlow?.queue?.length > 0) && (
            <div style={{ marginBottom: 24 }}>
              <CapitalFlow flow={data.capitalFlow} />
            </div>
          )}

          {/* Watchlist candidates */}
          {data.watchlistCandidates?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <WatchlistCandidates candidates={data.watchlistCandidates} />
            </div>
          )}

          {/* Holds */}
          {data.holds?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <HoldsList holds={data.holds} />
            </div>
          )}

          {/* Warnings */}
          {data.warnings?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <WarningsList warnings={data.warnings} />
            </div>
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
