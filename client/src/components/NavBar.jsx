import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useUser, useClerk, useAuth } from '@clerk/clerk-react';

const API = import.meta.env.VITE_API_URL || '';

const IDEAS_PATHS = ['/ideas', '/analyst', '/commentary'];

// "synced 3m ago" / "synced 2h ago" style relative-time label.
function timeAgo(timestampMs) {
  const diffMs = Date.now() - timestampMs;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function tabStyle(isActive) {
  return {
    padding: '5px 14px',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: isActive ? 600 : 400,
    color: isActive ? '#f1f5f9' : '#64748b',
    background: isActive ? '#1e2330' : 'transparent',
    textDecoration: 'none',
    transition: 'color 0.15s, background 0.15s',
    whiteSpace: 'nowrap',
  };
}

export default function NavBar() {
  const { user } = useUser();
  const { signOut } = useClerk();
  const { getToken } = useAuth();
  const { pathname } = useLocation();
  const email = user?.primaryEmailAddress?.emailAddress ?? user?.username ?? '';

  // Schwab "sync on login" status — visible from any tab, since NavBar is
  // always rendered. Fires at most once per browser tab session
  // (sessionStorage gate); the server itself makes no Schwab API calls if
  // every linked account was synced within the last 4h (autoSyncStaleAccounts).
  const [schwabStatus, setSchwabStatus] = useState(null); // { label, justSynced } | null

  useEffect(() => {
    if (sessionStorage.getItem('schwabAutoSyncDone')) return;
    sessionStorage.setItem('schwabAutoSyncDone', '1');

    (async () => {
      try {
        const token = await getToken();
        const res = await fetch(`${API}/api/schwab/auto-sync`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'Auto-sync failed');

        const all = [...(json.synced || []), ...(json.skipped || [])];
        const mostRecentMs = all.reduce((latest, a) => {
          const t = a.lastSyncedAt ? new Date(a.lastSyncedAt).getTime() : 0;
          return t > latest ? t : latest;
        }, 0);

        if (json.synced?.length) {
          setSchwabStatus({ label: `Schwab synced just now (${json.synced.length})`, justSynced: true });
        } else if (mostRecentMs > 0) {
          setSchwabStatus({ label: `Schwab synced ${timeAgo(mostRecentMs)}`, justSynced: false });
        }
        if (json.errors?.length) {
          console.error('Schwab auto-sync errors:', json.errors);
        }
      } catch (err) {
        console.error('Schwab auto-sync error:', err);
      }
    })();
  }, [getToken]);

  return (
    <nav style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      height: 52,
      background: '#0f1117',
      borderBottom: '1px solid #1e2330',
      display: 'flex',
      alignItems: 'center',
      padding: '0 24px',
      zIndex: 100,
      gap: 4,
    }}>
      <div style={{ display: 'flex', gap: 4, flex: 1 }}>
        <NavLink to="/" end style={({ isActive }) => tabStyle(isActive)}>
          Portfolio Manager
        </NavLink>
        <NavLink to="/glance" style={({ isActive }) => tabStyle(isActive)}>
          At a Glance
        </NavLink>
        <NavLink to="/accounts" style={({ isActive }) => tabStyle(isActive)}>
          Accounts
        </NavLink>
        {/* Highlight for /ideas, /analyst, and /commentary */}
        <NavLink to="/ideas" style={({ isActive }) => tabStyle(isActive || IDEAS_PATHS.includes(pathname))}>
          Investment Ideas
        </NavLink>
        <NavLink to="/admin" style={({ isActive }) => tabStyle(isActive)}>
          Admin
        </NavLink>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        {schwabStatus && (
          <span style={{ color: schwabStatus.justSynced ? '#4ade80' : '#64748b', fontSize: 12 }}>
            ⟳ {schwabStatus.label}
          </span>
        )}
        <span style={{ color: '#475569', fontSize: 12 }}>{email}</span>
        <button
          onClick={() => signOut()}
          style={{
            background: 'transparent',
            border: '1px solid #2d3748',
            borderRadius: 5,
            color: '#94a3b8',
            fontSize: 12,
            padding: '4px 10px',
            cursor: 'pointer',
          }}
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
