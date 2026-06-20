/**
 * schwabAuth.js
 *
 * Schwab Trader API — 3-legged OAuth (Phase 1: scaffolding only, no data
 * sync). Read-only scope is sufficient for everything this app needs
 * (account positions, balances, quotes) — never request trading scopes.
 *
 * Flow:
 *  1. GET /api/schwab/connect redirects the user to Schwab's authorization
 *     page (getAuthUrl()).
 *  2. User logs in with their Schwab brokerage credentials (NOT developer
 *     portal credentials) and selects which account(s) to link.
 *  3. Schwab redirects back to SCHWAB_REDIRECT_URI with ?code=...
 *  4. GET /api/schwab/callback calls exchangeCodeForTokens(), which trades
 *     the code for an access_token + refresh_token and persists both in the
 *     single-row SchwabToken table.
 *  5. Any future Trader API call should go through getValidAccessToken(),
 *     which transparently refreshes the access_token when it's expired or
 *     near expiry.
 *
 * Env required: SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET, SCHWAB_REDIRECT_URI
 * (SCHWAB_REDIRECT_URI must exactly match the callback URL registered in the
 * Schwab developer app.)
 *
 * Token lifetimes (per Schwab Trader API docs):
 *  - access_token:  ~30 minutes
 *  - refresh_token: ~7 days, and Schwab issues a NEW refresh_token on every
 *    refresh — the old one becomes invalid, so the new one must be persisted
 *    every time or the chain breaks and re-authorization (step 1-4) is
 *    required again.
 *
 * Token storage: single shared SchwabToken row (id: 1). One Schwab login is
 * account-holder level and covers all linked brokerage accounts, so this is
 * intentionally not scoped per-OwnerProfile.
 */

const SCHWAB_AUTH_BASE = 'https://api.schwabapi.com/v1/oauth';
const TOKEN_ROW_ID = 1;

// 60s safety buffer before actual expiry to avoid using a token that expires
// mid-request.
const EXPIRY_BUFFER_MS = 60 * 1000;

function requireEnv(name) {
  const val = process.env[name];
  if (!val) throw new Error(`${name} is not set`);
  return val;
}

function basicAuthHeader() {
  const id = requireEnv('SCHWAB_CLIENT_ID');
  const secret = requireEnv('SCHWAB_CLIENT_SECRET');
  return 'Basic ' + Buffer.from(`${id}:${secret}`).toString('base64');
}

/**
 * Builds the Schwab authorization URL the user's browser should be sent to.
 */
function getAuthUrl() {
  const id = requireEnv('SCHWAB_CLIENT_ID');
  const redirectUri = requireEnv('SCHWAB_REDIRECT_URI');
  const params = new URLSearchParams({
    client_id: id,
    redirect_uri: redirectUri,
    response_type: 'code',
  });
  return `${SCHWAB_AUTH_BASE}/authorize?${params.toString()}`;
}

/**
 * Exchanges an authorization code (from the /callback query string) for an
 * access_token + refresh_token pair, and persists them.
 */
async function exchangeCodeForTokens(prisma, code) {
  const redirectUri = requireEnv('SCHWAB_REDIRECT_URI');
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: redirectUri,
  });

  const res = await fetch(`${SCHWAB_AUTH_BASE}/token`, {
    method: 'POST',
    headers: {
      Authorization: basicAuthHeader(),
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: body.toString(),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Schwab token exchange failed (${res.status}): ${text}`);
  }

  const data = await res.json();
  await saveTokens(prisma, data);
  return data;
}

/**
 * Uses the stored refresh_token to obtain a new access_token (and a new
 * refresh_token, which Schwab rotates on every call), and persists both.
 */
async function refreshAccessToken(prisma) {
  const row = await prisma.schwabToken.findUnique({ where: { id: TOKEN_ROW_ID } });
  if (!row) {
    throw new Error('Schwab not connected — visit /api/schwab/connect first');
  }

  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: row.refreshToken,
  });

  const res = await fetch(`${SCHWAB_AUTH_BASE}/token`, {
    method: 'POST',
    headers: {
      Authorization: basicAuthHeader(),
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: body.toString(),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Schwab token refresh failed (${res.status}): ${text}`);
  }

  const data = await res.json();
  await saveTokens(prisma, data);
  return data;
}

/**
 * Persists a token response from Schwab into the singleton SchwabToken row.
 * data shape: { access_token, refresh_token, expires_in, token_type, scope }
 */
async function saveTokens(prisma, data) {
  const expiresAt = new Date(Date.now() + (data.expires_in ?? 1800) * 1000);

  await prisma.schwabToken.upsert({
    where: { id: TOKEN_ROW_ID },
    create: {
      id: TOKEN_ROW_ID,
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      expiresAt,
    },
    update: {
      accessToken: data.access_token,
      // Schwab rotates the refresh_token on every refresh. Keep the existing
      // one only if a response somehow omits it (shouldn't happen).
      ...(data.refresh_token ? { refreshToken: data.refresh_token } : {}),
      expiresAt,
    },
  });
}

