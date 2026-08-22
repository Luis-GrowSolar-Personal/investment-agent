/**
 * schwabSync.js
 *
 * Phase 2, step 2 — account reconciliation, matching, and sync.
 *
 * Design notes (see docs/CoWork_handoff_2026-06-13b.md "Phase 2 next steps"
 * and docs/architecture/DESIGN_PRINCIPLES.md):
 *
 *  - Matching is by `Account.schwabAccountHash` (nullable, unique). Nothing
 *    is auto-created — unmatched Schwab accounts are surfaced for Luis to
 *    confirm name/type/owner before a local Account row is written, since
 *    those fields affect tax treatment and allocator scoping.
 *
 *  - LOT-HISTORY CONSTRAINT: the Schwab Trader API's transaction history
 *    endpoint only covers a ~60 day window, so we cannot reconstruct
 *    accurate historical lots (acquisition dates / per-lot cost basis) for
 *    positions that predate that window — which is most existing holdings.
 *    Given that, sync NEVER overwrites or deletes lots created by CSV
 *    import (source: 'import') or manual entry (source: 'manual'). Those
 *    are the source of truth for cost-basis/tax-lot data.
 *
 *    Instead:
 *      - For a position that already has at least one open lot (any
 *        source), sync leaves lots untouched and instead reports a
 *        share-count diff (Schwab quantity vs. local total shares) so Luis
 *        can review and reconcile manually if they differ.
 *      - For a brand-new position (Schwab reports shares, no local lots at
 *        all), sync creates ONE lot tagged source: 'schwab' using Schwab's
 *        reported averagePrice as cost basis and today's date as a
 *        placeholder acquisition date — flagged in the response so Luis can
 *        correct the date for accurate LTCG/STCG treatment
 *        (CLAUDE.md "Key Design Decisions" #4). On a later resync, only
 *        source: 'schwab' lots are replaced (full-replace, same pattern as
 *        the existing CSV `source: 'import'` re-import).
 *
 *    If a CSV with real transaction history is later imported for a position
 *    that only has a 'schwab' placeholder lot, the import route
 *    (routes/portfolio.js, /accounts/:id/import) deletes that placeholder
 *    when it writes the new 'import' lots — the CSV's per-lot data
 *    supersedes the placeholder, avoiding double-counted shares.
 *
 *  - Cash balance sync is low-risk (no tax implication) and always applied
 *    for matched accounts.
 */

const { previewAccounts, maskAccountNumber } = require('./schwabAccounts');
const { smartDefaultBucket } = require('./portfolioImport');
const { getTransactions } = require('./schwabAuth');

/**
 * Mirrors ensureOwnerProfile() in routes/portfolio.js — kept local here to
 * avoid a cross-route dependency. No-op if the row already exists.
 */
async function ensureOwnerProfile(prisma, owner) {
  await prisma.ownerProfile.upsert({
    where: { owner },
    update: {},
    create: { owner },
  });
}

/**
 * Normalizes Schwab Trader API assetType values (e.g. "EQUITY",
 * "COLLECTIVE_INVESTMENT") to the casing smartDefaultBucket() expects
 * (from CSV exports, e.g. "Equity"). Symbol-based lists in
 * smartDefaultBucket cover ETFs/crypto/commodities regardless of casing.
 */
function normalizeAssetType(schwabAssetType) {
  if (!schwabAssetType) return '';
  return schwabAssetType === 'EQUITY' ? 'Equity' : schwabAssetType;
}

/**
 * Loads { account, positions } for a local account, where positions include
 * ticker symbol and total open shares — used to diff against Schwab.
 */
async function loadLocalPositions(prisma, accountId) {
  const positions = await prisma.position.findMany({
    where: { accountId, status: 'active' },
    include: {
      ticker: { select: { id: true, symbol: true } },
      lots: { where: { closedDate: null } },
    },
  });
  return positions.map(p => ({
    positionId: p.id,
    tickerId: p.ticker.id,
    symbol: p.ticker.symbol,
    totalShares: p.lots.reduce((s, l) => s + l.shares, 0),
    lotCount: p.lots.length,
    lotSources: [...new Set(p.lots.map(l => l.source))],
  }));
}

/**
 * Builds the reconciliation view: matches Schwab-reported accounts against
 * local Account rows by schwabAccountHash, and for matched accounts,
 * computes a position-level share-count diff. No writes.
 *
 * @param {PrismaClient} prisma
 * @returns {{
 *   matched: Array,         // { schwab, local, positionDiffs, schwabOnly, localOnly }
 *   unmatchedSchwab: Array, // schwab accounts with no local row, excluding ignored
 *   unmatchedLocal: Array,  // local accounts with no schwabAccountHash set
 *   ignoredSchwab: Array,   // schwab accounts the user has dismissed/ignored
 * }}
 */
