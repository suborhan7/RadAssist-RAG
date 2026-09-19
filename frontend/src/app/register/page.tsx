"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, registerDoctor, updateProfile } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";

const FIELD = "h-46 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted";

/**
 * Register a doctor account (design/ "Register a doctor account" mockup, ported
 * to the Reading Room theme). Form on the left, a LIVE signature-block preview
 * on the right showing exactly how the name / qualifications / BMDC print on a
 * signed report.
 *
 * Data wiring, honest to the backend:
 * - full_name / email / password  -> POST /auth/register (the real Doctor entity).
 * - bmdc_number  -> optional; the column exists but register does not accept it,
 *   so it is set with a follow-up PATCH /auth/me when provided (partial update).
 * - qualifications -> there is NO backend column for it yet, so it drives the
 *   live preview only and is not persisted. Making it save + print on reports
 *   needs a new `qualifications` column (model + migration + register/settings/
 *   report-formatter wiring); flagged rather than silently dropped.
 */
export default function RegisterPage() {
  const router = useRouter();
  const { t } = useT();
  const [fullName, setFullName] = useState("");
  const [qualifications, setQualifications] = useState("");
  const [bmdc, setBmdc] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await registerDoctor({ email, password, full_name: fullName });
      // BMDC is optional; persist it if given (its column exists, register doesn't take it).
      if (bmdc.trim()) {
        try {
          await updateProfile({ bmdc_number: bmdc.trim() });
        } catch {
          // A failed BMDC save must not block a successful registration.
        }
      }
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(t("register.errExists"));
      } else {
        setError(err instanceof ApiError ? err.message : t("register.errFailed"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-app px-30 py-50">
      <div className="grid w-full max-w-[960px] grid-cols-1 gap-44 lg:grid-cols-[1fr_320px] lg:items-start">
        {/* Form */}
        <div className="min-w-0">
          <h1 className="text-page-title text-text-primary">{t("register.title")}</h1>
          <p className="mt-10 max-w-md text-sm leading-relaxed text-text-secondary">
            {t("register.subtitle")}
          </p>

          <form onSubmit={handleSubmit} className="mt-26 flex flex-col gap-18">
            <label className="flex flex-col gap-8">
              <span className="text-sm text-text-secondary">{t("register.fullName")}</span>
              <input required value={fullName} onChange={(e) => setFullName(e.target.value)} className={FIELD} />
            </label>

            <div className="grid grid-cols-1 gap-18 sm:grid-cols-2">
              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("register.qualifications")}</span>
                <input
                  value={qualifications}
                  onChange={(e) => setQualifications(e.target.value)}
                  placeholder="MBBS, FCPS (Radiology)"
                  className={FIELD}
                />
              </label>
              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("register.bmdcOptional")}</span>
                <input
                  value={bmdc}
                  onChange={(e) => setBmdc(e.target.value)}
                  placeholder="A-41822"
                  className={`${FIELD} font-mono`}
                />
              </label>
            </div>

            <div className="grid grid-cols-1 gap-18 sm:grid-cols-2">
              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("common.email")}</span>
                <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={FIELD} />
              </label>
              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">{t("common.password")}</span>
                <input
                  required
                  type="password"
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={FIELD}
                />
              </label>
            </div>

            {error && (
              <p className="rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
                {error}
              </p>
            )}

            <div className="mt-2 flex flex-wrap items-center gap-16">
              <Button type="submit" variant="primary" size="lg" loading={submitting}>
                {submitting ? t("register.creating") : t("register.create")}
              </Button>
              <span className="text-sm text-text-secondary">
                {t("register.already")}{" "}
                <Link href="/login" className="text-cyan transition-colors duration-hover hover:text-text-primary">
                  {t("common.signIn")}
                </Link>
              </span>
            </div>
          </form>
        </div>

        {/* Live signature-block preview */}
        <aside className="flex-none">
          <div className="font-mono text-eyebrow uppercase text-text-tertiary">{t("register.sigBlock")}</div>
          <div className="mt-10 rounded-panel border border-hairline bg-bg-raised p-20">
            <div className="border-t-2 border-cyan pt-14">
              <div className={cn("text-base font-medium", fullName ? "text-text-primary" : "text-text-muted")}>
                {fullName || t("register.yourName")}
              </div>
              <div className={cn("mt-3 text-sm", qualifications ? "text-text-secondary" : "text-text-muted")}>
                {qualifications || t("register.qualifications")}
              </div>
              <div className={cn("mt-10 font-mono text-mono-meta-lg", bmdc ? "text-text-tertiary" : "text-text-muted")}>
                {bmdc ? `BMDC ${bmdc}` : t("register.bmdcNotEntered")}
              </div>
            </div>
          </div>
          <p className="mt-16 text-sm-tight leading-relaxed text-text-secondary">
            {t("register.sigNote")}
          </p>
        </aside>
      </div>
    </div>
  );
}
