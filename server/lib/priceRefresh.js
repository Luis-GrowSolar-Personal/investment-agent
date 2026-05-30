/**
 * priceRefresh.js
 *
 * Fetches current market prices via Polygon.io (formerly polygon.io, now Massive)
 * and updates Position rows in the database.
 *
 * Uses the snapshot endpoint — one call returns all symbols at once.
 * Free tier: 15-min delayed data, unlimited calls.
 *
 * Env: POLYGON_API_KEY
 */

const POLYGON_BASE = 'https://api.polygon.io';

/**
 * Refresh prices for all active positions in an account.
 *
 * @param {PrismaClient} prisma
 * @param {number}       accountId
 * @returns {{ updated: number, errors: Array<{symbol: string, error: string}> }}
 */
async function refreshAccountPrices(prisma, accountId) {
  const positions = await prisma.position.findMany({
    where: { accountId, status: 'active' },
    select: { id: true },
  });
  return refreshPrices(prisma, positions.map(p => p.id));
}

/**
 * Refresh prices for a list of positions (by ID).
 */
async function refreshPrices(prisma, positionIds) {
  if (!positionIds || positionIds.length === 0) {
    return { updated: 0, errors: [] };
  }

  const apiKey = process.env.POLYGON_API_KEY;
  if (!apiKey) {
    return { updated: 0, errors: [{ symbol: 'ALL', error: 'POLYGON_API_KEY not set' }] };
  }

  // Load positions with ticker symbols
  const positions = await prisma.position.findMany({
    where: { id: { in: positionIds }, status: 'active' },
    include: { ticker: { select: { symbol: true } } },
  });

  if (!positions.length) return { updated: 0, errors: [] };

  // Deduplicate symbols
  const symbolToPositionIds = {};
  for (const pos of positions) {
    const sym = pos.ticker.symbol;
    if (!symbolToPositionIds[sym]) symbolToPositionIds[sym] = [];
    symbolToPositionIds[sym].push(pos.id);
  }

  const symbols = Object.keys(symbolToPositionIds);
  const errors  = [];
  let updated   = 0;
  const asOf    = new Date();

  // Use prev-close endpoint (free tier) for all symbols in parallel
  const result = await refreshViaIndividualQuotes(prisma, symbols, symbolToPositionIds, apiKey, asOf);
  return result;
}

// Map portfolio symbols to Polygon ticker format
// Crypto ETFs (IBIT, GBTC) are regular stocks on Polygon — no mapping needed
// Raw crypto symbols need the X: prefix
const CRYPTO_RAW = new Set(['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'AVAX', 'MATIC']);

function toPolygonTicker(sym) {
  if (CRYPTO_RAW.has(sym)) return `X:${sym}USD`;
  return sym;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/**
 * Fetch each symbol sequentially via Polygon's previous close endpoint.
 * Sequential (not parallel) to avoid burst rate limit on free tier.
 */
async function refreshViaIndividualQuotes(prisma, symbols, symbolToPositionIds, apiKey, asOf) {
  const errors = [];
  let updated  = 0;
  const updatePromises = [];

  for (const sym of symbols) {
    try {
      const polygonTicker = toPolygonTicker(sym);
      const url = `${POLYGON_BASE}/v2/aggs/ticker/${polygonTicker}/prev?adjusted=true&apiKey=${apiKey}`;
      const res = await fetch(url);
      if (!res.ok) {
        errors.push({ symbol: sym, error: `Polygon ${res.status}` });
        await sleep(250);
        continue;
      }
      const data = await res.json();
      const bar  = data.results?.[0];
      if (!bar) {
        errors.push({ symbol: sym, error: 'No prev-close data' });
        await sleep(250);
        continue;
      }
      const price = bar.c;
      for (const posId of symbolToPositionIds[sym]) {
        updatePromises.push(
          prisma.position.update({
            where: { id: posId },
            data: { lastPrice: price, lastPriceAsOf: asOf, dayChangePct: null, dayChangeDollar: null },
          })
        );
        updated++;
      }
    } catch (err) {
      errors.push({ symbol: sym, error: err.message });
    }
    await sleep(250); // 250ms between calls → well under 5 req/min burst limit
  }

  await Promise.all(updatePromises);
  return { updated, errors };
}

module.exports = { refreshPrices, refreshAccountPrices };