async function getReconciliation(prisma) {
  const { schwabAccounts, localAccounts } = await previewAccounts(prisma);

  const localByHash = new Map(
    localAccounts.filter(a => a.schwabAccountHash).map(a => [a.schwabAccountHash, a])
  );

  const ignored = await prisma.ignoredSchwabAccount.findMany();
  const ignoredHashes = new Set(ignored.map(i => i.schwabAccountHash));

  const matched = [];
  const unmatchedSchwab = [];
  const ignoredSchwab = [];

  for (const schwab of schwabAccounts) {
    const local = schwab.hashValue ? localByHash.get(schwab.hashValue) : null;
    if (!local) {
      if (schwab.hashValue && ignoredHashes.has(schwab.hashValue)) {
        ignoredSchwab.push(schwab);
      } else {
        unmatchedSchwab.push(schwab);
      }
      continue;
    }

    const localPositions = await loadLocalPositions(prisma, local.id);
    const localBySymbol = new Map(localPositions.map(p => [p.symbol, p]));
    const schwabBySymbol = new Map(schwab.positions.map(p => [p.symbol, p]));

    const positionDiffs = [];
    for (const [symbol, schwabPos] of schwabBySymbol) {
      const localPos = localBySymbol.get(symbol);
      const schwabShares = (schwabPos.longQuantity ?? 0) - (schwabPos.shortQuantity ?? 0);
      if (!localPos) {
        positionDiffs.push({
          symbol,
          schwabShares,
          localShares: 0,
          status: 'schwab_only', // sync would create this position
        });
      } else if (Math.abs(localPos.totalShares - schwabShares) > 0.0001) {
        positionDiffs.push({
          symbol,
          schwabShares,
          localShares: localPos.totalShares,
          status: 'mismatch', // sync will NOT touch existing lots — flag for manual review
        });
      }
    }
    // Local positions with no corresponding Schwab position.
    // If they have open manual/import lots, surface as a trim-to-zero diff
    // so the user gets an actionable button. Otherwise just informational.
    const localOnly = [];
    for (const localPos of localPositions) {
      if (schwabBySymbol.has(localPos.symbol)) continue;
      const hasManualOrImportLots = localPos.lotSources.some(s => s !== 'schwab');
      if (hasManualOrImportLots && localPos.lotCount > 0) {
        positionDiffs.push({
          symbol: localPos.symbol,
          schwabShares: 0,
          localShares: localPos.totalShares,
          status: 'mismatch',
          diffDirection: 'trim',
        });
      } else {
        localOnly.push({ symbol: localPos.symbol, localShares: localPos.totalShares });
      }
    }

    matched.push({
      schwab,
      local,
      positionDiffs,
      localOnly,
    });
  }

  // Local accounts that don't have a Schwab hash set yet.
  const unmatchedLocal = localAccounts.filter(a => !a.schwabAccountHash);

  return { matched, unmatchedSchwab, unmatchedLocal, ignoredSchwab };
}

/**
 * Marks a Schwab account (by hash) as ignored — it will be excluded from
 * `unmatchedSchwab` in getReconciliation() until un-ignored. Used for
 * accounts the user doesn't want to link or manage (e.g. accounts at a
 * different brokerage tier, or ones not yet ready to track).
 *
 * @param {PrismaClient} prisma
 * @param {string} schwabAccountHash
 */
async function ignoreAccount(prisma, schwabAccountHash) {
  if (!schwabAccountHash) throw new Error('schwabAccountHash is required');
  return prisma.ignoredSchwabAccount.upsert({
    where: { schwabAccountHash },
    update: {},
    create: { schwabAccountHash },
  });
}

/**
 * Reverses ignoreAccount() — the Schwab account will reappear under
 * `unmatchedSchwab` on the next reconciliation.
 *
 * @param {PrismaClient} prisma
 * @param {string} schwabAccountHash
 */
async function unignoreAccount(prisma, schwabAccountHash) {
  if (!schwabAccountHash) throw new Error('schwabAccountHash is required');
  await prisma.ignoredSchwabAccount.deleteMany({ where: { schwabAccountHash } });
  return { schwabAccountHash };
}

/**
 * Links an existing local Account to a Schwab account hash.
 *
 * @param {PrismaClient} prisma
 * @param {number} accountId
 * @param {string} schwabAccountHash
 */
async function matchAccount(prisma, accountId, schwabAccountHash) {
  const account = await prisma.account.findUnique({ where: { id: accountId } });
  if (!account) throw new Error('Account not found');

  return prisma.account.update({
    where: { id: accountId },
    data: { schwabAccountHash },
  });
}

/**
 * Creates a new local Account from a Schwab account the user has confirmed
 * (name/type/owner chosen by Luis — never guessed), and links it via hash.
 *
 * @param {PrismaClient} prisma
 * @param {{ schwabAccountHash: string, name: string, type: string, owner: string, managed?: boolean }} input
 */
