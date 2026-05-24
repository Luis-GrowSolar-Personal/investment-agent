import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';

const API_URL = import.meta.env.VITE_API_URL || '';

// ── Helpers ───────────────────────────────────────────────────────────────────

const ACCOUNTS = ['taxable', 'ira', 'roth'];

const ACCOUNT_LABELS = { taxable: 'Taxable', ira: 'IRA', roth: 'Roth IRA' };

function accountColor(account) {
  switch (account) {
    case 'taxable': return '#60a5fa';
    case 'ira':     return '#a78bfa';
    case 'roth':    return '#34d399';
    default:        return '#64748b';
  }
}

function typeLabel(type) {
  return type === 'B' ? 'Platform' : 'Pure-play';
}

function typeColor(type) {
  return type === 'B' ? '#f59e0b' : '#60a5fa';
}

function fmt(n, decimals = 2) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtDollars(n) {
  if (n === null || n === undefined) return '—';
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

function SectionHeader({ children }) {
  return (
    <div style={{
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      color: '#475569',
      margin: '28px 0 10px',
    }}>
      {children}
    </div>
  );
}

function Badge({ color, children }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 7px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 600,
      background: color + '1a',
      color,
      border: `1px solid ${color}33`,
    }}>
      {children}
    </span>
  );
}

// ── Position list ─────────────────────────────────────────────────────────────

