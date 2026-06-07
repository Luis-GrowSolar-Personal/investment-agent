import { useLocation } from 'react-router-dom';
import { SignIn, SignedIn, SignedOut } from '@clerk/clerk-react';
import NavBar from './components/NavBar.jsx';
import PortfolioManager from './pages/PortfolioManager.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Portfolio from './pages/Portfolio.jsx';
import InvestmentIdeas from './pages/InvestmentIdeas.jsx';
import Admin from './pages/Admin.jsx';
import Evaluator from './pages/Evaluator.jsx';

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
        <NavBar />
        {/* All pages stay mounted permanently so in-flight fetches and form
            state survive tab switches. Visibility toggled with display:none.

            /analyst is a direct-access route for the Analyst page — not in
            the nav, but bookmarkable. Useful for opening multiple tabs to
            paste earnings calls in parallel. */}
        <div style={{ paddingTop: 52 }}>
          <div style={{ display: path === '/'         ? 'block' : 'none' }}><PortfolioManager /></div>
          <div style={{ display: path === '/glance'   ? 'block' : 'none' }}><Dashboard /></div>
          <div style={{ display: path === '/accounts' ? 'block' : 'none' }}><Portfolio /></div>
          <div style={{ display: path === '/ideas'    ? 'block' : 'none' }}><InvestmentIdeas /></div>
          <div style={{ display: path === '/admin'    ? 'block' : 'none' }}><Admin /></div>
          <div style={{ display: path === '/analyst'  ? 'block' : 'none' }}><Evaluator /></div>
        </div>
      </SignedIn>
    </>
  );
}