async function createAccountFromSchwab(prisma, input) {
  const { schwabAccountHash, name, type, owner, managed = false } = input;
  if (!schwabAccountHash || !name || !type || !owner) {
    throw new Error('schwabAccountHash, name, type, and owner are required');
  }
  const VALID_TYPES = ['taxable', 'ira', 'roth', 'custodial'];
  if (!VALID_TYPES.includes(type)) {
    throw new Error(`type must be one of: ${VALID_TYPES.join(', ')}`);
  }

  const account = await prisma.account.create({
    data: { name, type, owner, managed, schwabAccountHash },
  });
  await ensureOwnerProfile(prisma, owner);
  return account;
}

/**
 * Syncs a matched account from Schwab:
 *  - cash balance (always)
 *  - new positions (Schwab reports shares, no local position exists at all)
 *    -> creates Position + a single source: 'schwab' lot (placeholder
 *       acquisition date = today, flagged for manual correction)
 *  - existing positions with lots already -> left untouched; reported as a
 *    diff if share counts disagree
 *  - on resync, source: 'schwab' lots are fully replaced (same pattern as
 *    CSV source: 'import')
 *
 * @param {PrismaClient} prisma
 * @param {number} accountId
 */
async function syncAccount(prisma, accountId) {
  const account = await prisma.account.findUnique({ where: { id: accountId } });
  if (!account) throw new Error('Account not found');
  if (!account.schwabAccountHash) throw new Error('Account is not linked to a Schwab account');

  const { schwabAccounts } = await previewAccounts(prisma);
  const schwab = schwabAccounts.find(a => a.hashValue === account.schwabAccountHash);
  if (!schwab) {
    throw new Error('Linked Schwab account not found in current Schwab data (hash mismatch or account removed)');
  }

  await ensureOwnerProfile(prisma, account.owner);

  // Cash balance — always synced, no tax implication. lastSyncedAt is
  // stamped regardless of whether cashBalance is present, so the "Synced X
  // ago" indicator reflects this sync attempt either way.
  const accountUpdateData = { lastSyncedAt: new Date() };
  if (schwab.cashBalance != null) {
    accountUpdateData.cashBalance = schwab.cashBalance;
    accountUpdateData.cashAsOfDate = new Date();
  }
  await prisma.account.update({ where: { id: accountId }, data: accountUpdateData });

  const localPositions = await loadLocalPositions(prisma, accountId);
  const localBySymbol = new Map(localPositions.map(p => [p.symbol, p]));

  // Detect fractional positions — any non-integer quantity suggests the account
  // supports fractional share trading. Surfaced to the frontend so it can prompt
  // the user to enable allowsFractional on this account if not already set.
  const fractionalDetected = !account.allowsFractional && schwab.positions.some(p => {
    const qty = (p.longQuantity ?? 0) - (p.shortQuantity ?? 0);
    return qty > 0 && Math.abs(qty - Math.round(qty)) > 0.0001;
  });

  const result = {
    cashBalance: schwab.cashBalance ?? null,
    lastSyncedAt: accountUpdateData.lastSyncedAt,
    fractionalDetected,    // true when non-integer shares found but allowsFractional is false
    newPositions: [],      // symbols newly created with a placeholder 'schwab' lot
    updatedSchwabLots: [],  // symbols where an existing 'schwab' lot was refreshed
    autoResolvedAdds: [],  // adds auto-resolved from transaction history: { symbol, shares, price, tradeDate }
    autoClosedFullExits: [], // full exits auto-closed (Schwab shows 0 shares, no ambiguity about which lots): { symbol, lotsClosed, shares, matched }
    positionDiffs: [],      // diffs that couldn't be auto-resolved (trim, or add > 60 days old) — require manual action
    skippedAssetTypes: [],  // schwab positions we didn't sync (e.g. options, cash equivalents)
    promotedTickers: [],    // watchlist tickers promoted to portfolio because Schwab now shows a real position
  };

  // Fetch 60 days of trade transactions once per sync — used to resolve add diffs
  // with exact purchase price + date instead of the position-level averagePrice,
  // and full-exit trims with the real sale price + date instead of a placeholder.
  let recentTrades = null; // lazy-loaded on first add/exit diff: { opening: Map, closing: Map }
  async function ensureRecentTrades() {
    if (recentTrades !== null) return recentTrades;
    try {
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - 60);
      const txns = await getTransactions(prisma, schwab.hashValue, startDate);
      // Build lookups: symbol -> array of OPENING (buy) / CLOSING (sell) trade legs
      const opening = new Map();
      const closing = new Map();
      for (const txn of (Array.isArray(txns) ? txns : [])) {
        if (txn.type !== 'TRADE') continue;
        for (const item of (txn.transferItems ?? [])) {
          const sym = item.instrument?.symbol;
          if (!sym) continue;
          const map = item.positionEffect === 'OPENING' ? opening
            : item.positionEffect === 'CLOSING' ? closing
            : null;
          if (!map) continue;
          if (!map.has(sym)) map.set(sym, []);
          map.get(sym).push({
            tradeDate: txn.tradeDate,
            shares: Math.abs(item.amount ?? 0),
            price: item.price ?? null,
          });
        }
      }
      // Sort each symbol's trades newest-first for matching
      for (const map of [opening, closing]) {
        for (const [, trades] of map) {
          trades.sort((a, b) => new Date(b.tradeDate) - new Date(a.tradeDate));
        }
      }
      recentTrades = { opening, closing };
    } catch (err) {
      console.warn('schwabSync: could not fetch transaction history — add/exit diffs will require manual entry:', err.message);
      recentTrades = { opening: new Map(), closing: new Map() }; // empty, falls through to manual path
    }
    return recentTrades;
  }

  for (const schwabPos of schwab.positions) {
    const symbol = schwabPos.symbol;
    if (!symbol) continue;

    const schwabShares = (schwabPos.longQuantity ?? 0) - (schwabPos.shortQuantity ?? 0);
    if (schwabShares <= 0) continue; // skip closed/short positions for now

    const localPos = localBySymbol.get(symbol);

    if (localPos && localPos.lotCount > 0) {
      // Position already tracked. If it has any non-'schwab' lots, treat
      // those as authoritative and never touch them — just diff.
      const hasManualOrImportLots = localPos.lotSources.some(s => s !== 'schwab');
      if (hasManualOrImportLots) {
        const diff = schwabShares - localPos.totalShares;
        if (Math.abs(diff) > 0.0001) {
          if (diff > 0) {
            // Buy detected. Try to resolve from transaction history (exact price + date).
            const trades = await ensureRecentTrades();
            const candidates = trades.opening.get(symbol) ?? [];
            // Find the most recent trade whose share count is within 0.01% of the diff.
            const match = candidates.find(t => Math.abs(t.shares - diff) / diff < 0.0001);
            if (match && match.price != null) {
              await prisma.lot.create({
                data: {
                  positionId: localPos.positionId,
                  shares: diff,
                  costBasis: match.price,
                  acquiredDate: new Date(match.tradeDate),
                  source: 'schwab',
                  notes: `Auto-resolved from Schwab transaction history: ${diff.toFixed(6)} shares @ $${match.price} on ${match.tradeDate}.`,
                },
              });
              result.autoResolvedAdds.push({ symbol, shares: +diff.toFixed(6), price: match.price, tradeDate: match.tradeDate });
            } else {
              // No single trade in the last 60 days matches the diff exactly. This
              // commonly happens when a broker splits one logical buy into multiple
              // fills (partial fills, large orders, lower-liquidity tickers). Try
              // summing ALL same-symbol OPENING legs in the window — if the total
              // closes the diff, create one Lot per leg (never merge/average: each
              // fill has its own real price and trade date, which matters for
              // LTCG/STCG holding period and cost basis).
              const pricedCandidates = candidates.filter(t => t.price != null);
              const legSum = pricedCandidates.reduce((sum, t) => sum + t.shares, 0);
              if (pricedCandidates.length > 1 && Math.abs(legSum - diff) / diff < 0.0001) {
                for (let i = 0; i < pricedCandidates.length; i++) {
                  const leg = pricedCandidates[i];
                  await prisma.lot.create({
                    data: {
                      positionId: localPos.positionId,
                      shares: leg.shares,
                      costBasis: leg.price,
                      acquiredDate: new Date(leg.tradeDate),
                      source: 'schwab',
                      notes: `Auto-resolved from Schwab transaction history (${i + 1} of ${pricedCandidates.length} fills): ${leg.shares.toFixed(6)} shares @ $${leg.price} on ${leg.tradeDate}.`,
                    },
                  });
                  result.autoResolvedAdds.push({ symbol, shares: +leg.shares.toFixed(6), price: leg.price, tradeDate: leg.tradeDate });
                }
              } else {
                // Could mean the purchase predates the 60-day window, OR the
                // candidate legs are a mix of unrelated fills we can't safely
                // attribute (e.g. some belong to an earlier, already-resolved
                // diff) — don't guess which legs belong together. Surface for
                // manual entry and let the user consult Schwab's own lot detail.
                result.positionDiffs.push({
                  symbol,
                  schwabShares,
                  localShares: localPos.totalShares,
                  status: 'mismatch',
                  diffDirection: 'add',
                  positionAvgPrice: schwabPos.averagePrice ?? null,
                });
              }
            }
          } else {
            // Trim detected — always requires lot-picker (we can't know which lot
            // Schwab matched against for tax purposes).
            result.positionDiffs.push({
              symbol,
              schwabShares,
              localShares: localPos.totalShares,
              status: 'mismatch',
              diffDirection: 'trim',
              positionAvgPrice: schwabPos.averagePrice ?? null,
            });
          }
        }
        continue;
      }
      // Only 'schwab'-sourced lots exist for this position — safe to
      // full-replace with fresh data (same pattern as source: 'import').
      await prisma.lot.deleteMany({ where: { positionId: localPos.positionId, source: 'schwab' } });
      await prisma.lot.create({
        data: {
          positionId: localPos.positionId,
          shares: schwabShares,
          costBasis: schwabPos.averagePrice ?? 0,
          acquiredDate: new Date(),
          source: 'schwab',
          notes: 'Estimated from Schwab sync — acquisition date is a placeholder (Schwab API does not expose lot-level history beyond 60 days). Verify/edit for accurate LTCG/STCG treatment.',
        },
      });
      result.updatedSchwabLots.push(symbol);
      continue;
    }

    // Brand-new position for this account.
    let ticker = await prisma.ticker.findUnique({ where: { symbol } });
    if (!ticker) {
      const bucket = smartDefaultBucket(normalizeAssetType(schwabPos.assetType), symbol);
      ticker = await prisma.ticker.create({
        data: {
          symbol,
          name: symbol,
          shortName: symbol,
          type: 'A',
          capPercent: 0,
          status: 'watchlist',
          inScope: false,
          // Store the bucket explicitly. enrichPosition()'s display-time
          // fallback is smartDefaultBucket(pos.assetType || '', symbol) —
          // Position has no assetType column, so that call always sees ''
          // and defaults to 'etf'. Leaving bucketOverride null for
          // newly-created equities (the old `bucket !== 'equity' ? bucket :
          // null` pattern) silently misfiled them into the ETFs tab. See
          // CoWork_handoff_2026-06-13c.md "SPCX in ETFs tab" fix.
          bucketOverride: bucket,
        },
      });
    } else if (ticker.status === 'watchlist') {
      // Ticker already tracked as a watchlist candidate but Schwab now
      // reports an actual position for it — promote to portfolio so it
      // stops appearing as an "Open <symbol>" promotion candidate in the
      // Capital Flow while simultaneously generating an "Add <symbol>"
      // from the positions path. Without this, both entries appear and
      // the allocator double-counts the required capital.
      //
      // Also backfill bucketOverride if null: watchlist tickers created
      // before the bucket fix have bucketOverride=null, which causes the
      // display-time fallback smartDefaultBucket('', symbol) to return
      // 'etf' for any equity (Position has no assetType column). Use
      // Schwab's assetType — available here — to set the correct bucket.
      const updateData = { status: 'portfolio' };
      if (ticker.bucketOverride == null) {
        updateData.bucketOverride = smartDefaultBucket(normalizeAssetType(schwabPos.assetType), symbol);
      }
      ticker = await prisma.ticker.update({
        where: { id: ticker.id },
        data:  updateData,
      });
      result.promotedTickers.push(symbol);
    }

    const position = await prisma.position.upsert({
      where: { tickerId_accountId: { tickerId: ticker.id, accountId } },
      update: { status: 'active' },
      create: { tickerId: ticker.id, accountId },
    });

    await prisma.lot.create({
      data: {
        positionId: position.id,
        shares: schwabShares,
        costBasis: schwabPos.averagePrice ?? 0,
        acquiredDate: new Date(),
        source: 'schwab',
        notes: 'Estimated from Schwab sync — acquisition date is a placeholder (Schwab API does not expose lot-level history beyond 60 days). Verify/edit for accurate LTCG/STCG treatment.',
      },
    });

    result.newPositions.push(symbol);
  }

  // Detect local positions that Schwab no longer reports at all — i.e. fully
  // sold positions. Schwab drops a position from /accounts?fields=positions
  // once shares reach zero, so these never appear in the loop above.
  // This is a full exit — every open lot closed, with no ambiguity about
  // WHICH lots close (unlike a partial trim) — so auto-close them rather
  // than requiring the manual lot-picker. Try to find the real Schwab
  // CLOSING transaction(s) for accurate sale price/date; if none matches
  // cleanly, still auto-close (the "which lots" question has only one
  // answer regardless) but say so honestly in the note.
  const schwabSymbols = new Set(schwab.positions.map(p => p.symbol));
  for (const localPos of localPositions) {
    if (schwabSymbols.has(localPos.symbol)) continue; // handled in the loop above
    if (localPos.lotCount === 0) continue;            // already closed locally
    // Only flag if there are open (non-schwab) lots — a 'schwab'-only position
    // with no Schwab counterpart just means the placeholder will be cleaned up
    // on next sync when the position reappears (unlikely but safe to skip).
    const hasManualOrImportLots = localPos.lotSources.some(s => s !== 'schwab');
    if (!hasManualOrImportLots) continue;

    const openLots = await prisma.lot.findMany({
      where: { positionId: localPos.positionId, closedDate: null },
    });
    const trades = await ensureRecentTrades();
    const closingLegs = (trades.closing.get(localPos.symbol) ?? []).filter(t => t.price != null);
    const closingSum = closingLegs.reduce((sum, t) => sum + t.shares, 0);
    const matched = closingLegs.length > 0 && Math.abs(closingSum - localPos.totalShares) / localPos.totalShares < 0.0001;
    const closingDate = matched ? new Date(closingLegs[0].tradeDate) : new Date();
    const noteSuffix = matched
      ? `Closed ${closingDate.toISOString().slice(0, 10)} — full exit auto-accepted (Schwab reports 0 shares). Matched Schwab closing transaction history: ${closingSum.toFixed(6)} shares across ${closingLegs.length} fill(s) @ ~$${(closingLegs.reduce((s, t) => s + t.shares * t.price, 0) / closingSum).toFixed(4)} avg.`
      : `Closed ${closingDate.toISOString().slice(0, 10)} — full exit auto-accepted (Schwab reports 0 shares). No matching closing transaction found in the last 60 days; closing date is a placeholder (today). Verify actual sale date/price in Schwab's transaction history for accurate LTCG/STCG treatment.`;

    await prisma.$transaction([
      ...openLots.map(lot => prisma.lot.update({
        where: { id: lot.id },
        data: {
          closedDate: closingDate,
          notes: (lot.notes ? lot.notes + ' ' : '') + noteSuffix,
        },
      })),
      // Every open lot just closed above — close the Position itself too
      // (same status/closedAt pattern as the manual DELETE route in
      // portfolio.js), so it stops showing as a zero-share 'active' ghost
      // and stops being counted as "currently held" by the allocator/RADAR
      // eligibility gate (both filter on Position.status === 'active').
      prisma.position.update({
        where: { id: localPos.positionId },
        data: { status: 'closed', closedAt: closingDate },
      }),
    ]);
    result.autoClosedFullExits.push({ symbol: localPos.symbol, lotsClosed: openLots.length, shares: localPos.totalShares, matched });
  }

  return result;
}

