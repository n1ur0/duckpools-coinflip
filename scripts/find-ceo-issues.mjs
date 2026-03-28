import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\n=== CEO-RELATED ISSUES ===\n`);

  // Get CEO ID
  const ceo = await sql`SELECT id FROM agents WHERE name = 'CEO'`;

  if (ceo.length === 0) {
    console.log('CEO agent not found!');
    process.exit(1);
  }

  console.log(`CEO ID: ${ceo[0].id}`);

  // Get issues assigned to CEO
  const issues = await sql`
    SELECT id, identifier, title, status, priority
    FROM issues
    WHERE assignee_agent_id = ${ceo[0].id}
      AND status NOT IN ('done', 'cancelled')
    ORDER BY priority DESC
  `;

  console.log(`\nIssues assigned to CEO: ${issues.length}\n`);

  for (const issue of issues) {
    console.log(`[${issue.priority.toUpperCase()}] ${issue.identifier || 'NO ID'} - ${issue.title}`);
    console.log(`  Status: ${issue.status}`);
    console.log();
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
