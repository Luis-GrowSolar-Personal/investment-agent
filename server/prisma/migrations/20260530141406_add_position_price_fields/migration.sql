-- AlterTable
ALTER TABLE "Position" ADD COLUMN     "dayChangeDollar" DOUBLE PRECISION,
ADD COLUMN     "dayChangePct" DOUBLE PRECISION,
ADD COLUMN     "lastPrice" DOUBLE PRECISION,
ADD COLUMN     "lastPriceAsOf" TIMESTAMP(3);
