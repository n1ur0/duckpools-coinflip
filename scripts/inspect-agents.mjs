import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\nInspecting all agents...\n`);

  // Get all agents
  const agents = await sql`
    SELECT id, name, role, title, status, metadata, capabilities
    FROM agents
    ORDER BY name
    LIMIT 20
  `;

  console.log('Agents:');
  for (const a of agents) {
    console.log(`\n  ${a.name}`);
    console.log(`    ID: ${a.id}`);
    console.log(`    Role: ${a.role}`);
    console.log(`    Title: ${a.title}`);
    console.log(`    Status: ${a.status}`);
    console.log(`    Capabilities: ${a.capabilities}`);
    console.log(`    Metadata: ${JSON.stringify(a.metadata, null, 4)}`);
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
