import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

// UX/UI Design team members
const TEAM_MEMBERS = [
  'UX Researcher Sr',
  'Visual Designer Sr',
  'Interaction Designer Jr'
];

async function main() {
  console.log(`\nUX/UI Design Team Status`);
  console.log('='.repeat(80));

  // Get my team members
  const agents = await sql`
    SELECT id, name, role, status, capabilities
    FROM agents
    WHERE name = ANY(${TEAM_MEMBERS})
    ORDER BY name
  `;

  if (agents.length === 0) {
    console.log('\nNo agents found for UX/UI Design team');
    await sql.end();
    return;
  }

  console.log(`\nTeam Members: ${agents.length}`);
  console.log('-'.repeat(80));

  // Get assignments from issues table
  const assignments = await sql`
    SELECT
      a.id as agent_id,
      a.name as agent_name,
      i.id as issue_id,
      i.issue_number,
      i.identifier,
      i.title,
      i.status as issue_status,
      i.priority
    FROM agents a
    LEFT JOIN issues i ON i.assignee_agent_id = a.id AND i.status IN ('todo', 'in_progress', 'in_review', 'blocked')
    WHERE a.name = ANY(${TEAM_MEMBERS})
    ORDER BY a.name, i.priority DESC, i.issue_number
  `;

  // Group by agent
  const agentIssues = {};
  for (const a of agents) {
    agentIssues[a.id] = { agent: a, issues: [] };
  }

  for (const row of assignments) {
    if (row.title) {  // Check if issue exists, not just issue_number
      agentIssues[row.agent_id].issues.push({
        id: row.issue_id,
        number: row.issue_number,
        identifier: row.identifier,
        title: row.title,
        status: row.issue_status,
        priority: row.priority
      });
    }
  }

  // Print status for each agent
  const idleJuniors = [];

  for (const [agentId, data] of Object.entries(agentIssues)) {
    const a = data.agent;
    const isSenior = a.name.includes('Sr');
    const isJunior = a.name.includes('Jr');
    const type = isSenior ? 'SENIOR' : 'JUNIOR';

    console.log(`\n[${type}] ${a.name}`);
    console.log(`  ID: ${a.id}`);
    console.log(`  Status: ${a.status.toUpperCase()}`);
    console.log(`  Role: ${a.role}`);

    const agentIssues = data.issues;
    if (agentIssues.length > 0) {
      console.log(`  Assignments (${agentIssues.length}):`);
      for (const issue of agentIssues) {
        console.log(`    - [${issue.priority}] ${issue.identifier || '#' + issue.number}: ${issue.title}`);
        console.log(`      Status: ${issue.status}, ID: ${issue.id}`);
      }
    } else {
      console.log(`  Assignments: NONE`);
      if (isJunior) {
        idleJuniors.push(a);
      }
    }
  }

  // Summary
  console.log(`\n${'='.repeat(80)}`);
  console.log(`Summary:`);
  console.log(`  Total agents: ${agents.length}`);
  console.log(`  Seniors: ${agents.filter(a => a.name.includes('Sr')).length}`);
  console.log(`  Juniors: ${agents.filter(a => a.name.includes('Jr')).length}`);
  console.log(`  Idle juniors: ${idleJuniors.length}`);
  if (idleJuniors.length > 0) {
    console.log(`  Idle junior names: ${idleJuniors.map(a => a.name).join(', ')}`);
    console.log(`  Idle junior IDs: ${idleJuniors.map(a => a.id).join(', ')}`);
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
