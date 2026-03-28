import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');
import { execSync } from 'child_process';

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const qaAgentNames = ['QA Tester Jr', 'Protocol Tester Jr', 'Performance Tester Jr', 'Regression Tester Jr', 'Accessibility Tester Jr'];

async function main() {
  console.log(`\n=== QA TEAM VELOCITY REPORT ===\n`);
  console.log(`Date: ${new Date().toISOString()}\n`);

  // Get PR velocity from GitHub
  console.log(`--- GITHUB PR VELOCITY (Today: 2026-03-28) ---\n`);

  try {
    const prsMergedToday = execSync('cd /Users/n1ur0/projects/DuckPools && ~/bin/gh pr list --state merged --limit 100 | grep "2026-03-28" | wc -l', { encoding: 'utf-8' }).trim();
    console.log(`Total PRs merged today: ${prsMergedToday}`);

    // Count PRs by QA team members
    const qaPRs = execSync('cd /Users/n1ur0/projects/DuckPools && ~/bin/gh pr list --state merged --limit 100 | grep -E "(Tester|Regression|Performance|Accessibility|qa|QA)" | grep "2026-03-28" | wc -l', { encoding: 'utf-8' }).trim();
    console.log(`PRs from QA team: ${qaPRs}\n`);
  } catch (e) {
    console.log(`Error getting PR info: ${e.message}\n`);
  }

  // Get team status from database
  console.log(`--- TEAM STATUS ---\n`);

  const qaAgents = await sql`
    SELECT id, name, status
    FROM agents
    WHERE name = ANY(${qaAgentNames})
    ORDER BY name
  `;

  for (const agent of qaAgents) {
    const statusIcon = agent.status === 'running' ? '🔄' : (agent.status === 'idle' ? '💤' : (agent.status === 'error' ? '⚡' : '?'));

    const activeIssues = await sql`
      SELECT COUNT(*) as count
      FROM issues
      WHERE assignee_agent_id = ${agent.id} AND status NOT IN ('completed', 'cancelled')
    `;

    const completedIssues = await sql`
      SELECT COUNT(*) as count
      FROM issues
      WHERE assignee_agent_id = ${agent.id} AND status = 'completed' AND completed_at::date = CURRENT_DATE
    `;

    console.log(`${statusIcon} ${agent.name} [${agent.status.toUpperCase()}]`);
    console.log(`   Active: ${activeIssues[0].count} | Completed today: ${completedIssues[0].count}`);
  }

  // Summary
  const totalAgents = qaAgents.length;
  const idleAgents = qaAgents.filter(a => a.status === 'idle').length;
  const runningAgents = qaAgents.filter(a => a.status === 'running').length;
  const errorAgents = qaAgents.filter(a => a.status === 'error').length;

  const allActiveIssues = await sql`
    SELECT COUNT(*) as count
    FROM issues i
    JOIN agents a ON i.assignee_agent_id = a.id
    WHERE a.name = ANY(${qaAgentNames}) AND i.status NOT IN ('completed', 'cancelled')
  `;

  const allCompletedToday = await sql`
    SELECT COUNT(*) as count
    FROM issues i
    JOIN agents a ON i.assignee_agent_id = a.id
    WHERE a.name = ANY(${qaAgentNames}) AND i.status = 'completed' AND i.completed_at::date = CURRENT_DATE
  `;

  console.log(`\n--- SUMMARY ---`);
  console.log(`Total juniors: ${totalAgents}`);
  console.log(`Idle: ${idleAgents} | Running: ${runningAgents} | Error: ${errorAgents}`);
  console.log(`Active issues: ${allActiveIssues[0].count}`);
  console.log(`Issues completed today: ${allCompletedToday[0].count}`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
