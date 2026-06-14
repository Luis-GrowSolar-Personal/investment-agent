/**
 * schwabAccounts.js
 *
 * Phase 2, step 1 — READ-ONLY preview of Schwab-linked accounts.
 *
 * No DB writes (other than the token refresh that may happen inside
 * getValidAccessToken()). This exists so Luis can see exactly what Schwab
 * reports — including accounts that may not yet exist in our Account table
 * — before any account-matching / sync logic is built.
 *
 * Endpoints used (Schwab Trader API, base https://api.schwabapi.com/trader/v1):
 *  - GET /accounts/accountNumbers  -> [{ accountNumber, hashValue }, ...]
 *  - GET /accounts?fields=positions -> [{ securitiesAccount: {...} }, ...]
 */

const { getValidAccessToken } = require('./schwabAuth');

const TRADER_BASE = 'https://api.schwabapi.com/trader/v1';

function maskAccountNumber(accountNumber) {
  if (!accountNumber) return null;
  const str = String(accountNumber);
  return str.length > 4 ? `***${str.slice(-4)}` : str;
}

/**
 * Fetches all Schwab-linked accounts + positions and returns a masked
 * summary, alongside the app's existing local Account rows for comparison.
 *
 * @param {PrismaClient} prisma
 * @returns {{ schwabAccounts: Array, localAccounts: Array }}
 */
async function previewAccounts(prisma) {
  const accessToken = await getValidAccessToken(prisma);
  const headers = { Authorization: `Bearer ${accessToken}` };

  // 1. Account number -> hash value map (hash values are used in all other
  //    account-scoped Trader API calls, never the raw account number).
  const numbersRes = await fetch(`${TRADER_BASE}/accounts/accountNumbers`, { headers });
  if (!numbersRes.ok) {
    throw new Error(`Schwab /accounts/accountNumbers failed (${numbersRes.status}): ${await numbersRes.text()}`);
  }
  const accountNumbers = await numbersRes.json(); // [{ accountNumber, hashValue }, ...]

  const hashByAccountNumber = new Map(
    accountNumbers.map(a => [a.accountNumber, a.hashValue])
  );

  // 2. Full account details with positions.
  const accountsRes = await fetch(`${TRADER_BASE}/accounts?fields=positions`, { headers });
  if (!accountsRes.ok) {
    throw new Error(`Schwab /accounts?fields=positions failed (${accountsRes.status}): ${await accountsRes.text()}`);
  }
  const accountsData = await accountsRes.json(); // [{ securitiesAccount: {...} }, ...]

  const schwabAccounts = accountsData.map(entry => {
    const acct = entry.securitiesAccount ?? {};
    const balances = acct.currentBalances ?? {};
    const positions = (acct.positions ?? []).map(pos => ({
      symbol:       pos.instrument?.symbol ?? null,
      assetType:    pos.instrument?.assetType ?? null,
      longQuantity: pos.longQuantity ?? 0,
      shortQuantity: pos.shortQuantity ?? 0,
      marketValue:  pos.marketValue ?? null,
      averagePrice: pos.averagePrice ?? null,
    }));

    return {
      hashValue:           hashByAccountNumber.get(acct.accountNumber) ?? null,
      accountNumberMasked: maskAccountNumber(acct.accountNumber),
      type:                acct.type ?? null, // "CASH" | "MARGIN"
      cashBalance:         balances.cashBalance ?? null,
      liquidationValue:    balances.liquidationValue ?? null,
      positionCount:       positions.length,
      positions,
    };
  });

  // Existing local accounts, for side-by-side comparison in the UI/response.
  const localAccounts = await prisma.account.findMany({
    select: { id: true, name: true, type: true, owner: true, cashBalance: true, schwabAccountHash: true, lastSyncedAt: true },
    orderBy: { id: 'asc' },
  });

  return { schwabAccounts, localAccounts };
}

module.exports = { previewAccounts, maskAccountNumber };
