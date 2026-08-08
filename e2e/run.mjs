// e2e/run.mjs
// ============================================================================
// E2E owner-flow harness orchestrator.
//
// Lifecycle: seed a DISPOSABLE test DB from a fixture -> start the backend
// pointed at it -> prove the override took effect (cheap write, cleaned up)
// BEFORE the expensive flow -> run the flow -> ID-scoped cleanup -> drop the
// test DB. The real dev.db is never opened by the backend.
//
// Everything is env-configurable (no hardcoded DB path in the flow). Defaults
// target this dev machine; override E2E_PYTHON / E2E_EDGE on Linux/CI.
// ============================================================================
import { spawn, spawnSync } from "node:child_process";
import { rmSync, existsSync, mkdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { counts, copyFixture, recordDerivedIds, cleanupByIds, dropDb, dbId } from "./db.mjs";
import { runOwnerFlow } from "./owner-flow.mjs";

const REPO = resolve(import.meta.dirname, "..");
const BACKEND = join(REPO, "backend");
const env = (k, d) => process.env[k] ?? d;

const cfg = {
  devDb: resolve(env("E2E_FIXTURE", join(BACKEND, "dev.db"))),           // fixture source (never written)
  testDb: resolve(env("E2E_DB", join(BACKEND, "test-e2e.db"))),          // disposable target
  apiBase: env("E2E_API", "http://localhost:8000"),
  frontendBase: env("E2E_FRONTEND", "http://localhost:3000"),
  backendPort: Number(env("E2E_BACKEND_PORT", "8000")),
  cdpPort: Number(env("E2E_CDP_PORT", "9222")),
  python: env("E2E_PYTHON", join(REPO, ".venv", "Scripts", "python.exe")),
  edge: env("E2E_EDGE", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
  image: resolve(env("E2E_IMAGE", join(REPO, "ml/datasets/raw/images/images_normalized/1000_IM-0003-1001.dcm.png"))),
  patientId: env("E2E_PATIENT_ID", "eec21b1214814bae9850354f5f3a5327"),
  outDir: env("E2E_OUT", ""),
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(...a);

// --- Hard guard: refuse to run against the real dev.db ----------------------
if (cfg.testDb === cfg.devDb) {
  console.error(`FATAL: E2E_DB (${cfg.testDb}) is the fixture/dev DB. Refusing to run against real data.`);
  process.exit(2);
}

function killTree(pid) {
  if (!pid) return;
  if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
  else { try { process.kill(-pid, "SIGKILL"); } catch { try { process.kill(pid, "SIGKILL"); } catch {} } }
}

async function waitHealth(timeoutMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try { if ((await (await fetch(`${cfg.apiBase}/health`)).json()).status === "ok") return true; } catch {}
    await sleep(1500);
  }
  return false;
}

let backend, edge;
async function teardown() {
  killTree(backend?.pid);
  killTree(edge?.pid);
  await sleep(1500); // let the backend release the sqlite file
}

async function main() {
  if (cfg.outDir) mkdirSync(cfg.outDir, { recursive: true });
  log("=== config ===");
  log(`  test DB (disposable): ${cfg.testDb}`);
  log(`  fixture (read-only):  ${cfg.devDb}`);
  log(`  api=${cfg.apiBase} frontend=${cfg.frontendBase} backendPort=${cfg.backendPort} cdp=${cfg.cdpPort}`);

  const devBefore = counts(cfg.devDb);
  log(`  dev.db BEFORE: ${JSON.stringify(devBefore)}`);

  // 1. Seed disposable DB
  dropDb(cfg.testDb);
  copyFixture(cfg.devDb, cfg.testDb);
  log(`\n=== seeded test DB from fixture ===`);

  // 2. Start backend pointed at the disposable DB
  log(`=== starting backend on :${cfg.backendPort} (DATABASE_URL -> test DB) ===`);
  backend = spawn(cfg.python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(cfg.backendPort)], {
    cwd: BACKEND,
    env: { ...process.env, PYTHONPATH: REPO, DATABASE_URL: `sqlite:///${cfg.testDb}` },
    stdio: "ignore",
    detached: process.platform !== "win32",
  });
  if (!(await waitHealth(120000))) throw new Error("backend did not become healthy");
  log("backend healthy");

  // 3. PRE-FLIGHT: prove the DB override took effect before the expensive flow.
  //    Register a throwaway doctor, confirm it landed in test.db and NOT dev.db,
  //    then delete it (by id) from test.db.
  log("\n=== pre-flight: confirm backend writes to test DB, not dev.db ===");
  const pf = await fetch(`${cfg.apiBase}/auth/register`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: `e2e-preflight-${Date.now()}@example.test`, password: "e2epass12345", full_name: "E2E preflight" }),
  });
  const pfId = (await pf.json()).doctor?.id;
  const devAfterPf = counts(cfg.devDb);
  const testHasPf = counts(cfg.testDb).doctors === devBefore.doctors + 1;
  if (devAfterPf.doctors !== devBefore.doctors) {
    // Override FAILED and the write hit dev.db. Remove the stray immediately, abort.
    cleanupByIds(cfg.devDb, { doctorId: pfId });
    throw new Error("DB override FAILED: preflight write hit dev.db. Removed the stray doctor; aborting.");
  }
  if (!testHasPf) throw new Error("preflight write did not land in test.db");
  cleanupByIds(cfg.testDb, { doctorId: pfId });
  log(`  OK: preflight doctor landed in test.db, dev.db unchanged (${devAfterPf.doctors} doctors). Removed preflight doctor.`);

  // 4. Launch Edge (CDP) and run the owner flow
  log("\n=== launching Edge + running owner flow ===");
  const profile = join(REPO, "e2e", ".edge-profile");
  edge = spawn(cfg.edge, ["--headless=new", "--disable-gpu", `--remote-debugging-port=${cfg.cdpPort}`, `--user-data-dir=${profile}`, "--hide-scrollbars", "--window-size=1440,900", "about:blank"], { stdio: "ignore" });
  await sleep(3000);

  const { createdIds, results, issues } = await runOwnerFlow(cfg);
  log(`\n=== flow steps: ${JSON.stringify(results.steps)}`);
  log(`=== recorded created ids: ${JSON.stringify(createdIds)}`);
  log(`=== browser issues: console=${issues.console.length} exceptions=${issues.exceptions.length} http4xx5xx=${issues.http.length}`);

  // 5. Stop backend/edge BEFORE touching the DB (release sqlite locks)
  await teardown();

  // 6. Record the derived ids the driver created, then ID-scoped cleanup
  recordDerivedIds(cfg.testDb, createdIds);
  log(`\n=== full recorded id set (post-derivation): ${JSON.stringify(createdIds)}`);

  // delete recorded uploaded image files (by recorded path only)
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

  // 7. Drop the disposable DB
  dropDb(cfg.testDb);
  log(`\n=== dropped test DB (exists now: ${existsSync(cfg.testDb)}) ===`);

  // 8. Prove dev.db is untouched
  const devAfter = counts(cfg.devDb);
  const unchanged = JSON.stringify(devAfter) === JSON.stringify(devBefore);
  log(`\n=== dev.db AFTER: ${JSON.stringify(devAfter)}`);
  log(`=== dev.db UNCHANGED: ${unchanged ? "YES ✓" : "NO !!!"} ===`);

  process.exit(unchanged ? 0 : 1);
}

main().catch(async (e) => { console.error("FATAL:", e.message); await teardown(); dropDb(cfg.testDb); process.exit(1); });
