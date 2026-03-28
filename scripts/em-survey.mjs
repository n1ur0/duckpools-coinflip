import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const COMPANY_ID = 'c3a27363-6930-45ad-b684-a6116c0f3313';
const EM_JUNIOR_TEAM = [
  'Contract Auditor Jr',
  'Serialization Specialist Jr',
  'Oracle Engineer Jr',
  'Oracle Engineer Jr 2',
  'SDK Developer Jr',
  'DevOps Engineer Jr'
];

function pad(s, len, right = false) {
  s = String(s);
  if (s.length >= len) return s.slice(0, len);
  return right ? s.padEnd(len) : s.padStart(len);
}

function rpad(s, len) { return pad(s, len, true); }
function lpad(s, len) { return pad(s, len, false); }

async function main() {
  console.log(`\n=== PROTOCOL CORE - EM SURVEY ===\n`);

  // Get all junior agents with their assigned issues
  const agents = await sql`
    SELECT
      a.id,
      a.name,
      a.status as agent_status,
      a.title,
      COUNT(i.id) FILTER (WHERE i.status NOT IN ('completed', 'cancelled')) as active_issues
    FROM agents a
    LEFT JOIN issues i ON i.assignee_agent_id = a.id AND i.company_id = a.company_id
    WHERE a.company_id = ${COMPANY_ID}
      AND a.name = ANY(${EM_JUNIOR_TEAM})
    GROUP BY a.id, a.name, a.status, a.title
    ORDER BY a.name
  `;

  if (agents.length === 0) {
    console.log('No junior agents found.\n');
    await sql.end();
    return;
  }

  console.log(`JUNIOR TEAM STATUS:\n`);

  // Get detailed assignment info for each junior
  for (const agent of agents) {
    const agent_issues = await sql`
      SELECT
        i.id,
        i.identifier,
        i.title,
        i.status,
        i.priority,
        i.started_at
      FROM issues i
      WHERE i.company_id = ${COMPANY_ID}
        AND i.assignee_agent_id = ${agent.id}
        AND i.status NOT IN ('completed', 'cancelled')
      ORDER BY i.priority DESC, i.created_at ASC
    `;

    const statusEmoji = agent.agent_status === 'idle' ? '💤' : '⚡';
    const statusText = agent.agent_status.toUpperCase();

    console.log(`${statusEmoji} ${agent.name} [${statusText}] - ${agent.title || 'No title'}`);
    console.log(`   Active issues: ${agent.active_issues}`);

    if (agent_issues.length > 0) {
      for (const issue of agent_issues) {
        const priorityEmoji = {
          'high': '🔴',
          'medium': '🟡',
          'low': '🟢'
        }[issue.priority] || '⚪';

        const started = issue.started_at ? new Date(issue.started_at).toISOString().slice(11, 19) : 'NOT STARTED';
        console.log(`   ${priorityEmoji} [${issue.identifier || 'N/A'}] ${issue.status.toUpperCase()}: ${issue.title}`);
        console.log(`      Priority: ${issue.priority} | Started: ${started}`);
      }
    } else {
      console.log(`   🔔 IDLE - Available for assignment`);
    }
    console.log('');
  }

  // Summary stats
  const idleCount = agents.filter(a => a.agent_status === 'idle').length;
  const busyCount = agents.filter(a => a.agent_status !== 'idle').length;
  const totalActiveIssues = agents.reduce((sum, a) => sum + parseInt(a.active_issues), 0);

  console.log(`--- SUMMARY ---`);
  console.log(`Total juniors: ${agents.length}`);
  console.log(`Idle: ${idleCount} | Busy: ${busyCount}`);
  console.log(`Active issues: ${totalActiveIssues}\n`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
