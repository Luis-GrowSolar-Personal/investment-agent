-- AlterTable
ALTER TABLE "Analysis" ADD COLUMN     "finalAction" TEXT,
ADD COLUMN     "finalConfidence" TEXT,
ADD COLUMN     "suggestedOverride" TEXT,
ADD COLUMN     "tier" TEXT,
ADD COLUMN     "trajectory" TEXT,
ADD COLUMN     "trendRationale" TEXT;
