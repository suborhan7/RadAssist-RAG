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
import { useDoctor } from "@/lib/doctor";
import { MAX_TOP_K, MIN_TOP_K, resolveTopK } from "@/lib/doctor-defaults";
import { useT } from "@/lib/i18n";
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
  const { t } = useT();
  const { refresh: refreshDoctor } = useDoctor();
  const [doctor, setDoctor] = useState<CurrentDoctorResponse | null>(null);
  const [stats, setStats] = useState<SystemStatsResponse | null>(null);
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "unreachable">("checking");
  const [loadError, setLoadError] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [bmdcNumber, setBmdcNumber] = useState("");
  const [defaultTopK, setDefaultTopK] = useState("");
  const [defaultLanguage, setDefaultLanguage] = useState("");
  const [defaultQuestionnaireSkip, setDefaultQuestionnaireSkip] = useState(false);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getCurrentDoctor()
      .then((result) => {
        if (!result) {
          setLoadError(t("settings.signInToView"));
          return;
        }
        setDoctor(result);
        setFullName(result.full_name);
        setBmdcNumber(result.bmdc_number ?? "");
        // Read through the same resolver the upload flow uses, so the field
        // shows the k actually in effect. A legacy value above the current
        // maximum (the control used to allow 20) would otherwise display as
        // itself while retrieval used the clamped number.
        setDefaultTopK(
          result.default_top_k == null ? "" : String(resolveTopK(result.default_top_k)),
        );
        setDefaultLanguage(result.default_language ?? "");
        setDefaultQuestionnaireSkip(result.default_questionnaire_skip ?? false);
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : t("settings.errLoadProfile")));

    getSystemStats()
      .then(setStats)
      .catch(() => {
        // System stats failing shouldn't block Profile/Workspace rendering.
      });

    getHealth()
      .then((response) => setBackendStatus(response.status === "ok" ? "ok" : "unreachable"))
      .catch(() => setBackendStatus("unreachable"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        // Narrowed here, at the one point the value crosses into the API.
        // DoctorUpdateRequest.default_language is Literal["en", "bn"] |
        // None, while this state is a bare string fed by a <select> and by
        // DoctorResponse (whose own default_language is still plain str) --
        // so the mismatch is real and belongs at the boundary rather than
        // pushed back through the select's onChange. Anything that is not
        // one of the two supported codes is sent as null (no preference),
        // which is what an empty selection already meant.
        //
        // Not part of the Input Admission and Modality Gate work: this
        // error only became visible when src/lib/generated/api.d.ts was
        // regenerated against the current backend, which had already
        // tightened this field.
        default_language: defaultLanguage === "en" || defaultLanguage === "bn" ? defaultLanguage : null,
        default_questionnaire_skip: defaultQuestionnaireSkip,
      });
      setDoctor(updated);
      setSaved(true);
      // The preferences are now read by DoctorProvider, which caches them per
      // navigation. Saving does not change the path, so without this the new k
      // would not reach the upload flow until the next full navigation -- the
      // save would appear to have done nothing, which is how this started.
      refreshDoctor();
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : t("settings.errSave"));
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
        <p className="text-text-tertiary">{t("settings.loading")}</p>
      </div>
    );
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
        <h1 className="text-screen-title text-text-primary">{t("nav.settings")}</h1>
        <span className="truncate font-mono text-mono-meta-lg text-text-tertiary">{doctor.email}</span>
        <span className="flex-1" />
        {saved && <span className="text-sm text-cyan">{t("settings.allSaved")}</span>}
      </header>

      <div className="flex-1 overflow-auto px-30 py-34">
        <div className="mx-auto max-w-[1080px]">
          <form onSubmit={handleSave} className="grid grid-cols-1 gap-44 lg:grid-cols-2">
            {/* Identity and signature */}
            <section className="flex flex-col gap-16">
              <div>
                <h2 className="text-panel text-text-primary">{t("settings.identityTitle")}</h2>
                <p className="mt-6 text-sm text-text-secondary">
                  {t("settings.identityDesc")}
                </p>
              </div>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("newPatient.fullName")}</span>
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} className={FIELD} />
              </label>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("common.email")}</span>
                <input disabled value={doctor.email} className={FIELD_DISABLED} />
              </label>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("settings.bmdcNumber")}</span>
                <input
                  value={bmdcNumber}
                  onChange={(e) => setBmdcNumber(e.target.value)}
                  placeholder="e.g. A-12345"
                  className={`${FIELD} font-mono`}
                />
                <span className="text-caption text-text-tertiary">
                  {t("settings.bmdcNote")}
                </span>
              </label>

              {/* Signature preview -- static; not wired to a specific report. */}
              <div className="rounded-panel border border-hairline bg-bg-raised p-20">
                <p className="font-mono text-eyebrow uppercase text-text-tertiary">
                  {t("settings.sigPreview")}
                </p>
                <div className="mt-14 border-t-2 border-cyan pt-12">
                  <p className="text-base font-medium text-text-primary">{fullName || t("register.yourName")}</p>
                  {bmdcNumber && (
                    <p className="mt-4 font-mono text-mono-meta-lg text-text-tertiary">BMDC {bmdcNumber}</p>
                  )}
                </div>
              </div>
            </section>

            {/* Reading defaults */}
            <section className="flex flex-col gap-16">
              <div>
                <h2 className="text-panel text-text-primary">{t("settings.defaultsTitle")}</h2>
                <p className="mt-6 text-sm text-text-secondary">
                  {t("settings.defaultsDesc")}
                </p>
              </div>

              {/* Bounds come from doctor-defaults.ts, the same module the
                  resolver uses. A control that accepted 20 while the resolver
                  silently fell back to 5 above 10 would reproduce the exact
                  bug this screen was reported for. */}
              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("settings.defaultK")}</span>
                <input
                  type="number"
                  min={MIN_TOP_K}
                  max={MAX_TOP_K}
                  value={defaultTopK}
                  onChange={(e) => setDefaultTopK(e.target.value)}
                  className={FIELD}
                />
                <span className="text-caption text-text-tertiary">
                  {t("settings.defaultKNote")}
                </span>
              </label>

              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("settings.defaultLanguage")}</span>
                <select
                  value={defaultLanguage}
                  onChange={(e) => setDefaultLanguage(e.target.value)}
                  className={FIELD}
                >
                  <option value="">{t("compare.none")}</option>
                  <option value="en">{t("settings.langEnglish")}</option>
                  <option value="bn">{t("settings.langBangla")}</option>
                </select>
              </label>

              <label className="flex items-center gap-10">
                <input
                  type="checkbox"
                  checked={defaultQuestionnaireSkip}
                  onChange={(e) => setDefaultQuestionnaireSkip(e.target.checked)}
                  className="h-16 w-16 accent-cyan"
                />
                <span className="text-sm text-text-secondary">{t("settings.skipQuestionnaire")}</span>
              </label>

              {/* "Rail state" and "Export format" used to sit here. Both were
                  removed rather than restyled: the rail is deliberately
                  non-collapsible (see app-rail.tsx -- collapsing was tried and
                  taken out), and PDF export does not exist. Offering a choice
                  the app cannot honour is the same defect as the k preference
                  that was saved and never read; a control that does nothing is
                  worse than no control, because it looks like it worked. The
                  doctors columns are left in place for whenever those features
                  land. */}
            </section>

            <div className="flex items-center gap-16 lg:col-span-2">
              <Button type="submit" variant="primary" size="lg" loading={saving}>
                {saving ? t("settings.saving") : t("settings.saveChanges")}
              </Button>
              {saved && <span className="text-sm text-cyan">{t("settings.savedShort")}</span>}
              {saveError && <span className="text-sm text-amber">{saveError}</span>}
            </div>
          </form>

          {/* System / this machine */}
          <section className="mt-44 max-w-[520px]">
            <h2 className="text-panel text-text-primary">{t("settings.thisMachine")}</h2>
            <p className="mb-18 mt-6 text-sm text-text-secondary">
              {t("settings.localNote")}
            </p>

            <ServiceChip
              name={t("settings.backend")}
              value={
                backendStatus === "checking"
                  ? t("settings.checking")
                  : backendStatus === "ok"
                    ? t("settings.statusOk")
                    : t("settings.statusUnreachable")
              }
              state={backendStatus === "ok" ? "online" : backendStatus === "unreachable" ? "offline" : "online"}
            />

            {stats && (
              <dl className="flex flex-col border-t border-hairline">
                <StatRow label={t("settings.indexSize")} value={t("settings.casesValue", { count: stats.index_size })} />
                <StatRow label={t("settings.embeddingModel")} value={`${stats.embedding_model} ${stats.embedding_version}`} />
                <StatRow label={t("settings.maskedStored")} value={String(stats.masked_images_stored)} />
                <StatRow
                  label={t("settings.originalStored")}
                  value={String(stats.original_images_stored)}
                  accent={stats.original_images_stored === 0}
                />
              </dl>
            )}

            <p className="mt-16 max-w-[66ch] text-sm-tight leading-relaxed text-text-secondary">
              {t("settings.phiNote")}
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
