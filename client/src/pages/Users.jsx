/**
 * Users.jsx — Owner profile management page
 *
 * Lists all OwnerProfile rows. Each row shows:
 *   owner name · display name · investment goal (enoughNumber) · account count · portfolio value
 *
 * Actions:
 *   ✎  inline-edit displayName and enoughNumber
 *   +  create new owner profile
 *   ×  delete (blocked if accounts exist)
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmt(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function pill(label, color) {
  const colors = {
    green:  { bg: '#14532d22', border: '#16a34a55', text: '#4ade80' },
    amber:  { bg: '#78350f22', border: '#d9770655', text: '#fbbf24' },
    slate:  { bg: '#1e293b',   border: '#334155',   text: '#94a3b8' },
  };
  const c = colors[color] ?? colors.slate;
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 8px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 600,
      background: c.bg,
      border: `1px solid ${c.border}`,
      color: c.text,
      whiteSpace: 'nowrap',
    }}>{label}</span>
  );
}

// ---------------------------------------------------------------------------
// Inline edit row component
// ---------------------------------------------------------------------------
function OwnerRow({ profile, onSave, onDelete }) {
  const [editing, setEditing]         = useState(false);
  const [displayName, setDisplayName] = useState(profile.displayName ?? '');
  const [enoughNumber, setEnoughNumber] = useState(
    profile.enoughNumber != null ? String(profile.enoughNumber) : ''
  );
  const [saving, setSaving]           = useState(false);
  const [err, setErr]                 = useState('');

  const handleSave = async () => {
    setSaving(true);
    setErr('');
    try {
      await onSave(profile.owner, { displayName, enoughNumber });
      setEditing(false);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setDisplayName(profile.displayName ?? '');
    setEnoughNumber(profile.enoughNumber != null ? String(profile.enoughNumber) : '');
    setEditing(false);
    setErr('');
  };

  // Progress bar: totalPortfolioValue / enoughNumber
  const pct = profile.enoughNumber && profile.totalPortfolioValue
    ? Math.min(100, (profile.totalPortfolioValue / profile.enoughNumber) * 100)
    : null;

  const goalColor = pct == null ? 'slate' : pct >= 100 ? 'green' : pct >= 60 ? 'amber' : 'slate';

  return (
    <div style={{
      borderBottom: '1px solid #1e2330',
      padding: '16px 20px',
    }}>
      {/* Top row: owner name + badges + actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: '#f1f5f9', minWidth: 160 }}>
          {profile.displayName || profile.owner}
        </span>
        {profile.displayName && (
          <span style={{ fontSize: 11, color: '#475569' }}>{profile.owner}</span>
        )}
        {pill(`${profile.accountCount} account${profile.accountCount !== 1 ? 's' : ''}`, 'slate')}
        <span style={{ fontSize: 13, color: '#94a3b8' }}>
          Portfolio: <strong style={{ color: '#f1f5f9' }}>{fmt(profile.totalPortfolioValue)}</strong>
        </span>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              title="Edit owner"
              style={iconBtn()}
            >✎</button>
          )}
          <button
            onClick={() => onDelete(profile.owner)}
            title="Delete owner"
            style={iconBtn('red')}
          >×</button>
        </div>
      </div>

      {/* Investment goal row */}
      {!editing && (
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: '#64748b' }}>Investment goal:</span>
          {profile.enoughNumber != null
            ? <><strong style={{ fontSize: 13, color: '#f1f5f9' }}>{fmt(profile.enoughNumber)}</strong>
                {pct != null && pill(`${pct.toFixed(0)}% there`, goalColor)}
              </>
            : <span style={{ fontSize: 12, color: '#475569', fontStyle: 'italic' }}>not set</span>
          }
          {pct != null && (
            <div style={{ flex: 1, minWidth: 120, maxWidth: 260, height: 4, background: '#1e2330', borderRadius: 2 }}>
              <div style={{ width: `${pct}%`, height: '100%', background: pct >= 100 ? '#4ade80' : pct >= 60 ? '#fbbf24' : '#3b82f6', borderRadius: 2, transition: 'width 0.3s' }} />
            </div>
          )}
        </div>
      )}

      {/* Inline edit form */}
      {editing && (
        <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
          <label style={labelStyle}>
            Display name
            <input
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder={profile.owner}
              style={inputStyle}
            />
          </label>
          <label style={labelStyle}>
            Investment goal ($)
            <input
              type="number"
              value={enoughNumber}
              onChange={e => setEnoughNumber(e.target.value)}
              placeholder="e.g. 6000000"
              style={{ ...inputStyle, width: 160 }}
            />
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleSave} disabled={saving} style={primaryBtn}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button onClick={handleCancel} style={cancelBtn}>Cancel</button>
          </div>
          {err && <span style={{ color: '#f87171', fontSize: 12 }}>{err}</span>}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// New owner modal
// ---------------------------------------------------------------------------
function NewOwnerModal({ onClose, onCreated }) {
  const { getToken } = useAuth();
  const [owner, setOwner]             = useState('');
  const [displayName, setDisplayName] = useState('');
  const [enoughNumber, setEnoughNumber] = useState('');
  const [saving, setSaving]           = useState(false);
  const [err, setErr]                 = useState('');

  const handleCreate = async () => {
    if (!owner.trim()) { setErr('Owner name is required'); return; }
    setSaving(true);
    setErr('');
    try {
      const token = await getToken();
      const r = await fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          owner: owner.trim(),
          displayName: displayName.trim() || null,
          enoughNumber: enoughNumber ? Number(enoughNumber) : null,
        }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Create failed');
      onCreated(data);
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={modalOverlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={modalBox}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: '#f1f5f9' }}>New Owner</span>
          <button onClick={onClose} style={iconBtn()}>×</button>
        </div>

        <label style={labelStyle}>
          Owner name <span style={{ color: '#f87171' }}>*</span>
          <input value={owner} onChange={e => setOwner(e.target.value)}
            placeholder="e.g. Luis Morales" style={inputStyle} autoFocus />
        </label>
        <label style={{ ...labelStyle, marginTop: 14 }}>
          Display name
          <input value={displayName} onChange={e => setDisplayName(e.target.value)}
            placeholder="e.g. Luis" style={inputStyle} />
        </label>
        <label style={{ ...labelStyle, marginTop: 14 }}>
          Investment goal ($)
          <input type="number" value={enoughNumber} onChange={e => setEnoughNumber(e.target.value)}
            placeholder="e.g. 6000000" style={inputStyle} />
        </label>

        {err && <div style={{ color: '#f87171', fontSize: 12, marginTop: 10 }}>{err}</div>}

        <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={cancelBtn}>Cancel</button>
          <button onClick={handleCreate} disabled={saving} style={primaryBtn}>
            {saving ? 'Creating…' : 'Create owner'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Users() {
  const { getToken } = useAuth();
  const [profiles, setProfiles]     = useState([]);
  const [loading, setLoading]       = useState(true);
  const [showNew, setShowNew]       = useState(false);
  const [deleteErr, setDeleteErr]   = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const r = await fetch('/api/users', { headers: { Authorization: `Bearer ${token}` } });
      const data = await r.json();
      if (r.ok) setProfiles(data);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async (owner, updates) => {
    const token = await getToken();
    const r = await fetch(`/api/users/${encodeURIComponent(owner)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(updates),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Save failed');
    setProfiles(prev => prev.map(p => p.owner === owner ? { ...p, ...data } : p));
  };

  const handleDelete = async (owner) => {
    setDeleteErr('');
    if (!window.confirm(`Delete owner "${owner}"? This cannot be undone.`)) return;
    const token = await getToken();
    const r = await fetch(`/api/users/${encodeURIComponent(owner)}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await r.json();
    if (!r.ok) { setDeleteErr(data.error || 'Delete failed'); return; }
    setProfiles(prev => prev.filter(p => p.owner !== owner));
  };

  const handleCreated = (profile) => {
    setProfiles(prev => [...prev, { ...profile, accountCount: 0, totalPortfolioValue: 0 }]);
  };

  return (
    <div style={{ maxWidth: 860, margin: '32px auto', padding: '0 24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>Owners</h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
            Manage investment owners and their goals. Each owner gets a separate Dashboard view.
          </p>
        </div>
        <button onClick={() => setShowNew(true)} style={primaryBtn}>+ New Owner</button>
      </div>

      {deleteErr && (
        <div style={{ background: '#450a0a', border: '1px solid #991b1b', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#f87171', fontSize: 13 }}>
          {deleteErr}
        </div>
      )}

      {/* Owner list */}
      <div style={{ border: '1px solid #1e2330', borderRadius: 10, background: '#0d1018', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#475569', fontSize: 13 }}>Loading…</div>
        ) : profiles.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#475569', fontSize: 13 }}>
            No owners yet. Create one to get started.
          </div>
        ) : (
          profiles.map(p => (
            <OwnerRow
              key={p.owner}
              profile={p}
              onSave={handleSave}
              onDelete={handleDelete}
            />
          ))
        )}
      </div>

      {showNew && (
        <NewOwnerModal onClose={() => setShowNew(false)} onCreated={handleCreated} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared style tokens
// ---------------------------------------------------------------------------
const iconBtn = (color) => ({
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  fontSize: color === 'red' ? 16 : 15,
  color: color === 'red' ? '#475569' : '#475569',
  padding: '2px 5px',
  borderRadius: 4,
  lineHeight: 1,
  transition: 'color 0.15s',
});

const labelStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 5,
  fontSize: 12,
  color: '#94a3b8',
};

const inputStyle = {
  background: '#0f1117',
  border: '1px solid #2d3748',
  borderRadius: 6,
  color: '#f1f5f9',
  fontSize: 13,
  padding: '7px 10px',
  outline: 'none',
  width: 220,
};

const primaryBtn = {
  background: '#2563eb',
  border: 'none',
  borderRadius: 6,
  color: '#fff',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
  padding: '7px 16px',
  whiteSpace: 'nowrap',
};

const cancelBtn = {
  background: 'transparent',
  border: '1px solid #2d3748',
  borderRadius: 6,
  color: '#94a3b8',
  cursor: 'pointer',
  fontSize: 13,
  padding: '7px 14px',
};

const modalOverlay = {
  position: 'fixed', inset: 0,
  background: 'rgba(0,0,0,0.6)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 200,
};

const modalBox = {
  background: '#0f1117',
  border: '1px solid #1e2330',
  borderRadius: 10,
  padding: 24,
  width: 420,
  maxWidth: '90vw',
};
