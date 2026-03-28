import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\n=== AGENTS IN SYSTEM ===\n`);

  const agents = await sql`
    SELECT id, name, role, status
    FROM agents
    ORDER BY name
  `;

  console.log(`ID                                  | Name                    | Role                | Status`);
  console.log(`------------------------------------+-------------------------+---------------------+--------`);
  for (const agent of agents) {
    console.log(`${agent.id} | ${agent.name.padEnd(23)} | ${agent.role.padEnd(19)} | ${agent.status}`);
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
