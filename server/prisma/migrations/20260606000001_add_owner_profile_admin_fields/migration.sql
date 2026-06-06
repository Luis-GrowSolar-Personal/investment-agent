-- Migration: add_owner_profile_admin_fields
-- Adds all portfolio management configuration fields to OwnerProfile.

ALTER TABLE "OwnerProfile"
  ADD COLUMN IF NOT EXISTS "minPositionDollar" DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS "maxPositions"      INTEGER,
  ADD COLUMN IF NOT EXISTS "cashReservePct"    DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS "yearsToGoal"       INTEGER,
  ADD COLUMN IF NOT EXISTS "estSpecRatio"      DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS "riskTolerance"     TEXT,
  ADD COLUMN IF NOT EXISTS "taxSensitivity"    TEXT,
  ADD COLUMN IF NOT EXISTS "accountPurpose"    TEXT,
  ADD COLUMN IF NOT EXISTS "domainsOfInterest" JSONB,
  ADD COLUMN IF NOT EXISTS "benchmarkBaseline" TEXT,
  ADD COLUMN IF NOT EXISTS "specExitSpeed"     TEXT,
  ADD COLUMN IF NOT EXISTS "newMoneyBehavior"  TEXT;