/**
 * Accepts a positive Schwab-vs-local share-count diff for an existing
 * position as a new lot — e.g. a dividend reinvestment (DRIP) that added
 * a small fractional share count Schwab now reports but the local lots
 * don't reflect yet.
 *
 * Creates ONE additional lot for the diff (source: 'schwab', cost basis =
 * Schwab's current averagePrice, acquisition date = today as a placeholder),
 * same flag-for-correction pattern as new positions. Does not touch any
 * existing lots. Only valid when Schwab reports MORE shares than local
 * (diff > 0) — for the reverse case (local > Schwab, e.g. a sale not yet
 * reflected locally), this is not the right tool; surfaced for manual review
 * instead.
 *
 * @param {PrismaClient} prisma
 * @param {number} accountId
 * @param {string} symbol
 */
async function acceptShareDiff(prisma, accountId, symbol) {
  const account = await prisma.account.findUnique({ where: { id: accountId } });
  if (!account) throw new Error('Account not found');
  if (!account.schwabAccountHash) throw new Error('Account is not linked to a Schwab account');

  const { schwabAccounts } = await previewAccounts(prisma);
  const schwab = schwabAccounts.find(a => a.hashValue === account.schwabAccountHash);
  if (!schwab) {
    throw new Error('Linked Schwab account not found in current Schwab data (hash mismatch or account removed)');
  }

  const schwabPos = schwab.positions.find(p => p.symbol === symbol);
  if (!schwabPos) throw new Error(`${symbol} not found in this Schwab account`);
  const schwabShares = (schwabPos.longQuantity ?? 0) - (schwabPos.shortQuantity ?? 0);

  const ticker = await prisma.ticker.findUnique({ where: { symbol } });
  if (!ticker) throw new Error(`${symbol} ticker not found locally`);

  const position = await prisma.position.findUnique({
    where: { tickerId_accountId: { tickerId: ticker.id, accountId } },
    include: { lots: { where: { closedDate: null } } },
  });
  if (!position) throw new Error(`No local position for ${symbol} in this account`);

  const localShares = position.lots.reduce((s, l) => s + l.shares, 0);
  const diffShares = schwabShares - localShares;
  if (diffShares <= 0) {
    throw new Error(`${symbol}: Schwab (${schwabShares}) is not greater than local (${localShares}) — nothing to accept`);
  }

  await prisma.lot.create({
    data: {
      positionId: position.id,
      shares: diffShares,
      costBasis: schwabPos.averagePrice ?? 0,
      acquiredDate: new Date(),
      source: 'schwab',
      notes: `Accepted Schwab share-count diff (+${diffShares} shares, likely a dividend reinvestment) — acquisition date is a placeholder (today). Verify/edit for accurate LTCG/STCG treatment.`,
    },
  });

  return { symbol, diffShares, newLocalShares: localShares + diffShares };
}

