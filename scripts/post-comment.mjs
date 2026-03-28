import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  const issueIdentifier = process.argv[2] || 'MAT-288';
  const commentBody = process.argv[3];

  if (!commentBody) {
    console.log('Usage: node post-comment.mjs <issue_identifier> <comment_body>');
    console.log('Note: comment body will be URL-encoded');
    process.exit(1);
  }

  console.log(`\n=== POSTING COMMENT TO ${issueIdentifier} ===\n`);

  // Get issue ID
  const issue = await sql`SELECT id FROM issues WHERE identifier = ${issueIdentifier}`;

  if (issue.length === 0) {
    console.log('Issue not found!');
    process.exit(1);
  }

  const issueId = issue[0].id;

  // Get company ID
  const company = await sql`SELECT id FROM companies WHERE name = 'Matsuzaka'`;

  if (company.length === 0) {
    console.log('Company not found!');
    process.exit(1);
  }

  // Post comment
  await sql`
    INSERT INTO issue_comments (issue_id, company_id, body, created_at, updated_at)
    VALUES (${issueId}, ${company[0].id}, ${commentBody}, NOW(), NOW())
  `;

  console.log(`=> Comment posted successfully!`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
