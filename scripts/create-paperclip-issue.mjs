import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  const title = process.argv[2];
  const description = process.argv[3] || '';
  const priority = process.argv[4] || 'medium';
  const agentId = process.argv[5];

  if (!title) {
    console.log('Usage: node create-paperclip-issue.mjs <title> [description] [priority] [agent_id]');
    console.log('Priorities: critical, high, medium, low');
    process.exit(1);
  }

  console.log(`\n=== CREATING ISSUE ===\n`);

  // Get company ID
  const company = await sql`SELECT id FROM companies WHERE name = 'Matsuzaka'`;
  if (company.length === 0) {
    console.log('Company not found!');
    process.exit(1);
  }

  // Create issue
  const result = await sql`
    INSERT INTO issues (company_id, title, description, priority, assignee_agent_id, status, created_at, updated_at)
    VALUES (${company[0].id}, ${title}, ${description}, ${priority}, ${agentId}, 'todo', NOW(), NOW())
    RETURNING id, issue_number
  `;

  console.log(`Title: ${title}`);
  console.log(`Priority: ${priority}`);
  console.log(`Assigned to: ${agentId || 'None'}`);
  console.log(`Status: todo`);
  console.log(`\n=> Issue created! Paperclip ID: ${result[0].id}, Issue Number: ${result[0].issue_number}`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
