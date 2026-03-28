import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const qaAgentNames = ['QA Tester Jr', 'Protocol Tester Jr', 'Performance Tester Jr', 'Regression Tester Jr', 'Accessibility Tester Jr'];

async function main() {
  console.log(`\n=== QA TEAM ASSIGNMENTS ===\n`);

  const assignments = await sql`
    SELECT
      a.id as agent_id,
      a.name as agent_name,
      a.status as agent_status,
      i.id as issue_id,
      i.title as issue_title,
      i.status as issue_status
    FROM agents a
    LEFT JOIN agent_assignments aa ON a.id = aa.agent_id
    LEFT JOIN issues i ON aa.issue_id = i.id
    WHERE a.name = ANY(${qaAgentNames})
    ORDER BY a.name
  `;

  console.log(`Agent Name                 | Status      | Issue # | Issue Title`);
  console.log(`---------------------------+-------------+---------+--------------------------------------------------`);
  for (const row of assignments) {
    const issueInfo = row.issue_id ? `#${row.issue_id} ${row.issue_title.substring(0, 40)}...` : 'No issue assigned';
    console.log(`${row.agent_name.padEnd(25)} | ${row.agent_status.padEnd(11)} | ${issueInfo}`);
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
