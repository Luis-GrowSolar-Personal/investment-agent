import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@clerk/clerk-react';

const API = import.meta.env.VITE_API_URL || '';

// ── Constants ─────────────────────────────────────────────────────────────────

const BUCKET_TABS   = ['equity', 'etf', 'crypto', 'commodity', 'cash'];
const BUCKET_LABELS = { equity: 'Equities', etf: 'ETFs', crypto: 'Crypto', commodity: 'Commodities', cash: 'Cash & Margin' };
const BUCKET_COLORS = { equity: '#60a5fa', etf: '#a78bfa', crypto: '#f59e0b', commodity: '#34d399', cash: '#94a3b8' };
const ACCOUNT_TYPE_LABELS = { taxable: 'Taxable', ira: 'IRA', roth: 'Roth IRA', custodial: 'Custodial' };

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtDollars(n, compact = false) {
  if (n == null) return '—';
  if (compact && Math.abs(n) >= 1_000_000) {
    return '$' + (n / 1_000_000).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + 'M';
  }
  return (n < 0 ? '-$' : '$') + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(n) {
  if (n == null) return '—';
  const sign = n >= 0 ? '+' : '';
  return sign + (n * 100).toFixed(2) + '%';
}

function fmtShares(n) {
  if (n == null) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 4 });
}

function gainColor(n) {
  if (n == null) return '#94a3b8';
  return n >= 0 ? '#34d399' : '#ef4444';
}

// ── Small UI primitives ───────────────────────────────────────────────────────

function Pill({ color, children, onClick, style = {} }) {
  return (
    <span
      onClick={onClick}
      style={{
        display: 'inline-block',
        padding: '1px 7px',
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        background: color + '1a',
        color,
        border: `1px solid ${color}33`,
        cursor: onClick ? 'pointer' : 'default',
        userSelect: 'none',
        ...style,
      }}
    >
      {children}
    </span>
  );
}

