"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  getCurrentDoctor,
  getHealth,
  getSystemStats,
  updateProfile,
} from "@/lib/api-client";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ServiceChip } from "@/components/ui/chip";
import type { paths } from "@/lib/generated/api";

type CurrentDoctorResponse =
  paths["/auth/me"]["get"]["responses"][200]["content"]["application/json"];
type SystemStatsResponse =
  paths["/system/stats"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Settings/Profile (Phase 16, scoped to Profile only per explicit user
 * decision -- the standalone Studies registry and access-log table/UI
 * remain deferred, each its own future phase/gate).
 *
 * Profile: identity + BMDC number. Copy is deliberately "Recorded as
 * entered. This system has no access to the BMDC registry and cannot
 * verify it." -- design_specification.md §8.16's own honesty
 * requirement, not softened into implying a real check happens.
 *
 * The "live signature preview" (§8.16: "showing exactly how the block
 * appears on a finalised report") is adapted, not built as specified --
 * no report is ever finalised in this system (Phase 13a's documented
 * finalize/edit/regenerate gap), so this renders a static preview of
 * name + BMDC number only, explicitly labelled as a preview, not tied to
 * any real report.
 *
 * Workspace: five per-doctor defaults (K, language, questionnaire-skip,
 * rail state, export format), persisted via PATCH /auth/me onto the
 * doctors table directly (explicit decision: not a separate
 * doctor_preferences table). Not yet wired: nothing else in this app
 * reads these defaults back (e.g. the upload flow does not yet
 * pre-fill K from default_top_k) -- that consumption is a separate,
 * not-yet-requested task, stated here rather than left as a silent
 * inconsistency. "Thresholds shown read-only" (§8.16) is not built --
 * no real backend-configured similarity threshold exists to show
 * honestly (Phase 14's Strong/Mixed/Weak cutoffs are a client-side
 * display convenience, not a system-configured value).
 *
 * System: masked-image count (real directory count) and index size
 * (real chromadb .count()) via GET /system/stats. Service health
 * deliberately reuses GET /health only -- no new Ollama/ChromaDB
 * reachability checks, per explicit user decision (that would be new
 * backend scope beyond Settings/Profile).
 */
export default function SettingsPage() {
  const [doctor, setDoctor] = useState<CurrentDoctorResponse | null>(null);
  const [stats, setStats] = useState<SystemStatsResponse | null>(null);
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "unreachable">(
    "checking",
  );
  const [loadError, setLoadError] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [bmdcNumber, setBmdcNumber] = useState("");
  const [defaultTopK, setDefaultTopK] = useState("");
  const [defaultLanguage, setDefaultLanguage] = useState("");
  const [defaultQuestionnaireSkip, setDefaultQuestionnaireSkip] = useState(false);
  const [defaultRailState, setDefaultRailState] = useState("");
  const [defaultExportFormat, setDefaultExportFormat] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getCurrentDoctor()
      .then((result) => {
        if (!result) {
          setLoadError("Sign in to view Settings.");
          return;
        }
        setDoctor(result);
        setFullName(result.full_name);
        setBmdcNumber(result.bmdc_number ?? "");
        setDefaultTopK(result.default_top_k?.toString() ?? "");
        setDefaultLanguage(result.default_language ?? "");
        setDefaultQuestionnaireSkip(result.default_questionnaire_skip ?? false);
        setDefaultRailState(result.default_rail_state ?? "");
        setDefaultExportFormat(result.default_export_format ?? "");
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Failed to load profile."));

    getSystemStats()
      .then(setStats)
      .catch(() => {
        // System stats failing independently shouldn't block the Profile/
        // Workspace sections from rendering -- degrades to "no stats
        // shown," not a hard error for the whole page.
      });

    getHealth()
      .then((response) => setBackendStatus(response.status === "ok" ? "ok" : "unreachable"))
      .catch(() => setBackendStatus("unreachable"));
  }, []);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaved(false);

    try {
      const updated = await updateProfile({
        full_name: fullName,
        bmdc_number: bmdcNumber || null,
        default_top_k: defaultTopK ? Number(defaultTopK) : null,
        default_language: defaultLanguage || null,
        default_questionnaire_skip: defaultQuestionnaireSkip,
        default_rail_state: defaultRailState || null,
        default_export_format: defaultExportFormat || null,
      });
      setDoctor(updated);
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <p className="rounded-card border border-critical-bd bg-critical-bg px-4 py-3 text-critical-ink">
          {loadError}
        </p>
      </div>
    );
  }

  if (!doctor) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <p className="text-ink-3">Loading settings...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-paper">
      <main className="flex w-full max-w-2xl flex-col gap-8 px-page py-16">
        <h1 className="text-h1 text-ink">Settings</h1>

        <form onSubmit={handleSave} className="flex flex-col gap-8">
          {/* Profile */}
          <Card>
            <CardHeader title="Profile" />
            <CardBody className="flex flex-col gap-4">
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-ink-2">Full name</span>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-ink-2">Email</span>
                <input
                  disabled
                  value={doctor.email}
                  className="h-10 rounded-btn border border-hairline bg-sunken px-3 text-ink-3"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-ink-2">BMDC number</span>
                <input
                  value={bmdcNumber}
                  onChange={(e) => setBmdcNumber(e.target.value)}
                  placeholder="e.g. A-12345"
                  className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 font-mono text-ink"
                />
                <span className="text-xs text-ink-3">
                  Recorded as entered. This system has no access to the BMDC registry and
                  cannot verify it.
                </span>
              </label>

              {/* Signature preview -- static, not tied to any real (finalised)
                  report, since no report is ever finalised in this system yet. */}
              <div className="rounded-card border border-hairline bg-sunken p-tight">
                <p className="text-eyebrow uppercase text-ink-3">Signature preview</p>
                <p className="mt-2 text-sm text-ink">
                  {fullName || "Your name"}
                  {bmdcNumber ? ` · BMDC ${bmdcNumber}` : ""}
                </p>
                <p className="mt-1 text-xs text-ink-3">
                  Preview only -- no report has been finalised in this system yet.
                </p>
              </div>
            </CardBody>
          </Card>

          {/* Workspace defaults */}
          <Card>
            <CardHeader title="Workspace" sub="Per-doctor defaults for new examinations" />
            <CardBody className="flex flex-col gap-4">
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-ink-2">Default K (retrieved cases)</span>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={defaultTopK}
                  onChange={(e) => setDefaultTopK(e.target.value)}
                  className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-ink-2">Default language</span>
                <select
                  value={defaultLanguage}
                  onChange={(e) => setDefaultLanguage(e.target.value)}
                  className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
                >
                  <option value="">(none)</option>
                  <option value="en">English</option>
                  <option value="bn">Bangla</option>
                </select>
              </label>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={defaultQuestionnaireSkip}
                  onChange={(e) => setDefaultQuestionnaireSkip(e.target.checked)}
                  className="h-4 w-4 accent-steel"
                />
                <span className="text-sm font-medium text-ink-2">
                  Skip questionnaire by default
                </span>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-ink-2">Evidence rail state</span>
                <select
                  value={defaultRailState}
                  onChange={(e) => setDefaultRailState(e.target.value)}
                  className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
                >
                  <option value="">(none)</option>
                  <option value="expanded">Expanded</option>
                  <option value="collapsed">Collapsed</option>
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-ink-2">Export format</span>
                <select
                  value={defaultExportFormat}
                  onChange={(e) => setDefaultExportFormat(e.target.value)}
                  className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
                >
                  <option value="">(none)</option>
                  <option value="pdf">PDF</option>
                </select>
                <span className="text-xs text-ink-3">
                  Stored as a preference only -- export (Download PDF) is not yet implemented
                  anywhere in this app.
                </span>
              </label>
            </CardBody>
          </Card>

          <div className="flex items-center gap-3">
            <Button type="submit" variant="primary" size="lg" loading={saving}>
              {saving ? "Saving..." : "Save changes"}
            </Button>
            {saved && <span className="text-sm text-stable">Saved.</span>}
          </div>
          {saveError && (
            <p className="rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
              {saveError}
            </p>
          )}
        </form>

        {/* System */}
        <Card>
          <CardHeader title="System" sub="Service health, index, and storage & privacy" />
          <CardBody className="flex flex-col gap-4">
            {/* Real service health -- reuses GET /health as-is, no new
                Ollama/ChromaDB reachability checks (explicit scope
                decision: that's new backend work beyond Settings/Profile). */}
            <ServiceChip
              name="Backend"
              value={backendStatus === "checking" ? "checking..." : backendStatus}
              state={backendStatus === "ok" ? "online" : backendStatus === "unreachable" ? "offline" : "online"}
            />

            {/* Index + storage stats -- plain data, not service-health
                rows, so a dl list rather than ServiceChip's dot/status
                register (which implies an online/degraded/offline state
                these values don't have). */}
            {stats && (
              <dl className="flex flex-col">
                <div className="flex items-center justify-between border-b border-hairline py-2">
                  <dt className="text-sm text-ink-2">Index size</dt>
                  <dd className="font-mono text-data-sm text-ink">{stats.index_size} cases</dd>
                </div>
                <div className="flex items-center justify-between border-b border-hairline py-2">
                  <dt className="text-sm text-ink-2">Embedding model</dt>
                  <dd className="font-mono text-data-sm text-ink">
                    {stats.embedding_model} {stats.embedding_version}
                  </dd>
                </div>
                <div className="flex items-center justify-between border-b border-hairline py-2">
                  <dt className="text-sm text-ink-2">Masked images stored</dt>
                  <dd className="font-mono text-data-sm text-ink">{stats.masked_images_stored}</dd>
                </div>
                <div className="flex items-center justify-between py-2">
                  <dt className="text-sm text-ink-2">Original images stored</dt>
                  <dd className="font-mono text-data-sm text-ink">{stats.original_images_stored}</dd>
                </div>
              </dl>
            )}
            <p className="rounded-card bg-sunken p-tight text-sm text-ink-2">
              The system cannot disclose unmasked PHI from storage, because unmasked PHI is
              never stored.
            </p>
          </CardBody>
        </Card>
      </main>
    </div>
  );
}
