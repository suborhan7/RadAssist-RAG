// e2e/db.mjs
// ============================================================================
// Disposable-DB + ID-scoped-cleanup layer for the E2E harness.
//
// SAFETY CONTRACT (Task 5a): nothing in this file may delete a row the driver
// did not itself create. Every DELETE below is keyed on an id that the run
// recorded (a report it generated, a session/doctor it registered, a
// comparison whose id it captured). There is deliberately NO date-based,
// name/email-based, "created today", or any other predicate deletion path.
// A predicate that matches other people's rows is what nearly destroyed a real
// account on the prior run; it does not exist here.
// ============================================================================
import { copyFileSync, existsSync, rmSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";

const COUNT_TABLES = ["doctors", "reports", "retrieval_sessions", "comparisons"];

/** Normalize an API uuid ("aaaa-bbbb-...") to the hyphenless form SQLAlchemy stores in SQLite. */
export const dbId = (id) => (id ? String(id).replace(/-/g, "") : id);

/** Seed a disposable DB from a fixture snapshot (a copy of an existing DB). */
export function copyFixture(fixture, dest) {
  if (!existsSync(fixture)) throw new Error(`fixture not found: ${fixture}`);
  copyFileSync(fixture, dest);
}

/** Row counts for the tables the E2E touches (read-only). */
export function counts(dbPath) {
  const db = new DatabaseSync(dbPath, { readOnly: true });
  const out = {};
  for (const t of COUNT_TABLES) out[t] = db.prepare(`SELECT count(*) c FROM ${t}`).get().c;
  db.close();
  return out;
}

/**
 * Record the ids the run created but did not directly observe from the UI:
 * the sessionId behind its report, the comparison ids its doctor produced, and
 * the uploaded image file path(s). These SELECTs are scoped to ids the driver
 * already holds (its own report / its own doctor), so they can only ever
 * surface rows the driver created. They RECORD; they never delete.
 */
export function recordDerivedIds(dbPath, ids) {
  const db = new DatabaseSync(dbPath, { readOnly: true });
  const rid = dbId(ids.reportId);
  const did = dbId(ids.doctorId);
  if (rid && !ids.sessionId) {
    const r = db.prepare("SELECT session_id FROM reports WHERE id = ?").get(rid);
    if (r) ids.sessionId = r.session_id;
  }
  if (did) {
    ids.comparisonIds = db.prepare("SELECT id FROM comparisons WHERE doctor_id = ?").all(did).map((r) => r.id);
  }
  if (ids.sessionId) {
    const s = db.prepare("SELECT query_image_path FROM retrieval_sessions WHERE id = ?").get(ids.sessionId);
    if (s?.query_image_path) ids.imagePaths = [s.query_image_path];
  }
  db.close();
  return ids;
}

/**
 * Delete EXACTLY the recorded ids. Returns a per-table changed-row report so
 * the caller can prove what was (and was not) removed. FK-safe order.
 */
export function cleanupByIds(dbPath, ids) {
  const db = new DatabaseSync(dbPath);
  const rid = dbId(ids.reportId);
  const sid = ids.sessionId;
  const did = dbId(ids.doctorId);
  const del = (sql, params) => db.prepare(sql).run(...params).changes;
  const report = {};

  if (rid) {
    report.report_audit_log = del("DELETE FROM report_audit_log WHERE report_id = ?", [rid]);
    report.explanations = del("DELETE FROM explanations WHERE report_id = ?", [rid]);
  }
  if (ids.comparisonIds?.length) {
    const ph = ids.comparisonIds.map(() => "?").join(",");
    report.comparisons = del(`DELETE FROM comparisons WHERE id IN (${ph})`, ids.comparisonIds);
  }
  if (rid) report.reports = del("DELETE FROM reports WHERE id = ?", [rid]);
  if (sid) {
    report.retrieved_evidence = del("DELETE FROM retrieved_evidence WHERE session_id = ?", [sid]);
    report.retrieval_sessions = del("DELETE FROM retrieval_sessions WHERE id = ?", [sid]);
  }
  if (did) report.doctors = del("DELETE FROM doctors WHERE id = ?", [did]);

  db.close();
  return report;
}

/** Remove the disposable DB and its WAL/SHM sidecars. */
export function dropDb(dbPath) {
  for (const p of [dbPath, `${dbPath}-wal`, `${dbPath}-shm`]) {
    if (existsSync(p)) rmSync(p, { force: true });
  }
}
