-- Migration: add_owner_profile_auth_fields
-- Adds clerkUserId (unique, nullable) and role (default "user") to OwnerProfile.
-- Existing rows get role = "user". Luis's row should be manually updated to "admin"
-- via Prisma Studio or a one-time SQL UPDATE after running this migration.

ALTER TABLE "OwnerProfile" ADD COLUMN "clerkUserId" TEXT;
ALTER TABLE "OwnerProfile" ADD COLUMN "role" TEXT NOT NULL DEFAULT 'user';

-- Unique index on clerkUserId (nullable — only enforced when non-null)
CREATE UNIQUE INDEX "OwnerProfile_clerkUserId_key" ON "OwnerProfile"("clerkUserId");
