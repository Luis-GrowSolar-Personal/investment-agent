const express = require('express');
const { requireAuth } = require('@clerk/express');
const prisma = require('../lib/prisma');
const { PROMPT_VERSION, MODEL_VERSION } = require('../lib/versions');
const { computeTrendVerdict, applyMatrix, computeFinalConfidence } = require('../lib/trendAnalyst');

const router = express.Router();

// ── Analysis parsers ──────────────────────────────────────────────────────────

function extractSection(text, sectionName) {
  const regex = new RegExp(`##\\s+${sectionName}[\\s\\S]*?(?=\\n##|$)`, 'i');
  const match = text.match(regex);
  return match ? match[0] : '';
}

function parseFirstLine(section, candidates) {
  const firstLine = section.split('\n').find(l => l.trim() && !l.startsWith('#')) ?? '';
  // Anchor to line start — verdict always leads ("Hold - ...", "Score: Weakening", "Add to 15%")
  for (const val of candidates) {
    if (new RegExp(`^\\s*(score:\\s*)?${val}\\b`, 'i').test(firstLine)) return val;
  }
  // Fallback: whole-word match anywhere in full section
  for (const val of candidates) {
    if (new RegExp(`\\b${val}\\b`, 'i').test(section)) return val;
  }
  return null;
}

function parseThesisHealth(text) {
  const section = extractSection(text, 'THESIS HEALTH');
  return parseFirstLine(section, ['Strengthening', 'Intact', 'Weakening', 'Broken']) ?? 'Unknown';
}

function parseRecommendation(text) {
  const section = extractSection(text, 'RECOMMENDATION');
  return parseFirstLine(section, ['Exit', 'Trim', 'Add', 'Hold']) ?? 'Unknown';
}

function parseRecommendedSize(text) {
  const section = extractSection(text, 'RECOMMENDATION');
  const match = section.match(/(\d+(?:\.\d+)?)\s*%/);
  return match ? parseFloat(match[1]) : null;
}

// ── Title generation ──────────────────────────────────────────────────────────

function generateTitle(shortName, symbol, callDate) {
  const date = callDate ? new Date(callDate) : new Date();
  const quarter = Math.floor(date.getMonth() / 3) + 1;
  const year = date.getFullYear();
  return `${shortName} (${symbol}) Q${quarter} ${year} Earnings Call Transcript`;
}

// ── Route ─────────────────────────────────────────────────────────────────────

