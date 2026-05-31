-- Migration: add_owner_profile
-- Creates OwnerProfile table for per-owner investment goals and display names.

CREATE TABLE "OwnerProfile" (
    "owner"        TEXT        NOT NULL,
    "displayName"  TEXT,
    "enoughNumber" DOUBLE PRECISION,
    "createdAt"    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "OwnerProfile_pkey" PRIMARY KEY ("owner")
);

-- Back-fill: create an OwnerProfile row for every distinct owner that already
-- exists in the Account table, so no existing accounts are orphaned.
INSERT INTO "OwnerProfile" ("owner", "updatedAt")
SELECT DISTINCT "owner", CURRENT_TIMESTAMP
FROM   "Account"
ON CONFLICT ("owner") DO NOTHING;
