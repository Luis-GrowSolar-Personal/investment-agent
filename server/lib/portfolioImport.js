/**
 * portfolioImport.js
 *
 * Parsers for Schwab brokerage exports:
 *   parsePositionsCSV(csvText)      → array of position objects (ground truth)
 *   parseTransactionsJSON(jsonText) → array of transaction objects
 *   reconstructLots(positions, transactions) → positions enriched with individual lots
 *   smartDefaultBucket(assetType, symbol)    → bucket string
 */

// ---------------------------------------------------------------------------
// Bucket classification
// ---------------------------------------------------------------------------

const CRYPTO_SYMBOLS   = ['IBIT', 'GBTC', 'ETHE', 'BTC', 'ETH'];
const COMMODITY_SYMS   = ['GLD', 'IAU', 'SLV', 'SIVR', 'GDX', 'GDXJ', 'PPLT', 'PALL'];
const EQUITY_ETF_SYMS  = ['QQQ', 'SPY', 'IVV', 'VTI', 'VOO', 'IWM', 'DIA', 'VGT', 'XLK'];

/**
 * Returns the economic bucket for a symbol.
 * Effective bucket = Ticker.bucketOverride ?? smartDefaultBucket(assetType, symbol)
 */
function smartDefaultBucket(schwabAssetType, symbol) {
  const sym = (symbol || '').toUpperCase();
  if (CRYPTO_SYMBOLS.includes(sym))   return 'crypto';
  if (COMMODITY_SYMS.includes(sym))   return 'commodity';
  if (EQUITY_ETF_SYMS.includes(sym))  return 'equity';
  if (schwabAssetType === 'Equity')   return 'equity';
  return 'etf'; // default for "ETFs & Closed End Funds"
}

// ---------------------------------------------------------------------------
// Positions CSV parser
// ---------------------------------------------------------------------------

/**
 * Parse a Schwab positions CSV export.
 *
 * File format:
 *   Line 1: metadata  "Positions for account {name} ...{last4} as of {time}, {date}"
 *   Line 2: blank
 *   Line 3: column headers
 *   Lines 4–N: position rows
 *   Second-to-last: "Cash & Cash Investments" row → cashBalance
 *   Last: "Positions Total" row → discard
 *
 * Returns:
 *   {
 *     accountMeta: { name, last4, asOf },
 *     cashBalance: number,
 *     positions: [{ symbol, description, qty, price, mktVal, costBasis,
 *                   gainDollar, gainPct, pctOfAcct, assetType, bucket }]
 *   }
 */
function parsePositionsCSV(csvText) {
  const lines = csvText.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  if (lines.length < 3) throw new Error('CSV too short — expected at least 3 lines');

  // Line 0: metadata header
  const metaLine = lines[0].replace(/^"|"$/g, '');
  const accountMeta = parseAccountMeta(metaLine);

  // Line 1: column headers (after stripping blank lines, idx 1 in filtered array)
  // But the blank line 2 is filtered out, so headers are at index 1
  const headers = parseCSVRow(lines[1]);
  const idx = buildIndex(headers);

  const positions = [];
  let cashBalance = null;

  for (let i = 2; i < lines.length; i++) {
    const cells = parseCSVRow(lines[i]);
    if (!cells[0]) continue;

    const symbol = cells[idx['Symbol']] || '';

    // Skip "Positions Total" summary row
    if (symbol.toLowerCase().includes('positions total') ||
        cells.join('').toLowerCase().includes('positions total')) continue;

    // Cash row
    const assetType = cells[idx['Asset Type']] || '';
    if (assetType === 'Cash and Money Market' ||
        symbol.toLowerCase().includes('cash')) {
      const rawCash = cells[idx['Mkt Val']] || cells[idx['Market Value']] || '0';
      cashBalance = parseDollar(rawCash);
      continue;
    }

    const qty      = parseFloat(cells[idx['Qty']] || cells[idx['Quantity']] || '0') || 0;
    const price    = parseDollar(cells[idx['Price']] || '0');
    const mktVal   = parseDollar(cells[idx['Mkt Val']] || cells[idx['Market Value']] || '0');
    const costBasisTotal = parseDollar(cells[idx['Cost Basis']] || '0');
    const gainDollar = parseDollar(cells[idx['Gain $']] || '0');
    const gainPct    = parsePct(cells[idx['Gain %']] || '0');
    const pctOfAcct  = parsePct(cells[idx['% Of Acct']] || cells[idx['% of Acct']] || '0');
    const dayChgDollar = parseDollar(cells[idx['Price Chng $']] || '0');
    const dayChgPct    = parsePct(cells[idx['Price Chng %']] || '0');
    const description  = cells[idx['Description']] || '';

    if (!symbol || qty === 0) continue;

    positions.push({
      symbol: symbol.toUpperCase(),
      description,
      qty,
      price,
      mktVal,
      costBasisTotal,   // total cost basis (Schwab authoritative)
      costBasisPerShare: qty > 0 ? costBasisTotal / qty : 0,
      gainDollar,
      gainPct,
      pctOfAcct,
      dayChgDollar,
      dayChgPct,
      assetType,
      bucket: smartDefaultBucket(assetType, symbol),
    });
  }

  return { accountMeta, cashBalance, positions };
}

