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
    // Local positions with no corresponding Schwab position (e.g. sold,
    // or held at a different broker under this account by mistake).
    const localOnly = localPositions
      .filter(p => !schwabBySymbol.has(p.symbol))
      .map(p => ({ symbol: p.symbol, localShares: p.totalShares }));

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

  const result = {
    cashBalance: schwab.cashBalance ?? null,
    lastSyncedAt: accountUpdateData.lastSyncedAt,
    newPositions: [],      // symbols newly created with a placeholder 'schwab' lot
    updatedSchwabLots: [],  // symbols where an existing 'schwab' lot was refreshed
    positionDiffs: [],      // symbols with existing (non-schwab-sourced) lots that disagree on share count
    skippedAssetTypes: [],  // schwab positions we didn't sync (e.g. options, cash equivalents)
    promotedTickers: [],    // watchlist tickers promoted to portfolio because Schwab now shows a real position
  };

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
        if (Math.abs(localPos.totalShares - schwabShares) > 0.0001) {
          result.positionDiffs.push({ symbol, schwabShares, localShares: localPos.totalShares });
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
  ignoreAccount,
  unignoreAccount,
  autoSyncStaleAccounts,
  maskAccountNumber,
};
