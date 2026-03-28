import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\nInspecting agents table...\n`);

  // Get table columns
  const columns = await sql`
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'agents'
    ORDER BY ordinal_position
  `;

  console.log('Columns:');
  for (const col of columns) {
    console.log(`  ${col.column_name}: ${col.data_type} (nullable: ${col.is_nullable})`);
  }

  // Get a sample row
  console.log(`\nSample data (UX/UI Design team):`);
  const agents = await sql`
    SELECT *
    FROM agents
    WHERE team = 'UX/UI Design'
    LIMIT 5
  `;

  for (const a of agents) {
    console.log(JSON.stringify(a, null, 2));
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
