/**
 * One-off backfill: copy the old single-value `domain` column into the new
 * `domains` array column. Run AFTER `prisma db push` has dropped `domain`
 * and added `domains String[]`.
 *
 * Captured values (2026-06-13, before column drop):
 *   EOSE -> energy_storage
 *   MSFT -> it_software_cloud
 *   SPWR -> solar
 *   TSLA -> energy_storage
 *   AAPL -> it_software_cloud
 *   AMPX -> energy_storage
 *   ENVX -> energy_storage
 *
 * Usage:
 *   cd server
 *   DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) node scripts/backfill_domains.js
 */

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

const BACKFILL = {
  EOSE: ['energy_storage'],
  MSFT: ['it_software_cloud'],
  SPWR: ['solar'],
  TSLA: ['energy_storage'],
  AAPL: ['it_software_cloud'],
  AMPX: ['energy_storage'],
  ENVX: ['energy_storage'],
};

async function main() {
  for (const [symbol, domains] of Object.entries(BACKFILL)) {
    const result = await prisma.ticker.updateMany({
      where: { symbol },
      data: { domains },
    });
    console.log(`${symbol}: ${result.count} row(s) updated -> ${JSON.stringify(domains)}`);
  }
}

main()
  .catch(e => { console.error(e); process.exit(1); })
  .finally(() => prisma.$disconnect());