function PositionRow({ pos, onAddLot }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        onClick={() => setExpanded(e => !e)}
        style={{ cursor: 'pointer', borderBottom: '1px solid #1e2330' }}
      >
        <td style={{ padding: '10px 12px', fontWeight: 600, color: '#f1f5f9', fontSize: 13 }}>
          {pos.ticker.symbol}
          {!pos.ticker.inScope && (
            <span style={{ marginLeft: 6, fontSize: 10, color: '#ef4444', fontWeight: 400 }}>legacy</span>
          )}
        </td>
        <td style={{ padding: '10px 12px' }}>
          <Badge color={accountColor(pos.account)}>{ACCOUNT_LABELS[pos.account]}</Badge>
        </td>
        <td style={{ padding: '10px 12px' }}>
          <Badge color={typeColor(pos.ticker.type)}>{typeLabel(pos.ticker.type)}</Badge>
        </td>
        <td style={{ padding: '10px 12px', color: '#94a3b8', fontSize: 13, textAlign: 'right' }}>
          {fmt(pos.totalShares, 4)} sh
        </td>
        <td style={{ padding: '10px 12px', color: '#94a3b8', fontSize: 13, textAlign: 'right' }}>
          {fmtDollars(pos.avgCostBasis)}
        </td>
        <td style={{ padding: '10px 12px', color: '#94a3b8', fontSize: 13, textAlign: 'right' }}>
          {fmtDollars(pos.totalShares * pos.avgCostBasis)}
        </td>
        <td style={{ padding: '10px 12px', color: '#475569', fontSize: 12, textAlign: 'right' }}>
          {pos.lots.length} lot{pos.lots.length !== 1 ? 's' : ''} {expanded ? '▲' : '▼'}
        </td>
      </tr>

      {expanded && (
        <tr>
          <td colSpan={7} style={{ background: '#0d1018', padding: '0 12px 12px 32px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, color: '#94a3b8' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e2330' }}>
                  <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>Acquired</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 500 }}>Shares</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 500 }}>Cost/sh</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 500 }}>Total cost</th>
                  <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>Notes</th>
                </tr>
              </thead>
              <tbody>
                {pos.lots.map(lot => (
                  <tr key={lot.id} style={{ borderBottom: '1px solid #161b26' }}>
                    <td style={{ padding: '5px 8px' }}>
                      {new Date(lot.acquiredDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                    </td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{fmt(lot.shares, 4)}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{fmtDollars(lot.costBasis)}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{fmtDollars(lot.shares * lot.costBasis)}</td>
                    <td style={{ padding: '5px 8px', color: '#475569' }}>{lot.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button
              onClick={e => { e.stopPropagation(); onAddLot(pos); }}
              style={{
                marginTop: 8,
                background: 'transparent',
                border: '1px solid #2d3748',
                color: '#60a5fa',
                fontSize: 12,
                padding: '4px 12px',
                borderRadius: 5,
                cursor: 'pointer',
              }}
            >
              + Add lot
            </button>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Add Position form ─────────────────────────────────────────────────────────

const emptyLot = () => ({ shares: '', costBasis: '', acquiredDate: '', notes: '' });

function AddPositionForm({ token, onSaved, onCancel }) {
  const [symbol, setSymbol]   = useState('');
  const [account, setAccount] = useState('taxable');
  const [lots, setLots]       = useState([emptyLot()]);
  const [error, setError]     = useState('');
  const [saving, setSaving]   = useState(false);

  function updateLot(idx, field, value) {
    setLots(prev => prev.map((l, i) => i === idx ? { ...l, [field]: value } : l));
  }

  function addLotRow() {
    setLots(prev => [...prev, emptyLot()]);
  }

  function removeLotRow(idx) {
    if (lots.length === 1) return;
    setLots(prev => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    const cleanLots = lots.filter(l => l.shares && l.costBasis && l.acquiredDate);
    if (!cleanLots.length) { setError('At least one complete lot is required.'); return; }

    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/portfolio/positions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ symbol: symbol.trim().toUpperCase(), account, lots: cleanLots }),
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

  const inputStyle = {
    background: '#0d1018',
    border: '1px solid #2d3748',
    borderRadius: 5,
    color: '#f1f5f9',
    fontSize: 13,
    padding: '6px 10px',
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
  };

  const labelStyle = { fontSize: 11, color: '#64748b', marginBottom: 4, display: 'block' };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <label style={labelStyle}>Ticker symbol</label>
          <input
            style={inputStyle}
            value={symbol}
            onChange={e => setSymbol(e.target.value.toUpperCase())}
            placeholder="e.g. ENPH"
            required
          />
          <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>
            Must already exist in RADAR
          </div>
        </div>
        <div>
          <label style={labelStyle}>Account</label>
          <select
            style={{ ...inputStyle, cursor: 'pointer' }}
            value={account}
            onChange={e => setAccount(e.target.value)}
          >
            {ACCOUNTS.map(a => (
              <option key={a} value={a}>{ACCOUNT_LABELS[a]}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <div style={{ ...labelStyle, marginBottom: 8 }}>Tax lots</div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1e2330' }}>
              <th style={{ padding: '4px 8px', textAlign: 'left', color: '#64748b', fontWeight: 500 }}>Acquired date</th>
              <th style={{ padding: '4px 8px', textAlign: 'left', color: '#64748b', fontWeight: 500 }}>Shares</th>
              <th style={{ padding: '4px 8px', textAlign: 'left', color: '#64748b', fontWeight: 500 }}>Cost/share ($)</th>
              <th style={{ padding: '4px 8px', textAlign: 'left', color: '#64748b', fontWeight: 500 }}>Notes</th>
              <th style={{ width: 24 }} />
            </tr>
          </thead>
          <tbody>
            {lots.map((lot, idx) => (
              <tr key={idx}>
                <td style={{ padding: '4px 6px' }}>
                  <input
                    type="date"
                    style={inputStyle}
                    value={lot.acquiredDate}
                    onChange={e => updateLot(idx, 'acquiredDate', e.target.value)}
                  />
                </td>
                <td style={{ padding: '4px 6px' }}>
                  <input
                    type="number"
                    step="0.0001"
                    min="0"
                    style={inputStyle}
                    placeholder="0.0000"
                    value={lot.shares}
                    onChange={e => updateLot(idx, 'shares', e.target.value)}
                  />
                </td>
                <td style={{ padding: '4px 6px' }}>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    style={inputStyle}
                    placeholder="0.00"
                    value={lot.costBasis}
                    onChange={e => updateLot(idx, 'costBasis', e.target.value)}
                  />
                </td>
                <td style={{ padding: '4px 6px' }}>
                  <input
                    style={inputStyle}
                    placeholder="optional"
                    value={lot.notes}
                    onChange={e => updateLot(idx, 'notes', e.target.value)}
                  />
                </td>
                <td style={{ padding: '4px 6px', textAlign: 'center' }}>
                  <button
                    type="button"
                    onClick={() => removeLotRow(idx)}
                    disabled={lots.length === 1}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: lots.length === 1 ? '#2d3748' : '#ef4444',
                      cursor: lots.length === 1 ? 'default' : 'pointer',
                      fontSize: 16,
                      lineHeight: 1,
                    }}
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button
          type="button"
          onClick={addLotRow}
          style={{
            marginTop: 8,
            background: 'transparent',
            border: '1px solid #2d3748',
            color: '#60a5fa',
            fontSize: 12,
            padding: '4px 12px',
            borderRadius: 5,
            cursor: 'pointer',
          }}
        >
          + Add another lot
        </button>
      </div>

      {error && (
        <div style={{ color: '#ef4444', fontSize: 12, padding: '6px 10px', background: '#ef444411', borderRadius: 5 }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button
          type="button"
          onClick={onCancel}
          style={{
            background: 'transparent',
            border: '1px solid #2d3748',
            color: '#94a3b8',
            fontSize: 13,
            padding: '6px 16px',
            borderRadius: 5,
            cursor: 'pointer',
          }}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving}
          style={{
            background: saving ? '#1e2330' : '#3b82f6',
            border: 'none',
            color: '#f1f5f9',
            fontSize: 13,
            fontWeight: 600,
            padding: '6px 20px',
            borderRadius: 5,
            cursor: saving ? 'wait' : 'pointer',
          }}
        >
          {saving ? 'Saving…' : 'Save position'}
        </button>
      </div>
    </form>
  );
}

// ── Add Lot form (inline, for existing position) ──────────────────────────────

function AddLotModal({ position, token, onSaved, onClose }) {
  const [lot, setLot]     = useState(emptyLot());
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const inputStyle = {
    background: '#0d1018',
    border: '1px solid #2d3748',
    borderRadius: 5,
    color: '#f1f5f9',
    fontSize: 13,
    padding: '6px 10px',
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
  };

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/portfolio/positions/${position.id}/lots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(lot),
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
    <div style={{
      position: 'fixed', inset: 0, background: '#00000099',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
    }}>
      <div style={{
        background: '#0f1117', border: '1px solid #1e2330', borderRadius: 10,
        padding: 24, width: 420, maxWidth: '95vw',
      }}>
        <div style={{ fontWeight: 600, color: '#f1f5f9', marginBottom: 16 }}>
          Add lot — {position.ticker.symbol} ({ACCOUNT_LABELS[position.account]})
        </div>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Acquired date</label>
            <input type="date" style={inputStyle} value={lot.acquiredDate}
              onChange={e => setLot(l => ({ ...l, acquiredDate: e.target.value }))} required />
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Shares</label>
            <input type="number" step="0.0001" min="0" style={inputStyle} placeholder="0.0000"
              value={lot.shares} onChange={e => setLot(l => ({ ...l, shares: e.target.value }))} required />
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Cost per share ($)</label>
            <input type="number" step="0.01" min="0" style={inputStyle} placeholder="0.00"
              value={lot.costBasis} onChange={e => setLot(l => ({ ...l, costBasis: e.target.value }))} required />
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 4 }}>Notes (optional)</label>
            <input style={inputStyle} placeholder="e.g. opened position"
              value={lot.notes} onChange={e => setLot(l => ({ ...l, notes: e.target.value }))} />
          </div>

          {error && (
            <div style={{ color: '#ef4444', fontSize: 12 }}>{error}</div>
          )}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button type="button" onClick={onClose}
              style={{ background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 13, padding: '6px 16px', borderRadius: 5, cursor: 'pointer' }}>
              Cancel
            </button>
            <button type="submit" disabled={saving}
              style={{ background: saving ? '#1e2330' : '#3b82f6', border: 'none', color: '#f1f5f9', fontSize: 13, fontWeight: 600, padding: '6px 20px', borderRadius: 5, cursor: saving ? 'wait' : 'pointer' }}>
              {saving ? 'Saving…' : 'Save lot'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Cash balance panel ────────────────────────────────────────────────────────

function CashPanel({ token }) {
  const [balances, setBalances] = useState([]);
  const [editing, setEditing]   = useState(null); // account string being edited
  const [draft, setDraft]       = useState({ balance: '', asOfDate: '' });
  const [saving, setSaving]     = useState(false);

  const fetchBalances = useCallback(async () => {
    const res = await fetch(`${API_URL}/api/portfolio/cash`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setBalances(await res.json());
  }, [token]);

  useEffect(() => { fetchBalances(); }, [fetchBalances]);

  async function saveBalance(account) {
    setSaving(true);
    await fetch(`${API_URL}/api/portfolio/cash`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ account, balance: draft.balance, asOfDate: draft.asOfDate }),
    });
    setSaving(false);
    setEditing(null);
    fetchBalances();
  }

  const byAccount = Object.fromEntries(balances.map(b => [b.account, b]));

  const inputStyle = {
    background: '#0d1018',
    border: '1px solid #2d3748',
    borderRadius: 5,
    color: '#f1f5f9',
    fontSize: 12,
    padding: '4px 8px',
    outline: 'none',
  };

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      {ACCOUNTS.map(acct => {
        const b = byAccount[acct];
        const isEditing = editing === acct;
        return (
          <div key={acct} style={{
            background: '#0d1018',
            border: '1px solid #1e2330',
            borderRadius: 8,
            padding: '12px 16px',
            minWidth: 180,
            flex: 1,
          }}>
            <div style={{ fontSize: 11, color: accountColor(acct), fontWeight: 600, marginBottom: 6 }}>
              {ACCOUNT_LABELS[acct]}
            </div>
            {isEditing ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <input type="number" step="0.01" placeholder="Balance ($)"
                  style={inputStyle} value={draft.balance}
                  onChange={e => setDraft(d => ({ ...d, balance: e.target.value }))} />
                <input type="date" style={inputStyle} value={draft.asOfDate}
                  onChange={e => setDraft(d => ({ ...d, asOfDate: e.target.value }))} />
                <div style={{ display: 'flex', gap: 6 }}>
                  <button onClick={() => saveBalance(acct)} disabled={saving}
                    style={{ background: '#3b82f6', border: 'none', color: '#fff', fontSize: 11, padding: '3px 10px', borderRadius: 4, cursor: 'pointer' }}>
                    {saving ? '…' : 'Save'}
                  </button>
                  <button onClick={() => setEditing(null)}
                    style={{ background: 'transparent', border: '1px solid #2d3748', color: '#94a3b8', fontSize: 11, padding: '3px 10px', borderRadius: 4, cursor: 'pointer' }}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#f1f5f9' }}>
                  {b ? fmtDollars(b.balance) : '—'}
                </div>
                {b && (
                  <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>
                    as of {new Date(b.asOfDate).toLocaleDateString()}
                  </div>
                )}
                <button
                  onClick={() => {
                    setDraft({ balance: b ? b.balance : '', asOfDate: b ? b.asOfDate.slice(0, 10) : '' });
                    setEditing(acct);
                  }}
                  style={{ marginTop: 8, background: 'transparent', border: '1px solid #2d3748', color: '#60a5fa', fontSize: 11, padding: '3px 10px', borderRadius: 4, cursor: 'pointer' }}
                >
                  {b ? 'Update' : 'Set balance'}
                </button>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Main Portfolio page ───────────────────────────────────────────────────────

export default function Portfolio() {
  const { getToken } = useAuth();
  const [positions, setPositions]     = useState([]);
  const [loading, setLoading]         = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addLotTarget, setAddLotTarget] = useState(null); // position for add-lot modal

  const fetchPositions = useCallback(async () => {
    const token = await getToken();
    const res = await fetch(`${API_URL}/api/portfolio/positions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setPositions(await res.json());
    setLoading(false);
  }, [getToken]);

  useEffect(() => { fetchPositions(); }, [fetchPositions]);

  async function handleSaved() {
    setShowAddForm(false);
    setAddLotTarget(null);
    const token = await getToken();
    const res = await fetch(`${API_URL}/api/portfolio/positions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setPositions(await res.json());
  }

  // Group positions by account for the summary row
  const totalCost = positions.reduce(
    (sum, p) => sum + p.lots.reduce((s, l) => s + l.shares * l.costBasis, 0), 0
  );
  const inScopePositions = positions.filter(p => p.ticker.inScope);
  const inScopeCost = inScopePositions.reduce(
    (sum, p) => sum + p.lots.reduce((s, l) => s + l.shares * l.costBasis, 0), 0
  );

  return (
    <div style={{ padding: '72px 32px 48px', maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>Portfolio</div>
          <div style={{ fontSize: 13, color: '#475569', marginTop: 2 }}>
            Position tracking · manual entry · Phase 1
          </div>
        </div>
        {!showAddForm && (
          <button
            onClick={() => setShowAddForm(true)}
            style={{
              background: '#3b82f6',
              border: 'none',
              color: '#fff',
              fontSize: 13,
              fontWeight: 600,
              padding: '7px 18px',
              borderRadius: 6,
              cursor: 'pointer',
            }}
          >
            + Add position
          </button>
        )}
      </div>

      {/* Add Position form */}
      {showAddForm && (
        <div style={{
          background: '#0d1018',
          border: '1px solid #1e2330',
          borderRadius: 10,
          padding: 20,
          margin: '16px 0',
        }}>
          <div style={{ fontWeight: 600, color: '#f1f5f9', marginBottom: 16, fontSize: 14 }}>
            Add position
          </div>
          <AddPositionFormWrapper
            getToken={getToken}
            onSaved={handleSaved}
            onCancel={() => setShowAddForm(false)}
          />
        </div>
      )}

      {/* Cash balances */}
      <SectionHeader>Cash balances</SectionHeader>
      <CashPanelWrapper getToken={getToken} />

      {/* Position summary */}
      {positions.length > 0 && (
        <>
          <SectionHeader>Positions</SectionHeader>
          <div style={{ fontSize: 12, color: '#475569', marginBottom: 10 }}>
            {positions.length} position{positions.length !== 1 ? 's' : ''} ·{' '}
            in-scope cost basis {fmtDollars(inScopeCost)} ·{' '}
            total cost basis {fmtDollars(totalCost)}
            {totalCost !== inScopeCost && (
              <span style={{ color: '#ef4444' }}> ({fmtDollars(totalCost - inScopeCost)} legacy)</span>
            )}
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e2330' }}>
                  {['Ticker', 'Account', 'Type', 'Shares', 'Avg cost/sh', 'Total cost', ''].map(h => (
                    <th key={h} style={{
                      padding: '8px 12px',
                      textAlign: h === 'Ticker' || h === '' || h === 'Account' || h === 'Type' ? 'left' : 'right',
                      fontSize: 11,
                      fontWeight: 600,
                      color: '#475569',
                      letterSpacing: '0.04em',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map(pos => (
                  <PositionRow
                    key={pos.id}
                    pos={pos}
                    onAddLot={setAddLotTarget}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {loading && (
        <div style={{ color: '#475569', fontSize: 13, marginTop: 24 }}>Loading…</div>
      )}

      {!loading && positions.length === 0 && !showAddForm && (
        <div style={{ color: '#475569', fontSize: 13, marginTop: 24 }}>
          No positions yet. Click "Add position" to enter your first holding.
        </div>
      )}

      {/* Add Lot modal */}
      {addLotTarget && (
        <AddLotModalWrapper
          position={addLotTarget}
          getToken={getToken}
          onSaved={handleSaved}
          onClose={() => setAddLotTarget(null)}
        />
      )}
    </div>
  );
}

// Wrappers that resolve the auth token once and pass it down

function AddPositionFormWrapper({ getToken, onSaved, onCancel }) {
  const [token, setToken] = useState(null);
  useEffect(() => { getToken().then(setToken); }, [getToken]);
  if (!token) return null;
  return <AddPositionForm token={token} onSaved={onSaved} onCancel={onCancel} />;
}

function CashPanelWrapper({ getToken }) {
  const [token, setToken] = useState(null);
  useEffect(() => { getToken().then(setToken); }, [getToken]);
  if (!token) return null;
  return <CashPanel token={token} />;
}

function AddLotModalWrapper({ position, getToken, onSaved, onClose }) {
  const [token, setToken] = useState(null);
  useEffect(() => { getToken().then(setToken); }, [getToken]);
  if (!token) return null;
  return <AddLotModal position={position} token={token} onSaved={onSaved} onClose={onClose} />;
}
