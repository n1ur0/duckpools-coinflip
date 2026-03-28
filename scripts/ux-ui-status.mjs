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

  // Check issues table for assignments
  const tableExists = await sql`
    SELECT EXISTS (
      SELECT FROM information_schema.tables
      WHERE table_name = 'issues'
    )
  `;

  let assignments = {};
  if (tableExists[0].exists) {
    const issueAssignments = await sql`
      SELECT
        a.id as agent_id,
        a.name as agent_name,
        i.data->>'github_number' as issue_number,
        i.data->>'title' as issue_title,
        i.data->>'state' as issue_state,
        i.status as issue_status
      FROM agents a
      LEFT JOIN issue_assignments ia ON ia.agent_id = a.id
      LEFT JOIN issues i ON i.id = ia.issue_id
      WHERE a.name = ANY(${TEAM_MEMBERS})
      ORDER BY a.name
    `;

    for (const row of issueAssignments) {
      if (!assignments[row.agent_id]) {
        assignments[row.agent_id] = [];
      }
      if (row.issue_number) {
        assignments[row.agent_id].push({
          number: row.issue_number,
          title: row.issue_title,
          state: row.issue_state,
          status: row.issue_status
        });
      }
    }
  }

  // Print status for each agent
  const idleJuniors = [];

  for (const agent of agents) {
    const isSenior = agent.name.includes('Sr');
    const isJunior = agent.name.includes('Jr');
    const type = isSenior ? 'SENIOR' : 'JUNIOR';

    console.log(`\n[${type}] ${agent.name}`);
    console.log(`  ID: ${agent.id}`);
    console.log(`  Status: ${agent.status.toUpperCase()}`);
    console.log(`  Role: ${agent.role}`);

    const agentIssues = assignments[agent.id] || [];
    if (agentIssues.length > 0) {
      console.log(`  Assignments:`);
      for (const issue of agentIssues) {
        const statusStr = issue.status ? `(${issue.status})` : '';
        console.log(`    - #${issue.number}: ${issue.title} ${statusStr}`);
      }
    } else {
      console.log(`  Assignments: NONE`);
      if (isJunior) {
        idleJuniors.push(agent);
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
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