// ---------------------------------------------------------------------------
// Transactions JSON parser
// ---------------------------------------------------------------------------

/**
 * Parse a Schwab transactions JSON export.
 *
 * Returns array of transactions (Buy / Sell / Reverse Split only):
 *   [{ date, action, symbol, qty, price, amount }]
 */
function parseTransactionsJSON(jsonText) {
  const data = typeof jsonText === 'string' ? JSON.parse(jsonText) : jsonText;
  const raw = data.BrokerageTransactions || [];

  const INCLUDE_ACTIONS = new Set(['Buy', 'Sell', 'Reverse Split']);

  return raw
    .filter(t => INCLUDE_ACTIONS.has(t.Action))
    .map(t => ({
      date:   parseTradeDate(t.Date),
      action: t.Action,
      symbol: (t.Symbol || '').toUpperCase(),
      qty:    parseFloat(t.Quantity) || 0,
      price:  parseDollar(t.Price || '0'),
      amount: parseDollar(t.Amount || '0'),
    }))
    .filter(t => t.symbol);
}

// ---------------------------------------------------------------------------
// Lot reconstruction
// ---------------------------------------------------------------------------

/**
 * Given the parsed positions (ground truth qty + cost basis from Schwab CSV)
 * and the parsed transactions (for lot dates), reconstruct individual lots.
 *
 * Strategy:
 *   1. Group transactions by symbol, sort ascending by date.
 *   2. Replay Buy/Sell/Reverse Split to get a list of open lots (date + qty).
 *   3. Reconcile: total qty from lots must match positions CSV qty (warn if not).
 *   4. Cost basis per lot = position.costBasisPerShare (Schwab authoritative).
 *      We use transaction qty proportions to assign cost when there are multiple lots.
 *
 * Returns positions array with each position enriched:
 *   { ...position, lots: [{ acquiredDate, shares, costBasisPerShare, source }] }
 */
