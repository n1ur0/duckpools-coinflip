import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  const issueId = process.argv[2];
  const agentId = process.argv[3];

  if (!issueId || !agentId) {
    console.log('Usage: node assign-issue.mjs <issue_id> <agent_id>');
    process.exit(1);
  }

  console.log(`\n=== ASSIGNING ISSUE ===\n`);

  // Get issue and agent info
  const issue = await sql`SELECT * FROM issues WHERE id = ${issueId}`;
  const agent = await sql`SELECT name, status FROM agents WHERE id = ${agentId}`;

  if (issue.length === 0) {
    console.log('Issue not found!');
    process.exit(1);
  }

  if (agent.length === 0) {
    console.log('Agent not found!');
    process.exit(1);
  }

  console.log(`Issue: ${issue[0].identifier || 'NO ID'} - ${issue[0].title}`);
  console.log(`Agent: ${agent[0].name} (${agent[0].status})`);

  // Update the issue
  await sql`
    UPDATE issues
    SET assignee_agent_id = ${agentId},
        status = 'todo',
        updated_at = NOW()
    WHERE id = ${issueId}
  `;

  console.log(`\n=> Issue assigned successfully!`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
