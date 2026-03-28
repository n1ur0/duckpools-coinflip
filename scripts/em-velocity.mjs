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

async function main() {
  console.log(`\n=== PROTOCOL CORE - VELOCITY REPORT ===\n`);

  const reportDate = new Date().toISOString().slice(0, 10);
  console.log(`Date: ${reportDate}\n`);

  // Get completed issues in last 24h
  const yesterday = new Date(Date.now() - 24 * 3600 * 1000).toISOString();

  const completedIssues = await sql`
    SELECT
      i.identifier,
      i.title,
      i.priority,
      a.name as completed_by,
      i.completed_at
    FROM issues i
    LEFT JOIN agents a ON a.id = i.assignee_agent_id
    WHERE i.company_id = ${COMPANY_ID}
      AND i.completed_at >= ${yesterday}
      AND i.status = 'completed'
    ORDER BY i.completed_at DESC
  `;

  // Get active runs in last 24h
  const recentRuns = await sql`
    SELECT
      a.name,
      COUNT(*) as run_count,
      COUNT(*) FILTER (WHERE r.status = 'completed') as completed_runs,
      COUNT(*) FILTER (WHERE r.status = 'error') as error_runs
    FROM heartbeat_runs r
    JOIN agents a ON a.id = r.agent_id
    WHERE r.company_id = ${COMPANY_ID}
      AND a.name = ANY(${EM_JUNIOR_TEAM})
      AND r.started_at >= ${yesterday}
    GROUP BY a.name
    ORDER BY a.name
  `;

  // Current team status
  const teamStatus = await sql`
    SELECT
      a.name,
      a.status,
      COUNT(i.id) FILTER (WHERE i.status NOT IN ('completed', 'cancelled')) as active_issues
    FROM agents a
    LEFT JOIN issues i ON i.assignee_agent_id = a.id AND i.company_id = a.company_id
    WHERE a.company_id = ${COMPANY_ID}
      AND a.name = ANY(${EM_JUNIOR_TEAM})
    GROUP BY a.id, a.name, a.status
    ORDER BY a.name
  `;

  // Open PRs from juniors (we need to check GitHub but will approximate)
  const openJuniorRuns = await sql`
    SELECT
      a.name,
      i.identifier,
      i.title,
      i.started_at
    FROM issues i
    JOIN agents a ON a.id = i.assignee_agent_id
    WHERE i.company_id = ${COMPANY_ID}
      AND a.name = ANY(${EM_JUNIOR_TEAM})
      AND i.status IN ('in_progress', 'todo')
      AND i.started_at IS NOT NULL
    ORDER BY i.started_at DESC
    LIMIT 10
  `;

  // Output report
  console.log('TEAM STATUS:');
  console.log('---');
  const runningCount = teamStatus.filter(t => t.status !== 'idle').length;
  const idleCount = teamStatus.filter(t => t.status === 'idle').length;
  console.log(`Total: ${teamStatus.length} | Running: ${runningCount} | Idle: ${idleCount}\n`);

  console.log('COMPLETED ISSUES (last 24h):');
  console.log('---');
  if (completedIssues.length > 0) {
    for (const issue of completedIssues) {
      const time = issue.completed_at ? new Date(issue.completed_at).toISOString().slice(11, 19) : 'N/A';
      console.log(`[${issue.identifier || 'N/A'}] ${issue.title}`);
      console.log(`  By: ${issue.completed_by || 'N/A'} | Priority: ${issue.priority} | At: ${time}`);
    }
  } else {
    console.log('No completed issues in last 24h');
  }
  console.log('');

  console.log('RECENT RUNS (last 24h):');
  console.log('---');
  if (recentRuns.length > 0) {
    let totalRuns = 0;
    let totalCompleted = 0;
    let totalErrors = 0;
    for (const run of recentRuns) {
      console.log(`${run.name}: ${run.run_count} runs (${run.completed_runs} OK, ${run.error_runs} ERR)`);
      totalRuns += parseInt(run.run_count);
      totalCompleted += parseInt(run.completed_runs);
      totalErrors += parseInt(run.error_runs);
    }
    console.log('');
    console.log(`TOTAL: ${totalRuns} runs (${totalCompleted} OK, ${totalErrors} ERR)`);
  } else {
    console.log('No recent runs');
  }
  console.log('');

  console.log('IN-PROGRESS WORK:');
  console.log('---');
  if (openJuniorRuns.length > 0) {
    for (const work of openJuniorRuns) {
      const started = work.started_at ? new Date(work.started_at).toISOString().slice(11, 16) : 'N/A';
      console.log(`[${work.identifier || 'N/A'}] ${work.title}`);
      console.log(`  By: ${work.name} | Started: ${started}`);
    }
  } else {
    console.log('No in-progress work tracked');
  }
  console.log('');

  // Summary
  const totalActive = teamStatus.reduce((sum, t) => sum + parseInt(t.active_issues), 0);
  console.log('--- SUMMARY ---');
  console.log(`Issues completed: ${completedIssues.length}`);
  console.log(`Total runs: ${recentRuns.reduce((sum, r) => sum + parseInt(r.run_count), 0)}`);
  console.log(`Active issues: ${totalActive}`);
  console.log('');

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
