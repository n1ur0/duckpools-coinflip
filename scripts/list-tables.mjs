import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\nList of tables in paperclip database:\n`);

  const tables = await sql`
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
  `;

  for (const t of tables) {
    console.log(`  ${t.table_name}`);
  }

  // Check if there's an agent_issues or assignments table
  console.log(`\nLooking for agent-related tables...`);

  const agentTables = tables.filter(t =>
    t.table_name.toLowerCase().includes('agent') ||
    t.table_name.toLowerCase().includes('issue') ||
    t.table_name.toLowerCase().includes('assign')
  );

  if (agentTables.length > 0) {
    console.log(`\nAgent/Issue/Assignment tables:`);
    for (const t of agentTables) {
      console.log(`  ${t.table_name}`);

      // Get column info
      const columns = await sql`
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = ${t.table_name}
        ORDER BY ordinal_position
      `;

      for (const c of columns) {
        console.log(`    ${c.column_name}: ${c.data_type}`);
      }

      // Get sample data
      const sample = await sql`
        SELECT *
        FROM ${sql.unsafe(t.table_name)}
        LIMIT 1
      `;

      if (sample.length > 0) {
        console.log(`    Sample: ${JSON.stringify(sample[0], null, 2).split('\n').join('\n    ')}`);
      }
    }
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
