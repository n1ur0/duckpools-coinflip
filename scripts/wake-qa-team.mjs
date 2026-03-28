import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');
import { execSync } from 'child_process';

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:***@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const qaAgentNames = ['QA Tester Jr', 'Protocol Tester Jr', 'Performance Tester Jr', 'Regression Tester Jr', 'Accessibility Tester Jr'];

async function main() {
  console.log(`\n=== WAKING UP QA TEAM ===\n`);

  const qaAgents = await sql`
    SELECT id, name, status
    FROM agents
    WHERE name = ANY(${qaAgentNames}) AND status = 'error'
    ORDER BY name
  `;

  for (const agent of qaAgents) {
    console.log(`\nWaking up ${agent.name} (ID: ${agent.id})...`);

    try {
      const response = execSync(`curl -s -X POST "http://127.0.0.1:3100/api/agents/${agent.id}/wakeup" -H "Content-Type: application/json" -d '{"source":"automation","triggerDetail":"system","reason":"QA EM checking on error status agents"}'`, { encoding: 'utf-8' });
      console.log(`Response: ${response}`);
    } catch (e) {
      console.log(`Error waking up ${agent.name}: ${e.message}`);
    }
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
