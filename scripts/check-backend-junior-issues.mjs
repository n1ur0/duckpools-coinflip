import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\n=== BACKEND & INFRASTRUCTURE JUNIOR ASSIGNMENTS ===\n`);

  const issues = await sql`
    SELECT
      i.id,
      i.title,
      i.status,
      i.priority,
      a.id as agent_id,
      a.name as agent_name,
      i.issue_number
    FROM issues i
    LEFT JOIN agents a ON i.assignee_agent_id = a.id
    WHERE a.name ILIKE '%API Developer Jr%'
       OR a.name ILIKE '%Database Developer Jr%'
       OR a.name ILIKE '%Deployment Engineer Jr%'
       OR a.name ILIKE '%DevOps Engineer Jr%'
    ORDER BY i.priority DESC, i.issue_number
  `;

  console.log(`Agent Name                 | Status      | Priority | Issue # | Issue Title`);
  console.log(`---------------------------+-------------+----------+---------+--------------------------------------------------`);
  for (const row of issues) {
    console.log(`${row.agent_name.padEnd(25)} | ${row.status.padEnd(11)} | ${row.priority.padEnd(8)} | ${row.issue_number}     | ${row.title.substring(0, 55)}`);
  }

  console.log(`\nTotal issues assigned to Backend & Infrastructure juniors: ${issues.length}`);

  if (issues.length === 0) {
    console.log(`\n⚠️  All Backend & Infrastructure juniors are IDLE - need assignments!`);
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
