import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';

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

function HistoryRow({ tickerId, colSpan, getToken }) {
  const [history, setHistory] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = await getToken();
        const res = await fetch(`http://localhost:3001/api/radar/tickers/${tickerId}/history`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        const data = await res.json();
        if (!cancelled) setHistory(data);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => { cancelled = true; };
  }, [tickerId, getToken]);

  return (
    <tr>
      <td colSpan={colSpan} style={{ padding: '0', background: '#0d1120' }}>
        <div style={{ padding: '16px 24px 20px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: '#475569', textTransform: 'uppercase', marginBottom: 12 }}>
            Thesis Trajectory
          </div>
          {error && <div style={{ color: '#fca5a5', fontSize: 12 }}>{error}</div>}
          {!history && !error && <div style={{ color: '#475569', fontSize: 12 }}>Loading…</div>}
          {history && history.length === 0 && (
            <div style={{ color: '#475569', fontSize: 12 }}>No analyses saved yet.</div>
          )}
          {history && history.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {history.map((entry, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 16,
                  padding: '8px 12px',
                  background: '#161b27',
                  borderRadius: 6,
                  border: '1px solid #2d3748',
                }}>
                  <span style={{ fontSize: 12, color: '#64748b', minWidth: 90 }}>
                    {new Date(entry.callDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                  </span>
                  <Badge value={entry.thesisHealth} color={healthColor(entry.thesisHealth)} />
                  <Badge value={entry.recommendation} color={recColor(entry.recommendation)} />
                  {entry.recommendedSize != null && (
                    <span style={{ fontSize: 12, color: '#94a3b8' }}>{entry.recommendedSize}%</span>
                  )}
                </div>
              ))}
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

  const colSpan = 9;

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
          <th style={th}>Symbol</th>
          <th style={th}>Company</th>
          <th style={th}>Type</th>
          <th style={th}>Cap %</th>
          <th style={th}>Calls</th>
          <th style={th}>Thesis Health</th>
          <th style={th}>Recommendation</th>
          <th style={th}>Last Updated</th>
          <th style={th}>Actions</th>
        </tr>
      </thead>
      <tbody>
        {tickers.map(ticker => {
          const isExpanded = expandedId === ticker.id;
          const isActing = acting === ticker.id;
          const la = ticker.latestAnalysis;

          return [
            <tr
              key={ticker.id}
              style={{ opacity: isActing ? 0.5 : 1, transition: 'opacity 0.15s' }}
            >
              <td style={td}>
                <button
                  onClick={() => setExpandedId(isExpanded ? null : ticker.id)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#93c5fd',
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: 'pointer',
                    padding: 0,
                    letterSpacing: '0.03em',
                  }}
                >
                  {ticker.symbol}
                  <span style={{ marginLeft: 4, fontSize: 10, color: '#475569' }}>
                    {isExpanded ? '▲' : '▼'}
                  </span>
                </button>
              </td>
              <td style={{ ...td, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {ticker.name}
              </td>
              <td style={td}>{ticker.type ?? '—'}</td>
              <td style={td}>{ticker.capPercent != null ? `${ticker.capPercent}%` : '—'}</td>
              <td style={td}>
                <span style={{ color: section === 'watchlist' && ticker.transcriptCount >= 6 ? '#f59e0b' : '#94a3b8' }}>
                  {ticker.transcriptCount}
                  {section === 'watchlist' && <span style={{ color: '#475569' }}>/6</span>}
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
                  <ActionButton
                    label="Delete"
                    color="#ef4444"
                    onClick={() => handleDelete(ticker)}
                    disabled={isActing}
                  />
                </div>
              </td>
            </tr>,
            isExpanded && (
              <HistoryRow
                key={`${ticker.id}-history`}
                tickerId={ticker.id}
                colSpan={colSpan}
                getToken={getToken}
              />
            ),
          ];
        })}
      </tbody>
    </table>
  );
}

function ActionButton({ label, color, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
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
  const res = await fetch(`http://localhost:3001/api/radar/tickers/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
}

async function apiDelete(id, getToken) {
  const token = await getToken();
  const res = await fetch(`http://localhost:3001/api/radar/tickers/${id}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`DELETE failed: ${res.status}`);
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Radar() {
  const { getToken } = useAuth();
  const [tickers, setTickers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTickers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await fetch('http://localhost:3001/api/radar/tickers', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setTickers(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => { fetchTickers(); }, [fetchTickers]);

  // Wrap an action call: run it, then refresh the list
  async function handleAction(actionFn) {
    try {
      await actionFn();
    } catch (err) {
      alert(`Action failed: ${err.message}`);
    }
    await fetchTickers();
  }

  const watchlist  = tickers.filter(t => t.status === 'watchlist');
  const portfolio  = tickers.filter(t => t.status === 'portfolio');

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4, color: '#f1f5f9' }}>
        RADAR
      </h1>
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
