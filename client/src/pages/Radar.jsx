import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Link } from 'react-router-dom';

// API origin: dev reads from .env.development (${API_URL}).
// Prod reads from .env.production (empty string → same-origin, since the
// server static-serves the SPA in prod).
const API_URL = import.meta.env.VITE_API_URL || '';

// ── Color helpers ─────────────────────────────────────────────────────────────

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

// Smaller, subdued chip for tier — speculative names get an amber outline,
// established names get a quiet slate look. Uses smaller padding/font than
// Badge so it reads as secondary metadata next to the symbol.
function TierChip({ tier }) {
  if (!tier) return null;
  const isSpec = tier === 'speculative';
  const color = isSpec ? '#f59e0b' : '#64748b';
  const label = isSpec ? 'SPEC' : 'EST';
  return (
    <span
      title={isSpec
        ? '3-axis classifier: ≥2 of {high σ, small cap, high P/E}'
        : 'Established: ≤1 of 3 axes fired'}
      style={{
        display: 'inline-block',
        padding: '1px 5px',
        borderRadius: 3,
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: '0.08em',
        color,
        background: color + '14',
        border: `1px solid ${color}30`,
      }}
    >
      {label}
    </span>
  );
}

// Clickable column header — toggles sort key/direction. Shows a subtle
// arrow when this column is the active sort.
function SortableTh({ sortKey, sort, onClick, children }) {
  const isActive = sort.key === sortKey;
  const arrow = isActive ? (sort.dir === 'asc' ? '↑' : '↓') : '↕';
  return (
    <th
      onClick={() => onClick(sortKey)}
      style={{
        ...th,
        cursor: 'pointer',
        color: isActive ? '#cbd5e1' : '#475569',
        userSelect: 'none',
      }}
    >
      {children}
      <span style={{ marginLeft: 4, fontSize: 10, color: isActive ? '#3b82f6' : '#334155' }}>
        {arrow}
      </span>
    </th>
  );
}

// "Expected new transcript" badge — shows when the latest call is old
// enough that a fresh quarterly transcript should be available. Pre-API-
// integration version: derived purely from days-since-last-call. When we
// hook up an earnings calendar later, this can become "transcript exists,
// not yet uploaded" instead of just "we're due."
//
// Thresholds:
//   < 85 days: no badge (next call not yet expected)
//   85-99 days: yellow ⏰ ("expected by now, time to check")
//   ≥ 100 days: red ⏰ ("definitely overdue")
function StaleTranscriptBadge({ daysSinceLastCall }) {
  if (daysSinceLastCall == null || daysSinceLastCall < 85) return null;
  const isOverdue = daysSinceLastCall >= 100;
  const color = isOverdue ? '#ef4444' : '#fbbf24';
  const tip = isOverdue
    ? `Last transcript: ${daysSinceLastCall} days ago. Quarterly companies typically release every 85-95 days — this one is overdue. Time to check your sources for a new earnings call.`
    : `Last transcript: ${daysSinceLastCall} days ago. Quarterly companies typically release every 85-95 days — a new one is likely available. Time to check your sources.`;
  return (
    <span
      title={tip}
      style={{
        color,
        fontSize: 13,
        marginLeft: 4,
        cursor: 'help',
        lineHeight: 1,
      }}
    >
      ⏰
    </span>
  );
}

// Yellow triangle for advisory rows — "trend layer noticed something but
// didn't override". Subtle, doesn't compete with the action chip.
function AdvisoryFlag({ confidence, trajectory, finalAction, perCallRec }) {
  if (confidence !== 'advisory') return null;
  const flipped = finalAction && perCallRec && finalAction !== perCallRec;
  const tip = flipped
    ? `Advisory: ${trajectory} — final action ${finalAction} (per-call was ${perCallRec})`
    : `Advisory: ${trajectory} — passthrough, no action change`;
  return (
    <span
      title={tip}
      style={{
        color: '#fbbf24',
        fontSize: 11,
        marginLeft: 2,
        cursor: 'help',
      }}
    >
      ⚠
    </span>
  );
}

// ── Transcript viewer modal ───────────────────────────────────────────────────

// ── Analysis section helpers (mirrors Stock Analyst rendering) ────────────────

