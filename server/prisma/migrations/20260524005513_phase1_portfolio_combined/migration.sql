-- AlterTable
ALTER TABLE "Ticker" ADD COLUMN     "activeDriverCount" INTEGER,
ADD COLUMN     "inScope" BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN     "tierMechanical" TEXT,
ADD COLUMN     "tierOverride" TEXT,
ADD COLUMN     "tierRationale" TEXT,
ADD COLUMN     "tierReviewedAt" TIMESTAMP(3),
ADD COLUMN     "typeReviewedAt" TIMESTAMP(3);

-- CreateTable
CREATE TABLE "Position" (
    "id" SERIAL NOT NULL,
    "tickerId" INTEGER NOT NULL,
    "account" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "closedAt" TIMESTAMP(3),

    CONSTRAINT "Position_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Lot" (
    "id" SERIAL NOT NULL,
    "positionId" INTEGER NOT NULL,
    "shares" DOUBLE PRECISION NOT NULL,
    "costBasis" DOUBLE PRECISION NOT NULL,
    "acquiredDate" TIMESTAMP(3) NOT NULL,
    "closedDate" TIMESTAMP(3),
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Lot_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CashBalance" (
    "account" TEXT NOT NULL,
    "balance" DOUBLE PRECISION NOT NULL,
    "asOfDate" TIMESTAMP(3) NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CashBalance_pkey" PRIMARY KEY ("account")
);

-- CreateIndex
CREATE UNIQUE INDEX "Position_tickerId_account_key" ON "Position"("tickerId", "account");

-- AddForeignKey
ALTER TABLE "Position" ADD CONSTRAINT "Position_tickerId_fkey" FOREIGN KEY ("tickerId") REFERENCES "Ticker"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Lot" ADD CONSTRAINT "Lot_positionId_fkey" FOREIGN KEY ("positionId") REFERENCES "Position"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
