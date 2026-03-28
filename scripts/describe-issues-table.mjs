import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\n=== ISSUES TABLE SCHEMA ===\n`);

  const columns = await sql`
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'issues'
    ORDER BY ordinal_position
  `;

  console.log(`Column Name              | Data Type`);
  console.log(`-------------------------+--------------------------`);
  for (const col of columns) {
    console.log(`${col.column_name.padEnd(24)} | ${col.data_type}`);
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
