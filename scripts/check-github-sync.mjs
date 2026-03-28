import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\n=== PAPERCLIP ISSUES WITH GITHUB REFERENCES ===\n`);

  const issues = await sql`
    SELECT
      i.id,
      i.issue_number,
      i.title,
      i.status,
      i.priority,
      i.identifier,
      a.name as agent_name
    FROM issues i
    LEFT JOIN agents a ON i.assignee_agent_id = a.id
    WHERE (a.name ILIKE '%API Developer Jr%'
       OR a.name ILIKE '%Database Developer Jr%'
       OR a.name ILIKE '%Deployment Engineer Jr%'
       OR a.name ILIKE '%DevOps Engineer Jr%')
      AND i.identifier IS NOT NULL
    ORDER BY i.priority DESC, i.issue_number
    LIMIT 20
  `;

  console.log(`Agent Name                 | Priority | Issue # | Identifier | Title`);
  console.log(`---------------------------+----------+---------+------------+--------------------------------------------------`);
  for (const row of issues) {
    console.log(`${row.agent_name.padEnd(25)} | ${row.priority.padEnd(8)} | ${String(row.issue_number).padEnd(7)} | ${String(row.identifier || 'N/A').padEnd(10)} | ${row.title.substring(0, 50)}`);
  }

  console.log(`\nTotal synced issues: ${issues.length}`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
