import { useLocation } from 'react-router-dom';
import { SignIn, SignedIn, SignedOut } from '@clerk/clerk-react';
import NavBar from './components/NavBar.jsx';
import { AppUserProvider } from './contexts/AppUserContext.jsx';
import PortfolioManager from './pages/PortfolioManager.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Portfolio from './pages/Portfolio.jsx';
import InvestmentIdeas from './pages/InvestmentIdeas.jsx';
import Admin from './pages/Admin.jsx';

// Sub-paths that belong to Investment Ideas — InvestmentIdeas stays mounted
// across all three so Radar/Evaluator/AdvisoryFeed state survives tab switches.
const IDEAS_PATHS = ['/ideas', '/analyst', '/commentary'];

export default function App() {
  const location = useLocation();
  const path = location.pathname;

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
        </AppUserProvider>
      </SignedIn>
    </>
  );
}
