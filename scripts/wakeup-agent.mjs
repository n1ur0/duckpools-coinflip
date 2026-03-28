import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  const agentId = process.argv[2];
  const reason = process.argv[3] || 'Manual wakeup request';

  if (!agentId) {
    console.log('Usage: node wakeup-agent.mjs <agent_id> [reason]');
    process.exit(1);
  }

  console.log(`\n=== WAKING UP AGENT ===\n`);

  // Get agent info
  const agent = await sql`SELECT id, name, status FROM agents WHERE id = ${agentId}`;

  if (agent.length === 0) {
    console.log('Agent not found!');
    process.exit(1);
  }

  console.log(`Agent: ${agent[0].name}`);
  console.log(`Current Status: ${agent[0].status}`);

  // Get company ID for this agent (assuming it's Matsuzaka)
  const company = await sql`SELECT id FROM companies WHERE name = 'Matsuzaka'`;

  if (company.length === 0) {
    console.log('Company not found!');
    process.exit(1);
  }

  // Create wakeup request
  await sql`
    INSERT INTO agent_wakeup_requests (agent_id, company_id, source, trigger_detail, reason, created_at)
    VALUES (${agentId}, ${company[0].id}, 'automation', 'system', ${reason}, NOW())
  `;

  console.log(`\n=> Wakeup request sent!`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