/**
 * Returns a valid access_token, transparently refreshing first if the
 * current one is expired or within EXPIRY_BUFFER_MS of expiring.
 * Throws if Schwab has never been connected.
 */
async function getValidAccessToken(prisma) {
  const row = await prisma.schwabToken.findUnique({ where: { id: TOKEN_ROW_ID } });
  if (!row) {
    throw new Error('Schwab not connected — visit /api/schwab/connect first');
  }

  if (row.expiresAt.getTime() - EXPIRY_BUFFER_MS > Date.now()) {
    return row.accessToken;
  }

  const refreshed = await refreshAccessToken(prisma);
  return refreshed.access_token;
}

/**
 * Connection status for the UI — never returns raw token values.
 */
async function getStatus(prisma) {
  const row = await prisma.schwabToken.findUnique({ where: { id: TOKEN_ROW_ID } });
  if (!row) return { connected: false };

  return {
    connected: true,
    expiresAt: row.expiresAt,
    accessTokenExpired: row.expiresAt.getTime() <= Date.now(),
    updatedAt: row.updatedAt,
  };
}

const TRADER_BASE  = 'https://api.schwabapi.com/trader/v1';
const MARKET_BASE  = 'https://api.schwabapi.com/marketdata/v1';

/**
 * Fetches trade transactions for a Schwab account within a date range.
 *
 * Schwab's transaction history covers approximately the last 60 days.
 * We use this to get the exact purchase price and date for new lots,
 * rather than relying on the position-level averagePrice (which is the
 * blended average across all lots and would corrupt the cost basis).
 *
 * @param {PrismaClient} prisma
 * @param {string} hashValue  - Schwab account hash (from /accounts/accountNumbers)
 * @param {Date}   startDate  - earliest transaction date to fetch
 * @param {Date}   endDate    - latest transaction date to fetch (defaults to now)
 * @returns {Array} Raw Schwab transaction objects filtered to TRADE type
 *
 * Each returned object has (at minimum):
 *   { type, tradeDate, settlementDate,
 *     netAmount,                       // negative = buy, positive = sell
 *     transferItems: [
 *       { instrument: { symbol, assetType }, amount, price, cost, positionEffect }
 *     ]
 *   }
 *
 * positionEffect values: 'OPENING' (buy), 'CLOSING' (sell).
 * price is per-share; amount is share count (negative for buys, positive for sells
 * in the equity leg — sign matches the direction of shares transferred to account).
 */
async function getTransactions(prisma, hashValue, startDate, endDate = new Date()) {
  const accessToken = await getValidAccessToken(prisma);

  const params = new URLSearchParams({
    types: 'TRADE',
    startDate: startDate.toISOString(),
    endDate:   endDate.toISOString(),
  });

  const url = `${TRADER_BASE}/accounts/${hashValue}/transactions?${params}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Schwab /transactions failed (${res.status}): ${text}`);
  }

  return res.json(); // array of transaction objects
}

/**
 * Fetches real-time (or delayed) market quotes for a list of symbols via
 * Schwab's market data API. Returns the raw response object keyed by symbol.
 *
 * Response shape (per symbol):
 *   {
 *     assetMainType: 'EQUITY' | 'ETF' | ...,
 *     symbol: 'AAPL',
 *     quote: {
 *       lastPrice: 182.5,
 *       closePrice: 181.0,
 *       netChange: 1.5,          // dollar change vs prev close
 *       netPercentChange: 0.829, // percent change (e.g. 0.829 = +0.829%)
 *       ...
 *     }
 *   }
 *
 * Symbols that Schwab cannot quote (e.g. raw crypto not listed on exchange)
 * will simply be absent from the returned object — the caller should treat
 * missing keys as "no price from Schwab" and fall back to another source.
 *
 * @param {PrismaClient} prisma
 * @param {string[]}     symbols  — up to ~500 per call
 * @returns {Object}              — { SYMBOL: { quote: { lastPrice, ... } }, ... }
 */
async function getQuotes(prisma, symbols) {
  if (!symbols || symbols.length === 0) return {};
  const accessToken = await getValidAccessToken(prisma);
  const params = new URLSearchParams({ symbols: symbols.join(','), fields: 'quote' });
  const url = `${MARKET_BASE}/quotes?${params}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json' },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Schwab /quotes failed (${res.status}): ${text}`);
  }
  return res.json();
}

module.exports = {
  getAuthUrl,
  exchangeCodeForTokens,
  refreshAccessToken,
  getValidAccessToken,
  getStatus,
  getTransactions,
  getQuotes,
};
