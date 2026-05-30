-- Phase 2: Account model, Position accountId, drop CashBalance
-- Manually edited to backfill existing Position rows before making accountId non-nullable.

-- DropIndex (old unique constraint on account string)
DROP INDEX "Position_tickerId_account_key";

-- AlterTable: add source to Lot
ALTER TABLE "Lot" ADD COLUMN "source" TEXT NOT NULL DEFAULT 'manual';

-- CreateTable Account
CREATE TABLE "Account" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "owner" TEXT NOT NULL,
    "managed" BOOLEAN NOT NULL DEFAULT false,
    "ltcgRate" DOUBLE PRECISION,
    "stcgRate" DOUBLE PRECISION,
    "cashBalance" DOUBLE PRECISION,
    "cashAsOfDate" TIMESTAMP(3),
    "marginBalance" DOUBLE PRECISION,
    "marginRate" DOUBLE PRECISION,
    "marginRateAsOf" TIMESTAMP(3),
    "marginRateLog" JSONB,
    "marginAsOfDate" TIMESTAMP(3),
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Account_pkey" PRIMARY KEY ("id")
);

-- CreateIndex for Account unique constraint
CREATE UNIQUE INDEX "Account_name_owner_key" ON "Account"("name", "owner");

-- Seed default account so existing Position rows can be backfilled
INSERT INTO "Account" ("name", "type", "owner", "managed", "createdAt")
VALUES ('Schwab Taxable 1', 'taxable', 'Luis', true, CURRENT_TIMESTAMP);

-- Add accountId as nullable first so the backfill can run
ALTER TABLE "Position" ADD COLUMN "accountId" INTEGER;

-- Backfill all existing rows to the default account
UPDATE "Position" SET "accountId" = (
    SELECT "id" FROM "Account" WHERE "name" = 'Schwab Taxable 1' AND "owner" = 'Luis'
);

-- Now enforce non-nullable
ALTER TABLE "Position" ALTER COLUMN "accountId" SET NOT NULL;

-- Drop old account string column
ALTER TABLE "Position" DROP COLUMN "account";

-- AddForeignKey
ALTER TABLE "Position" ADD CONSTRAINT "Position_accountId_fkey"
    FOREIGN KEY ("accountId") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- CreateIndex for new unique constraint
CREATE UNIQUE INDEX "Position_tickerId_accountId_key" ON "Position"("tickerId", "accountId");

-- DropTable CashBalance
DROP TABLE "CashBalance";