function parseAnalysisSections(text) {
  const sections = [];
  const lines = text.split('\n');
  let current = null;
  for (const line of lines) {
    const m = line.match(/^##\s+(.+)/);
    if (m) {
      if (current) sections.push(current);
      current = { title: m[1].trim(), body: [] };
    } else if (current) {
      current.body.push(line);
    }
  }
  if (current) sections.push(current);
  const filtered = sections.filter(s => s.title?.toUpperCase() !== 'FICTIONAL DETAIL CHECK');
  return filtered.length ? filtered : [{ title: null, body: text.split('\n') }];
}

function analysisSectionColor(title, body) {
  const text = body.join(' ').toLowerCase();
  if (title === 'THESIS HEALTH') {
    if (text.includes('strengthening')) return '#22c55e';
    if (text.includes('intact'))        return '#86efac';
    if (text.includes('weakening'))     return '#f59e0b';
    if (text.includes('broken'))        return '#ef4444';
  }
  if (title === 'RECOMMENDATION') {
    if (text.includes('exit'))  return '#ef4444';
    if (text.includes('trim'))  return '#f59e0b';
    if (text.includes('add'))   return '#22c55e';
    if (text.includes('hold'))  return '#94a3b8';
  }
  return null;
}

function AnalysisSection({ title, body }) {
  const accent = analysisSectionColor(title, body);
  return (
    <div style={{
      background: '#1e2330',
      border: `1px solid ${accent || '#2d3748'}`,
      borderRadius: 8,
      padding: '14px 18px',
      marginBottom: 10,
    }}>
      {title && (
        <div style={{
          fontSize: 11, fontWeight: 700, letterSpacing: '0.08em',
          color: accent || '#64748b', textTransform: 'uppercase', marginBottom: 8,
        }}>
          {title}
        </div>
      )}
      <div style={{ fontSize: 13, lineHeight: 1.7, color: '#cbd5e1', whiteSpace: 'pre-wrap' }}>
        {body.join('\n').trim()}
      </div>
    </div>
  );
}

// ── Transcript viewer modal ───────────────────────────────────────────────────

function TranscriptModal({ transcriptId, getToken, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('analysis'); // 'analysis' | 'transcript'

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const token = await getToken();
        const res = await fetch(`${API_URL}/api/radar/transcripts/${transcriptId}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [transcriptId, getToken]);

  // Close on backdrop click or Escape
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const sections = data?.analysis?.rawOutput ? parseAnalysisSections(data.analysis.rawOutput) : [];

  function TabBtn({ id, label }) {
    const active = tab === id;
    return (
      <button
        onClick={() => setTab(id)}
        style={{
          background: active ? '#1e2330' : 'transparent',
          border: `1px solid ${active ? '#3b82f6' : '#2d3748'}`,
          borderRadius: 5,
          color: active ? '#93c5fd' : '#475569',
          fontSize: 11, fontWeight: 600,
          padding: '3px 12px',
          cursor: 'pointer',
          letterSpacing: '0.04em',
        }}
      >
        {label}
      </button>
    );
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.75)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#0f1117',
          border: '1px solid #2d3748',
          borderRadius: 10,
          width: '100%',
          maxWidth: 860,
          maxHeight: '88vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 20px',
          borderBottom: '1px solid #2d3748',
          flexShrink: 0,
          gap: 16,
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data?.title ?? 'Loading…'}
            </div>
            {data?.callDate && (
              <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                {new Date(data.callDate).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' })}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            <TabBtn id="analysis" label="Analysis" />
            <TabBtn id="transcript" label="Transcript" />
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#64748b', fontSize: 20, cursor: 'pointer', lineHeight: 1, padding: '0 4px', flexShrink: 0 }}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div style={{ overflowY: 'auto', padding: '16px 20px', flex: 1 }}>
          {error && <div style={{ color: '#fca5a5', fontSize: 13 }}>{error}</div>}
          {!data && !error && <div style={{ color: '#475569', fontSize: 13 }}>Loading…</div>}

          {data && tab === 'analysis' && (
            sections.length > 0
              ? sections.map((s, i) => <AnalysisSection key={i} title={s.title} body={s.body} />)
              : <div style={{ color: '#475569', fontSize: 13 }}>No analysis saved for this transcript.</div>
          )}

          {data && tab === 'transcript' && (
            <pre style={{
              margin: 0, fontSize: 12, lineHeight: 1.7,
              color: '#94a3b8', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              fontFamily: 'inherit',
            }}>
              {data.rawText}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Table styles ──────────────────────────────────────────────────────────────

const th = {
  padding: '8px 12px',
  textAlign: 'left',
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: '0.06em',
  color: '#64748b',
  textTransform: 'uppercase',
  borderBottom: '1px solid #2d3748',
  whiteSpace: 'nowrap',
};

const td = {
  padding: '10px 12px',
  fontSize: 13,
  color: '#cbd5e1',
  borderBottom: '1px solid #1e2330',
  verticalAlign: 'middle',
};

// ── Thesis trajectory (expanded row) ─────────────────────────────────────────

function HistoryRow({ tickerId, colSpan, getToken, onLastDeleted, onRescored }) {
  const [history, setHistory] = useState(null);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(null); // transcriptId in flight
  const [editingId, setEditingId] = useState(null); // transcriptId being edited
  const [editValue, setEditValue] = useState('');
  const [viewingId, setViewingId] = useState(null); // transcriptId open in modal
  const [rescoring, setRescoring] = useState(null); // transcriptId being rescored
  const [tickerRescoreState, setTickerRescoreState] = useState(null); // null | 'running' | {updated}
  const [sortPrimary, setSortPrimary] = useState('date'); // 'date' | 'title'
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/radar/tickers/${tickerId}/history`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (mountedRef.current) setHistory(data);
      return data;
    } catch (e) {
      if (mountedRef.current) setError(e.message);
      return [];
    }
  }, [tickerId, getToken]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  function startEdit(transcriptId, currentTitle) {
    setEditingId(transcriptId);
    setEditValue(currentTitle ?? '');
  }

  async function commitEdit(transcriptId) {
    if (editingId !== transcriptId) return;
    setEditingId(null);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/radar/transcripts/${transcriptId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ title: editValue }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // Update local history so the new title shows immediately
      setHistory(prev => prev.map(e =>
        e.transcriptId === transcriptId ? { ...e, title: editValue.trim() || null } : e
      ));
    } catch (e) {
      alert(`Failed to save title: ${e.message}`);
    }
  }

  function handleEditKeyDown(e, transcriptId) {
    if (e.key === 'Enter') { e.target.blur(); }
    if (e.key === 'Escape') { setEditingId(null); }
  }

  async function handleRescore(transcriptId) {
    setRescoring(transcriptId);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/radar/transcripts/${transcriptId}/rescore`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      // Update local history so badges refresh immediately
      setHistory(prev => prev.map(e =>
        e.transcriptId === transcriptId
          ? { ...e, thesisHealth: data.thesisHealth, recommendation: data.recommendation }
          : e
      ));
    } catch (e) {
      alert(`Re-score failed: ${e.message}`);
    } finally {
      if (mountedRef.current) setRescoring(null);
    }
  }

  async function handleDelete(transcriptId) {
    if (!window.confirm('Delete this transcript and its analysis? This cannot be undone.')) return;
    setDeleting(transcriptId);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/radar/transcripts/${transcriptId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const updated = await fetchHistory();
      if (updated.length === 0) onLastDeleted();
    } catch (e) {
      alert(`Failed to delete: ${e.message}`);
    } finally {
      if (mountedRef.current) setDeleting(null);
    }
  }

  return (
    <tr>
      <td colSpan={colSpan} style={{ padding: '0', background: '#0d1120' }}>
        <div style={{ padding: '16px 24px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: '#475569', textTransform: 'uppercase' }}>
              Thesis Trajectory
            </span>
            <button
              disabled={tickerRescoreState === 'running'}
              onClick={async () => {
                setTickerRescoreState('running');
                try {
                  const token = await getToken();
                  const res = await fetch(`${API_URL}/api/radar/tickers/${tickerId}/rescore`, {
                    method: 'POST', headers: { 'Authorization': `Bearer ${token}` },
                  });
                  const data = await res.json();
                  if (!res.ok) throw new Error(data.error);
                  setTickerRescoreState(data);
                  await fetchHistory();   // refresh trajectory badges
                  if (onRescored) onRescored(); // refresh ticker-level badge
                } catch (e) {
                  alert(`Re-score failed: ${e.message}`);
                  setTickerRescoreState(null);
                }
              }}
              title="Re-score all calls for this ticker"
              style={{
                background: 'transparent', border: '1px solid #3b2f00', borderRadius: 4,
                color: tickerRescoreState === 'running' ? '#475569' : '#fbbf24',
                fontSize: 10, fontWeight: 600, padding: '2px 8px',
                cursor: tickerRescoreState === 'running' ? 'not-allowed' : 'pointer',
                letterSpacing: '0.04em', textTransform: 'uppercase',
              }}
            >
              {tickerRescoreState === 'running' ? 'Re-scoring…' : 'Re-score all'}
            </button>
            {tickerRescoreState && tickerRescoreState !== 'running' && (
              <span style={{ fontSize: 10, color: tickerRescoreState.updated > 0 ? '#86efac' : '#475569' }}>
                {tickerRescoreState.updated > 0
                  ? `✓ ${tickerRescoreState.updated} corrected`
                  : '✓ all correct'}
              </span>
            )}
            <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
              {['date', 'title'].map(opt => (
                <button
                  key={opt}
                  onClick={() => setSortPrimary(opt)}
                  style={{
                    background: sortPrimary === opt ? '#1e3a5f' : 'transparent',
                    border: `1px solid ${sortPrimary === opt ? '#3b82f6' : '#2d3748'}`,
                    borderRadius: 4,
                    color: sortPrimary === opt ? '#93c5fd' : '#475569',
                    fontSize: 10,
                    fontWeight: 600,
                    padding: '2px 8px',
                    cursor: 'pointer',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  {opt === sortPrimary
                    ? `${opt} → ${opt === 'date' ? 'title' : 'date'}`
                    : opt}
                </button>
              ))}
            </div>
          </div>
          {viewingId && (
            <TranscriptModal
              transcriptId={viewingId}
              getToken={getToken}
              onClose={() => setViewingId(null)}
            />
          )}
          {error && <div style={{ color: '#fca5a5', fontSize: 12 }}>{error}</div>}
          {!history && !error && <div style={{ color: '#475569', fontSize: 12 }}>Loading…</div>}
          {history && history.length === 0 && (
            <div style={{ color: '#475569', fontSize: 12 }}>No analyses saved yet.</div>
          )}
          {history && history.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[...history].sort((a, b) => {
                const dateA = new Date(a.callDate), dateB = new Date(b.callDate);
                const titleA = (a.title ?? '').toLowerCase(), titleB = (b.title ?? '').toLowerCase();
                if (sortPrimary === 'date') {
                  return dateB - dateA || titleA.localeCompare(titleB);
                } else {
                  return titleA.localeCompare(titleB) || dateB - dateA;
                }
              }).map((entry, i) => {
                const isDeleting  = deleting  === entry.transcriptId;
                const isRescoring = rescoring === entry.transcriptId;
                return (
                  <div key={i} style={{
                    display: 'grid',
                    gridTemplateColumns: '100px 200px 120px 70px 44px 150px 64px 56px 70px',
                    alignItems: 'center',
                    gap: '0 10px',
                    padding: '8px 12px',
                    background: '#161b27',
                    borderRadius: 6,
                    border: '1px solid #2d3748',
                    opacity: isDeleting ? 0.4 : 1,
                    transition: 'opacity 0.15s',
                  }}>
                    <span style={{ fontSize: 12, color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {new Date(entry.callDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' })}
                    </span>
                    {editingId === entry.transcriptId ? (
                      <input
                        autoFocus
                        value={editValue}
                        onChange={e => setEditValue(e.target.value)}
                        onBlur={() => commitEdit(entry.transcriptId)}
                        onKeyDown={e => handleEditKeyDown(e, entry.transcriptId)}
                        style={{
                          width: '100%',
                          background: '#0f1117',
                          border: '1px solid #3b82f6',
                          borderRadius: 4,
                          color: '#e2e8f0',
                          fontSize: 12,
                          padding: '2px 6px',
                          outline: 'none',
                          fontFamily: 'inherit',
                        }}
                      />
                    ) : (
                      <span
                        onClick={() => startEdit(entry.transcriptId, entry.title)}
                        title="Click to edit"
                        style={{
                          fontSize: 12,
                          color: entry.title ? '#94a3b8' : '#334155',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          cursor: 'text',
                          borderBottom: '1px dashed #2d3748',
                        }}
                      >
                        {entry.title ?? 'click to add title'}
                      </span>
                    )}
                    <span><Badge value={entry.thesisHealth} color={healthColor(entry.thesisHealth)} /></span>
                    <span><Badge value={entry.recommendation} color={recColor(entry.recommendation)} /></span>
                    <span style={{ fontSize: 12, color: '#94a3b8' }}>
                      {entry.recommendedSize != null ? `${entry.recommendedSize}%` : '—'}
                    </span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      {entry.trajectory ? (
                        <>
                          <Badge value={entry.trajectory} color={trajectoryColor(entry.trajectory)} />
                          {entry.finalAction && entry.finalAction !== entry.recommendation && (
                            <span
                              title={`Trend layer override: ${entry.recommendation} → ${entry.finalAction}`}
                              style={{
                                fontSize: 10,
                                color: recColor(entry.finalAction),
                                fontWeight: 700,
                                letterSpacing: '0.05em',
                              }}
                            >
                              → {entry.finalAction.toUpperCase()}
                            </span>
                          )}
                          <AdvisoryFlag
                            confidence={entry.finalConfidence}
                            trajectory={entry.trajectory}
                            finalAction={entry.finalAction}
                            perCallRec={entry.recommendation}
                          />
                        </>
                      ) : (
                        <span style={{ color: '#334155', fontSize: 11 }}>—</span>
                      )}
                    </span>
                    <IconBtn
                      icon={isRescoring ? '…' : <ResyncIcon />}
                      title="Re-score: re-parse scores from stored analysis text"
                      onClick={() => !isRescoring && handleRescore(entry.transcriptId)}
                      disabled={isRescoring}
                      hoverColor="#fbbf24"
                    />
                    <IconBtn
                      icon={<EyeIcon />}
                      title="View transcript"
                      onClick={() => setViewingId(entry.transcriptId)}
                      hoverColor="#60a5fa"
                    />
                    <IconBtn
                      icon="×"
                      title="Remove transcript"
                      onClick={() => handleDelete(entry.transcriptId)}
                      disabled={!!deleting}
                      hoverColor="#ef4444"
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

// ── Ticker table ──────────────────────────────────────────────────────────────

function TickerTable({ tickers, section, onAction, getToken }) {
  const [expandedId, setExpandedId] = useState(null);
  const [acting, setActing] = useState(null); // ticker id being acted on
  const [renamingId, setRenamingId] = useState(null);
  const [renameSymbol, setRenameSymbol] = useState('');
  const [renameName, setRenameName] = useState('');
  const [renameError, setRenameError] = useState(null);
  // Sort state: { key: 'symbol'|'type'|'lastUpdated', dir: 'asc'|'desc' }
  // Click a column header to sort by it. Click again to toggle direction.
  // Default: by symbol ascending.
  const [sort, setSort] = useState({ key: 'symbol', dir: 'asc' });

  const colSpan = 11;

  function setSortKey(key) {
    setSort(prev => prev.key === key
      ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: key === 'lastUpdated' ? 'desc' : 'asc' });
  }

  // Stable secondary sort by symbol asc breaks ties
  const sortedTickers = [...tickers].sort((a, b) => {
    let cmp = 0;
    if (sort.key === 'type') {
      cmp = (a.type ?? '').localeCompare(b.type ?? '');
    } else if (sort.key === 'lastUpdated') {
      const aT = a.latestAnalysis ? new Date(a.latestAnalysis.createdAt).getTime() : 0;
      const bT = b.latestAnalysis ? new Date(b.latestAnalysis.createdAt).getTime() : 0;
      cmp = aT - bT;
    } else if (sort.key === 'company') {
      cmp = (a.shortName || a.name || '').localeCompare(b.shortName || b.name || '');
    } else if (sort.key === 'cap') {
      cmp = (a.capPercent ?? 0) - (b.capPercent ?? 0);
    } else if (sort.key === 'calls') {
      cmp = (a.transcriptCount ?? 0) - (b.transcriptCount ?? 0);
    } else {
      cmp = a.symbol.localeCompare(b.symbol);
    }
    if (sort.dir === 'desc') cmp = -cmp;
    if (cmp !== 0) return cmp;
    return a.symbol.localeCompare(b.symbol);
  });

  async function handlePromote(ticker) {
    if (!window.confirm(`Promote ${ticker.symbol} to Portfolio? All existing transcripts will be preserved.`)) return;
    setActing(ticker.id);
    await onAction(() =>
      apiPatch(ticker.id, { status: 'portfolio' }, getToken)
    );
    setActing(null);
  }

  async function handleDemote(ticker) {
    if (!window.confirm(`Move ${ticker.symbol} back to Watchlist?`)) return;
    setActing(ticker.id);
    await onAction(() =>
      apiPatch(ticker.id, { status: 'watchlist' }, getToken)
    );
    setActing(null);
  }

  async function handleDelete(ticker) {
    if (!window.confirm(`Delete ${ticker.symbol} and all its transcripts and analyses? This cannot be undone.`)) return;
    setActing(ticker.id);
    await onAction(() => apiDelete(ticker.id, getToken));
    setActing(null);
  }

  function startRename(ticker) {
    setRenamingId(ticker.id);
    setRenameSymbol(ticker.symbol);
    setRenameName(ticker.name);
    setRenameError(null);
  }

  async function commitRename(tickerId) {
    const sym = renameSymbol.trim().toUpperCase();
    const nm  = renameName.trim();
    if (!sym) { setRenameError('Symbol is required'); return; }
    // Detect a merge: if the new symbol matches a *different* existing ticker,
    // the backend will move all transcripts over and delete the source ticker.
    // Surface this explicitly so the user doesn't merge accidentally.
    const conflict = tickers.find(t => t.symbol === sym && t.id !== tickerId);
    if (conflict) {
      const sourceTicker = tickers.find(t => t.id === tickerId);
      const sourceSym = sourceTicker?.symbol || '?';
      const sourceCount = sourceTicker?.transcriptCount || 0;
      const ok = window.confirm(
        `MERGE: ${sym} already exists.\n\n` +
        `This will move ${sourceCount} transcript(s) from ${sourceSym} into ${sym} ` +
        `and DELETE the ${sourceSym} ticker.\n\n` +
        `Use this for share-class duplicates (e.g. GOOG → GOOGL) where the same ` +
        `call was loaded under both symbols.\n\n` +
        `If this is unintentional, cancel and pick a different symbol.\n\n` +
        `After merging, run check_db_integrity.py to catch any duplicate ` +
        `(ticker, callDate) pairs.\n\n` +
        `Proceed with merge?`
      );
      if (!ok) return;
    }
    setRenameError(null);
    try {
      await onAction(() => apiPatch(tickerId, { symbol: sym, name: nm || sym }, getToken));
      setRenamingId(null);
    } catch (err) {
      setRenameError(err.message);
    }
  }

  if (tickers.length === 0) {
    return (
      <div style={{ padding: '24px 0', color: '#475569', fontSize: 13 }}>
        No {section} tickers yet.
      </div>
    );
  }

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ ...th, width: 24, padding: '10px 6px' }}></th>
          <SortableTh sortKey="symbol" sort={sort} onClick={setSortKey}>Symbol</SortableTh>
          <SortableTh sortKey="company" sort={sort} onClick={setSortKey}>Company</SortableTh>
          <SortableTh sortKey="type" sort={sort} onClick={setSortKey}>Type</SortableTh>
          <SortableTh sortKey="cap" sort={sort} onClick={setSortKey}>Cap %</SortableTh>
          <SortableTh sortKey="calls" sort={sort} onClick={setSortKey}>Calls</SortableTh>
          <th style={th}>Thesis Health</th>
          <th style={th}>Recommendation</th>
          <th style={th}>Trend</th>
          <SortableTh sortKey="lastUpdated" sort={sort} onClick={setSortKey}>Last Updated</SortableTh>
          <th style={th}>Actions</th>
        </tr>
      </thead>
      <tbody>
        {sortedTickers.map(ticker => {
          const isExpanded = expandedId === ticker.id;
          const isActing = acting === ticker.id;
          const la = ticker.latestAnalysis;

          return [
            <tr
              key={ticker.id}
              style={{ opacity: isActing ? 0.5 : 1, transition: 'opacity 0.15s' }}
            >
              <td
                style={{ ...td, width: 24, padding: '12px 6px', textAlign: 'center', color: '#475569', fontSize: 10, cursor: 'pointer' }}
                onClick={() => setExpandedId(isExpanded ? null : ticker.id)}
              >
                {isExpanded ? '▼' : '▶'}
              </td>
              <td style={td}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flexWrap: 'nowrap' }}>
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : ticker.id)}
                    style={{
                      background: 'none', border: 'none', color: '#93c5fd',
                      fontSize: 13, fontWeight: 700, cursor: 'pointer',
                      padding: 0, letterSpacing: '0.03em',
                    }}
                  >
                    {ticker.symbol}
                  </button>
                  {la?.tier && <TierChip tier={la.tier} />}
                  <StaleTranscriptBadge daysSinceLastCall={ticker.daysSinceLastCall} />
                </span>
              </td>
              <td style={{ ...td, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {ticker.shortName || ticker.name.split(' ')[0] || ticker.symbol}
              </td>
              <td style={td}>{ticker.type ?? '—'}</td>
              <td style={td}>{ticker.capPercent != null ? `${ticker.capPercent}%` : '—'}</td>
              <td style={td}>
                <span style={{ color: section === 'watchlist' && ticker.transcriptCount >= 50 ? '#f59e0b' : '#94a3b8' }}>
                  {ticker.transcriptCount}
                  {section === 'watchlist' && <span style={{ color: '#475569' }}>/50</span>}
                </span>
              </td>
              <td style={td}>
                {la
                  ? <Badge value={la.thesisHealth} color={healthColor(la.thesisHealth)} />
                  : <span style={{ color: '#334155' }}>—</span>}
              </td>
              <td style={td}>
                {la
                  ? <Badge value={la.recommendation} color={recColor(la.recommendation)} />
                  : <span style={{ color: '#334155' }}>—</span>}
              </td>
              <td style={td}>
                {la?.trajectory
                  ? (() => {
                    const isAdvisory = la.finalConfidence === 'advisory';
                    const inner = (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <Badge value={la.trajectory} color={trajectoryColor(la.trajectory)} />
                        {la.finalAction && la.finalAction !== la.recommendation && (
                          <span
                            title={`Trend layer overrode per-call ${la.recommendation} → ${la.finalAction}`}
                            style={{
                              fontSize: 10,
                              color: recColor(la.finalAction),
                              fontWeight: 700,
                              letterSpacing: '0.05em',
                            }}
                          >
                            → {la.finalAction.toUpperCase()}
                          </span>
                        )}
                        <AdvisoryFlag
                          confidence={la.finalConfidence}
                          trajectory={la.trajectory}
                          finalAction={la.finalAction}
                          perCallRec={la.recommendation}
                        />
                      </span>
                    );
                    return isAdvisory && la.id ? (
                      <Link
                        to={`/advisories?focus=${la.id}`}
                        title="Click to open this advisory in the Advisory Feed"
                        style={{ textDecoration: 'none', cursor: 'pointer' }}
                      >
                        {inner}
                      </Link>
                    ) : inner;
                  })()
                  : <span style={{ color: '#334155' }}>—</span>}
              </td>
              <td style={{ ...td, color: '#64748b', fontSize: 12 }}>
                {la ? new Date(la.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
              </td>
              <td style={td}>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'nowrap' }}>
                  {section === 'watchlist' ? (
                    <ActionButton
                      label="→ Portfolio"
                      color="#60a5fa"
                      onClick={() => handlePromote(ticker)}
                      disabled={isActing}
                    />
                  ) : (
                    <ActionButton
                      label="→ Watchlist"
                      color="#94a3b8"
                      onClick={() => handleDemote(ticker)}
                      disabled={isActing}
                    />
                  )}
                  <IconBtn
                    icon={<PencilIcon />}
                    title="Rename / merge — change symbol to merge transcripts into an existing ticker"
                    onClick={() => startRename(ticker)}
                    disabled={isActing}
                    hoverColor="#a78bfa"
                  />
                  <IconBtn
                    icon="×"
                    title="Delete ticker and all transcripts"
                    onClick={() => handleDelete(ticker)}
                    disabled={isActing}
                    hoverColor="#ef4444"
                  />
                </div>
              </td>
            </tr>,
            renamingId === ticker.id && (
              <tr key={`${ticker.id}-rename`} style={{ background: '#0d1120' }}>
                <td colSpan={colSpan} style={{ padding: '12px 24px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#a78bfa', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                      Rename
                    </span>
                    <input
                      value={renameSymbol}
                      onChange={e => setRenameSymbol(e.target.value.toUpperCase())}
                      placeholder="New symbol"
                      maxLength={10}
                      style={{ width: 90, padding: '4px 8px', background: '#1e2330', border: '1px solid #a78bfa', borderRadius: 4, color: '#e2e8f0', fontSize: 13, fontFamily: 'inherit', outline: 'none' }}
                    />
                    <input
                      value={renameName}
                      onChange={e => setRenameName(e.target.value)}
                      placeholder="Full company name"
                      style={{ width: 260, padding: '4px 8px', background: '#1e2330', border: '1px solid #2d3748', borderRadius: 4, color: '#e2e8f0', fontSize: 13, fontFamily: 'inherit', outline: 'none' }}
                    />
                    <button
                      onClick={() => commitRename(ticker.id)}
                      style={{ padding: '4px 14px', background: '#4c1d95', border: '1px solid #a78bfa', borderRadius: 4, color: '#c4b5fd', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
                    >
                      Save
                    </button>
                    <button
                      onClick={() => { setRenamingId(null); setRenameError(null); }}
                      style={{ padding: '4px 10px', background: 'transparent', border: '1px solid #2d3748', borderRadius: 4, color: '#64748b', fontSize: 12, cursor: 'pointer' }}
                    >
                      Cancel
                    </button>
                    {renameError && <span style={{ fontSize: 12, color: '#fca5a5' }}>{renameError}</span>}
                  </div>
                </td>
              </tr>
            ),
            isExpanded && (
              <HistoryRow
                key={`${ticker.id}-history`}
                tickerId={ticker.id}
                colSpan={colSpan}
                getToken={getToken}
                onLastDeleted={() => {
                  setExpandedId(null);
                  onAction(async () => {});
                }}
                onRescored={() => onAction(async () => {})}
              />
            ),
          ];
        })}
      </tbody>
    </table>
  );
}

// ── Shared icon set (outline/stroke style — matches ✎ and × in Portfolio) ─────

const EyeIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
);

const ResyncIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="1 4 1 10 7 10"/>
    <path d="M3.51 15a9 9 0 1 0 .49-4.5"/>
  </svg>
);

const PencilIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
);

/**
 * IconBtn — borderless icon button matching Portfolio's ✎ and × style.
 * Use for all edit/destructive actions in tables.
 */
function IconBtn({ icon, title, onClick, disabled, hoverColor = '#94a3b8' }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: 'none',
        border: 'none',
        color: disabled ? '#2d3748' : hover ? hoverColor : '#475569',
        cursor: disabled ? 'not-allowed' : 'pointer',
        padding: '2px 4px',
        lineHeight: 1,
        fontSize: 14,
        display: 'inline-flex',
        alignItems: 'center',
        transition: 'color 0.15s',
      }}
    >
      {icon}
    </button>
  );
}

function ActionButton({ label, color, onClick, disabled, title }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        background: 'transparent',
        border: `1px solid ${disabled ? '#2d3748' : color + '60'}`,
        borderRadius: 4,
        color: disabled ? '#334155' : color,
        fontSize: 11,
        fontWeight: 600,
        padding: '3px 8px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        whiteSpace: 'nowrap',
        transition: 'all 0.15s',
      }}
    >
      {label}
    </button>
  );
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiPatch(id, body, getToken) {
  const token = await getToken();
  const res = await fetch(`${API_URL}/api/radar/tickers/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
}

async function apiDelete(id, getToken) {
  const token = await getToken();
  const res = await fetch(`${API_URL}/api/radar/tickers/${id}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`DELETE failed: ${res.status}`);
}

// ── Module-level cache (persists across tab switches) ─────────────────────────

let tickerCache = null;

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Radar() {
  const { getToken } = useAuth();
  const [tickers, setTickers] = useState(tickerCache ?? []);
  const [loading, setLoading] = useState(tickerCache === null);
  const [error, setError] = useState(null);
  const [rescoreAllState, setRescoreAllState] = useState(null); // null | 'running' | {total, updated}
  const [showNewTicker, setShowNewTicker]     = useState(false);

  const fetchTickers = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/radar/tickers`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      tickerCache = data;
      setTickers(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    // If we have cached data, refresh silently in the background
    fetchTickers({ silent: tickerCache !== null });
  }, [fetchTickers]);

  // Refresh automatically whenever the Analyst saves a new transcript
  useEffect(() => {
    function onSave() { fetchTickers({ silent: true }); }
    window.addEventListener('radar:refresh', onSave);
    return () => window.removeEventListener('radar:refresh', onSave);
  }, [fetchTickers]);

  // Wrap an action call: run it, then refresh the list
  async function handleAction(actionFn) {
    try {
      await actionFn();
    } catch (err) {
      alert(`Action failed: ${err.message}`);
    }
    await fetchTickers({ silent: true });
  }

  const watchlist  = tickers.filter(t => t.status === 'watchlist');
  const portfolio  = tickers.filter(t => t.status === 'portfolio');

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
          Stock Radar
        </h1>
        <button
          onClick={() => setShowNewTicker(true)}
          style={{
            background: 'transparent',
            border: '1px solid #2d3748',
            borderRadius: 5,
            color: '#60a5fa',
            fontSize: 11, fontWeight: 600,
            padding: '4px 12px',
            cursor: 'pointer',
            letterSpacing: '0.04em', textTransform: 'uppercase',
          }}
        >
          + New ticker
        </button>
        <button
          disabled={rescoreAllState === 'running'}
          onClick={async () => {
            setRescoreAllState('running');
            try {
              const token = await getToken();
              const res = await fetch(`${API_URL}/api/radar/rescore-all`, {
                method: 'POST', headers: { 'Authorization': `Bearer ${token}` },
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data.error);
              setRescoreAllState(data);
              await fetchTickers({ silent: true });
            } catch (e) {
              alert(`Re-score failed: ${e.message}`);
              setRescoreAllState(null);
            }
          }}
          style={{
            background: 'transparent',
            border: '1px solid #3b2f00',
            borderRadius: 5,
            color: rescoreAllState === 'running' ? '#475569' : '#fbbf24',
            fontSize: 11, fontWeight: 600,
            padding: '4px 12px',
            cursor: rescoreAllState === 'running' ? 'not-allowed' : 'pointer',
            letterSpacing: '0.04em', textTransform: 'uppercase',
          }}
        >
          {rescoreAllState === 'running' ? 'Re-scoring…' : 'Re-score Radar'}
        </button>
      </div>

      {/* Re-score result banner — persists until next run */}
      {rescoreAllState && rescoreAllState !== 'running' && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '10px 16px', marginBottom: 16,
          background: rescoreAllState.updated > 0 ? '#0f2a1a' : '#161b27',
          border: `1px solid ${rescoreAllState.updated > 0 ? '#166534' : '#2d3748'}`,
          borderRadius: 6,
        }}>
          <span style={{ fontSize: 13, color: rescoreAllState.updated > 0 ? '#86efac' : '#64748b' }}>
            {rescoreAllState.updated > 0
              ? `✓ Re-scored ${rescoreAllState.total} calls — ${rescoreAllState.updated} score${rescoreAllState.updated !== 1 ? 's' : ''} corrected`
              : `✓ Re-scored ${rescoreAllState.total} calls — all scores already correct, nothing changed`}
          </span>
          <button
            onClick={() => setRescoreAllState(null)}
            style={{ background: 'none', border: 'none', color: '#475569', fontSize: 16, cursor: 'pointer', padding: 0, marginLeft: 'auto', lineHeight: 1 }}
          >
            ×
          </button>
        </div>
      )}

      <p style={{ fontSize: 13, color: '#64748b', marginBottom: 32 }}>
        Watchlist tickers cap at 6 transcripts (oldest auto-discarded). Portfolio tickers keep unlimited history.
      </p>

      {loading && (
        <div style={{ color: '#64748b', fontSize: 14 }}>Loading…</div>
      )}
      {error && (
        <div style={{ color: '#fca5a5', fontSize: 13 }}>Error: {error}</div>
      )}

      {!loading && !error && (
        <>
          {/* ── Portfolio ── */}
          <Section title="Portfolio" count={portfolio.length}>
            <TickerTable
              tickers={portfolio}
              section="portfolio"
              onAction={handleAction}
              getToken={getToken}
            />
          </Section>

          {/* ── Watchlist ── */}
          <Section title="Watchlist" count={watchlist.length} style={{ marginTop: 40 }}>
            <TickerTable
              tickers={watchlist}
              section="watchlist"
              onAction={handleAction}
              getToken={getToken}
            />
          </Section>
        </>
      )}

      {showNewTicker && (
        <NewTickerModal
          getToken={getToken}
          onSaved={() => { setShowNewTicker(false); fetchTickers({ silent: true }); }}
          onClose={() => setShowNewTicker(false)}
        />
      )}
    </div>
  );
}

