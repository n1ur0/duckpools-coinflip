import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\n=== STATUS/REPORTING ISSUES ===\n`);

  const keywords = ['status', 'report', 'velocity', 'sprint', 'weekly', 'em', 'manager'];

  const issues = await sql`
    SELECT
      i.id,
      i.identifier,
      i.title,
      i.status,
      i.priority,
      i.assignee_agent_id,
      a.name as assignee_name
    FROM issues i
    LEFT JOIN agents a ON i.assignee_agent_id = a.id
    WHERE i.status NOT IN ('done', 'cancelled')
    ORDER BY i.priority DESC
  `;

  const matching = issues.filter(i =>
    keywords.some(kw =>
      i.title.toLowerCase().includes(kw) ||
      (i.identifier && i.identifier.toLowerCase().includes(kw))
    )
  );

  console.log(`Found ${matching.length} status/reporting issues:\n`);

  for (const issue of matching) {
    console.log(`[${issue.priority.toUpperCase()}] ${issue.identifier || 'NO ID'} - ${issue.title}`);
    console.log(`  Status: ${issue.status}, Assignee: ${issue.assignee_name || 'NONE'}`);
    console.log();
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
