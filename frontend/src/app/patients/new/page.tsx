"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, createPatient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

const FIELD = "h-46 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted";
const SEX_OPTIONS = ["Female", "Male", "Other"];

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
      setError(err instanceof ApiError ? err.message : "Failed to register patient.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
        <Link
          href="/patients/search"
          className="text-sm text-text-tertiary transition-colors duration-hover hover:text-cyan"
        >
          Find patient
        </Link>
        <span className="text-text-muted">/</span>
        <h1 className="text-screen-title text-text-primary">Register patient</h1>
      </header>

      <div className="flex-1 overflow-auto px-30 py-34">
        <div className="mx-auto grid max-w-[960px] grid-cols-1 gap-44 lg:grid-cols-[1fr_320px]">
          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-18">
            <label className="flex flex-col gap-8">
              <span className="text-sm text-text-secondary">Full name</span>
              <input required value={name} onChange={(e) => setName(e.target.value)} className={FIELD} />
            </label>

            <div className="grid grid-cols-1 gap-18 sm:grid-cols-2">
              <label className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">Date of birth</span>
                <input
                  required
                  type="date"
                  value={dateOfBirth}
                  onChange={(e) => setDateOfBirth(e.target.value)}
                  className={`${FIELD} font-mono`}
                />
              </label>

              <div className="flex flex-col gap-8">
                <span className="text-sm text-text-secondary">Sex</span>
                <div className="flex flex-wrap gap-9">
                  {SEX_OPTIONS.map((option) => {
                    const selected = gender === option;
                    return (
                      <button
                        key={option}
                        type="button"
                        onClick={() => setGender(option)}
                        aria-pressed={selected}
                        className={cn(
                          "rounded-full border px-20 py-9 text-sm transition-colors duration-hover",
                          selected
                            ? "border-cyan-line bg-cyan-wash text-cyan"
                            : "border-strong text-text-secondary hover:text-text-primary",
                        )}
                      >
                        {option}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="pt-4">
              <Button type="submit" variant="primary" size="lg" loading={submitting} disabled={!gender}>
                {submitting ? "Registering…" : "Register patient"}
              </Button>
            </div>

            {error && (
              <p className="rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
                {error}
              </p>
            )}

            {createdPatientCode && (
              <p className="rounded-field border border-cyan-line bg-cyan-wash px-14 py-12 text-sm text-cyan">
                Patient registered as{" "}
                <span className="font-mono font-semibold">{createdPatientCode}</span>. Opening the
                profile…
              </p>
            )}
          </form>

          {/* Assigned-code panel */}
          <aside className="flex flex-col gap-26">
            <div>
              <div className="font-mono text-eyebrow uppercase text-text-tertiary">Will be assigned</div>
              <div className="mt-10 font-mono text-metric-sm text-text-primary">PAT-XXXXXX</div>
              <p className="mt-8 text-sm-tight leading-relaxed text-text-secondary">
                Sequential and permanent, assigned on registration. Written on the film envelope at
                reception.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
