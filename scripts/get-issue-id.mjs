import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  const issueIdentifier = process.argv[2] || 'MAT-288';

  console.log(`\n=== ISSUE ID: ${issueIdentifier} ===\n`);

  const issue = await sql`SELECT id, title, status, priority FROM issues WHERE identifier = ${issueIdentifier}`;

  if (issue.length === 0) {
    console.log('Issue not found!');
    process.exit(1);
  }

  console.log(`ID: ${issue[0].id}`);
  console.log(`Title: ${issue[0].title}`);
  console.log(`Status: ${issue[0].status}, Priority: ${issue[0].priority}`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
