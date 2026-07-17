"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, createPatient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

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
      const patient = await createPatient({
        name,
        date_of_birth: dateOfBirth,
        gender,
      });
      setCreatedPatientCode(patient.patient_code);
      setTimeout(() => router.push(`/patients/${patient.id}`), 1200);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to register patient.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-paper">
      <main className="flex w-full max-w-md flex-col gap-6 px-page py-16">
        <h1 className="text-h1 text-ink">Register New Patient</h1>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-ink-2">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-ink-2">Date of Birth</span>
            <input
              required
              type="date"
              value={dateOfBirth}
              onChange={(e) => setDateOfBirth(e.target.value)}
              className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-ink-2">Gender</span>
            <input
              required
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
            />
          </label>

          <Button type="submit" variant="primary" size="lg" block loading={submitting} className="mt-2">
            {submitting ? "Registering..." : "Register Patient"}
          </Button>
        </form>

        {error && (
          <p className="rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
            {error}
          </p>
        )}

        {createdPatientCode && (
          <p className="rounded-card border border-stable-bd bg-stable-bg px-3 py-2 text-sm text-stable-ink">
            Patient registered -- code:{" "}
            <span className="font-mono font-semibold">{createdPatientCode}</span>. Redirecting to
            profile...
          </p>
        )}
      </main>
    </div>
  );
}
