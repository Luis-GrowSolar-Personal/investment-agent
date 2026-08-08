-- Migration: add_top_level_allocation_targets
-- Adds explicit top-level target percentages (Equities / ETF / Crypto /
-- Commodities) to OwnerProfile. Replaces the old bottom-up derivation that
-- summed per-ticker capPercent on whatever ETF/crypto happened to be held.
-- User-owned targets, independent of yearsToGoal/riskTolerance by design.

ALTER TABLE "OwnerProfile"
  ADD COLUMN IF NOT EXISTS "equitiesTargetPct"    DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS "etfTargetPct"         DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS "cryptoTargetPct"      DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS "commoditiesTargetPct" DOUBLE PRECISION;
