/**
 * priceRefresh.js
 *
 * Fetches current market prices via yahoo-finance2 and updates
 * Position rows in the database.
 *
 * Usage:
 *   const { refreshPrices } = require('./priceRefresh');
 *   const results = await refreshPrices(prisma, positionIds);
 *   // results: { updated: number, errors: [{ symbol, error }] }
 */

// yahoo-finance2 is ESM-only — must use dynamic import in a CJS module
let _yahooFinance = null;
async function getYahoo() {
  if (!_yahooFinance) {
    const mod = await import('yahoo-finance2');
    // Handle different ESM/CJS interop shapes
    const candidate = mod?.default ?? mod;
    // Some bundlers double-wrap: mod.default.default
    _yahooFinance = (typeof candidate?.quote === 'function')
      ? candidate
      : (candidate?.default ?? candidate);
    if (typeof _yahooFinance?.quote !== 'function') {
      throw new Error(`yahoo-finance2 loaded but .quote not found. Keys: ${Object.keys(mod).join(', ')}`);
    }
  }
  return _yahooFinance;
}

/**
 * Refresh prices for a list of positions (by ID).
 *
 * Fetches quote data from Yahoo Finance for each unique symbol,
 * then updates lastPrice / lastPriceAsOf / dayChangePct / dayChangeDollar
 * on each Position row.
 *
 * @param {PrismaClient} prisma
 * @param {number[]}     positionIds  — IDs of positions to refresh
 * @returns {{ updated: number, errors: Array<{symbol: string, error: string}> }}
 */
async function refreshPrices(prisma, positionIds) {
  if (!positionIds || positionIds.length === 0) {
    return { updated: 0, errors: [] };
  }

  // Load positions with ticker symbols
  const positions = await prisma.position.findMany({
    where: { id: { in: positionIds }, status: 'active' },
    include: { ticker: { select: { symbol: true } } },
  });

  // Deduplicate symbols
  const symbolToPositionIds = {};
  for (const pos of positions) {
    const sym = pos.ticker.symbol;
    if (!symbolToPositionIds[sym]) symbolToPositionIds[sym] = [];
    symbolToPositionIds[sym].push(pos.id);
  }

  const symbols = Object.keys(symbolToPositionIds);
  const errors = [];
  let updated = 0;
  const asOf = new Date();

  // Fetch quotes in parallel
  const yahooFinance = await getYahoo();

  // Suppress yahoo-finance2's Yup validation noise globally (safe to call multiple times)
  try {
    yahooFinance.setGlobalConfig({ validation: { logErrors: false, logOptionsErrors: false } });
  } catch (_) { /* older versions may not support this */ }

  const quotePromises = symbols.map(async sym => {
    try {
      const quote = await yahooFinance.quote(sym, {}, { validateResult: false });
      return { sym, quote };
    } catch (err) {
      const msg = err.message || String(err);
      console.error(`[priceRefresh] ${sym}: ${msg}`);
      errors.push({ symbol: sym, error: msg });
      return { sym, quote: null };
    }
  });

  const results = await Promise.all(quotePromises);

  // Update DB
  const updatePromises = [];
  for (const { sym, quote } of results) {
    if (!quote) continue;

    const price          = quote.regularMarketPrice ?? null;
    const dayChangeDollar = quote.regularMarketChange ?? null;
    const dayChangePct   = quote.regularMarketChangePercent != null
      ? quote.regularMarketChangePercent / 100
      : null;

    if (price == null) {
      errors.push({ symbol: sym, error: 'No price returned' });
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
  return { updated, errors };
}

/**
 * Convenience: refresh all active positions in a single account.
 */
async function refreshAccountPrices(prisma, accountId) {
  const positions = await prisma.position.findMany({
    where: { accountId, status: 'active' },
    select: { id: true },
  });
  return refreshPrices(prisma, positions.map(p => p.id));
}

module.exports = { refreshPrices, refreshAccountPrices };
