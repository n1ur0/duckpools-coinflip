import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const postgres = require('postgres');

const DB_URL = process.env.DATABASE_URL || 'postgresql://paperclip:paperclip@127.0.0.1:54329/paperclip';
const sql = postgres(DB_URL);

const COMPANY_ID = 'c3a27363-6930-45ad-b684-a6116c0f3313';

function pad(s, len, right = false) {
  s = String(s);
  if (s.length >= len) return s.slice(0, len);
  return right ? s.padEnd(len) : s.padStart(len);
}

function rpad(s, len) { return pad(s, len, true); }
function lpad(s, len) { return pad(s, len, false); }

async function main() {
  const hours = parseInt(process.argv[2]) || 24;
  const since = new Date(Date.now() - hours * 3600 * 1000).toISOString();

  console.log(`Cost/Run Tracking — last ${hours}h (since ${since})\n`);

  const rows = await sql`
    SELECT
      a.name,
      r.status,
      COUNT(*) as run_count,
      SUM(EXTRACT(EPOCH FROM (r.finished_at - r.started_at))) as total_seconds,
      COUNT(*) FILTER (WHERE r.status = 'completed') as completed,
      COUNT(*) FILTER (WHERE r.status = 'error') as errors,
      COUNT(*) FILTER (WHERE r.status = 'running') as running,
      COUNT(*) FILTER (WHERE r.status NOT IN ('completed', 'error', 'running')) as other
    FROM heartbeat_runs r
    JOIN agents a ON a.id = r.agent_id
    WHERE r.company_id = ${COMPANY_ID}
      AND r.started_at >= ${since}
    GROUP BY a.name, r.status
    ORDER BY a.name, r.status
  `;

  if (rows.length === 0) {
    console.log('No runs found in the specified time window.');
    await sql.end();
    return;
  }

  // Aggregate by agent name
  const agents = {};
  for (const r of rows) {
    if (!agents[r.name]) {
      agents[r.name] = { runs: 0, seconds: 0, completed: 0, errors: 0, running: 0, other: 0 };
    }
    const a = agents[r.name];
    a.runs += parseInt(r.run_count);
    a.seconds += parseFloat(r.total_seconds) || 0;
    a.completed += parseInt(r.completed);
    a.errors += parseInt(r.errors);
    a.running += parseInt(r.running);
    a.other += parseInt(r.other);
  }

  // Format output
  const colAgent = 'AGENT';
  const colRuns = 'RUNS';
  const colDuration = 'DURATION';
  const colDone = 'OK';
  const colErr = 'ERR';
  const colRun = 'RUNNING';

  const wAgent = Math.max(colAgent.length, ...Object.keys(agents).map(n => n.length)) + 2;

  const header = `${rpad(colAgent, wAgent)} ${lpad(colRuns, 6)} ${lpad(colDuration, 10)} ${lpad(colDone, 6)} ${lpad(colErr, 6)} ${lpad(colRun, 7)}`;
  const sep = '-'.repeat(header.length);

  console.log(header);
  console.log(sep);

  let totalRuns = 0, totalSeconds = 0, totalOk = 0, totalErr = 0;

  for (const [name, data] of Object.entries(agents).sort()) {
    const mins = (data.seconds / 60).toFixed(1);
    const durStr = data.seconds >= 3600
      ? `${(data.seconds / 3600).toFixed(1)}h`
      : `${mins}m`;
    console.log(
      `${rpad(name, wAgent)} ${lpad(data.runs, 6)} ${lpad(durStr, 10)} ${lpad(data.completed, 6)} ${lpad(data.errors, 6)} ${lpad(data.running, 7)}`
    );
    totalRuns += data.runs;
    totalSeconds += data.seconds;
    totalOk += data.completed;
    totalErr += data.errors;
  }

  console.log(sep);
  const totalDur = totalSeconds >= 3600
    ? `${(totalSeconds / 3600).toFixed(1)}h`
    : `${(totalSeconds / 60).toFixed(1)}m`;
  console.log(
    `${rpad('TOTAL', wAgent)} ${lpad(totalRuns, 6)} ${lpad(totalDur, 10)} ${lpad(totalOk, 6)} ${lpad(totalErr, 6)} ${lpad('', 7)}`
  );

  // Error rate
  if (totalRuns > 0) {
    console.log(`\nError rate: ${((totalErr / totalRuns) * 100).toFixed(1)}%`);
  }

  await sql.end();
}

main().catch(e => { console.error(e.message); process.exit(1); });
