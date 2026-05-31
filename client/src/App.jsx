import { useLocation } from 'react-router-dom';
import { SignIn, SignedIn, SignedOut } from '@clerk/clerk-react';
import NavBar from './components/NavBar.jsx';
import Evaluator from './pages/Evaluator.jsx';
import Radar from './pages/Radar.jsx';
import AdvisoryFeed from './pages/AdvisoryFeed.jsx';
import Portfolio from './pages/Portfolio.jsx';
import Users from './pages/Users.jsx';
import Dashboard from './pages/Dashboard.jsx';

export default function App() {
  const location = useLocation();

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
        <NavBar />
        {/* All pages stay mounted permanently so in-flight fetches and form state
            survive tab switches. Visibility is toggled with display:none only. */}
        <div style={{ paddingTop: 52 }}>
          <div style={{ display: location.pathname === '/' ? 'block' : 'none' }}>
            <Evaluator />
          </div>
          <div style={{ display: location.pathname === '/radar' ? 'block' : 'none' }}>
            <Radar />
          </div>
          <div style={{ display: location.pathname === '/advisories' ? 'block' : 'none' }}>
            <AdvisoryFeed />
          </div>
          <div style={{ display: location.pathname === '/portfolio' ? 'block' : 'none' }}>
            <Portfolio />
          </div>
          <div style={{ display: location.pathname === '/users' ? 'block' : 'none' }}>
            <Users />
          </div>
          <div style={{ display: location.pathname === '/dashboard' ? 'block' : 'none' }}>
            <Dashboard />
          </div>
        </div>
      </SignedIn>
    </>
  );
}
