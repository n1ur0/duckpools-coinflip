import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const myJuniors = [
  'API Developer Jr',
  'Database Developer Jr',
  'Deployment Engineer Jr',
  'DevOps Engineer Jr'
];

async function main() {
  console.log(`\n${'='.repeat(80)}`);
  console.log(`BACKEND & INFRASTRUCTURE EM - SPRINT VELOCITY REPORT`);
  console.log(`Date: ${new Date().toISOString().split('T')[0]}`);
  console.log(`Time: ${new Date().toISOString().split('T')[1].split('.')[0]} UTC`);
  console.log(`${'='.repeat(80)}\n`);

  // Get all junior assignments
  const assignments = await sql`
    SELECT
      a.name as agent_name,
      a.status as agent_status,
      i.id as issue_id,
      i.issue_number as issue_num,
      i.title as issue_title,
      i.status as issue_status,
      i.priority as issue_priority,
      i.started_at,
      i.completed_at
    FROM agents a
    LEFT JOIN issues i ON a.id = i.assignee_agent_id
    WHERE a.name = ANY(${myJuniors})
    ORDER BY a.name, i.priority DESC, i.issue_number
  `;

  // Group by agent
  const byAgent = {};
  for (const row of assignments) {
    if (!byAgent[row.agent_name]) {
      byAgent[row.agent_name] = {
        status: row.agent_status,
        issues: []
      };
    }
    if (row.issue_id) {
      byAgent[row.agent_name].issues.push(row);
    }
  }

  // Print agent status
  console.log(`## JUNIOR TEAM STATUS\n`);
  for (const [agentName, data] of Object.entries(byAgent)) {
    const statusIcon = data.status === 'running' ? '🟢' : data.status === 'idle' ? '🔴' : '⚠️';
    const activeIssues = data.issues.filter(i => i.issue_status === 'in_progress').length;
    const todoIssues = data.issues.filter(i => i.issue_status === 'todo').length;
    const doneIssues = data.issues.filter(i => i.issue_status === 'done').length;

    console.log(`${statusIcon} ${agentName}`);
    console.log(`   Status: ${data.status.toUpperCase()}`);
    console.log(`   Issues: ${data.issues.length} total (in_progress: ${activeIssues}, todo: ${todoIssues}, done: ${doneIssues})`);

    // Show high priority issues
    const highPriority = data.issues.filter(i => i.issue_priority === 'high' || i.issue_priority === 'critical');
    if (highPriority.length > 0) {
      console.log(`   ⚡ HIGH PRIORITY:`);
      for (const issue of highPriority) {
        const statusIcon2 = issue.issue_status === 'done' ? '✅' : issue.issue_status === 'in_progress' ? '🔨' : '📋';
        console.log(`      ${statusIcon2} [${issue.issue_status}] ${issue.issue_title.substring(0, 60)}`);
      }
    }
    console.log('');
  }

  // Calculate velocity
  const allIssues = assignments.filter(r => r.issue_id);
  const doneThisWeek = allIssues.filter(i => {
    if (!i.completed_at) return false;
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    return new Date(i.completed_at) > weekAgo;
  });

  const inProgress = allIssues.filter(i => i.issue_status === 'in_progress');
  const todo = allIssues.filter(i => i.issue_status === 'todo');

  console.log(`\n## VELOCITY METRICS (Last 7 Days)\n`);
  console.log(`Issues Completed: ${doneThisWeek.length}`);
  console.log(`In Progress: ${inProgress.length}`);
  console.log(`Pending (Todo): ${todo.length}`);
  console.log(`Total Assigned: ${allIssues.length}`);

  const completionRate = allIssues.length > 0 ? ((doneThisWeek.length / allIssues.length) * 100).toFixed(1) : 0;
  console.log(`Completion Rate: ${completionRate}%`);

  // Critical items
  console.log(`\n## CRITICAL BLOCKERS\n`);
  const critical = allIssues.filter(i => i.issue_priority === 'critical');
  if (critical.length > 0) {
    for (const issue of critical) {
      console.log(`🚨 ${issue.issue_title}`);
      console.log(`   Agent: ${issue.agent_name} | Status: ${issue.issue_status}`);
    }
  } else {
    console.log(`✅ No critical blockers`);
  }

  // Idle agents with high-priority work
  console.log(`\n## ACTION ITEMS\n`);
  for (const [agentName, data] of Object.entries(byAgent)) {
    if (data.status === 'idle') {
      const highPriority = data.issues.filter(i => i.issue_priority === 'high' || i.issue_priority === 'critical' && i.issue_status === 'todo');
      if (highPriority.length > 0) {
        console.log(`⚠️ ${agentName} is IDLE with ${highPriority.length} high-priority tasks`);
      }
    }
  }

  console.log(`\n${'='.repeat(80)}\n`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
