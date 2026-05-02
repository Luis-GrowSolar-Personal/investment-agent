import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { useLocation } from 'react-router-dom';

// API origin: dev reads from .env.development (${API_URL}).
// Prod reads from .env.production (empty string → same-origin).
const API_URL = import.meta.env.VITE_API_URL || '';

// Reuse the same color helpers + Badge as Radar — keep visual language
// consistent across the two pages. We import them rather than re-define
// to avoid drift if Radar ever updates its palette.
//
// Importing from a sibling page is unusual — could be cleaner to extract
// a shared module later. For now this keeps the diff small and the
// chip logic in one place.

function healthColor(value) {
  if (!value) return '#64748b';
  switch (value.toLowerCase()) {
    case 'strengthening': return '#22c55e';
    case 'intact':        return '#60a5fa';
    case 'weakening':     return '#f59e0b';
    case 'broken':        return '#ef4444';
    default:              return '#64748b';
  }
}

function recColor(value) {
  if (!value) return '#64748b';
  switch (value.toLowerCase()) {
    case 'add':  return '#22c55e';
    case 'hold': return '#60a5fa';
    case 'trim': return '#f59e0b';
    case 'exit': return '#ef4444';
    default:     return '#64748b';
  }
}

function trajectoryColor(value) {
  if (!value) return '#64748b';
  switch (value.toLowerCase()) {
    case 'improving':     return '#22c55e';
    case 'stable':        return '#64748b';
    case 'flattening':    return '#06b6d4';
    case 'softening':     return '#f59e0b';
    case 'deteriorating': return '#ef4444';
    case 'unknown':       return '#475569';
    default:              return '#64748b';
  }
}

function Badge({ value, color }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: '0.05em',
      color,
      background: color + '18',
      border: `1px solid ${color}40`,
    }}>
      {value ?? '—'}
    </span>
  );
}

function TierChip({ tier }) {
  if (!tier) return null;
  const isSpec = tier === 'speculative';
  const color = isSpec ? '#f59e0b' : '#64748b';
  const label = isSpec ? 'SPEC' : 'EST';
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 5px',
      borderRadius: 3,
      fontSize: 9,
      fontWeight: 700,
      letterSpacing: '0.08em',
      color,
      background: color + '14',
      border: `1px solid ${color}30`,
    }}>{label}</span>
  );
}

const th = {
  textAlign: 'left',
  padding: '10px 12px',
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: '#475569',
  borderBottom: '1px solid #1e2330',
};

const td = {
  padding: '12px',
  fontSize: 13,
  color: '#cbd5e1',
  borderBottom: '1px solid #1e2330',
  verticalAlign: 'middle',
};

let advisoryCache = null;
// Cache the rawOutput per analysisId across expand/collapse cycles so we
// don't re-fetch when the user toggles the same row.
const rawOutputCache = new Map();

// Pull just the THESIS HEALTH and RECOMMENDATION sections out of the v6
// evaluator's full rawOutput. These are what the user wants to read for
// the "why" — the analyst's actual prose about the call.
function extractAnalystSection(text, sectionName) {
  if (!text) return null;
  const re = new RegExp(`##\\s+${sectionName}\\s*\\n([\\s\\S]*?)(?=\\n##|$)`, 'i');
  const m = text.match(re);
  return m ? m[1].trim() : null;
}

// Short, scannable phrase explaining what the trend layer decided and why.
// The verbose rationale is in the expand panel; this is the at-a-glance
// version for the Final column. Derived purely from data shape — no
// natural-language parsing required.
function shortReason({ trajectory, thesisHealth, suggestedOverride, perCallRec, finalAction }) {
  const flipped = finalAction && perCallRec && finalAction !== perCallRec;
  if (flipped) {
    if (suggestedOverride === 'trim_regardless') return 'multi-quarter softening';
    if (suggestedOverride === 'downgrade_one') return 'two-quarter softening';
    if (suggestedOverride === 'upgrade_one') return 'improving inflection';
    return 'override fired';
  }
  // No override case
  if (trajectory === 'softening' && thesisHealth === 'Strengthening') {
    return 'thesis still Strengthening';
  }
  if (trajectory === 'softening') return 'isolated soft signal';
  if (trajectory === 'flattening') return 'thesis maturing — awaits Layer 3 rotation target';
  if (trajectory === 'improving') return 'awaiting 2nd improving quarter (established tier)';
  if (trajectory === 'deteriorating' && (thesisHealth === 'Weakening' || thesisHealth === 'Broken')) {
    return 'analyst already calling Weakening — defer to ratchet';
  }
  if (trajectory === 'deteriorating') return 'soft pattern but action floored';
  if (trajectory === 'stable') return 'no trajectory signal';
  return '';
}

