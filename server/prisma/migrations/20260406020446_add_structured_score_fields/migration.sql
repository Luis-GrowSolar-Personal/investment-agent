-- AlterTable
ALTER TABLE "Analysis" ADD COLUMN     "activeDriverCount" INTEGER,
ADD COLUMN     "blindSpotsTriggered" JSONB,
ADD COLUMN     "capPercent" DOUBLE PRECISION,
ADD COLUMN     "credibilityDelta" TEXT,
ADD COLUMN     "freshMoneyAllocation" DOUBLE PRECISION,
ADD COLUMN     "mitigationArgumentPresent" BOOLEAN,
ADD COLUMN     "mitigationCapabilityTrackRecord" TEXT,
ADD COLUMN     "ratchetTranche" INTEGER,
ADD COLUMN     "stumbleType" TEXT,
ADD COLUMN     "thesisDelta" TEXT,
ADD COLUMN     "threatMechanismImpaired" BOOLEAN;
