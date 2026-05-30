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

  try {
    // Snapshot endpoint: fetch all symbols in one call
    const url = `${POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/tickers`
      + `?tickers=${symbols.join(',')}&apiKey=${apiKey}`;

    const res = await fetch(url);
    if (!res.ok) {
      const body = await res.text();
      return { updated: 0, errors: [{ symbol: 'ALL', error: `Polygon ${res.status}: ${body.slice(0, 200)}` }] };
    }

    const data = await res.json();
    const tickers = data.tickers || [];

    if (!tickers.length) {
      // May be crypto/ETF symbols — try them individually via previous close
      // (snapshot only covers US stocks; for others fall back to prev close endpoint)
      return await refreshViaIndividualQuotes(prisma, symbols, symbolToPositionIds, apiKey, asOf);
    }

    // Build a map from symbol → quote data
    const quoteMap = {};
    for (const t of tickers) {
      quoteMap[t.ticker] = t;
    }

    // Update DB for each symbol
    const updatePromises = [];
    for (const sym of symbols) {
      const q = quoteMap[sym];
      if (!q) {
        errors.push({ symbol: sym, error: 'Not returned by Polygon snapshot' });
        continue;
      }

      // Use lastTrade price, fall back to day close
      const price          = q.lastTrade?.p ?? q.day?.c ?? null;
      const dayChangeDollar = q.todaysChange ?? null;
      const dayChangePct   = q.todaysChangePerc != null ? q.todaysChangePerc / 100 : null;

      if (price == null) {
        errors.push({ symbol: sym, error: 'No price in snapshot response' });
        continue;
      }

      for (const posId of symbolToPositionIds[sym]) {
        updatePromises.push(
          prisma.position.update({
            where: { id: posId },
            data: { lastPrice: price, lastPriceAsOf: asOf, dayChangePct, dayChangeDollar },
          })
        );
        updated++;
      }
    }

    await Promise.all(updatePromises);

  } catch (err) {
    return { updated: 0, errors: [{ symbol: 'ALL', error: err.message }] };
  }

  return { updated, errors };
}

/**
 * Fallback: fetch each symbol individually via Polygon's previous close endpoint.
 * Used for ETFs/crypto that may not appear in the US stocks snapshot.
 */
async function refreshViaIndividualQuotes(prisma, symbols, symbolToPositionIds, apiKey, asOf) {
  const errors = [];
  let updated  = 0;
  const updatePromises = [];

  await Promise.all(symbols.map(async sym => {
    try {
      const url = `${POLYGON_BASE}/v2/aggs/ticker/${sym}/prev?adjusted=true&apiKey=${apiKey}`;
      const res = await fetch(url);
      if (!res.ok) {
        errors.push({ symbol: sym, error: `Polygon ${res.status}` });
        return;
      }
      const data = await res.json();
      const bar  = data.results?.[0];
      if (!bar) {
        errors.push({ symbol: sym, error: 'No prev-close data' });
        return;
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
  }));

  await Promise.all(updatePromises);
  return { updated, errors };
}

module.exports = { refreshPrices, refreshAccountPrices };