function MetricCard({ label, value, sub, subColor }) {
  return (
    <div style={{
      background: '#0d1018',
      border: '1px solid #1e2330',
      borderRadius: 8,
      padding: '14px 20px',
      flex: 1,
      minWidth: 160,
    }}>
      <div style={{ fontSize: 11, color: '#475569', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>{value}</div>
      {sub && (
        <div style={{ fontSize: 12, color: subColor || '#94a3b8', marginTop: 2 }}>{sub}</div>
      )}
    </div>
  );
}

// ── Bucket pill dropdown ──────────────────────────────────────────────────────

const BUCKET_OPTIONS = ['equity', 'etf', 'crypto', 'commodity'];

function BucketPill({ ticker, onBucketChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const effective = ticker.bucketOverride || ticker._smartBucket || 'equity';

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <Pill
        color={BUCKET_COLORS[effective]}
        onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
        style={{ cursor: 'pointer', whiteSpace: 'nowrap' }}
      >
        {effective} ▾
      </Pill>
      {open && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          marginTop: 4,
          background: '#0f1117',
          border: '1px solid #1e2330',
          borderRadius: 6,
          zIndex: 100,
          minWidth: 110,
          boxShadow: '0 4px 16px #00000066',
        }}>
          {BUCKET_OPTIONS.map(b => (
            <div
              key={b}
              onClick={e => {
                e.stopPropagation();
                setOpen(false);
                onBucketChange(ticker.id, b === effective && ticker.bucketOverride ? null : b);
              }}
              style={{
                padding: '7px 12px',
                fontSize: 12,
                color: b === effective ? BUCKET_COLORS[b] : '#94a3b8',
                cursor: 'pointer',
                background: b === effective ? BUCKET_COLORS[b] + '15' : 'transparent',
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#1e2330'}
              onMouseLeave={e => e.currentTarget.style.background = b === effective ? BUCKET_COLORS[b] + '15' : 'transparent'}
            >
              {BUCKET_LABELS[b]}
            </div>
          ))}
          {ticker.bucketOverride && (
            <div
              onClick={e => { e.stopPropagation(); setOpen(false); onBucketChange(ticker.id, null); }}
              style={{ padding: '7px 12px', fontSize: 11, color: '#475569', cursor: 'pointer', borderTop: '1px solid #1e2330' }}
            >
              Reset to default
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Position row ──────────────────────────────────────────────────────────────

function PositionRow({ pos, onBucketChange, onDelete, onEdit }) {
  const [expanded, setExpanded] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const mktVal    = pos.marketValue ?? pos.totalCost;
  const gain      = pos.unrealisedGain;
  const gainPct   = pos.unrealisedGainPct;
  const dayGain   = pos.dayGainDollar;
  const dayPct    = pos.dayChangePct;

  return (
    <>
      <tr
        onClick={() => setExpanded(e => !e)}
        style={{ cursor: 'pointer', borderBottom: '1px solid #161b26' }}
        onMouseEnter={e => e.currentTarget.style.background = '#0d1018'}
        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
      >
        {/* Expand chevron — left of symbol */}
        <td style={{ padding: '9px 6px', width: 24, textAlign: 'center', color: '#475569', fontSize: 10 }}>
          {expanded ? '▼' : '▶'}
        </td>
        <td style={{ padding: '9px 12px' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, flexWrap: 'nowrap' }}>
            <span style={{ fontWeight: 700, color: '#f1f5f9', fontSize: 13 }}>{pos.ticker.symbol}</span>
            {!pos.ticker.inScope && (
              <span style={{
                display: 'inline-block', padding: '1px 5px', borderRadius: 3,
                fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
                color: '#ef4444', background: '#ef444414', border: '1px solid #ef444430',
              }}>legacy</span>
            )}
          </span>
        </td>
        <td style={{ padding: '9px 12px', color: '#94a3b8', fontSize: 12 }}>
          {pos.ticker.shortName || pos.ticker.name}
        </td>
        <td style={{ padding: '9px 12px', color: '#94a3b8', fontSize: 12, textAlign: 'right' }}>
          {fmtShares(pos.totalShares)}
        </td>
        <td style={{ padding: '9px 12px', color: '#94a3b8', fontSize: 12, textAlign: 'right' }}>
          {pos.lastPrice ? fmtDollars(pos.lastPrice) : '—'}
        </td>
        <td style={{ padding: '9px 12px', color: '#f1f5f9', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>
          {fmtDollars(mktVal)}
        </td>
        <td style={{ padding: '9px 12px', fontSize: 12, textAlign: 'right' }}>
          <span style={{ color: gainColor(gain) }}>{fmtDollars(gain)}</span>
          <span style={{ color: gainColor(gainPct), marginLeft: 5, fontSize: 11 }}>{fmtPct(gainPct)}</span>
        </td>
        <td style={{ padding: '9px 12px', fontSize: 12, textAlign: 'right' }}>
          <span style={{ color: gainColor(dayGain) }}>{dayGain != null ? fmtDollars(dayGain) : '—'}</span>
          <span style={{ color: gainColor(dayPct), marginLeft: 5, fontSize: 11 }}>{dayPct != null ? fmtPct(dayPct) : ''}</span>
        </td>
        <td style={{ padding: '9px 12px', textAlign: 'right', fontSize: 11, color: '#475569' }}>
          {pos.pctOfAcct != null ? (pos.pctOfAcct * 100).toFixed(1) + '%' : '—'}
        </td>
        <td style={{ padding: '9px 12px' }} onClick={e => e.stopPropagation()}>
          <BucketPill ticker={{ ...pos.ticker, _smartBucket: pos.effectiveBucket }} onBucketChange={onBucketChange} />
        </td>
        <td style={{ padding: '9px 8px', textAlign: 'right', whiteSpace: 'nowrap' }} onClick={e => e.stopPropagation()}>
          <button onClick={() => onEdit(pos)} title="Edit lots"
            style={{ background: 'none', border: 'none', color: '#475569', cursor: 'pointer', fontSize: 14, padding: '0 4px', lineHeight: 1 }}
            onMouseEnter={e => e.currentTarget.style.color = '#60a5fa'}
            onMouseLeave={e => e.currentTarget.style.color = '#475569'}>✎</button>
          <button onClick={() => setConfirmDelete(true)} title="Remove position (no taxable event)"
            style={{ background: 'none', border: 'none', color: '#475569', cursor: 'pointer', fontSize: 14, padding: '0 4px', lineHeight: 1 }}
            onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
            onMouseLeave={e => e.currentTarget.style.color = '#475569'}>×</button>
        </td>
      </tr>
      {confirmDelete && (
        <tr>
          <td colSpan={12} style={{ background: '#1a0a0a', padding: '8px 16px', borderBottom: '1px solid #3d1515' }}>
            <span style={{ fontSize: 12, color: '#fca5a5' }}>
              Remove <strong>{pos.ticker.symbol}</strong> from tracking? This does not generate a taxable event — it only removes it from the agent's records.
            </span>
            <button
              onClick={() => { setConfirmDelete(false); onDelete(pos.id); }}
              style={{ marginLeft: 12, background: '#ef4444', border: 'none', color: '#fff', fontSize: 11, fontWeight: 600, padding: '3px 12px', borderRadius: 4, cursor: 'pointer' }}
            >
              Remove
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              style={{ marginLeft: 6, background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 11, padding: '3px 10px', borderRadius: 4, cursor: 'pointer' }}
            >
              Cancel
            </button>
          </td>
        </tr>
      )}
      {expanded && (
        <tr>
          <td colSpan={12} style={{ background: '#090c12', padding: '0 12px 12px 40px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, color: '#94a3b8', marginTop: 8 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e2330' }}>
                  {['Acquired', 'Shares', 'Cost/sh', 'Total cost', 'Source', 'Notes'].map(h => (
                    <th key={h} style={{ padding: '5px 8px', textAlign: h === 'Acquired' || h === 'Source' || h === 'Notes' ? 'left' : 'right', fontWeight: 500, color: '#475569' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pos.lots.filter(l => !l.closedDate).map(lot => (
                  <tr key={lot.id} style={{ borderBottom: '1px solid #0f1117' }}>
                    <td style={{ padding: '5px 8px' }}>{new Date(lot.acquiredDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{fmtShares(lot.shares)}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{fmtDollars(lot.costBasis)}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{fmtDollars(lot.shares * lot.costBasis)}</td>
                    <td style={{ padding: '5px 8px' }}>
                      <Pill color={lot.source === 'import' ? '#a78bfa' : '#60a5fa'}>{lot.source}</Pill>
                    </td>
                    <td style={{ padding: '5px 8px', color: '#475569' }}>{lot.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Bucket tab content ────────────────────────────────────────────────────────

const SORT_KEYS = {
  'Symbol':    p => p.ticker.symbol,
  'Name':      p => p.ticker.shortName || p.ticker.name || '',
  'Shares':    p => p.totalShares ?? 0,
  'Price':     p => p.lastPrice ?? 0,
  'Mkt Value': p => p.marketValue ?? p.totalCost ?? 0,
  'Total G/L': p => p.unrealisedGain ?? 0,
  'Day G/L':   p => p.dayGainDollar ?? 0,
  '% Acct':    p => p.pctOfAcct ?? 0,
};

function BucketTabContent({ bucket, positions, cashBalance, marginBalance, marginRate, marginAsOfDate, cashAsOfDate, onBucketChange, onDeletePosition, onEditPosition, onUpdateCash }) {
  const [sortKey, setSortKey] = useState('Symbol');
  const [sortDir, setSortDir] = useState('asc');

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }
  if (bucket === 'cash') {
    const net = (cashBalance ?? 0) - (marginBalance ?? 0);
    return (
      <div style={{ padding: '16px 0' }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ background: '#0d1018', border: '1px solid #1e2330', borderRadius: 8, padding: '14px 18px', minWidth: 180 }}>
            <div style={{ fontSize: 11, color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Cash & money market</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: cashBalance < 0 ? '#ef4444' : '#f1f5f9' }}>
              {cashBalance != null ? fmtDollars(cashBalance) : '—'}
            </div>
            {cashAsOfDate && <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>as of {new Date(cashAsOfDate).toLocaleDateString()}</div>}
          </div>
          {marginBalance != null && (
            <div style={{ background: '#0d1018', border: '1px solid #1e2330', borderRadius: 8, padding: '14px 18px', minWidth: 180 }}>
              <div style={{ fontSize: 11, color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Margin debit</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#ef4444' }}>{fmtDollars(marginBalance)}</div>
              {marginRate && <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{(marginRate * 100).toFixed(2)}% annual rate</div>}
              {marginAsOfDate && <div style={{ fontSize: 11, color: '#475569' }}>as of {new Date(marginAsOfDate).toLocaleDateString()}</div>}
            </div>
          )}
          <div style={{ background: '#0d1018', border: '1px solid #1e2330', borderRadius: 8, padding: '14px 18px', minWidth: 180 }}>
            <div style={{ fontSize: 11, color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Net cash</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: net < 0 ? '#ef4444' : '#f1f5f9' }}>{fmtDollars(net)}</div>
          </div>
        </div>
        <button
          onClick={onUpdateCash}
          style={{ marginTop: 14, background: 'transparent', border: '1px solid #2d3748', color: '#60a5fa', fontSize: 12, padding: '4px 12px', borderRadius: 5, cursor: 'pointer' }}
        >
          Update manually
        </button>
      </div>
    );
  }

  const bucketPositions = positions
    .filter(p => p.effectiveBucket === bucket)
    .slice()
    .sort((a, b) => {
      const fn = SORT_KEYS[sortKey];
      if (!fn) return 0;
      const av = fn(a), bv = fn(b);
      if (typeof av === 'string') return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortDir === 'asc' ? av - bv : bv - av;
    });

  if (!bucketPositions.length) {
    return <div style={{ padding: '24px 0', color: '#475569', fontSize: 13 }}>No {BUCKET_LABELS[bucket].toLowerCase()} positions.</div>;
  }

  const HEADERS = ['', 'Symbol', 'Name', 'Shares', 'Price', 'Mkt Value', 'Total G/L', 'Day G/L', '% Acct', 'Bucket', ''];
  const RIGHT_ALIGN = new Set(['Shares', 'Price', 'Mkt Value', 'Total G/L', 'Day G/L', '% Acct']);
  const SORTABLE = new Set(Object.keys(SORT_KEYS));

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #1e2330' }}>
            {HEADERS.map(h => (
              <th
                key={h}
                onClick={SORTABLE.has(h) ? () => handleSort(h) : undefined}
                style={{
                  padding: '7px 12px',
                  textAlign: RIGHT_ALIGN.has(h) ? 'right' : 'left',
                  fontSize: 10,
                  fontWeight: 600,
                  color: sortKey === h ? '#60a5fa' : '#475569',
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                  cursor: SORTABLE.has(h) ? 'pointer' : 'default',
                  userSelect: 'none',
                  whiteSpace: 'nowrap',
                }}
              >
                {h}
                {SORTABLE.has(h) && (
                  <span style={{ marginLeft: 3, fontSize: 9, color: sortKey === h ? '#60a5fa' : '#334155' }}>
                    {sortKey === h ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bucketPositions.map(pos => (
            <PositionRow key={pos.id} pos={pos} onBucketChange={onBucketChange} onDelete={onDeletePosition} onEdit={onEditPosition} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Inline account expand panel ───────────────────────────────────────────────

function AccountPanel({ account, token, onRefresh, onUpdateCash }) {
  const [activeTab, setActiveTab]       = useState('equity');
  const [refreshing, setRefreshing]     = useState(false);
  const [refreshMsg, setRefreshMsg]     = useState('');
  const [importing, setImporting]       = useState(false);
  const [importMsg, setImportMsg]       = useState('');
  const [showAddPosition, setShowAddPosition] = useState(false);
  const [editPosition, setEditPosition]       = useState(null);
  const posFileRef = useRef(null);
  const txFileRef  = useRef(null);

  const positions = account.positions || [];

  // Count per bucket tab
  function countForTab(bucket) {
    if (bucket === 'cash') return null;
    return positions.filter(p => p.effectiveBucket === bucket).length;
  }

  async function handleBucketChange(tickerId, bucket) {
    await fetch(`${API}/api/portfolio/tickers/${tickerId}/bucket`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ bucket }),
    });
    onRefresh();
  }

  async function handleDeletePosition(positionId) {
    await fetch(`${API}/api/portfolio/positions/${positionId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    onRefresh();
  }

  async function handleRefreshPrices() {
    setRefreshing(true);
    setRefreshMsg('');
    try {
      const res = await fetch(`${API}/api/portfolio/accounts/${account.id}/refresh-prices`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      const errDetail = data.errors?.length
        ? ` Errors: ${data.errors.map(e => `${e.symbol}: ${e.error}`).join(' | ')}`
        : '';
      setRefreshMsg(`Updated ${data.updated} position${data.updated !== 1 ? 's' : ''}.${errDetail}`);
      onRefresh();
    } catch (err) {
      setRefreshMsg('Error: ' + err.message);
    } finally {
      setRefreshing(false);
    }
  }

  async function handleImport(file) {
    setImporting(true);
    setImportMsg('');
    try {
      const text = await readFileText(file);
      const isJSON = file.name.toLowerCase().endsWith('.json');

      const body = isJSON
        ? { transactionsJSON: text }        // JSON only → lot reconstruction from transactions
        : { positionsCSV: text };           // CSV only → AI-parsed positions

      const res = await fetch(`${API}/api/portfolio/accounts/${account.id}/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      setImportMsg(data.message || 'Import complete.');
      onRefresh();
    } catch (err) {
      setImportMsg('Error: ' + err.message);
    } finally {
      setImporting(false);
    }
  }

  function onFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    handleImport(file);
    e.target.value = '';
  }

  return (
    <div style={{
      background: '#090c12',
      border: '1px solid #1e2330',
      borderTop: 'none',
      borderRadius: '0 0 10px 10px',
      padding: '0 20px 20px',
    }}>
      {/* Panel header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 0 12px', borderBottom: '1px solid #1e2330' }}>
        <div style={{ fontWeight: 600, color: '#f1f5f9', fontSize: 14 }}>
          {account.name}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {/* Add position */}
          <ActionButton
            onClick={() => setShowAddPosition(true)}
            disabled={false}
            icon="+"
            label="Add position"
          />
          {/* Import file — accepts CSV (positions) or JSON (transactions) */}
          <input ref={posFileRef} type="file" accept=".csv,.json" style={{ display: 'none' }} onChange={onFileChange} />
          <ActionButton
            onClick={() => posFileRef.current?.click()}
            disabled={importing}
            icon="⬆"
            label={importing ? 'Importing…' : 'Import file'}
          />
          {/* Refresh prices */}
          <ActionButton
            onClick={handleRefreshPrices}
            disabled={refreshing}
            icon="↻"
            label={refreshing ? 'Refreshing…' : 'Refresh prices'}
          />
          {/* Connect brokerage (placeholder) */}
          <ActionButton
            onClick={() => {}}
            disabled
            icon="⟳"
            label="Connect brokerage"
            title="Coming soon — direct Schwab API sync"
          />
        </div>
      </div>

      {/* Status messages */}
      {(importMsg || refreshMsg) && (
        <div style={{ fontSize: 12, color: '#94a3b8', padding: '8px 0 0', marginBottom: -4 }}>
          {importMsg || refreshMsg}
        </div>
      )}

      {/* Bucket tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid #1e2330', marginTop: 12 }}>
        {BUCKET_TABS.map(tab => {
          const count = countForTab(tab);
          const active = activeTab === tab;
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: active ? `2px solid ${BUCKET_COLORS[tab]}` : '2px solid transparent',
                color: active ? BUCKET_COLORS[tab] : '#475569',
                fontSize: 12,
                fontWeight: active ? 700 : 400,
                padding: '8px 14px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 5,
              }}
            >
              {BUCKET_LABELS[tab]}
              {count != null && count > 0 && (
                <span style={{
                  background: active ? BUCKET_COLORS[tab] + '22' : '#1e2330',
                  color: active ? BUCKET_COLORS[tab] : '#475569',
                  borderRadius: 10,
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '1px 6px',
                }}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <BucketTabContent
        bucket={activeTab}
        positions={positions}
        cashBalance={account.cashBalance}
        marginBalance={account.marginBalance}
        marginRate={account.marginRate}
        marginAsOfDate={account.marginAsOfDate}
        cashAsOfDate={account.cashAsOfDate}
        onBucketChange={handleBucketChange}
        onDeletePosition={handleDeletePosition}
        onEditPosition={pos => setEditPosition(pos)}
        onUpdateCash={onUpdateCash}
      />

      {showAddPosition && (
        <AddPositionModal
          accountId={account.id}
          token={token}
          onSaved={() => { setShowAddPosition(false); onRefresh(); }}
          onClose={() => setShowAddPosition(false)}
        />
      )}

      {editPosition && (
        <EditPositionModal
          position={editPosition}
          token={token}
          onSaved={() => { setEditPosition(null); onRefresh(); }}
          onClose={() => setEditPosition(null)}
        />
      )}
    </div>
  );
}

function ActionButton({ onClick, disabled, icon, label, title }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        background: disabled && !label.includes('…') ? '#0d1018' : 'transparent',
        border: '1px solid #2d3748',
        color: disabled && !label.includes('…') ? '#2d3748' : '#94a3b8',
        fontSize: 12,
        padding: '5px 12px',
        borderRadius: 5,
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 5,
      }}
    >
      <span style={{ fontSize: 13 }}>{icon}</span> {label}
    </button>
  );
}

// ── Add Position modal ────────────────────────────────────────────────────────

const emptyLot = () => ({ shares: '', costBasis: '', acquiredDate: '', notes: '' });

function AddPositionModal({ accountId, token, onSaved, onClose }) {
  const [symbol, setSymbol] = useState('');
  const [lots, setLots]     = useState([emptyLot()]);
  const [error, setError]   = useState('');
  const [saving, setSaving] = useState(false);

  const inputStyle = {
    background: '#0d1018', border: '1px solid #2d3748', borderRadius: 5,
    color: '#f1f5f9', fontSize: 13, padding: '6px 10px', outline: 'none',
    width: '100%', boxSizing: 'border-box',
  };
  const labelStyle = { fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 };

  function updateLot(idx, field, val) {
    setLots(prev => prev.map((l, i) => i === idx ? { ...l, [field]: val } : l));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    const cleanLots = lots.filter(l => l.shares && l.costBasis && l.acquiredDate);
    if (!cleanLots.length) { setError('At least one complete lot is required.'); return; }
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/portfolio/positions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ symbol: symbol.trim().toUpperCase(), accountId, lots: cleanLots }),
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

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#00000099', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ background: '#0f1117', border: '1px solid #1e2330', borderRadius: 10, padding: 24, width: 520, maxWidth: '95vw', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ fontWeight: 600, color: '#f1f5f9', marginBottom: 16, fontSize: 14 }}>Add position</div>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={labelStyle}>Ticker symbol</label>
            <input style={{ ...inputStyle, width: 160 }} value={symbol}
              onChange={e => setSymbol(e.target.value.toUpperCase())}
              placeholder="e.g. ENPH" required />
            <div style={{ fontSize: 11, color: '#475569', marginTop: 3 }}>Must already exist in RADAR</div>
          </div>

          <div>
            <div style={{ ...labelStyle, marginBottom: 8 }}>Tax lots</div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e2330' }}>
                  {['Acquired date', 'Shares', 'Cost/share ($)', 'Notes', ''].map(h => (
                    <th key={h} style={{ padding: '4px 6px', textAlign: 'left', color: '#64748b', fontWeight: 500 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {lots.map((lot, idx) => (
                  <tr key={idx}>
                    <td style={{ padding: '4px 4px' }}>
                      <input type="date" style={inputStyle} value={lot.acquiredDate}
                        onChange={e => updateLot(idx, 'acquiredDate', e.target.value)} />
                    </td>
                    <td style={{ padding: '4px 4px' }}>
                      <input type="number" step="0.0001" min="0" style={inputStyle} placeholder="0.0000"
                        value={lot.shares} onChange={e => updateLot(idx, 'shares', e.target.value)} />
                    </td>
                    <td style={{ padding: '4px 4px' }}>
                      <input type="number" step="0.01" min="0" style={inputStyle} placeholder="0.00"
                        value={lot.costBasis} onChange={e => updateLot(idx, 'costBasis', e.target.value)} />
                    </td>
                    <td style={{ padding: '4px 4px' }}>
                      <input style={inputStyle} placeholder="optional"
                        value={lot.notes} onChange={e => updateLot(idx, 'notes', e.target.value)} />
                    </td>
                    <td style={{ padding: '4px 4px', textAlign: 'center' }}>
                      <button type="button" onClick={() => setLots(prev => prev.filter((_, i) => i !== idx))}
                        disabled={lots.length === 1}
                        style={{ background: 'none', border: 'none', color: lots.length === 1 ? '#2d3748' : '#ef4444', cursor: lots.length === 1 ? 'default' : 'pointer', fontSize: 16 }}>
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button type="button" onClick={() => setLots(prev => [...prev, emptyLot()])}
              style={{ marginTop: 8, background: 'transparent', border: '1px solid #2d3748', color: '#60a5fa', fontSize: 12, padding: '4px 12px', borderRadius: 5, cursor: 'pointer' }}>
              + Add another lot
            </button>
          </div>

          {error && <div style={{ color: '#ef4444', fontSize: 12, padding: '6px 10px', background: '#ef444411', borderRadius: 5 }}>{error}</div>}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button type="button" onClick={onClose}
              style={{ background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 13, padding: '6px 16px', borderRadius: 5, cursor: 'pointer' }}>
              Cancel
            </button>
            <button type="submit" disabled={saving}
              style={{ background: saving ? '#1e2330' : '#3b82f6', border: 'none', color: '#f1f5f9', fontSize: 13, fontWeight: 600, padding: '6px 20px', borderRadius: 5, cursor: saving ? 'wait' : 'pointer' }}>
              {saving ? 'Saving…' : 'Save position'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Edit Position modal ───────────────────────────────────────────────────────

function EditPositionModal({ position, token, onSaved, onClose }) {
  const openLots = position.lots.filter(l => !l.closedDate);
  const [lots, setLots] = useState(openLots.map(l => ({
    id: l.id,
    shares:      String(l.shares),
    costBasis:   String(l.costBasis),
    acquiredDate: l.acquiredDate ? l.acquiredDate.slice(0, 10) : '',
    notes:       l.notes || '',
  })));
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const inputStyle = {
    background: '#0d1018', border: '1px solid #2d3748', borderRadius: 5,
    color: '#f1f5f9', fontSize: 12, padding: '5px 8px', outline: 'none',
    width: '100%', boxSizing: 'border-box',
  };

  function updateLot(idx, field, val) {
    setLots(prev => prev.map((l, i) => i === idx ? { ...l, [field]: val } : l));
  }

  async function handleSave(e) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      // For each lot: delete and recreate with new values (simplest approach)
      await Promise.all(lots.map(lot =>
        fetch(`${API}/api/portfolio/lots/${lot.id}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        })
      ));
      await Promise.all(lots.map(lot =>
        fetch(`${API}/api/portfolio/lots`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            positionId:  position.id,
            shares:      parseFloat(lot.shares),
            costBasis:   parseFloat(lot.costBasis),
            acquiredDate: lot.acquiredDate,
            notes:       lot.notes || null,
            source:      'manual',
          }),
        })
      ));
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#00000099', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ background: '#0f1117', border: '1px solid #1e2330', borderRadius: 10, padding: 24, width: 580, maxWidth: '95vw', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ fontWeight: 600, color: '#f1f5f9', marginBottom: 4, fontSize: 14 }}>
          Edit lots — {position.ticker.symbol}
        </div>
        <div style={{ fontSize: 12, color: '#475569', marginBottom: 16 }}>
          Changes apply to open lots only. Closed lots are preserved.
        </div>
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e2330' }}>
                {['Acquired date', 'Shares', 'Cost/share ($)', 'Notes', ''].map(h => (
                  <th key={h} style={{ padding: '5px 6px', textAlign: 'left', color: '#64748b', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {lots.map((lot, idx) => (
                <tr key={lot.id} style={{ borderBottom: '1px solid #0f1117' }}>
                  <td style={{ padding: '5px 4px' }}>
                    <input type="date" style={inputStyle} value={lot.acquiredDate}
                      onChange={e => updateLot(idx, 'acquiredDate', e.target.value)} required />
                  </td>
                  <td style={{ padding: '5px 4px' }}>
                    <input type="number" step="0.0001" min="0" style={inputStyle}
                      value={lot.shares} onChange={e => updateLot(idx, 'shares', e.target.value)} required />
                  </td>
                  <td style={{ padding: '5px 4px' }}>
                    <input type="number" step="0.01" min="0" style={inputStyle}
                      value={lot.costBasis} onChange={e => updateLot(idx, 'costBasis', e.target.value)} required />
                  </td>
                  <td style={{ padding: '5px 4px' }}>
                    <input style={inputStyle} placeholder="optional"
                      value={lot.notes} onChange={e => updateLot(idx, 'notes', e.target.value)} />
                  </td>
                  <td style={{ padding: '5px 4px', textAlign: 'center' }}>
                    <button
                      type="button"
                      onClick={() => setLots(prev => prev.filter((_, i) => i !== idx))}
                      disabled={lots.length === 1}
                      title="Remove this lot"
                      style={{ background: 'none', border: 'none', color: lots.length === 1 ? '#2d3748' : '#ef4444', cursor: lots.length === 1 ? 'default' : 'pointer', fontSize: 16, lineHeight: 1 }}
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {error && <div style={{ color: '#ef4444', fontSize: 12 }}>{error}</div>}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button type="button" onClick={onClose}
              style={{ background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 13, padding: '6px 16px', borderRadius: 5, cursor: 'pointer' }}>
              Cancel
            </button>
            <button type="submit" disabled={saving}
              style={{ background: saving ? '#1e2330' : '#3b82f6', border: 'none', color: '#f1f5f9', fontSize: 13, fontWeight: 600, padding: '6px 20px', borderRadius: 5, cursor: saving ? 'wait' : 'pointer' }}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Account card ──────────────────────────────────────────────────────────────

function AccountCard({ account, expanded, onToggle, token, onRefresh, onDeleted }) {
  const [showCashEdit, setShowCashEdit]       = useState(false);
  const [showDeleteStep1, setShowDeleteStep1] = useState(false);
  const [showDeleteStep2, setShowDeleteStep2] = useState(false);

  const typeLabel = ACCOUNT_TYPE_LABELS[account.type] || account.type;
  const managed   = account.managed;
  const totalMV   = account.totalMarketValue ?? 0;
  const gain      = account.totalUnrealised ?? 0;
  const gainPct   = totalMV > 0 ? gain / (totalMV - gain) : 0;
  const dayGain   = account.totalDayGain ?? 0;
  const netCash   = (account.cashBalance ?? 0) - (account.marginBalance ?? 0);
  const buckets   = account.bucketTotals || {};

  return (
    <div style={{ marginBottom: 12 }}>
      {/* Card */}
      <div
        onClick={onToggle}
        style={{
          background: '#0f1117',
          border: `1px solid ${expanded ? '#2d3d5a' : '#1e2330'}`,
          borderRadius: expanded ? '10px 10px 0 0' : 10,
          padding: '16px 20px',
          cursor: 'pointer',
          transition: 'border-color 0.15s',
        }}
        onMouseEnter={e => { if (!expanded) e.currentTarget.style.borderColor = '#2d3748'; }}
        onMouseLeave={e => { if (!expanded) e.currentTarget.style.borderColor = '#1e2330'; }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          {/* Left: name + badges */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ color: '#475569', fontSize: 10 }}>{expanded ? '▼' : '▶'}</span>
              <span style={{ fontWeight: 700, color: '#f1f5f9', fontSize: 15 }}>{account.name}</span>
              <Pill color="#60a5fa">{typeLabel}</Pill>
              <Pill color="#94a3b8">{account.owner}</Pill>
              <Pill color={managed ? '#34d399' : '#475569'}>{managed ? 'agent-managed' : 'manual'}</Pill>
            </div>
            {/* Today + all-time gain */}
            <div style={{ fontSize: 12, color: '#475569', marginTop: 2 }}>
              Today:{' '}
              <span style={{ color: gainColor(dayGain) }}>{fmtDollars(dayGain)}</span>
              {'  ·  '}All-time:{' '}
              <span style={{ color: gainColor(gain) }}>{fmtDollars(gain)} ({fmtPct(gainPct)})</span>
            </div>
          </div>
          {/* Right: total MV + delete */}
          <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>{fmtDollars(totalMV, true)}</div>
            <button
              onClick={e => { e.stopPropagation(); setShowDeleteStep1(true); }}
              title="Delete account"
              style={{ background: 'none', border: 'none', color: '#334155', cursor: 'pointer', fontSize: 12, padding: 0 }}
              onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
              onMouseLeave={e => e.currentTarget.style.color = '#334155'}
            >
              Delete account
            </button>
          </div>
        </div>
        {/* Bucket pills */}
        <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
          {Object.entries(buckets).map(([b, val]) => val > 0 && (
            <span key={b} style={{
              fontSize: 11,
              color: BUCKET_COLORS[b],
              background: BUCKET_COLORS[b] + '11',
              border: `1px solid ${BUCKET_COLORS[b]}22`,
              borderRadius: 4,
              padding: '2px 8px',
            }}>
              {BUCKET_LABELS[b]} {fmtDollars(val, true)}
            </span>
          ))}
          {account.cashBalance != null && (
            <span style={{ fontSize: 11, color: '#94a3b8', background: '#94a3b811', border: '1px solid #94a3b822', borderRadius: 4, padding: '2px 8px' }}>
              Cash {fmtDollars(netCash, true)}
            </span>
          )}
        </div>
      </div>

      {/* Inline expand panel */}
      {expanded && (
        <AccountPanel
          account={account}
          token={token}
          onRefresh={onRefresh}
          onUpdateCash={() => setShowCashEdit(true)}
        />
      )}

      {/* Cash edit modal */}
      {showCashEdit && (
        <UpdateCashModal
          account={account}
          token={token}
          onSaved={() => { setShowCashEdit(false); onRefresh(); }}
          onClose={() => setShowCashEdit(false)}
        />
      )}

      {/* Delete step 1 */}
      {showDeleteStep1 && (
        <DeleteAccountStep1
          account={account}
          onNext={() => { setShowDeleteStep1(false); setShowDeleteStep2(true); }}
          onClose={() => setShowDeleteStep1(false)}
        />
      )}

      {/* Delete step 2 */}
      {showDeleteStep2 && (
        <DeleteAccountStep2
          account={account}
          token={token}
          onDeleted={() => { setShowDeleteStep2(false); onDeleted(); }}
          onClose={() => setShowDeleteStep2(false)}
        />
      )}
    </div>
  );
}

// ── Update cash modal ─────────────────────────────────────────────────────────

function UpdateCashModal({ account, token, onSaved, onClose }) {
  const [cashBalance, setCash]     = useState(account.cashBalance ?? '');
  const [marginBalance, setMargin] = useState(account.marginBalance ?? '');
  const [marginRate, setRate]      = useState(account.marginRate ? (account.marginRate * 100).toString() : '');
  const [saving, setSaving]        = useState(false);
  const [error, setError]          = useState('');

  const inputStyle = {
    background: '#0d1018', border: '1px solid #2d3748', borderRadius: 5,
    color: '#f1f5f9', fontSize: 13, padding: '6px 10px', outline: 'none', width: '100%', boxSizing: 'border-box',
  };

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const body = {
        cashBalance:    parseFloat(cashBalance) || 0,
        cashAsOfDate:   new Date().toISOString(),
      };
      if (marginBalance !== '') body.marginBalance = parseFloat(marginBalance);
      if (marginRate !== '')    body.marginRate    = parseFloat(marginRate) / 100;
      const res = await fetch(`${API}/api/portfolio/accounts/${account.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#00000099', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ background: '#0f1117', border: '1px solid #1e2330', borderRadius: 10, padding: 24, width: 380, maxWidth: '95vw' }}>
        <div style={{ fontWeight: 600, color: '#f1f5f9', marginBottom: 16 }}>Update cash — {account.name}</div>
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Cash & money market ($)</label>
            <input type="number" step="0.01" style={inputStyle} value={cashBalance} onChange={e => setCash(e.target.value)} placeholder="0.00" />
            <div style={{ fontSize: 11, color: '#475569', marginTop: 3 }}>Negative = margin debit balance</div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Margin debit balance ($) — optional</label>
            <input type="number" step="0.01" min="0" style={inputStyle} value={marginBalance} onChange={e => setMargin(e.target.value)} placeholder="0.00" />
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Margin interest rate (%) — optional</label>
            <input type="number" step="0.01" min="0" style={inputStyle} value={marginRate} onChange={e => setRate(e.target.value)} placeholder="8.25" />
          </div>
          {error && <div style={{ color: '#ef4444', fontSize: 12 }}>{error}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button type="button" onClick={onClose} style={{ background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 13, padding: '6px 16px', borderRadius: 5, cursor: 'pointer' }}>Cancel</button>
            <button type="submit" disabled={saving} style={{ background: saving ? '#1e2330' : '#3b82f6', border: 'none', color: '#f1f5f9', fontSize: 13, fontWeight: 600, padding: '6px 20px', borderRadius: 5, cursor: saving ? 'wait' : 'pointer' }}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Add account modal ─────────────────────────────────────────────────────────

function AddAccountModal({ token, onSaved, onClose }) {
  const [name, setName]     = useState('');
  const [type, setType]     = useState('taxable');
  const [owner, setOwner]   = useState('Luis');
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const inputStyle = {
    background: '#0d1018', border: '1px solid #2d3748', borderRadius: 5,
    color: '#f1f5f9', fontSize: 13, padding: '6px 10px', outline: 'none', width: '100%', boxSizing: 'border-box',
  };

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`${API}/api/portfolio/accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name, type, owner }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#00000099', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ background: '#0f1117', border: '1px solid #1e2330', borderRadius: 10, padding: 24, width: 380, maxWidth: '95vw' }}>
        <div style={{ fontWeight: 600, color: '#f1f5f9', marginBottom: 16 }}>Add account</div>
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Account name</label>
            <input style={inputStyle} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Schwab Taxable 1" required />
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Type</label>
            <select style={{ ...inputStyle, cursor: 'pointer' }} value={type} onChange={e => setType(e.target.value)}>
              {Object.entries(ACCOUNT_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Owner</label>
            <input style={inputStyle} value={owner} onChange={e => setOwner(e.target.value)} placeholder="Luis" required />
          </div>
          {error && <div style={{ color: '#ef4444', fontSize: 12 }}>{error}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button type="button" onClick={onClose} style={{ background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 13, padding: '6px 16px', borderRadius: 5, cursor: 'pointer' }}>Cancel</button>
            <button type="submit" disabled={saving} style={{ background: saving ? '#1e2330' : '#3b82f6', border: 'none', color: '#f1f5f9', fontSize: 13, fontWeight: 600, padding: '6px 20px', borderRadius: 5, cursor: saving ? 'wait' : 'pointer' }}>
              {saving ? 'Saving…' : 'Add account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function readFileText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => resolve(e.target.result);
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsText(file);
  });
}

// ── Delete account modals ─────────────────────────────────────────────────────

function DeleteAccountStep1({ account, onNext, onClose }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: '#00000099', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ background: '#0f1117', border: '1px solid #3d1515', borderRadius: 10, padding: 28, width: 460, maxWidth: '95vw' }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#fca5a5', marginBottom: 12 }}>⚠ Delete account</div>
        <p style={{ fontSize: 14, color: '#f1f5f9', lineHeight: 1.6, margin: '0 0 12px' }}>
          You are about to permanently delete <strong>{account.name}</strong>.
        </p>
        <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.6, margin: '0 0 20px' }}>
          This will erase all positions, tax lots, and cost basis history for this account.
          Any unrealised gain/loss data and import history will be gone permanently.
          This action <strong style={{ color: '#fca5a5' }}>cannot be undone</strong>.
        </p>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose}
            style={{ background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 13, padding: '7px 18px', borderRadius: 5, cursor: 'pointer' }}>
            Cancel
          </button>
          <button onClick={onNext}
            style={{ background: '#7f1d1d', border: '1px solid #ef4444', color: '#fca5a5', fontSize: 13, fontWeight: 600, padding: '7px 18px', borderRadius: 5, cursor: 'pointer' }}>
            I understand — continue
          </button>
        </div>
      </div>
    </div>
  );
}

function DeleteAccountStep2({ account, token, onDeleted, onClose }) {
  const [typed, setTyped]   = useState('');
  const [deleting, setDeleting] = useState(false);
  const [error, setError]   = useState('');
  const confirmed = typed === account.name;

  async function handleDelete() {
    setDeleting(true);
    setError('');
    try {
      const res = await fetch(`${API}/api/portfolio/accounts/${account.id}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ confirm: true }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      onDeleted();
    } catch (err) {
      setError(err.message);
      setDeleting(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#00000099', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ background: '#0f1117', border: '1px solid #3d1515', borderRadius: 10, padding: 28, width: 420, maxWidth: '95vw' }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: '#fca5a5', marginBottom: 12 }}>Final confirmation</div>
        <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.6, margin: '0 0 16px' }}>
          Type the account name exactly to confirm deletion:
        </p>
        <div style={{ fontSize: 12, color: '#475569', marginBottom: 6, fontFamily: 'monospace' }}>{account.name}</div>
        <input
          style={{
            background: '#0d1018', border: `1px solid ${confirmed ? '#ef4444' : '#2d3748'}`,
            borderRadius: 5, color: '#f1f5f9', fontSize: 13, padding: '7px 10px',
            outline: 'none', width: '100%', boxSizing: 'border-box', marginBottom: 16,
          }}
          value={typed}
          onChange={e => setTyped(e.target.value)}
          placeholder="Type account name here"
          autoFocus
        />
        {error && <div style={{ color: '#ef4444', fontSize: 12, marginBottom: 12 }}>{error}</div>}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose}
            style={{ background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 13, padding: '7px 18px', borderRadius: 5, cursor: 'pointer' }}>
            Cancel
          </button>
          <button
            onClick={handleDelete}
            disabled={!confirmed || deleting}
            style={{
              background: confirmed && !deleting ? '#ef4444' : '#2d1515',
              border: 'none', color: confirmed ? '#fff' : '#475569',
              fontSize: 13, fontWeight: 600, padding: '7px 18px', borderRadius: 5,
              cursor: confirmed && !deleting ? 'pointer' : 'not-allowed',
            }}
          >
            {deleting ? 'Deleting…' : 'Delete permanently'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Portfolio page ───────────────────────────────────────────────────────

export default function Portfolio() {
  const { getToken }           = useAuth();
  const [token, setToken]      = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading]  = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [showAddAccount, setShowAddAccount] = useState(false);

  useEffect(() => { getToken().then(setToken); }, [getToken]);

  const fetchAccounts = useCallback(async () => {
    if (!token) return;
    const res = await fetch(`${API}/api/portfolio/accounts`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setAccounts(await res.json());
    setLoading(false);
  }, [token]);

  useEffect(() => { fetchAccounts(); }, [fetchAccounts]);

  // Summary banner aggregates
  const totalMV        = accounts.reduce((s, a) => s + (a.totalMarketValue ?? 0), 0);
  const totalCost      = accounts.reduce((s, a) => s + (a.totalCost ?? 0), 0);
  const totalUnrealised = accounts.reduce((s, a) => s + (a.totalUnrealised ?? 0), 0);
  const unrealisedPct  = totalCost > 0 ? totalUnrealised / totalCost : 0;
  const totalDayGain   = accounts.reduce((s, a) => s + (a.totalDayGain ?? 0), 0);
  const dayPct         = totalMV > 0 ? totalDayGain / (totalMV - totalDayGain) : 0;
  const totalMargin    = accounts.reduce((s, a) => s + (a.marginBalance ?? 0), 0);
  const netValue       = totalMV - totalMargin;

  function toggleExpand(id) {
    setExpandedId(prev => prev === id ? null : id);
  }

  return (
    <div style={{ padding: '72px 32px 48px', maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>Portfolio</div>
          <div style={{ fontSize: 13, color: '#475569', marginTop: 2 }}>Account · Position · Lot tracking</div>
        </div>
        <button
          onClick={() => setShowAddAccount(true)}
          style={{ background: '#3b82f6', border: 'none', color: '#fff', fontSize: 13, fontWeight: 600, padding: '7px 18px', borderRadius: 6, cursor: 'pointer' }}
        >
          + Add account
        </button>
      </div>

      {/* Summary banner */}
      {accounts.length > 0 && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 28 }}>
          <MetricCard label="Total portfolio" value={fmtDollars(totalMV, true)} />
          <MetricCard
            label="Unrealised gain"
            value={fmtDollars(totalUnrealised, true)}
            sub={fmtPct(unrealisedPct)}
            subColor={gainColor(totalUnrealised)}
          />
          <MetricCard
            label="Today's change"
            value={fmtDollars(totalDayGain, true)}
            sub={fmtPct(dayPct)}
            subColor={gainColor(totalDayGain)}
          />
          <MetricCard
            label="Net value"
            value={fmtDollars(netValue, true)}
            sub={totalMargin > 0 ? `−${fmtDollars(totalMargin, true)} margin` : 'No margin debt'}
            subColor={totalMargin > 0 ? '#ef4444' : '#475569'}
          />
        </div>
      )}

      {/* Account card grid */}
      {loading ? (
        <div style={{ color: '#475569', fontSize: 13 }}>Loading…</div>
      ) : accounts.length === 0 ? (
        <div style={{ color: '#475569', fontSize: 13, marginTop: 8 }}>
          No accounts yet. Click "+ Add account" to create your first.
        </div>
      ) : (
        accounts.map(acct => (
          <AccountCard
            key={acct.id}
            account={acct}
            expanded={expandedId === acct.id}
            onToggle={() => toggleExpand(acct.id)}
            token={token}
            onRefresh={fetchAccounts}
            onDeleted={fetchAccounts}
          />
        ))
      )}

      {/* Add account modal */}
      {showAddAccount && token && (
        <AddAccountModal
          token={token}
          onSaved={() => { setShowAddAccount(false); fetchAccounts(); }}
          onClose={() => setShowAddAccount(false)}
        />
      )}
    </div>
  );
}
