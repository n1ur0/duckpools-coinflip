import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\n=== COMPANIES ===\n`);

  const companies = await sql`SELECT id, name FROM companies`;

  for (const company of companies) {
    console.log(`  ${company.id} - ${company.name}`);
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
