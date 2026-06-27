import { useLocation } from 'react-router-dom';
import { SignIn, SignedIn, SignedOut, useClerk } from '@clerk/clerk-react';
import NavBar from './components/NavBar.jsx';
import { AppUserProvider, useAppUser } from './contexts/AppUserContext.jsx';
import PortfolioManager from './pages/PortfolioManager.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Portfolio from './pages/Portfolio.jsx';
import InvestmentIdeas from './pages/InvestmentIdeas.jsx';
import Admin from './pages/Admin.jsx';

// Sub-paths that belong to Investment Ideas — InvestmentIdeas stays mounted
// across all three so Radar/Evaluator/AdvisoryFeed state survives tab switches.
const IDEAS_PATHS = ['/ideas', '/analyst', '/commentary'];

// Shown when a Clerk session exists but no OwnerProfile is linked to it.
function AccessRevoked() {
  const { signOut } = useClerk();
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', background: '#090c12',
    }}>
      <div style={{
        background: '#0f1117', border: '1px solid #1e2330', borderRadius: 12,
        padding: '40px 48px', maxWidth: 400, textAlign: 'center',
      }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>🔒</div>
        <h2 style={{ color: '#f1f5f9', margin: '0 0 10px', fontWeight: 700 }}>Access removed</h2>
        <p style={{ color: '#64748b', fontSize: 14, margin: '0 0 24px', lineHeight: 1.6 }}>
          Your account is no longer linked to this app. Contact your administrator to restore access.
        </p>
        <button
          onClick={() => signOut()}
          style={{
            background: 'transparent', border: '1px solid #2d3748', borderRadius: 6,
            color: '#94a3b8', fontSize: 13, padding: '8px 20px', cursor: 'pointer',
          }}
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

// Inner component — has access to AppUserContext
function AppShell() {
  const location = useLocation();
  const path = location.pathname;
  const { accessRevoked, loading } = useAppUser();

  if (loading) return null; // brief flash while /api/users/me resolves
  if (accessRevoked) return <AccessRevoked />;

  return (
    <>
      <NavBar />
      {/* All pages stay mounted permanently so in-flight fetches and form
          state survive tab switches. Visibility toggled with display:none. */}
      <div style={{ paddingTop: 52 }}>
        <div style={{ display: path === '/'         ? 'block' : 'none' }}><PortfolioManager /></div>
        <div style={{ display: path === '/glance'   ? 'block' : 'none' }}><Dashboard /></div>
        <div style={{ display: path === '/accounts' ? 'block' : 'none' }}><Portfolio /></div>
        <div style={{ display: IDEAS_PATHS.includes(path) ? 'block' : 'none' }}><InvestmentIdeas /></div>
        <div style={{ display: path === '/admin'    ? 'block' : 'none' }}><Admin /></div>
      </div>
    </>
  );
}

export default function App() {
  return (
    <>
      <SignedOut>
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <SignIn />
        </div>
      </SignedOut>
      <SignedIn>
        <AppUserProvider>
          <AppShell />
        </AppUserProvider>
      </SignedIn>
    </>
  );
}
