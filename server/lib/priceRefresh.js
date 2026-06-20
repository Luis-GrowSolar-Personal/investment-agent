/**
 * priceRefresh.js
 *
 * Fetches current market prices and updates Position rows.
 *
 * Source priority:
 *   1. Schwab market data quotes API — equities, ETFs, commodities.
 *      Requires Schwab to be connected (valid SchwabToken row). Also
 *      populates dayChangeDollar / dayChangePct from Schwab's netChange
 *      and netPercentChange fields.
 *   2. Polygon.io fallback for:
 *        – crypto positions (ticker.bucketOverride === 'crypto')
 *        – any equity symbol Schwab did not return a price for
 *
 * Env: POLYGON_API_KEY — required only for crypto / Schwab misses.
 */

const POLYGON_BASE = 'https://api.polygon.io';

// Raw crypto symbols held outside Schwab (e.g. on an exchange).
// Crypto ETFs (IBIT, GBTC, BTC) are regular NYSE securities — bucket 'etf'
// not 'crypto' — so they go through Schwab quotes, not this list.
const CRYPTO_RAW = new Set(['ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'AVAX', 'MATIC']);

function toPolygonTicker(sym) {
  if (CRYPTO_RAW.has(sym)) return `X:${sym}USD`;
  return sym;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ─── Core refresh (list of position IDs) ──────────────────────────────────────

/**
 * Refresh prices for a specific list of position IDs.
 * Used by both refreshAllPrices() and the legacy per-account route.
 *
 * Strategy:
 *  1. Load positions + ticker info.
 *  2. Schwab quotes for all non-crypto symbols (single API call).
 *  3. Polygon for crypto + any Schwab misses (sequential, free-tier safe).
 *  4. Batch-update Position rows.
 *
 * @param {PrismaClient} prisma
 * @param {number[]}     positionIds
 * @returns {{ updated, schwabCount, polygonCount, errors, sources }}
 */
async function refreshPrices(prisma, positionIds) {
  if (!positionIds || positionIds.length === 0) {
    return { updated: 0, schwabCount: 0, polygonCount: 0, errors: [], sources: {} };
  }

  // Load positions with ticker metadata
  const positions = await prisma.position.findMany({
    where: { id: { in: positionIds }, status: 'active' },
    include: { ticker: { select: { symbol: true, bucketOverride: true } } },
  });

  if (!positions.length) {
    return { updated: 0, schwabCount: 0, polygonCount: 0, errors: [], sources: {} };
  }

  // Group position IDs by symbol; track crypto flag
  const symbolMap = new Map(); // symbol → { positionIds: number[], isCrypto: boolean }
  for (const pos of positions) {
    const sym      = pos.ticker.symbol;
    const isCrypto = pos.ticker.bucketOverride === 'crypto';
    if (!symbolMap.has(sym)) symbolMap.set(sym, { positionIds: [], isCrypto });
    symbolMap.get(sym).positionIds.push(pos.id);
  }

  const equitySymbols = [...symbolMap.entries()].filter(([, v]) => !v.isCrypto).map(([s]) => s);
  const cryptoSymbols = [...symbolMap.entries()].filter(([, v]) =>  v.isCrypto).map(([s]) => s);

  // price data: symbol → { price, dayChangeDollar, dayChangePct }
  const priceData = new Map();
  const sources   = {}; // symbol → 'schwab' | 'polygon'
  const errors    = [];
  const asOf      = new Date();

  // ── 1. Schwab quotes for equities ──────────────────────────────────────────
  let schwabMissed = [...equitySymbols]; // narrows as Schwab fills in data

  if (equitySymbols.length > 0) {
    try {
      const { getQuotes } = require('./schwabAuth');
      const data = await getQuotes(prisma, equitySymbols);
      schwabMissed = [];
      for (const sym of equitySymbols) {
        const entry = data[sym];
        // Schwab returns lastPrice during extended hours; closePrice is prev close.
        // Prefer lastPrice; fall back to closePrice if lastPrice is 0 or absent.
        const price = (entry?.quote?.lastPrice > 0 ? entry.quote.lastPrice : null)
                   ?? (entry?.quote?.closePrice > 0 ? entry.quote.closePrice : null);
        if (price != null) {
          // netPercentChange from Schwab is already in percent (e.g. 1.23 = +1.23%).
          // Schema stores as fraction (0.0123 = +1.23%) per the comment.
          const netPct = entry.quote.netPercentChange != null
            ? entry.quote.netPercentChange / 100
            : null;
          priceData.set(sym, {
            price,
            dayChangeDollar: entry.quote.netChange ?? null,
            dayChangePct:    netPct,
          });
          sources[sym] = 'schwab';
        } else {
          schwabMissed.push(sym);
        }
      }
    } catch (err) {
      console.warn('[priceRefresh] Schwab quotes unavailable — falling back to Polygon for all equities:', err.message);
      // schwabMissed stays as the full equitySymbols list
    }
  }

  // ── 2. Polygon for crypto + Schwab misses ──────────────────────────────────
  const polygonSymbols = [...cryptoSymbols, ...schwabMissed];

  if (polygonSymbols.length > 0) {
    const apiKey = process.env.POLYGON_API_KEY;
    if (!apiKey) {
      for (const sym of polygonSymbols) {
        errors.push({ symbol: sym, error: 'POLYGON_API_KEY not set and Schwab returned no price' });
      }
    } else {
      for (const sym of polygonSymbols) {
        try {
          const polygonTicker = toPolygonTicker(sym);
          const url = `${POLYGON_BASE}/v2/aggs/ticker/${polygonTicker}/prev?adjusted=true&apiKey=${apiKey}`;
          let res = await fetch(url);
          if (res.status === 429) {
            console.log(`[priceRefresh] ${sym}: 429 — waiting 15s then retrying`);
            await sleep(15000);
            res = await fetch(url);
          }
          if (!res.ok) {
            errors.push({ symbol: sym, error: `Polygon ${res.status}` });
            await sleep(500);
            continue;
          }
          const json = await res.json();
          const bar  = json.results?.[0];
          if (!bar) {
            errors.push({ symbol: sym, error: 'No prev-close data' });
            await sleep(250);
            continue;
          }
          priceData.set(sym, {
            price:          bar.c,
            // Polygon prev-close doesn't give day change vs the bar before it;
            // leave nulls so we don't show stale % from a prior refresh.
            dayChangeDollar: null,
            dayChangePct:    null,
          });
          sources[sym] = 'polygon';
        } catch (err) {
          errors.push({ symbol: sym, error: err.message });
        }
        await sleep(500); // stay under free-tier burst limit
      }
    }
  }

  // ── 3. Write prices to DB ──────────────────────────────────────────────────
  const updates = [];
  for (const [sym, { positionIds: ids }] of symbolMap.entries()) {
    const pd = priceData.get(sym);
    if (!pd) continue; // no price obtained for this symbol
    for (const id of ids) {
      updates.push(
        prisma.position.update({
          where: { id },
          data: {
            lastPrice:      pd.price,
            lastPriceAsOf:  asOf,
            dayChangeDollar: pd.dayChangeDollar,
            dayChangePct:    pd.dayChangePct,
          },
        })
      );
    }
  }
  await Promise.all(updates);

  const schwabCount  = Object.values(sources).filter(s => s === 'schwab').length;
  const polygonCount = Object.values(sources).filter(s => s === 'polygon').length;

  return { updated: updates.length, schwabCount, polygonCount, errors, sources };
}

// ─── Convenience wrappers ─────────────────────────────────────────────────────

/**
 * Refresh prices for ALL active positions across every account.
 * This is the primary entry point for the /api/schwab/refresh-prices endpoint.
 */
async function refreshAllPrices(prisma) {
  const positions = await prisma.position.findMany({
    where: { status: 'active' },
    select: { id: true },
  });
  return refreshPrices(prisma, positions.map(p => p.id));
}

/**
 * Refresh prices for all active positions in a single account.
 * Retained for the existing POST /api/portfolio/accounts/:id/refresh-prices route.
 */
async function refreshAccountPrices(prisma, accountId) {
  const positions = await prisma.position.findMany({
    where: { accountId, status: 'active' },
    select: { id: true },
  });
  return refreshPrices(prisma, positions.map(p => p.id));
}

module.exports = { refreshPrices, refreshAccountPrices, refreshAllPrices };
