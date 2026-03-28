import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const COMPANY_ID = 'c3a27363-6930-45ad-b684-a6116c0f3313';
const DEFI_BANKROLL_TEAM = [
  'LP Contract Developer Jr',
  'Yield Engineer Jr',
  'Risk Analyst Jr',
  'Risk Analyst Jr 2'
];

async function main() {
  console.log(`\n=== DEFI & BANKROLL - TEAM SURVEY ===\n`);

  // Get junior agents with their IDs and statuses
  const agents = await sql`
    SELECT
      a.id,
      a.name,
      a.status,
      a.adapter_config
    FROM agents a
    WHERE a.company_id = ${COMPANY_ID}
      AND a.name = ANY(${DEFI_BANKROLL_TEAM})
    ORDER BY a.name
  `;

  if (agents.length === 0) {
    console.log('No DeFi & Bankroll junior agents found.\n');
    await sql.end();
    return;
  }

  console.log('JUNIOR TEAM STATUS:\n');
  for (const agent of agents) {
    const statusEmoji = agent.status === 'idle' ? '💤 IDLE' : '⚡ ACTIVE';
    console.log(`${statusEmoji}`);
    console.log(`   Name: ${agent.name}`);
    console.log(`   ID: ${agent.id}`);
    console.log(`   Status: ${agent.status}`);
    
    // Get assigned issues
    const assignedIssues = await sql`
      SELECT i.identifier, i.title, i.status
      FROM issues i
      WHERE i.assignee_agent_id = ${agent.id}
        AND i.company_id = ${COMPANY_ID}
        AND i.status NOT IN ('done', 'cancelled')
      ORDER BY i.priority DESC, i.created_at ASC
    `;
    
    if (assignedIssues.length > 0) {
      console.log(`   Assigned Issues (${assignedIssues.length}):`);
      for (const issue of assignedIssues) {
        console.log(`      - ${issue.identifier}: ${issue.title} [${issue.status}]`);
      }
    } else {
      console.log(`   Assigned Issues: None`);
    }
    
    console.log(`   Wake Command: curl -s -X POST "http://127.0.0.1:3100/api/agents/${agent.id}/wakeup" -H "Content-Type: application/json" -d '{"source":"automation","triggerDetail":"system","reason":"EM assignment"}'`);
    console.log('');
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
