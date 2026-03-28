import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const qaAgentNames = ['QA Tester Jr', 'Protocol Tester Jr', 'Performance Tester Jr', 'Regression Tester Jr', 'Accessibility Tester Jr'];

async function main() {
  console.log(`\n=== QA TEAM SURVEY ===\n`);

  const qaAgents = await sql`
    SELECT id, name, status
    FROM agents
    WHERE name = ANY(${qaAgentNames})
    ORDER BY name
  `;

  console.log(`\nJUNIOR TEAM STATUS:\n\n`);

  for (const agent of qaAgents) {
    const statusIcon = agent.status === 'running' ? '🔄' : (agent.status === 'idle' ? '💤' : (agent.status === 'error' ? '⚡' : '?'));

    const activeIssues = await sql`
      SELECT id, title, status, priority
      FROM issues
      WHERE assignee_agent_id = ${agent.id} AND status NOT IN ('completed', 'cancelled')
      ORDER BY priority DESC, created_at ASC
    `;

    console.log(`${statusIcon} ${agent.name} [${agent.status.toUpperCase()}]`);
    console.log(`   Active issues: ${activeIssues.length}`);

    for (const issue of activeIssues) {
      const priorityIcon = issue.priority === 'critical' ? '🔴' : (issue.priority === 'high' ? '🟡' : '⚪');
      const started = issue.started_at ? `Started: ${Math.floor((new Date() - new Date(issue.started_at)) / 3600000)}h ago` : 'NOT STARTED';
      console.log(`   ${priorityIcon} [${issue.identifier || 'N/A'}] ${issue.title.substring(0, 60)}...`);
      console.log(`      Priority: ${issue.priority} | ${started}`);
    }
    console.log('');
  }

  // Summary
  const totalAgents = qaAgents.length;
  const idleAgents = qaAgents.filter(a => a.status === 'idle').length;
  const busyAgents = qaAgents.filter(a => a.status === 'running').length;
  const errorAgents = qaAgents.filter(a => a.status === 'error').length;

  const allActiveIssues = await sql`
    SELECT COUNT(*) as count
    FROM issues i
    JOIN agents a ON i.assignee_agent_id = a.id
    WHERE a.name = ANY(${qaAgentNames}) AND i.status NOT IN ('completed', 'cancelled')
  `;

  console.log(`--- SUMMARY ---`);
  console.log(`Total juniors: ${totalAgents}`);
  console.log(`Idle: ${idleAgents} | Running: ${busyAgents} | Error: ${errorAgents}`);
  console.log(`Active issues: ${allActiveIssues[0].count}`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
