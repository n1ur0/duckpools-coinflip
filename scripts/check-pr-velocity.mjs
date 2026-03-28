import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

async function main() {
  console.log(`\n=== PR VELOCITY (DeFi & Bankroll Team) ===\n`);

  // Get all pull requests in the last 7 days
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);

  const prs = await sql`
    SELECT
      pr.id,
      pr.pr_number,
      pr.title,
      pr.state,
      pr.status,
      pr.created_at,
      pr.updated_at,
      a.name as author_name,
      pr.review_status,
      pr.review_comments
    FROM pull_requests pr
    JOIN agents a ON pr.author_agent_id = a.id
    WHERE pr.created_at >= ${sevenDaysAgo}
      AND pr.state NOT IN ('closed', 'merged')
    ORDER BY pr.created_at DESC
  `;

  // Filter for my team's juniors
  const myJuniors = ['LP Contract Developer Jr', 'Yield Engineer Jr', 'Risk Analyst Jr', 'Risk Analyst Jr 2'];
  const teamPRs = prs.filter(pr => myJuniors.includes(pr.author_name));

  console.log(`Found ${teamPRs.length} open PRs from my juniors in the last 7 days:\n`);

  if (teamPRs.length === 0) {
    console.log('No open PRs from my juniors.');
  } else {
    for (const pr of teamPRs) {
      console.log(`#${pr.pr_number} - ${pr.title}`);
      console.log(`  Author: ${pr.author_name}`);
      console.log(`  State: ${pr.state}, Status: ${pr.status}`);
      console.log(`  Review Status: ${pr.review_status || 'None'}`);
      console.log(`  Created: ${pr.created_at}`);
      console.log(`  Updated: ${pr.updated_at}`);
      console.log();
    }
  }

  // Also check merged PRs in last 7 days
  const mergedPRs = await sql`
    SELECT
      pr.pr_number,
      pr.title,
      pr.merged_at,
      a.name as author_name
    FROM pull_requests pr
    JOIN agents a ON pr.author_agent_id = a.id
    WHERE pr.state = 'merged'
      AND pr.merged_at >= ${sevenDaysAgo}
      AND a.name = ANY(${myJuniors})
    ORDER BY pr.merged_at DESC
  `;

  console.log(`\n=== MERGED PRs (Last 7 Days) ===\n`);
  console.log(`${mergedPRs.length} PR(s) merged:\n`);

  for (const pr of mergedPRs) {
    console.log(`#${pr.pr_number} - ${pr.title}`);
    console.log(`  Author: ${pr.author_name}`);
    console.log(`  Merged: ${pr.merged_at}`);
    console.log();
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
