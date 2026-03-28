import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\nSearching for GitHub issue mappings...\n`);

  // Search for issues that might map to GitHub design issues
  const githubRelated = await sql`
    SELECT
      i.id,
      i.issue_number,
      i.identifier,
      i.title,
      i.status,
      i.priority,
      i.assignee_agent_id,
      a.name as assignee_name,
      i.origin_kind,
      i.origin_id
    FROM issues i
    LEFT JOIN agents a ON a.id = i.assignee_agent_id
    WHERE i.company_id = (
      SELECT id FROM companies WHERE name = 'Matsuzaka' LIMIT 1
    )
    AND (i.origin_kind = 'github' OR i.title ILIKE '%color%' OR i.title ILIKE '%style%' OR i.title ILIKE '%CSS%')
    ORDER BY i.issue_number
  `;

  if (githubRelated.length === 0) {
    console.log('No GitHub-related issues found');
  } else {
    console.log(`Found ${githubRelated.length} potentially GitHub-related issues:\n`);
    for (const issue of githubRelated) {
      console.log(`  ${issue.identifier || '#' + issue.issue_number} - ${issue.title}`);
      console.log(`    ID: ${issue.id}, Origin: ${issue.origin_kind}, Origin ID: ${issue.origin_id}`);
      console.log(`    Status: ${issue.status}, Priority: ${issue.priority}`);
      console.log(`    Assignee: ${issue.assignee_name || 'NONE'}`);
      console.log();
    }
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
