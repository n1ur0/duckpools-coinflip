import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  const agentId = process.argv[2];

  if (!agentId) {
    console.log('Usage: node agent-issues.mjs <agent_id>');
    process.exit(1);
  }

  console.log(`\nIssues assigned to agent: ${agentId}\n`);

  const issues = await sql`
    SELECT
      i.id,
      i.issue_number,
      i.identifier,
      i.title,
      i.status,
      i.priority,
      i.created_at,
      i.updated_at,
      i.description
    FROM issues i
    WHERE i.assignee_agent_id = ${agentId}
      AND i.status NOT IN ('done', 'cancelled')
    ORDER BY i.priority DESC, i.issue_number
  `;

  if (issues.length === 0) {
    console.log('No active issues assigned to this agent');
  } else {
    console.log(`Found ${issues.length} issues:\n`);
    for (const issue of issues) {
      console.log(`[${issue.priority.toUpperCase()}] ${issue.identifier || 'NO ID'} - ${issue.title}`);
      console.log(`  ID: ${issue.id}`);
      console.log(`  Number: ${issue.issue_number}`);
      console.log(`  Status: ${issue.status}`);
      console.log(`  Created: ${issue.created_at}`);
      console.log(`  Updated: ${issue.updated_at}`);
      console.log(`  Description: ${issue.description?.substring(0, 200)}...`);
      console.log();
    }
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
