import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');
const { execSync } = require('child_process');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const COMPANY_ID = 'c3a27363-6930-45ad-b684-a6116c0f3313';
const DEFI_BANKROLL_TEAM = [
  'LP Contract Developer Jr',
  'Yield Engineer Jr',
  'Risk Analyst Jr',
  'Risk Analyst Jr 2'
];

async function main() {
  console.log(`\n=== DEFI & BANKROLL - VELOCITY REPORT ===\n`);

  // Get junior agents with their IDs
  const agents = await sql`
    SELECT a.id, a.name
    FROM agents a
    WHERE a.company_id = ${COMPANY_ID}
      AND a.name = ANY(${DEFI_BANKROLL_TEAM})
    ORDER BY a.name
  `;

  const agentIds = agents.map(a => a.id);
  const agentIdMap = Object.fromEntries(agents.map(a => [a.id, a.name]));

  // Get PR work products from last 7 days
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);

  const prs = await sql`
    SELECT
      wp.id,
      wp.external_id as pr_number,
      wp.title,
      wp.status,
      wp.review_state,
      wp.created_at,
      wp.updated_at,
      wp.issue_id
    FROM issue_work_products wp
    WHERE wp.company_id = ${COMPANY_ID}
      AND wp.type = 'pr'
      AND wp.provider = 'github'
      AND wp.created_at >= ${sevenDaysAgo}
    ORDER BY wp.created_at DESC
  `;

  // Filter for PRs created by our team (via issue assignments)
  const teamPRs = [];
  for (const pr of prs) {
    // Get the issue this PR is linked to
    const issue = await sql`
      SELECT i.identifier, i.title as issue_title, i.assignee_agent_id
      FROM issues i
      WHERE i.id = ${pr.issue_id}
    `;
    
    if (issue.length > 0 && agentIds.includes(issue[0].assignee_agent_id)) {
      teamPRs.push({
        ...pr,
        identifier: issue[0].identifier,
        issue_title: issue[0].issue_title,
        agent_name: agentIdMap[issue[0].assignee_agent_id]
      });
    }
  }

  console.log(`PRs from DeFi & Bankroll team (last 7 days):\n`);

  if (teamPRs.length === 0) {
    console.log('No PRs found.\n');
  } else {
    for (const pr of teamPRs) {
      const reviewStatus = pr.review_state === 'approved' ? '✅ APPROVED' :
                          pr.review_state === 'changes_requested' ? '🔴 CHANGES REQUESTED' :
                          pr.review_state === 'reviewed' ? '👀 REVIEWED' :
                          '⏳ PENDING REVIEW';
      
      const prStatus = pr.status === 'merged' ? '🟢 MERGED' :
                       pr.status === 'closed' ? '⚫ CLOSED' :
                       '🔵 OPEN';
      
      console.log(`${prStatus} #${pr.pr_number} - ${pr.title}`);
      console.log(`   Issue: ${pr.identifier || 'N/A'}: ${pr.issue_title}`);
      console.log(`   Author: ${pr.agent_name}`);
      console.log(`   Review: ${reviewStatus}`);
      console.log(`   Created: ${pr.created_at.toLocaleString()}`);
      console.log('');
    }
  }

  // Summary
  const openPRs = teamPRs.filter(pr => pr.status === 'open');
  const mergedPRs = teamPRs.filter(pr => pr.status === 'merged');
  const changesRequested = teamPRs.filter(pr => pr.review_state === 'changes_requested');
  const pendingReview = teamPRs.filter(pr => pr.status === 'open' && (!pr.review_state || pr.review_state === 'pending'));

  console.log('=== SUMMARY ===\n');
  console.log(`Total PRs (7 days): ${teamPRs.length}`);
  console.log(`Open PRs: ${openPRs.length}`);
  console.log(`Merged PRs: ${mergedPRs.length}`);
  console.log(`Changes Requested: ${changesRequested.length}`);
  console.log(`Pending Review: ${pendingReview.length}`);

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