// ── New Ticker modal (ETFs, commodities, crypto — no transcript needed) ────────

function NewTickerModal({ getToken, onSaved, onClose }) {
  const [symbol,    setSymbol]    = useState('');
  const [name,      setName]      = useState('');
  const [shortName, setShortName] = useState('');
  const [bucket,    setBucket]    = useState('etf');
  const [notes,     setNotes]     = useState('');
  const [saving,    setSaving]    = useState(false);
  const [error,     setError]     = useState('');

  const inputStyle = {
    background: '#0d1018', border: '1px solid #2d3748', borderRadius: 5,
    color: '#f1f5f9', fontSize: 13, padding: '6px 10px', outline: 'none',
    width: '100%', boxSizing: 'border-box',
  };
  const labelStyle = { fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 };

  async function handleSave(e) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/radar/tickers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          symbol: symbol.trim().toUpperCase(),
          name:   name.trim(),
          shortName: shortName.trim() || name.trim(),
          bucket,
          notes: notes.trim() || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Save failed');
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const BUCKET_OPTIONS = [
    { value: 'etf',       label: 'ETF' },
    { value: 'equity',    label: 'Equity' },
    { value: 'crypto',    label: 'Crypto' },
    { value: 'commodity', label: 'Commodity' },
  ];

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#00000099', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ background: '#0f1117', border: '1px solid #1e2330', borderRadius: 10, padding: 24, width: 400, maxWidth: '95vw' }}>
        <div style={{ fontWeight: 600, color: '#f1f5f9', marginBottom: 4, fontSize: 14 }}>Add ticker</div>
        <div style={{ fontSize: 12, color: '#475569', marginBottom: 16 }}>
          For ETFs, commodities, and crypto — no earnings call required.
        </div>
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 10 }}>
            <div>
              <label style={labelStyle}>Symbol *</label>
              <input style={inputStyle} value={symbol}
                onChange={e => setSymbol(e.target.value.toUpperCase())}
                placeholder="e.g. GLD" required />
            </div>
            <div>
              <label style={labelStyle}>Asset type *</label>
              <select style={{ ...inputStyle, cursor: 'pointer' }} value={bucket} onChange={e => setBucket(e.target.value)}>
                {BUCKET_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label style={labelStyle}>Full name *</label>
            <input style={inputStyle} value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. SPDR Gold Shares" required />
          </div>
          <div>
            <label style={labelStyle}>Short name (optional)</label>
            <input style={inputStyle} value={shortName}
              onChange={e => setShortName(e.target.value)}
              placeholder="e.g. Gold ETF" />
          </div>
          <div>
            <label style={labelStyle}>Notes (optional)</label>
            <input style={inputStyle} value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="e.g. Defensive hedge position" />
          </div>

          {error && <div style={{ color: '#ef4444', fontSize: 12, padding: '6px 10px', background: '#ef444411', borderRadius: 5 }}>{error}</div>}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button type="button" onClick={onClose}
              style={{ background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 13, padding: '6px 16px', borderRadius: 5, cursor: 'pointer' }}>
              Cancel
            </button>
            <button type="submit" disabled={saving}
              style={{ background: saving ? '#1e2330' : '#3b82f6', border: 'none', color: '#f1f5f9', fontSize: 13, fontWeight: 600, padding: '6px 20px', borderRadius: 5, cursor: saving ? 'wait' : 'pointer' }}>
              {saving ? 'Saving…' : 'Add ticker'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Section({ title, count, children, style }) {
  return (
    <div style={style}>
      <div style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 8,
        marginBottom: 12,
        paddingBottom: 10,
        borderBottom: '1px solid #1e2330',
      }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: '#e2e8f0' }}>{title}</span>
        <span style={{ fontSize: 12, color: '#475569' }}>{count} ticker{count !== 1 ? 's' : ''}</span>
      </div>
      {children}
    </div>
  );
}
