import { Routes, Route } from 'react-router-dom';
import { SignIn, SignedIn, SignedOut } from '@clerk/clerk-react';
import NavBar from './components/NavBar.jsx';
import Evaluator from './pages/Evaluator.jsx';
import Radar from './pages/Radar.jsx';

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
        <NavBar />
        <div style={{ paddingTop: 52 }}>
          <Routes>
            <Route path="/" element={<Evaluator />} />
            <Route path="/radar" element={<Radar />} />
          </Routes>
        </div>
      </SignedIn>
    </>
  );
}
