import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  const issueIdentifier = 'MAT-288';

  console.log(`\n=== ISSUE: ${issueIdentifier} ===\n`);

  // Get issue
  const issue = await sql`SELECT * FROM issues WHERE identifier = ${issueIdentifier}`;

  if (issue.length === 0) {
    console.log('Issue not found!');
    process.exit(1);
  }

  const i = issue[0];
  console.log(`Title: ${i.title}`);
  console.log(`Status: ${i.status}, Priority: ${i.priority}`);
  console.log(`Description:`);
  console.log(`  ${i.description || 'No description'}`);

  // Get comments
  const comments = await sql`
    SELECT
      c.id,
      c.content,
      c.created_at,
      a.name as author_name
    FROM issue_comments c
    LEFT JOIN agents a ON c.author_agent_id = a.id
    WHERE c.issue_id = ${i.id}
    ORDER BY c.created_at ASC
  `;

  console.log(`\nComments: ${comments.length}\n`);

  for (const comment of comments) {
    console.log(`[${comment.created_at}] ${comment.author_name || 'Unknown'}:`);
    console.log(`  ${comment.content}`);
    console.log();
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
