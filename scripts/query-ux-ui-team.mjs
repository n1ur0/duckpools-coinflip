import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const TEAM = 'UX/UI Design';

async function main() {
  console.log(`\nUX/UI Design Team - Assignments\n` + '='.repeat(80));

  // Get all agents in this team
  const agents = await sql`
    SELECT id, name, role, is_senior, is_active
    FROM agents
    WHERE team = ${TEAM}
    ORDER BY is_senior DESC, name
  `;

  if (agents.length === 0) {
    console.log('No agents found for team: ' + TEAM);
    await sql.end();
    return;
  }

  // Get current assignments
  const assignments = await sql`
    SELECT
      a.id as agent_id,
      a.name as agent_name,
      a.is_senior,
      i.number as issue_number,
      i.title as issue_title,
      i.state as issue_state,
      i.assignee_id,
      i.labels
    FROM agents a
    LEFT JOIN issues i ON i.assignee_id = a.id
    WHERE a.team = ${TEAM}
      AND (i.state IS NULL OR i.state = 'open')
    ORDER BY a.is_senior DESC, a.name
  `;

  // Group by agent
  const agentIssues = {};
  for (const a of agents) {
    agentIssues[a.id] = { agent: a, issues: [] };
  }

  for (const row of assignments) {
    if (row.issue_number) {
      agentIssues[row.agent_id].issues.push({
        number: row.issue_number,
        title: row.issue_title,
        state: row.issue_state
      });
    }
  }

  // Print assignments
  for (const [agentId, data] of Object.entries(agentIssues)) {
    const a = data.agent;
    const type = a.is_senior ? 'SENIOR' : 'JUNIOR';
    const status = a.is_active ? 'ACTIVE' : 'INACTIVE';

    console.log(`\n[${type}] ${a.name} (${status})`);
    console.log(`  ID: ${a.id}`);
    console.log(`  Role: ${a.role}`);

    if (data.issues.length > 0) {
      console.log(`  Assignments:`);
      for (const issue of data.issues) {
        console.log(`    - #${issue.number}: ${issue.title} (${issue.state})`);
      }
    } else {
      console.log(`  Assignments: NONE (idle)`);
    }
  }

  // Summary
  const idleJuniors = agents.filter(a => !a.is_senior && agentIssues[a.id].issues.length === 0);
  console.log(`\n${'='.repeat(80)}`);
  console.log(`Summary:`);
  console.log(`  Total agents: ${agents.length}`);
  console.log(`  Seniors: ${agents.filter(a => a.is_senior).length}`);
  console.log(`  Juniors: ${agents.filter(a => !a.is_senior).length}`);
  console.log(`  Idle juniors: ${idleJuniors.length}`);
  if (idleJuniors.length > 0) {
    console.log(`  Idle junior names: ${idleJuniors.map(a => a.name).join(', ')}`);
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
