"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, createPatient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { BackLink } from "@/components/layout/screen-header";
import { MIN_DATE_OF_BIRTH, todayISO } from "@/lib/date-bounds";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";

const FIELD = "h-46 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted";
// Value stored as `gender` stays English; label is looked up per option.
const SEX_OPTIONS: { value: string; labelKey: string }[] = [
  { value: "Female", labelKey: "newPatient.sexFemale" },
  { value: "Male", labelKey: "newPatient.sexMale" },
  { value: "Other", labelKey: "newPatient.sexOther" },
];

/**
 * Register patient (Phase 11/12, ported to the Reading Room theme in the
 * redesign step 4). The PAT-000001 code is sequential and server-assigned on
 * creation, so the "will be assigned" panel states the guarantee without
 * predicting a specific number (the mock's PAT-000318 preview and its
 * possible-duplicate warning are not backed by any endpoint). createPatient
 * logic unchanged: on success it shows the real assigned code, then routes to
 * the new profile.
 */
export default function RegisterPatientPage() {
  const router = useRouter();
  const { t } = useT();
  const [name, setName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdPatientCode, setCreatedPatientCode] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const patient = await createPatient({ name, date_of_birth: dateOfBirth, gender });
      setCreatedPatientCode(patient.patient_code);
      setTimeout(() => router.push(`/patients/${patient.id}`), 1200);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("newPatient.errFailed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
        <BackLink href="/patients/search" labelKey="nav.find" />
        <h1 className="text-screen-title text-text-primary">{t("newPatient.title")}</h1>
      </header>

      <div className="flex-1 overflow-auto px-30 py-34">
        <div className="mx-auto grid max-w-[960px] grid-cols-1 gap-44 lg:grid-cols-[1fr_320px]">
          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-18">
            <label className="flex flex-col gap-8">
              <span className="text-sm text-text-secondary">{t("newPatient.fullName")}</span>
              <input required value={name} onChange={(e) => setName(e.target.value)} className={FIELD} />
            </label>

            <div className="grid grid-cols-1 gap-18 sm:grid-cols-2">
              {/* min/max bound the native year spinner, which otherwise
                  accepts any year up to 275760 -- a tester reached the form's
                  own 500 by typing one. The server enforces the same range;
                  this just makes the browser refuse it first, in place. */}
              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("search.dob")}</span>
                <input
                  required
                  type="date"
                  min={MIN_DATE_OF_BIRTH}
                  max={todayISO()}
                  value={dateOfBirth}
                  onChange={(e) => setDateOfBirth(e.target.value)}
                  className={`${FIELD} font-mono`}
                />
              </label>

              <div className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("newPatient.sex")}</span>
                <div className="flex flex-wrap gap-9">
                  {SEX_OPTIONS.map((option) => {
                    const selected = gender === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setGender(option.value)}
                        aria-pressed={selected}
                        className={cn(
                          "rounded-full border px-20 py-9 text-sm transition-colors duration-hover",
                          selected
                            ? "border-cyan-line bg-cyan-wash text-cyan"
                            : "border-strong text-text-secondary hover:text-text-primary",
                        )}
                      >
                        {t(option.labelKey)}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="pt-4">
              <Button type="submit" variant="primary" size="lg" loading={submitting} disabled={!gender}>
                {submitting ? t("newPatient.registering") : t("newPatient.title")}
              </Button>
            </div>

            {error && (
              <p className="rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
                {error}
              </p>
            )}

            {createdPatientCode && (
              <p className="rounded-field border border-cyan-line bg-cyan-wash px-14 py-12 text-sm text-cyan">
                {t("newPatient.registeredPre")}{" "}
                <span className="font-mono font-semibold">{createdPatientCode}</span>
                {t("newPatient.registeredPost")}
              </p>
            )}
          </form>

          {/* Assigned-code panel */}
          <aside className="flex flex-col gap-26">
            <div>
              <div className="font-mono text-eyebrow uppercase text-text-tertiary">{t("newPatient.willAssign")}</div>
              <div className="mt-10 font-mono text-metric-sm text-text-primary">PAT-XXXXXX</div>
              <p className="mt-8 text-sm-tight leading-relaxed text-text-secondary">
                {t("newPatient.assignNote")}
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
