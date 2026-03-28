import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const COMPANY_ID = 'c3a27363-6930-45ad-b684-a6116c0f3313';

function pad(s, len, right = false) {
  s = String(s);
  if (s.length >= len) return s.slice(0, len);
  return right ? s.padEnd(len) : s.padStart(len);
}

function rpad(s, len) { return pad(s, len, true); }
function lpad(s, len) { return pad(s, len, false); }

async function main() {
  console.log(`\n=== PROTOCOL CORE - BACKLOG ===\n`);

  // Get all backlog issues (no assignee or in backlog status)
  const backlog = await sql`
    SELECT
      i.id,
      i.identifier,
      i.title,
      i.status,
      i.priority,
      a.name as assigned_to,
      i.created_at
    FROM issues i
    LEFT JOIN agents a ON a.id = i.assignee_agent_id
    WHERE i.company_id = ${COMPANY_ID}
      AND i.status NOT IN ('completed', 'cancelled')
      AND (i.assignee_agent_id IS NULL OR i.status = 'backlog')
    ORDER BY
      CASE i.priority
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
      END,
      i.created_at ASC
  `;

  if (backlog.length === 0) {
    console.log('No backlog issues found.\n');
    await sql.end();
    return;
  }

  console.log(`BACKLOG ISSUES:\n`);

  const priorityEmoji = {
    'high': '🔴',
    'medium': '🟡',
    'low': '🟢'
  };

  for (const issue of backlog) {
    const emoji = priorityEmoji[issue.priority] || '⚪';
    const assigned = issue.assigned_to || 'UNASSIGNED';
    const created = new Date(issue.created_at).toISOString().slice(0, 10);

    console.log(`${emoji} [${issue.identifier || 'N/A'}] ${issue.status.toUpperCase()}`);
    console.log(`   Title: ${issue.title}`);
    console.log(`   Priority: ${issue.priority} | Created: ${created} | Assigned: ${assigned}`);
    console.log('');
  }

  // Summary
  const highPriority = backlog.filter(i => i.priority === 'high').length;
  const mediumPriority = backlog.filter(i => i.priority === 'medium').length;
  const lowPriority = backlog.filter(i => i.priority === 'low').length;
  const unassigned = backlog.filter(i => !i.assigned_to).length;

  console.log(`--- SUMMARY ---`);
  console.log(`Total backlog: ${backlog.length}`);
  console.log(`High: ${highPriority} | Medium: ${mediumPriority} | Low: ${lowPriority}`);
  console.log(`Unassigned: ${unassigned}\n`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
