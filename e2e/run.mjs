// e2e/run.mjs
// ============================================================================
// E2E owner-flow harness (proof of the disposable-DB + ID-scoped-cleanup path).
//
// seed disposable DB from fixture -> start backend on it -> pre-flight proves
// the DATABASE_URL override BEFORE the flow -> run owner flow -> ID-scoped
// cleanup -> drop the test DB. dev.db is never opened. Fails closed: E2E_DB
// must be set to a disposable path (see harness.assertSafeTarget).
// ============================================================================
import { rmSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { counts, copyFixture, recordDerivedIds, cleanupByIds, dropDb } from "./db.mjs";
import { runOwnerFlow } from "./owner-flow.mjs";
import { loadConfig, assertSafeTarget, killTree, startBackend, launchEdge, preflightOverride, BACKEND, sleep } from "./harness.mjs";

const cfg = loadConfig();
assertSafeTarget(cfg); // fail closed before anything runs
const log = (...a) => console.log(...a);

let backend, edge;
async function teardown() { killTree(backend?.pid); killTree(edge?.pid); await sleep(1500); }

async function main() {
  if (cfg.outDir) mkdirSync(cfg.outDir, { recursive: true });
  log("=== config ===");
  log(`  test DB (disposable): ${cfg.testDb}`);
  log(`  fixture (read-only):  ${cfg.devDb}`);

  const devBefore = counts(cfg.devDb);
  log(`  dev.db BEFORE: ${JSON.stringify(devBefore)}`);

  dropDb(cfg.testDb);
  copyFixture(cfg.devDb, cfg.testDb);
  log(`\n=== seeded test DB from fixture ===`);

  log(`=== starting backend on :${cfg.backendPort} (DATABASE_URL -> test DB) ===`);
  backend = await startBackend(cfg);
  log("backend healthy");

  log("\n=== pre-flight: confirm backend writes to test DB, not dev.db ===");
  await preflightOverride(cfg, devBefore);
  log(`  OK: preflight write landed in test.db, dev.db unchanged (${devBefore.doctors} doctors).`);

  log("\n=== launching Edge + running owner flow ===");
  edge = launchEdge(cfg);
  await sleep(3000);

  const { createdIds, results, issues } = await runOwnerFlow(cfg);
  log(`\n=== flow steps: ${JSON.stringify(results.steps)}`);
  log(`=== recorded created ids: ${JSON.stringify(createdIds)}`);
  log(`=== browser issues: console=${issues.console.length} exceptions=${issues.exceptions.length} http4xx5xx=${issues.http.length}`);

  await teardown(); // release sqlite locks before touching the DB

  recordDerivedIds(cfg.testDb, createdIds);
  log(`\n=== full recorded id set (post-derivation): ${JSON.stringify(createdIds)}`);

  let imgsRemoved = 0;
  for (const p of createdIds.imagePaths ?? []) {
    for (const cand of [p, join(BACKEND, p)]) { if (cand && existsSync(cand)) { rmSync(cand, { force: true }); imgsRemoved++; break; } }
  }

  const testBeforeCleanup = counts(cfg.testDb);
  const delReport = cleanupByIds(cfg.testDb, createdIds);
  const testAfterCleanup = counts(cfg.testDb);
  log(`\n=== ID-scoped cleanup (deletes only recorded ids) ===`);
  log(`  deletions: ${JSON.stringify(delReport)}`);
  log(`  image files removed: ${imgsRemoved}`);
  log(`  test.db counts  before cleanup: ${JSON.stringify(testBeforeCleanup)}`);
  log(`  test.db counts   after cleanup: ${JSON.stringify(testAfterCleanup)}`);

  dropDb(cfg.testDb);
  log(`\n=== dropped test DB (exists now: ${existsSync(cfg.testDb)}) ===`);

  const devAfter = counts(cfg.devDb);
  const unchanged = JSON.stringify(devAfter) === JSON.stringify(devBefore);
  log(`\n=== dev.db AFTER: ${JSON.stringify(devAfter)}`);
  log(`=== dev.db UNCHANGED: ${unchanged ? "YES ✓" : "NO !!!"} ===`);
  process.exit(unchanged ? 0 : 1);
}

main().catch(async (e) => { console.error("FATAL:", e.message); await teardown(); dropDb(cfg.testDb); process.exit(1); });