/**
 * Same "Schwab has more shares than local" case as acceptShareDiff, but for
 * the manual-entry flow: the user supplies the actual acquisition date(s)
 * and cost/share for the missed purchase(s) (Schwab's averagePrice is a
 * blended figure across all lots, not the price for any one of them, so
 * it's often wrong for a single missed lot — this is the accurate
 * alternative to acceptShareDiff's placeholder).
 *
 * A single share-count diff is frequently the sum of SEVERAL distinct lots
 * (e.g. multiple DRIP reinvestments, or a position that was never fully
 * imported), not one missed trade — Schwab's own lot detail (schwab.com,
 * Cost Basis view) will show the real breakdown. So this accepts an array
 * of lots rather than a single date/cost pair, and verifies the entered
 * shares sum to the actual diff before creating anything.
 *
 * @param {PrismaClient} prisma
 * @param {number} accountId
 * @param {string} symbol
 * @param {{ acquiredDate: string, shares: number, costPerShare: number }[]} lots
 */
async function acceptAddWithCost(prisma, accountId, symbol, lots) {
  if (!lots?.length) throw new Error('At least one lot is required');
  for (const l of lots) {
    if (isNaN(new Date(l.acquiredDate))) throw new Error(`Invalid acquiredDate: ${l.acquiredDate}`);
    if (!(l.shares > 0)) throw new Error('Each lot must have shares > 0');
    if (l.costPerShare == null || l.costPerShare < 0) throw new Error('Each lot must have costPerShare >= 0');
  }

  const account = await prisma.account.findUnique({ where: { id: accountId } });
  if (!account) throw new Error('Account not found');
  if (!account.schwabAccountHash) throw new Error('Account is not linked to a Schwab account');

  const { schwabAccounts } = await previewAccounts(prisma);
  const schwab = schwabAccounts.find(a => a.hashValue === account.schwabAccountHash);
  if (!schwab) {
    throw new Error('Linked Schwab account not found in current Schwab data (hash mismatch or account removed)');
  }

  const schwabPos = schwab.positions.find(p => p.symbol === symbol);
  if (!schwabPos) throw new Error(`${symbol} not found in this Schwab account`);
  const schwabShares = (schwabPos.longQuantity ?? 0) - (schwabPos.shortQuantity ?? 0);

  const ticker = await prisma.ticker.findUnique({ where: { symbol } });
  if (!ticker) throw new Error(`${symbol} ticker not found locally`);

  const position = await prisma.position.findUnique({
    where: { tickerId_accountId: { tickerId: ticker.id, accountId } },
    include: { lots: { where: { closedDate: null } } },
  });
  if (!position) throw new Error(`No local position for ${symbol} in this account`);

  const localShares = position.lots.reduce((s, l) => s + l.shares, 0);
  const diffShares = +(schwabShares - localShares).toFixed(6);
  if (diffShares <= 0) {
    throw new Error(`${symbol}: Schwab (${schwabShares}) is not greater than local (${localShares}) — nothing to add`);
  }

  const enteredTotal = +lots.reduce((s, l) => s + l.shares, 0).toFixed(6);
  if (Math.abs(enteredTotal - diffShares) > 0.0001) {
    throw new Error(`Entered lots total ${enteredTotal} shares but the diff is ${diffShares} shares — they must match exactly`);
  }

  await prisma.$transaction(
    lots.map(l => prisma.lot.create({
      data: {
        positionId: position.id,
        shares: l.shares,
        costBasis: l.costPerShare,
        acquiredDate: new Date(l.acquiredDate),
        source: 'manual',
        notes: `Added to reconcile Schwab share-count diff (part of +${diffShares} shares total) — cost/date entered manually.`,
      },
    }))
  );

  return { symbol, diffShares, lotsAdded: lots.length, newLocalShares: localShares + diffShares };
}

