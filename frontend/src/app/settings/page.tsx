"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  getCurrentDoctor,
  getHealth,
  getSystemStats,
  updateProfile,
} from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { ServiceChip } from "@/components/ui/chip";
import type { paths } from "@/lib/generated/api";

type CurrentDoctorResponse =
  paths["/auth/me"]["get"]["responses"][200]["content"]["application/json"];
type SystemStatsResponse =
  paths["/system/stats"]["get"]["responses"][200]["content"]["application/json"];

const FIELD = "h-46 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted";
const FIELD_DISABLED = "h-46 rounded-field border border-hairline bg-bg-hover px-16 text-text-tertiary";

/**
 * Settings/Profile (Phase 16, scoped to Profile only, ported to the Reading
 * Room theme in the redesign step 4). Copy honesty is load-bearing: BMDC is
 * "Recorded as entered. This system has no access to the BMDC registry and
 * cannot verify it." The signature preview is a static preview of the
 * name/BMDC format, not wired to a specific finalized report. Workspace
 * defaults persist via PATCH /auth/me; the export-format note stays honest
 * (Download PDF isn't implemented). System stats are real (GET /system/stats);
 * service health reuses GET /health only. All fields/handlers unchanged.
 */
export default function SettingsPage() {
  const [doctor, setDoctor] = useState<CurrentDoctorResponse | null>(null);
  const [stats, setStats] = useState<SystemStatsResponse | null>(null);
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "unreachable">("checking");
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
        // System stats failing shouldn't block Profile/Workspace rendering.
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
      <div className="flex min-h-screen items-center justify-center bg-bg-app p-30">
        <p className="rounded-field border border-amber-line bg-amber-wash px-16 py-12 text-sm text-amber">
          {loadError}
        </p>
      </div>
    );
  }

  if (!doctor) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-app">
        <p className="text-text-tertiary">Loading settings…</p>
      </div>
    );
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
        <h1 className="text-screen-title text-text-primary">Settings</h1>
        <span className="truncate font-mono text-mono-meta-lg text-text-tertiary">{doctor.email}</span>
        <span className="flex-1" />
        {saved && <span className="text-sm text-cyan">All changes saved</span>}
      </header>

      <div className="flex-1 overflow-auto px-30 py-34">
        <div className="mx-auto max-w-[1080px]">
          <form onSubmit={handleSave} className="grid grid-cols-1 gap-44 lg:grid-cols-2">
            {/* Identity and signature */}
            <section className="flex flex-col gap-16">
              <div>
                <h2 className="text-panel text-text-primary">Identity and signature</h2>
                <p className="mt-6 text-sm text-text-secondary">
                  Printed at the foot of every report you sign.
                </p>
              </div>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">Full name</span>
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} className={FIELD} />
              </label>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">Email</span>
                <input disabled value={doctor.email} className={FIELD_DISABLED} />
              </label>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">BMDC number</span>
                <input
                  value={bmdcNumber}
                  onChange={(e) => setBmdcNumber(e.target.value)}
                  placeholder="e.g. A-12345"
                  className={`${FIELD} font-mono`}
                />
                <span className="text-caption text-text-tertiary">
                  Recorded as entered. This system has no access to the BMDC registry and cannot
                  verify it.
                </span>
              </label>

              {/* Signature preview -- static; not wired to a specific report. */}
              <div className="rounded-panel border border-hairline bg-bg-raised p-20">
                <p className="font-mono text-eyebrow uppercase text-text-tertiary">
                  As it appears on a signed report
                </p>
                <div className="mt-14 border-t-2 border-cyan pt-12">
                  <p className="text-base font-medium text-text-primary">{fullName || "Your name"}</p>
                  {bmdcNumber && (
                    <p className="mt-4 font-mono text-mono-meta-lg text-text-tertiary">BMDC {bmdcNumber}</p>
                  )}
                </div>
              </div>
            </section>

            {/* Reading defaults */}
            <section className="flex flex-col gap-16">
              <div>
                <h2 className="text-panel text-text-primary">Reading defaults</h2>
                <p className="mt-6 text-sm text-text-secondary">
                  Applied to every new examination you start.
                </p>
              </div>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">Default K (retrieved cases)</span>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={defaultTopK}
                  onChange={(e) => setDefaultTopK(e.target.value)}
                  className={FIELD}
                />
                <span className="text-caption text-text-tertiary">
                  Five is what the evaluation used. More cases means slower generation.
                </span>
              </label>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">Default language</span>
                <select
                  value={defaultLanguage}
                  onChange={(e) => setDefaultLanguage(e.target.value)}
                  className={FIELD}
                >
                  <option value="">(none)</option>
                  <option value="en">English</option>
                  <option value="bn">Bangla</option>
                </select>
              </label>

              <label className="flex items-center gap-10">
                <input
                  type="checkbox"
                  checked={defaultQuestionnaireSkip}
                  onChange={(e) => setDefaultQuestionnaireSkip(e.target.checked)}
                  className="h-16 w-16 accent-cyan"
                />
                <span className="text-sm text-text-secondary">Skip the questionnaire by default</span>
              </label>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">Evidence rail state</span>
                <select
                  value={defaultRailState}
                  onChange={(e) => setDefaultRailState(e.target.value)}
                  className={FIELD}
                >
                  <option value="">(none)</option>
                  <option value="expanded">Expanded</option>
                  <option value="collapsed">Collapsed</option>
                </select>
              </label>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">Export format</span>
                <select
                  value={defaultExportFormat}
                  onChange={(e) => setDefaultExportFormat(e.target.value)}
                  className={FIELD}
                >
                  <option value="">(none)</option>
                  <option value="pdf">PDF</option>
                </select>
                <span className="text-caption text-text-tertiary">
                  Stored as a preference only. Export (Download PDF) is not yet implemented anywhere
                  in this app.
                </span>
              </label>
            </section>

            <div className="flex items-center gap-16 lg:col-span-2">
              <Button type="submit" variant="primary" size="lg" loading={saving}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
              {saved && <span className="text-sm text-cyan">Saved.</span>}
              {saveError && <span className="text-sm text-amber">{saveError}</span>}
            </div>
          </form>

          {/* System / this machine */}
          <section className="mt-44 max-w-[520px]">
            <h2 className="text-panel text-text-primary">This machine</h2>
            <p className="mb-18 mt-6 text-sm text-text-secondary">
              Everything runs locally. Nothing leaves the building.
            </p>

            <ServiceChip
              name="Backend"
              value={backendStatus === "checking" ? "checking…" : backendStatus}
              state={backendStatus === "ok" ? "online" : backendStatus === "unreachable" ? "offline" : "online"}
            />

            {stats && (
              <dl className="flex flex-col border-t border-hairline">
                <StatRow label="Index size" value={`${stats.index_size} cases`} />
                <StatRow label="Embedding model" value={`${stats.embedding_model} ${stats.embedding_version}`} />
                <StatRow label="Masked images stored" value={String(stats.masked_images_stored)} />
                <StatRow
                  label="Original images stored"
                  value={String(stats.original_images_stored)}
                  accent={stats.original_images_stored === 0}
                />
              </dl>
            )}

            <p className="mt-16 max-w-[66ch] text-sm-tight leading-relaxed text-text-secondary">
              The system cannot disclose unmasked PHI from storage, because unmasked PHI is never
              stored.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

function StatRow({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-hairline py-12">
      <dt className="text-sm text-text-secondary">{label}</dt>
      <dd className={`font-mono text-sm ${accent ? "text-cyan" : "text-text-primary"}`}>{value}</dd>
    </div>
  );
}
