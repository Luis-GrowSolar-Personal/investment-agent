/**
 * AppUserContext — provides the caller's OwnerProfile to the React tree.
 *
 * Fetches GET /api/users/me once after sign-in and exposes:
 *   myOwner  — the owner key linked to this Clerk login (e.g. "Luis Morales")
 *   isAdmin  — true if role === 'admin'
 *   loading  — true while the fetch is in flight
 *
 * Non-admins receive only their own data from the backend (enforced server-side).
 * The context is used on the frontend to:
 *   • Hide the Admin tab from non-admins
 *   • Auto-select the correct owner in pages that have an owner selector
 */

import { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from '@clerk/clerk-react';

const AppUserContext = createContext({ myOwner: null, isAdmin: false, accessRevoked: false, loading: true });

export function AppUserProvider({ children }) {
  const { getToken, isSignedIn } = useAuth();
  const [myOwner,       setMyOwner]       = useState(null);
  const [isAdmin,       setIsAdmin]       = useState(false);
  const [accessRevoked, setAccessRevoked] = useState(false);
  const [loading,       setLoading]       = useState(true);

  useEffect(() => {
    if (!isSignedIn) { setLoading(false); return; }
    (async () => {
      try {
        const token = await getToken();
        const r = await fetch('/api/users/me', { headers: { Authorization: `Bearer ${token}` } });
        if (r.ok) {
          const d = await r.json();
          setMyOwner(d.owner);
          setIsAdmin(d.role === 'admin');
        } else if (r.status === 404) {
          // Clerk session is valid but this login is not linked to any owner profile.
          // Treat as revoked — show the access denied screen.
          setAccessRevoked(true);
        }
      } catch (err) {
        console.error('[AppUserContext] /api/users/me failed:', err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [isSignedIn, getToken]);

  return (
    <AppUserContext.Provider value={{ myOwner, isAdmin, accessRevoked, loading }}>
      {children}
    </AppUserContext.Provider>
  );
}

export function useAppUser() {
  return useContext(AppUserContext);
}