router.post('/', requireAuth(), async (req, res) => {
  const { transcript, tickerSymbol, tickerName, shortName, callDate, title, analysis, structuredScore, formerSymbol } = req.body;

  if (!tickerSymbol || typeof tickerSymbol !== 'string' || tickerSymbol.trim().length === 0) {
    return res.status(400).json({ error: 'tickerSymbol is required' });
  }
  if (!analysis || typeof analysis !== 'string' || analysis.trim().length === 0) {
    return res.status(400).json({ error: 'analysis is required' });
  }
  if (!transcript || typeof transcript !== 'string' || transcript.trim().length === 0) {
    return res.status(400).json({ error: 'transcript is required' });
  }

  const symbol = tickerSymbol.trim().toUpperCase();

  // shortName fallback: provided → first word of tickerName → symbol
  const effectiveShortName =
    shortName?.trim() ||
    (tickerName?.trim() ? tickerName.trim().split(/\s+/)[0] : symbol);

  const thesisHealth    = parseThesisHealth(analysis);
  const recommendation  = parseRecommendation(analysis);
  const recommendedSize = parseRecommendedSize(analysis);

  try {
    // If the company changed its ticker, migrate old history to the new symbol
    if (formerSymbol?.trim()) {
      const oldSymbol = formerSymbol.trim().toUpperCase();
      if (oldSymbol !== symbol) {
        const oldTicker = await prisma.ticker.findUnique({ where: { symbol: oldSymbol } });
        if (oldTicker) {
          const newTicker = await prisma.ticker.findUnique({ where: { symbol } });
          if (newTicker) {
            // Both old and new symbol exist — move old transcripts to new ticker, delete old
            await prisma.transcript.updateMany({
              where: { tickerId: oldTicker.id },
              data: { tickerId: newTicker.id },
            });
            await prisma.ticker.delete({ where: { id: oldTicker.id } });
          } else {
            // New symbol doesn't exist yet — simple rename
            await prisma.ticker.update({ where: { symbol: oldSymbol }, data: { symbol } });
          }
        }
      }
    }

    const ticker = await prisma.ticker.upsert({
      where: { symbol },
      // Update shortName if provided — it may have been corrected by the user
      update: {
        ...(shortName?.trim() && { shortName: shortName.trim() }),
      },
      create: {
        symbol,
        name: tickerName?.trim() || symbol,
        shortName: effectiveShortName,
        type: 'A',
        capPercent: 35,
      },
    });

    // Enforce transcript limit for watchlist tickers (Design Principle #3 in
    // CLAUDE.md). Cap raised from 6 → 50 to support the historical
    // backtest-load workflow: a 4-year horizon means ~16 quarters per ticker,
    // and we want headroom above that. Storage cost is trivial (text-only,
    // ~50KB per transcript). The cap can stay at 50 indefinitely or get
    // removed entirely once we've validated the simulator end-to-end.
    const WATCHLIST_TRANSCRIPT_CAP = 50;
    if (ticker.status === 'watchlist') {
      const existing = await prisma.transcript.findMany({
        where: { tickerId: ticker.id },
        orderBy: { callDate: 'asc' },
        select: { id: true },
      });
      if (existing.length >= WATCHLIST_TRANSCRIPT_CAP) {
        const oldest = existing[0];
        await prisma.analysis.deleteMany({ where: { transcriptId: oldest.id } });
        await prisma.transcript.delete({ where: { id: oldest.id } });
      }
    }

    // Use saved shortName (may have just been updated) for the title
    const displayShortName = ticker.shortName || effectiveShortName;
    const standardTitle = title?.trim() || generateTitle(displayShortName, symbol, callDate);

    const transcriptRecord = await prisma.transcript.create({
      data: {
        tickerId: ticker.id,
        rawText:  transcript,
        callDate: callDate ? new Date(callDate) : new Date(),
        title:    standardTitle,
      },
    });

    const s = structuredScore || {};
    const analysisRecord = await prisma.analysis.create({
      data: {
        transcriptId:    transcriptRecord.id,
        rawOutput:       analysis,
        thesisHealth,
        recommendation,
        recommendedSize,
        // Structured score fields (all optional)
        thesisDelta:                     s.thesisDelta                     ?? null,
        freshMoneyAllocation:            s.freshMoneyAllocation            ?? null,
        stumbleType:                     s.stumbleType                     ?? null,
        threatMechanismImpaired:         s.threatMechanismImpaired         ?? null,
        credibilityDelta:                s.credibilityDelta                ?? null,
        activeDriverCount:               s.activeDriverCount               ?? null,
        ratchetTranche:                  s.ratchetTranche                  ?? null,
        blindSpotsTriggered:             s.blindSpotsTriggered             ?? null,
        capPercent:                      s.capPercent                      ?? null,
        mitigationArgumentPresent:       s.mitigationArgumentPresent       ?? null,
        mitigationCapabilityTrackRecord: s.mitigationCapabilityTrackRecord ?? null,
        typeClassificationRationale:     s.typeClassificationRationale     ?? null,
        summary:                         s.summary                         ?? null,
        // Version stamps — always server-controlled, never from client input
        promptVersion:                   PROMPT_VERSION,
        modelVersion:                    MODEL_VERSION,
      },
    });

    // ── Trend layer recompute (per-ticker, event-driven) ─────────────────
    // Recompute the trend verdict + finalAction for THIS TICKER ONLY,
    // writing the 6 trend fields onto the just-created Analysis row. Pure
    // in-memory operation over this ticker's existing Analysis history — no
    // price/fundamentals fetch, no full-portfolio sweep. Tier is read-only
    // here (Ticker.tierOverride ?? Ticker.tierMechanical ?? 'established');
    // tier *re*classification remains a separate (not-yet-built) cron.
    // See docs/CoWork_handoff_2026-06-14f.md.
    try {
      const transcripts = await prisma.transcript.findMany({
        where: { tickerId: ticker.id },
        include: {
          analyses: { orderBy: { createdAt: 'desc' }, take: 1 },
        },
        orderBy: { callDate: 'asc' },
      });

      const latestTranscript = transcripts[transcripts.length - 1];
      if (latestTranscript?.id !== transcriptRecord.id) {
        // Out-of-order insert (backfilling an older quarter than the current
        // latest). A correct recompute would need to re-walk every later
        // entry's verdict too — out of scope for this per-save path.
        console.warn(
          `[trend] ${symbol}: new transcript is not the chronological latest ` +
          `for this ticker — skipping trend recompute. Run ` +
          `"python3 analysis/sync_trend_to_db.py --ticker ${symbol}" to resync ` +
          `the full history.`
        );
      } else {
        // Latest-per-transcript history, chronological (oldest → newest),
        // mapped to trend_analyst.py's snake_case schema for fixture parity.
        const history = transcripts
          .map(t => t.analyses[0])
          .filter(Boolean)
          .map(a => ({
            thesis_health:           a.thesisHealth,
            recommendation:          a.recommendation,
            recommended_size:        a.recommendedSize,
            fresh_money_allocation:  a.freshMoneyAllocation,
            credibility_delta:       a.credibilityDelta,
            mitigation_track_record: a.mitigationCapabilityTrackRecord,
            thesis_delta:            a.thesisDelta,
            stumble_type:            a.stumbleType,
          }));

        const tier = ticker.tierOverride ?? ticker.tierMechanical ?? 'established';
        const verdict = computeTrendVerdict(history, tier);
        const [finalAction, finalRationale] = applyMatrix(recommendation, verdict);
        const finalConfidence = computeFinalConfidence(verdict, recommendation, finalAction);

        await prisma.analysis.update({
          where: { id: analysisRecord.id },
          data: {
            tier,
            trajectory:        verdict?.trajectory ?? null,
            suggestedOverride: verdict?.suggested_override ?? null,
            finalAction,
            finalConfidence,
            trendRationale:    finalRationale,
          },
        });
      }
    } catch (trendErr) {
      // Best-effort — never block the save on a trend-layer failure.
      console.error(`[trend] ${symbol}: trend recompute failed:`, trendErr.message);
    }

    res.json({
      tickerId:     ticker.id,
      transcriptId: transcriptRecord.id,
      analysisId:   analysisRecord.id,
      title:        standardTitle,
    });
  } catch (err) {
    console.error('Error in /api/save:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
