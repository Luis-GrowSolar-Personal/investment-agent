CREATE TABLE "OwnerTickerConfig" (
  "id"         SERIAL PRIMARY KEY,
  "owner"      TEXT NOT NULL,
  "tickerId"   INTEGER NOT NULL,
  "capPercent" DOUBLE PRECISION,
  CONSTRAINT "OwnerTickerConfig_owner_tickerId_key"
    UNIQUE ("owner", "tickerId"),
  CONSTRAINT "OwnerTickerConfig_tickerId_fkey"
    FOREIGN KEY ("tickerId") REFERENCES "Ticker"("id")
    ON DELETE CASCADE ON UPDATE CASCADE
);
