import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\nSearching for design issues in database...\n`);

  // Search for design-related issues
  const designIssues = await sql`
    SELECT
      i.id,
      i.issue_number,
      i.identifier,
      i.title,
      i.status,
      i.priority,
      i.assignee_agent_id,
      a.name as assignee_name,
      i.description
    FROM issues i
    LEFT JOIN agents a ON a.id = i.assignee_agent_id
    WHERE i.company_id = (
      SELECT id FROM companies WHERE name = 'Matsuzaka' LIMIT 1
    )
    AND (i.title ILIKE '%DESIGN%' OR i.title ILIKE '%UX%' OR i.title ILIKE '%UI%')
    ORDER BY i.issue_number
  `;

  if (designIssues.length === 0) {
    console.log('No design issues found');
  } else {
    console.log(`Found ${designIssues.length} design issues:\n`);
    for (const issue of designIssues) {
      console.log(`  #${issue.issue_number}: ${issue.identifier || 'NO ID'} - ${issue.title}`);
      console.log(`    ID: ${issue.id}`);
      console.log(`    Status: ${issue.status}, Priority: ${issue.priority}`);
      console.log(`    Assignee: ${issue.assignee_name || 'NONE'}`);
      console.log(`    Assignee ID: ${issue.assignee_agent_id || 'NONE'}`);
      console.log(`    Description: ${issue.description?.substring(0, 100)}...`);
      console.log();
    }
  }

  // Also search for FEAT issues (game components)
  console.log(`\nSearching for game component issues (FEAT)...\n`);
  const featIssues = await sql`
    SELECT
      i.id,
      i.issue_number,
      i.identifier,
      i.title,
      i.status,
      i.priority,
      i.assignee_agent_id,
      a.name as assignee_name
    FROM issues i
    LEFT JOIN agents a ON a.id = i.assignee_agent_id
    WHERE i.company_id = (
      SELECT id FROM companies WHERE name = 'Matsuzaka' LIMIT 1
    )
    AND i.title ILIKE '%FEAT%'
    ORDER BY i.issue_number
  `;

  if (featIssues.length === 0) {
    console.log('No FEAT issues found');
  } else {
    console.log(`Found ${featIssues.length} FEAT issues:\n`);
    for (const issue of featIssues) {
      console.log(`  #${issue.issue_number}: ${issue.identifier || 'NO ID'} - ${issue.title}`);
      console.log(`    ID: ${issue.id}`);
      console.log(`    Status: ${issue.status}, Priority: ${issue.priority}`);
      console.log(`    Assignee: ${issue.assignee_name || 'NONE'}`);
      console.log();
    }
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