/**
 * Returns open lots for a position — used to populate the lot-picker modal
 * when the user accepts a trim.
 *
 * @param {PrismaClient} prisma
 * @param {number} accountId
 * @param {string} symbol
 */
async function getOpenLots(prisma, accountId, symbol) {
  const ticker = await prisma.ticker.findUnique({ where: { symbol } });
  if (!ticker) throw new Error(`${symbol} ticker not found locally`);

  const position = await prisma.position.findUnique({
    where: { tickerId_accountId: { tickerId: ticker.id, accountId } },
    include: {
      lots: {
        where:   { closedDate: null },
        orderBy: { acquiredDate: 'asc' },
      },
    },
  });
  if (!position) throw new Error(`No local position for ${symbol} in this account`);
  return position.lots;
}

/**
 * Accepts a trim by closing/reducing specific lots as designated by the user.
 * The caller provides explicit lot selections so tax-lot choice is intentional
 * (not auto-FIFO'd).
 *
 * @param {PrismaClient} prisma
 * @param {number} accountId
 * @param {string} symbol
 * @param {string} saleDate   — ISO date string for the closing date on sold lots
 * @param {{ lotId: number, sharesSold: number }[]} selections
 */
async function acceptTrim(prisma, accountId, symbol, saleDate, selections) {
  if (!selections?.length) throw new Error('No lot selections provided');
  const closingDate = new Date(saleDate);
  if (isNaN(closingDate)) throw new Error(`Invalid saleDate: ${saleDate}`);

  const ticker = await prisma.ticker.findUnique({ where: { symbol } });
  if (!ticker) throw new Error(`${symbol} ticker not found locally`);

  const position = await prisma.position.findUnique({
    where: { tickerId_accountId: { tickerId: ticker.id, accountId } },
    include: { lots: { where: { closedDate: null } } },
  });
  if (!position) throw new Error(`No local position for ${symbol} in this account`);

  const lotMap = new Map(position.lots.map(l => [l.id, l]));
  const closed = [], reduced = [];

  for (const { lotId, sharesSold } of selections) {
    const lot = lotMap.get(lotId);
    if (!lot) throw new Error(`Lot ${lotId} not found or already closed`);
    if (sharesSold <= 0) continue;

    if (sharesSold >= lot.shares - 0.00001) {
      // Close entirely
      await prisma.lot.update({
        where: { id: lot.id },
        data: {
          closedDate: closingDate,
          notes: (lot.notes ? lot.notes + ' ' : '') +
            `Closed ${closingDate.toISOString().slice(0, 10)} via lot-picker trim (${lot.shares} shares sold).`,
        },
      });
      closed.push({ lotId: lot.id, shares: lot.shares });
    } else {
      // Partial sell — reduce shares in place
      const newShares = +(lot.shares - sharesSold).toFixed(6);
      await prisma.lot.update({
        where: { id: lot.id },
        data: {
          shares: newShares,
          notes: (lot.notes ? lot.notes + ' ' : '') +
            `Partially sold ${closingDate.toISOString().slice(0, 10)}: ${lot.shares} → ${newShares} shares (${sharesSold} sold).`,
        },
      });
      reduced.push({ lotId: lot.id, from: lot.shares, to: newShares });
    }
  }

  const totalSold = selections.reduce((s, sel) => s + sel.sharesSold, 0);
  return { symbol, totalSold: +totalSold.toFixed(6), closedLots: closed, reducedLots: reduced };
}

