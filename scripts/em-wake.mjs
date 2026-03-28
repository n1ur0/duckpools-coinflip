import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const COMPANY_ID = 'c3a27363-6930-45ad-b684-a6116c0f3313';
const EM_JUNIOR_TEAM = [
  'Contract Auditor Jr',
  'Serialization Specialist Jr',
  'Oracle Engineer Jr',
  'Oracle Engineer Jr 2',
  'SDK Developer Jr',
  'DevOps Engineer Jr'
];

async function main() {
  console.log(`\n=== PROTOCOL CORE - AGENT WAKEUP ===\n`);

  // Get junior agents with their IDs
  const agents = await sql`
    SELECT
      a.id,
      a.name,
      a.status
    FROM agents a
    WHERE a.company_id = ${COMPANY_ID}
      AND a.name = ANY(${EM_JUNIOR_TEAM})
    ORDER BY a.name
  `;

  if (agents.length === 0) {
    console.log('No junior agents found.\n');
    await sql.end();
    return;
  }

  // Output agent IDs for waking up
  console.log('AGENT ID MAPPING:\n');
  for (const agent of agents) {
    const statusEmoji = agent.status === 'idle' ? '💤' : '⚡';
    console.log(`${statusEmoji} ${agent.name}`);
    console.log(`   ID: ${agent.id}`);
    console.log(`   Wake command: curl -s -X POST "http://127.0.0.1:3100/api/agents/${agent.id}/wakeup" -H "Content-Type: application/json"`);
    console.log('');
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
