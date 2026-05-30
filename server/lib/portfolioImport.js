/**
 * portfolioImport.js
 *
 * Parsers for brokerage exports:
 *   parsePositionsCSV(csvText)      → position objects (via Claude AI — format-agnostic)
 *   parseTransactionsJSON(jsonText) → array of transaction objects
 *   reconstructLots(positions, transactions) → positions enriched with individual lots
 *   smartDefaultBucket(assetType, symbol)    → bucket string
 */

const Anthropic = require('@anthropic-ai/sdk');

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
  if (EQUITY_ETF_SYMS.includes(sym))  return 'etf';
  if (schwabAssetType === 'Equity')   return 'equity';
  return 'etf'; // default for "ETFs & Closed End Funds"
}

// ---------------------------------------------------------------------------
// Positions CSV parser — AI-powered (format-agnostic)
// ---------------------------------------------------------------------------

/**
 * Parse any brokerage positions CSV using Claude.
 * Handles any column naming convention, any row order, any brokerage.
 *
 * Returns:
 *   {
 *     accountMeta: { name, last4, asOf },
 *     cashBalance: number | null,
 *     positions: [{ symbol, description, qty, price, mktVal, costBasisTotal,
 *                   costBasisPerShare, gainDollar, gainPct, pctOfAcct,
 *                   dayChgDollar, dayChgPct, assetType, bucket }]
 *   }
 */
async function parsePositionsCSV(csvText) {
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  const prompt = `You are parsing a brokerage positions CSV export. Extract all holdings and return ONLY valid JSON — no explanation, no markdown, no code fences.

Return this exact structure:
{
  "accountMeta": {
    "name": "<account name from file header, or null>",
    "last4": "<last 4 digits of account number, or null>",
    "asOf": "<date/time string from header, or null>"
  },
  "cashBalance": <cash & money market balance as a number, or null>,
  "positions": [
    {
      "symbol": "<ticker symbol, uppercase>",
      "description": "<full security name>",
      "qty": <number of shares, as a number>,
      "price": <current price per share, as a number>,
      "mktVal": <total market value, as a number>,
      "costBasisTotal": <total cost basis, as a number>,
      "gainDollar": <unrealised gain in dollars, as a number>,
      "gainPct": <unrealised gain as decimal, e.g. 0.6594 for 65.94%>,
      "dayChgDollar": <today's dollar change, as a number>,
      "dayChgPct": <today's % change as decimal>,
      "pctOfAcct": <% of account as decimal, e.g. 0.0572 for 5.72%>,
      "assetType": "<Equity|ETFs & Closed End Funds|Cash and Money Market>"
    }
  ]
}

Rules:
- Exclude the cash/money market row from positions — put its value in cashBalance instead
- Exclude any "Positions Total" or summary rows
- Convert dollar strings like "$1,703.52" or "-$47.88" to numbers
- Convert percentage strings like "65.94%" or "-2.73%" to decimals (divide by 100)
- Convert qty strings with commas like "1,183" to numbers
- If a field is missing or "--", use null

CSV to parse:
${csvText}`;

  const response = await client.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 4096,
    messages: [{ role: 'user', content: prompt }],
  });

  const raw = response.content[0].text.trim();

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    // Try to extract JSON if Claude wrapped it in anything
    const match = raw.match(/\{[\s\S]*\}/);
    if (!match) throw new Error(`AI parser returned non-JSON: ${raw.slice(0, 200)}`);
    parsed = JSON.parse(match[0]);
  }

  // Enrich each position with derived fields
  const positions = (parsed.positions || []).map(pos => ({
    ...pos,
    symbol:           (pos.symbol || '').toUpperCase(),
    costBasisPerShare: pos.qty > 0 ? (pos.costBasisTotal || 0) / pos.qty : 0,
    bucket:           smartDefaultBucket(pos.assetType || '', pos.symbol || ''),
  }));

  return {
    accountMeta: parsed.accountMeta || {},
    cashBalance: parsed.cashBalance ?? null,
    positions,
  };
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
// Helpers (used by transaction parser)
// ---------------------------------------------------------------------------

function parseDollar(str) {
  if (str === null || str === undefined) return 0;
  const s = String(str).replace(/[$,\s]/g, '');
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
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