function reconstructLots(positions, transactions) {
  // Group transactions by symbol
  const txBySymbol = {};
  for (const tx of transactions) {
    if (!txBySymbol[tx.symbol]) txBySymbol[tx.symbol] = [];
    txBySymbol[tx.symbol].push(tx);
  }

  return positions.map(pos => {
    const txs = (txBySymbol[pos.symbol] || [])
      .slice()
      .sort((a, b) => a.date - b.date);

    if (!txs.length) {
      // No transaction history — create one lot with today as acquired date
      return {
        ...pos,
        lots: [{
          acquiredDate: new Date(),
          shares: pos.qty,
          costBasisPerShare: pos.costBasisPerShare,
          source: 'import',
          notes: 'No transaction history — single lot',
        }],
        reconciled: false,
      };
    }

    // Replay FIFO
    const openLots = [];
    let splitRatio = 1; // accumulated reverse split ratio

    for (const tx of txs) {
      if (tx.action === 'Reverse Split') {
        // Adjust all existing open lots
        const ratio = tx.qty; // Schwab reports new qty in the Reverse Split row
        const totalBefore = openLots.reduce((s, l) => s + l.shares, 0);
        if (totalBefore > 0) {
          const factor = ratio / totalBefore;
          for (const lot of openLots) {
            lot.shares = lot.shares * factor;
          }
        }
        splitRatio = ratio;
        continue;
      }

      if (tx.action === 'Buy') {
        openLots.push({
          acquiredDate: tx.date,
          shares: tx.qty,
          source: 'import',
        });
      }

      if (tx.action === 'Sell') {
        // FIFO — reduce oldest lots first
        let remaining = tx.qty;
        while (remaining > 0 && openLots.length > 0) {
          const oldest = openLots[0];
          if (oldest.shares <= remaining + 0.0001) {
            remaining -= oldest.shares;
            openLots.shift();
          } else {
            oldest.shares -= remaining;
            remaining = 0;
          }
        }
      }
    }

    // Reconcile total qty
    const lotTotal = openLots.reduce((s, l) => s + l.shares, 0);
    const reconciled = Math.abs(lotTotal - pos.qty) < 0.01;

    // Scale lots if off by small rounding (keep proportions, trust Schwab qty)
    if (!reconciled && lotTotal > 0) {
      const scale = pos.qty / lotTotal;
      for (const lot of openLots) lot.shares *= scale;
    }

    // Assign cost basis per share from Schwab authoritative value
    const lotsWithCost = openLots.map(lot => ({
      ...lot,
      costBasisPerShare: pos.costBasisPerShare,
    }));

    return { ...pos, lots: lotsWithCost, reconciled };
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseAccountMeta(metaLine) {
  // "Positions for account Individual-XXXX-1234 as of 09:30 PM ET, 05/30/2026"
  const last4Match = metaLine.match(/[-\s](\d{4})[\s,]/);
  const last4 = last4Match ? last4Match[1] : null;
  const nameMatch = metaLine.match(/Positions for account ([^,]+?) as of/i);
  const name = nameMatch ? nameMatch[1].trim() : metaLine.slice(0, 40);
  const asOfMatch = metaLine.match(/as of (.+)$/i);
  const asOf = asOfMatch ? asOfMatch[1].trim() : null;
  return { name, last4, asOf };
}

function parseCSVRow(line) {
  // Handles quoted fields (including commas inside quotes)
  const result = [];
  let current = '';
  let inQuote = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      inQuote = !inQuote;
    } else if (ch === ',' && !inQuote) {
      result.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  result.push(current.trim());
  return result;
}

function buildIndex(headers) {
  const idx = {};
  headers.forEach((h, i) => { idx[h.trim()] = i; });
  return idx;
}

function parseDollar(str) {
  if (str === null || str === undefined) return 0;
  const s = String(str).replace(/[$,\s]/g, '');
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}

function parsePct(str) {
  if (str === null || str === undefined) return 0;
  const s = String(str).replace(/[%\s]/g, '');
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n / 100;
}

/**
 * Parse Schwab transaction date, handling "MM/DD/YYYY as of MM/DD/YYYY" format.
 * The "as of" date is the trade date (used for LTCG/STCG holding period).
 */
function parseTradeDate(dateStr) {
  if (!dateStr) return new Date();
  const asOfMatch = dateStr.match(/as of\s+(\d{2}\/\d{2}\/\d{4})/i);
  const datepart = asOfMatch ? asOfMatch[1] : dateStr.trim().split(' ')[0];
  return new Date(datepart);
}

// ---------------------------------------------------------------------------

module.exports = {
  smartDefaultBucket,
  parsePositionsCSV,
  parseTransactionsJSON,
  reconstructLots,
};