/**
 * Auto-sync entry point for "sync on login" — intended to be called once per
 * browser session (client-side gating) from the Portfolio page. Cheap when
 * there's nothing to do: checks `Account.lastSyncedAt` against `maxAgeHours`
 * using only a local query, and makes NO Schwab API calls at all if every
 * linked account was synced recently. Only accounts that are stale (or have
 * never been synced) get a real `syncAccount()` call.
 *
 * Does not touch unmatched/unlinked accounts — linking is still a manual
 * step via the Schwab Sync modal.
 *
 * @param {PrismaClient} prisma
 * @param {number} maxAgeHours
 * @returns {{
 *   maxAgeHours: number,
 *   synced: Array,   // accounts that were stale and got a fresh syncAccount() result
 *   skipped: Array,  // accounts synced recently enough to skip ({ accountId, name, lastSyncedAt })
 *   errors: Array,   // accounts where syncAccount() threw ({ accountId, name, error })
 * }}
 */
async function autoSyncStaleAccounts(prisma, maxAgeHours = 4) {
  const cutoff = new Date(Date.now() - maxAgeHours * 60 * 60 * 1000);

  const linkedAccounts = await prisma.account.findMany({
    where: { schwabAccountHash: { not: null } },
    select: { id: true, name: true, lastSyncedAt: true },
  });

  const stale = linkedAccounts.filter(a => !a.lastSyncedAt || a.lastSyncedAt < cutoff);
  const fresh = linkedAccounts.filter(a => a.lastSyncedAt && a.lastSyncedAt >= cutoff);

  const synced = [];
  const errors = [];

  for (const acct of stale) {
    try {
      const result = await syncAccount(prisma, acct.id);
      synced.push({ accountId: acct.id, name: acct.name, ...result });
    } catch (err) {
      errors.push({ accountId: acct.id, name: acct.name, error: err.message });
    }
  }

  return {
    maxAgeHours,
    synced,
    skipped: fresh.map(a => ({ accountId: a.id, name: a.name, lastSyncedAt: a.lastSyncedAt })),
    errors,
  };
}

module.exports = {
  getReconciliation,
  matchAccount,
  createAccountFromSchwab,
  syncAccount,
  acceptShareDiff,
  acceptAddWithCost,
  getOpenLots,
  acceptTrim,
  ignoreAccount,
  unignoreAccount,
  autoSyncStaleAccounts,
  maskAccountNumber,
};