export default function AdvisoryFeed() {
  const { getToken } = useAuth();
  const location = useLocation();
  const [rows, setRows] = useState(advisoryCache ?? []);
  const [loading, setLoading] = useState(advisoryCache === null);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all'); // all | portfolio | watchlist
  // sortMode: 'date' (latest advisory date desc per ticker) or 'symbol' (alpha)
  const [sortMode, setSortMode] = useState('date');
  // Two levels of expansion: ticker-row → reveal all that ticker's advisory
  // calls; individual call → reveal verbose rationale panel.
  const [expandedTickers, setExpandedTickers] = useState(new Set());
  const [expandedId, setExpandedId] = useState(null);
  const [expandedRaw, setExpandedRaw] = useState({}); // analysisId → { thesisHealth, recommendation, loading, error }
  const rowRefs = useRef({});

  const fetchAdvisories = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/radar/advisories`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      advisoryCache = data;
      setRows(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchAdvisories({ silent: advisoryCache !== null });
  }, [fetchAdvisories]);

  // When the user lands on this page with ?focus=<analysisId> (from a Radar
  // trend-chip click), expand the matching ticker, expand the matching call,
  // and scroll the call into view.
  useEffect(() => {
    if (loading || rows.length === 0) return;
    const params = new URLSearchParams(location.search);
    const focusId = params.get('focus');
    if (!focusId) return;
    const id = parseInt(focusId, 10);
    if (Number.isNaN(id)) return;
    const target = rows.find(r => r.analysisId === id);
    if (!target) return;
    setExpandedTickers(prev => {
      const next = new Set(prev);
      next.add(target.symbol);
      return next;
    });
    setExpandedId(id);
    loadRaw(target);
    setTimeout(() => {
      const node = rowRefs.current[id];
      if (node) node.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 150);
  }, [loading, rows, location.search]);

  // Lazy-load the analyst rawOutput when a row is expanded. Reuses the
  // existing /api/radar/transcripts/:id endpoint which returns the latest
  // analysis's rawOutput.
  async function loadRaw(row) {
    const aid = row.analysisId;
    if (rawOutputCache.has(aid)) {
      setExpandedRaw(prev => ({ ...prev, [aid]: rawOutputCache.get(aid) }));
      return;
    }
    setExpandedRaw(prev => ({ ...prev, [aid]: { loading: true } }));
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/radar/transcripts/${row.transcriptId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      const raw = data.analysis?.rawOutput || '';
      const parsed = {
        thesisHealth: extractAnalystSection(raw, 'THESIS HEALTH'),
        recommendation: extractAnalystSection(raw, 'RECOMMENDATION'),
        loading: false,
      };
      rawOutputCache.set(aid, parsed);
      setExpandedRaw(prev => ({ ...prev, [aid]: parsed }));
    } catch (err) {
      setExpandedRaw(prev => ({ ...prev, [aid]: { error: err.message, loading: false } }));
    }
  }

  function toggleTicker(symbol) {
    setExpandedTickers(prev => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  }

  function toggleExpand(row) {
    if (expandedId === row.analysisId) {
      setExpandedId(null);
    } else {
      setExpandedId(row.analysisId);
      loadRaw(row);
    }
  }

  const filtered = rows.filter(r => {
    if (statusFilter === 'all') return true;
    return r.tickerStatus === statusFilter;
  });

  // Group all advisories by ticker symbol. Each ticker shows once at the
  // top level (with its latest advisory's data); expanding reveals all of
  // that ticker's advisory calls newest-first.
  const tickerGroups = (() => {
    const grouped = new Map();
    for (const r of filtered) {
      if (!grouped.has(r.symbol)) grouped.set(r.symbol, []);
      grouped.get(r.symbol).push(r);
    }
    const entries = [];
    for (const [symbol, calls] of grouped.entries()) {
      // Newest first within ticker
      calls.sort((a, b) => new Date(b.callDate) - new Date(a.callDate));
      const latest = calls[0];
      entries.push({
        symbol,
        latest,
        calls,
        latestTime: new Date(latest.callDate).getTime(),
        // Carry through ticker-level static data
        tier: latest.tier,
        shortName: latest.shortName,
        tickerStatus: latest.tickerStatus,
      });
    }
    // Sort ticker groups by current sort mode
    entries.sort((a, b) => {
      if (sortMode === 'symbol') {
        return a.symbol.localeCompare(b.symbol);
      } else {
        // Date: tickers ordered by their latest advisory's date desc;
        // ties broken by symbol asc
        const cmp = b.latestTime - a.latestTime;
        return cmp !== 0 ? cmp : a.symbol.localeCompare(b.symbol);
      }
    });
    return entries;
  })();

  // Surfacing the trajectory mix at a glance — these are the cases worth
  // periodically scanning for emerging heuristics
  const trajectoryCounts = filtered.reduce((acc, r) => {
    acc[r.trajectory] = (acc[r.trajectory] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
          Advisory Feed
        </h1>
        <span style={{ fontSize: 12, color: '#64748b' }}>
          {tickerGroups.length} ticker{tickerGroups.length === 1 ? '' : 's'}
          {' · '}
          {filtered.length} advisory call{filtered.length === 1 ? '' : 's'} total
        </span>
      </div>
      <p style={{ fontSize: 12, color: '#64748b', margin: '4px 0 18px', maxWidth: 720, lineHeight: 1.5 }}>
        Calls where the trend layer noticed a non-stable trajectory but did not flip
        the per-call recommendation. Worth periodic review for emerging patterns —
        when a heuristic appears, we can encode it as a new rule in the trend layer.
      </p>

      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
        {['all', 'portfolio', 'watchlist'].map(opt => (
          <button
            key={opt}
            onClick={() => setStatusFilter(opt)}
            style={{
              background: statusFilter === opt ? '#1e3a5f' : 'transparent',
              border: `1px solid ${statusFilter === opt ? '#3b82f6' : '#2d3748'}`,
              borderRadius: 5,
              color: statusFilter === opt ? '#93c5fd' : '#64748b',
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
        {Object.keys(trajectoryCounts).length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto', fontSize: 11, color: '#64748b' }}>
            {['deteriorating', 'softening', 'flattening', 'improving', 'stable'].map(traj => {
              const n = trajectoryCounts[traj] || 0;
              if (!n) return null;
              return (
                <span key={traj} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: trajectoryColor(traj), display: 'inline-block',
                  }} />
                  <span>{traj} {n}</span>
                </span>
              );
            })}
          </div>
        )}
      </div>

      {loading && <div style={{ color: '#475569', fontSize: 13 }}>Loading…</div>}
      {error && <div style={{ color: '#fca5a5', fontSize: 13 }}>Error: {error}</div>}
      {!loading && !error && filtered.length === 0 && (
        <div style={{ color: '#475569', fontSize: 13, padding: '24px 0' }}>
          No advisory rows
          {statusFilter !== 'all' ? ` in ${statusFilter}` : ''}
          . Either there are no analyses yet or every call has a stable trajectory or
          a confident override.
        </div>
      )}

      {!loading && !error && tickerGroups.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', background: '#0f1117', borderRadius: 6, overflow: 'hidden' }}>
          <thead>
            <tr>
              <th style={{ ...th, width: 24 }}></th>
              <th
                onClick={() => setSortMode('symbol')}
                title="Sort tickers alphabetically (A→Z)"
                style={{
                  ...th,
                  cursor: 'pointer',
                  color: sortMode === 'symbol' ? '#cbd5e1' : '#475569',
                  userSelect: 'none',
                }}
              >
                Symbol
                {sortMode === 'symbol' && (
                  <span style={{ marginLeft: 4, fontSize: 10, color: '#3b82f6' }}>↑</span>
                )}
              </th>
              <th
                onClick={() => setSortMode('date')}
                title="Sort tickers by their latest advisory date (newest first)"
                style={{
                  ...th,
                  cursor: 'pointer',
                  color: sortMode === 'date' ? '#cbd5e1' : '#475569',
                  userSelect: 'none',
                }}
              >
                Date
                {sortMode === 'date' && (
                  <span style={{ marginLeft: 4, fontSize: 10, color: '#3b82f6' }}>↓</span>
                )}
              </th>
              <th style={th}>Per-call</th>
              <th style={th}>Trajectory</th>
              <th style={th}>Final</th>
            </tr>
          </thead>
          <tbody>
            {tickerGroups.flatMap(group =>
              renderTickerGroup(group, {
                expandedTickers, expandedId, expandedRaw,
                toggleTicker, toggleExpand, rowRefs,
              })
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Render helpers ─────────────────────────────────────────────────────────

// Render one ticker group: a header row + (when ticker is expanded) a
// sub-row per individual advisory call + (when a call is selected) the
// verbose Trend Verdict + Analyst Narrative panel.
function renderTickerGroup(group, ctx) {
  const { expandedTickers, expandedId, expandedRaw,
          toggleTicker, toggleExpand, rowRefs } = ctx;
  const isTickerExpanded = expandedTickers.has(group.symbol);
  const result = [];

  // Top-level ticker header row, showing latest advisory's data
  result.push(renderTickerHeaderRow(group, {
    isExpanded: isTickerExpanded,
    onToggle: () => toggleTicker(group.symbol),
  }));

  if (!isTickerExpanded) return result;

  // Expanded: render every advisory call for this ticker as a sub-row,
  // newest first. Each call's row is also expandable to show the verbose
  // Trend Verdict + Analyst Narrative panel.
  for (const call of group.calls) {
    const isCallExpanded = expandedId === call.analysisId;
    result.push(renderCallSubRow(call, {
      isCallExpanded,
      onToggle: () => toggleExpand(call),
      rowRefs,
    }));
    if (isCallExpanded) {
      result.push(renderRationalePanel(call, expandedRaw[call.analysisId]));
    }
  }
  return result;
}

function renderTickerHeaderRow(group, { isExpanded, onToggle }) {
  const latest = group.latest;
  const flipped = latest.finalAction && latest.perCallRec
                    && latest.finalAction !== latest.perCallRec;
  return (
    <tr
      key={`t-${group.symbol}`}
      onClick={onToggle}
      style={{
        cursor: 'pointer',
        background: isExpanded ? '#0d1120' : 'transparent',
        borderTop: '1px solid #1e2330',
      }}
    >
      <td style={{ ...td, color: '#475569', fontSize: 10, textAlign: 'center', width: 24 }}>
        {isExpanded ? '▼' : '▶'}
      </td>
      <td style={td}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: '#93c5fd', fontWeight: 700, fontSize: 13 }}>
            {group.symbol}
          </span>
          <TierChip tier={group.tier} />
          <span style={{ color: '#64748b', fontSize: 11 }}>
            {group.shortName ?? ''}
          </span>
          <span style={{ color: '#475569', fontSize: 10, marginLeft: 4 }}>
            {group.calls.length} advisor{group.calls.length === 1 ? 'y' : 'ies'}
          </span>
        </span>
      </td>
      <td style={{ ...td, color: '#94a3b8', fontSize: 12, whiteSpace: 'nowrap' }}>
        {new Date(latest.callDate).toLocaleDateString('en-US', {
          year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
        })}
      </td>
      <td style={td}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Badge value={latest.perCallRec} color={recColor(latest.perCallRec)} />
          {latest.thesisHealth && (
            <span style={{ fontSize: 10, color: healthColor(latest.thesisHealth), letterSpacing: '0.04em' }}>
              {latest.thesisHealth.toUpperCase()}
            </span>
          )}
        </span>
      </td>
      <td style={td}>
        <Badge value={latest.trajectory} color={trajectoryColor(latest.trajectory)} />
      </td>
      <td style={td}>
        {renderFinalCell(latest, flipped)}
      </td>
    </tr>
  );
}

function renderCallSubRow(call, { isCallExpanded, onToggle, rowRefs }) {
  const flipped = call.finalAction && call.perCallRec
                    && call.finalAction !== call.perCallRec;
  return (
    <tr
      key={`c-${call.analysisId}`}
      ref={node => { if (node) rowRefs.current[call.analysisId] = node; }}
      onClick={(e) => { e.stopPropagation(); onToggle(); }}
      style={{
        cursor: 'pointer',
        background: isCallExpanded ? '#0a0d14' : '#10131c',
        transition: 'background 0.15s',
      }}
    >
      <td style={{ ...td, color: '#475569', fontSize: 10, textAlign: 'center', width: 24 }}>
        {isCallExpanded ? '▾' : '▸'}
      </td>
      <td style={{ ...td, paddingLeft: 28, color: '#475569', fontSize: 11 }}>
        ↳
      </td>
      <td style={{ ...td, color: '#94a3b8', fontSize: 12, whiteSpace: 'nowrap' }}>
        {new Date(call.callDate).toLocaleDateString('en-US', {
          year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
        })}
      </td>
      <td style={td}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Badge value={call.perCallRec} color={recColor(call.perCallRec)} />
          {call.thesisHealth && (
            <span style={{ fontSize: 10, color: healthColor(call.thesisHealth), letterSpacing: '0.04em' }}>
              {call.thesisHealth.toUpperCase()}
            </span>
          )}
        </span>
      </td>
      <td style={td}>
        <Badge value={call.trajectory} color={trajectoryColor(call.trajectory)} />
      </td>
      <td style={td}>
        {renderFinalCell(call, flipped)}
      </td>
    </tr>
  );
}

// The "Final" cell — show the kept/overridden action plus a short reason
// phrase derived from the rule that fired. Verbose explanation lives in
// the expand panel.
function renderFinalCell(row, flipped) {
  const reason = shortReason({
    trajectory: row.trajectory,
    thesisHealth: row.thesisHealth,
    suggestedOverride: row.suggestedOverride,
    perCallRec: row.perCallRec,
    finalAction: row.finalAction,
  });
  return (
    <span style={{ display: 'inline-flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        {flipped ? (
          <>
            <Badge value={row.finalAction} color={recColor(row.finalAction)} />
            <span style={{ fontSize: 10, color: '#fbbf24', letterSpacing: '0.04em' }}>
              override
            </span>
          </>
        ) : (
          <span style={{ fontSize: 11, color: '#94a3b8' }}>
            kept <strong style={{ color: recColor(row.perCallRec) }}>{row.perCallRec}</strong>
          </span>
        )}
      </span>
      {reason && (
        <span style={{ fontSize: 10, color: '#64748b', fontStyle: 'italic' }}>
          {reason}
        </span>
      )}
    </span>
  );
}

function renderRationalePanel(call, expanded) {
  const flipped = call.finalAction && call.perCallRec
                    && call.finalAction !== call.perCallRec;
  return (
    <tr key={`p-${call.analysisId}`} style={{ background: '#0a0d14' }}>
      <td colSpan={6} style={{ padding: '0 12px 18px 48px' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 14,
          padding: '12px 8px 6px',
        }}>
          {/* Trend Layer Verdict panel */}
          <div style={{
            background: '#0f1117',
            border: '1px solid #1e2330',
            borderRadius: 6,
            padding: '12px 14px',
          }}>
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
              textTransform: 'uppercase', color: '#475569', marginBottom: 8,
            }}>
              Trend Layer Verdict
            </div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
              flexWrap: 'wrap',
            }}>
              <Badge value={call.trajectory} color={trajectoryColor(call.trajectory)} />
              {flipped ? (
                <span style={{ fontSize: 11, color: '#fbbf24' }}>
                  → override to <strong>{call.finalAction}</strong>
                </span>
              ) : (
                <span style={{ fontSize: 11, color: '#94a3b8' }}>
                  no override; per-call <strong>{call.perCallRec}</strong> kept
                </span>
              )}
            </div>
            <p style={{
              fontSize: 13, color: '#cbd5e1', margin: 0, lineHeight: 1.55,
              whiteSpace: 'pre-wrap',
            }}>
              {call.trendRationale ?? '—'}
            </p>
          </div>

          {/* Analyst Narrative panel */}
          <div style={{
            background: '#0f1117',
            border: '1px solid #1e2330',
            borderRadius: 6,
            padding: '12px 14px',
          }}>
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
              textTransform: 'uppercase', color: '#475569', marginBottom: 8,
            }}>
              Analyst Narrative (this call)
            </div>
            {expanded?.loading && (
              <div style={{ color: '#475569', fontSize: 12 }}>Loading…</div>
            )}
            {expanded?.error && (
              <div style={{ color: '#fca5a5', fontSize: 12 }}>
                Failed to load: {expanded.error}
              </div>
            )}
            {expanded && !expanded.loading && !expanded.error && (
              <>
                <div style={{ marginBottom: 12 }}>
                  <div style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                    color: healthColor(call.thesisHealth), textTransform: 'uppercase',
                    marginBottom: 4,
                  }}>
                    Thesis Health: {call.thesisHealth ?? '—'}
                  </div>
                  <p style={{
                    fontSize: 12, color: '#cbd5e1', margin: 0, lineHeight: 1.55,
                    whiteSpace: 'pre-wrap',
                  }}>
                    {expanded.thesisHealth || <span style={{ color: '#475569' }}>(no THESIS HEALTH section in this analysis)</span>}
                  </p>
                </div>
                <div>
                  <div style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                    color: recColor(call.perCallRec), textTransform: 'uppercase',
                    marginBottom: 4,
                  }}>
                    Recommendation: {call.perCallRec ?? '—'}
                  </div>
                  <p style={{
                    fontSize: 12, color: '#cbd5e1', margin: 0, lineHeight: 1.55,
                    whiteSpace: 'pre-wrap',
                  }}>
                    {expanded.recommendation || <span style={{ color: '#475569' }}>(no RECOMMENDATION section in this analysis)</span>}
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
}
