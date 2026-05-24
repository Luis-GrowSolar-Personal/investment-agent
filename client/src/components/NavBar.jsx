import { NavLink } from 'react-router-dom';
import { useUser, useClerk } from '@clerk/clerk-react';

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
  };
}

export default function NavBar() {
  const { user } = useUser();
  const { signOut } = useClerk();
  const email = user?.primaryEmailAddress?.emailAddress ?? user?.username ?? '';

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
      gap: 24,
    }}>
      <span style={{ fontSize: 13, fontWeight: 700, color: '#475569', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>
        Portfolio Analyst
      </span>

      <div style={{ display: 'flex', gap: 4, flex: 1 }}>
        <NavLink to="/" end style={({ isActive }) => tabStyle(isActive)}>
          Stock Analyst
        </NavLink>
        <NavLink to="/radar" style={({ isActive }) => tabStyle(isActive)}>
          Stock Radar
        </NavLink>
        <NavLink to="/advisories" style={({ isActive }) => tabStyle(isActive)}>
          Advisory Feed
        </NavLink>
        <NavLink to="/portfolio" style={({ isActive }) => tabStyle(isActive)}>
          Portfolio
        </NavLink>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
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
