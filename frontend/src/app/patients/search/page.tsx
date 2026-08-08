"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, searchPatients } from "@/lib/api-client";
import { BUTTON_BASE, Button, SIZE, VARIANT } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { paths } from "@/lib/generated/api";

type PatientResponse =
  paths["/patients/search"]["get"]["responses"][200]["content"]["application/json"][number];

type SearchState =
  | { kind: "idle" }
  | { kind: "error"; message: string }
  | { kind: "zero-matches" }
  | { kind: "results"; patients: PatientResponse[] };

export default function SearchPatientsPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"code" | "name-dob">("code");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [searching, setSearching] = useState(false);
  const [state, setState] = useState<SearchState>({ kind: "idle" });

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSearching(true);
    setState({ kind: "idle" });

    try {
      const results =
        mode === "code" ? await searchPatients({ code }) : await searchPatients({ name, dob });

      setState(results.length === 0 ? { kind: "zero-matches" } : { kind: "results", patients: results });
    } catch (err) {
      // A malformed request is a distinct error from a well-formed search
      // finding zero matches -- mirroring the backend's Phase 11 distinction.
      setState({ kind: "error", message: err instanceof ApiError ? err.message : "Search failed." });
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
        <Link
          href="/dashboard"
          className="text-sm text-text-tertiary transition-colors duration-hover hover:text-cyan"
        >
          Queue
        </Link>
        <span className="text-text-muted">/</span>
        <h1 className="text-screen-title text-text-primary">Find patient</h1>
      </header>

      <div className="flex-1 overflow-auto px-30 py-34">
        <div className="mx-auto max-w-[900px]">
          <div className="mb-16 flex gap-8">
            <Button type="button" variant={mode === "code" ? "primary" : "secondary"} size="sm" onClick={() => setMode("code")}>
              By patient code
            </Button>
            <Button type="button" variant={mode === "name-dob" ? "primary" : "secondary"} size="sm" onClick={() => setMode("name-dob")}>
              By name and date of birth
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-12 sm:flex-row sm:items-end">
            {mode === "code" ? (
              <label className="flex flex-1 flex-col gap-8">
                <span className="text-sm text-text-secondary">Patient code</span>
                <input
                  required
                  placeholder="PAT-000001"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="h-46 rounded-field border border-strong bg-bg-raised px-16 font-mono text-text-primary placeholder:text-text-muted"
                />
              </label>
            ) : (
              <>
                <label className="flex flex-1 flex-col gap-8">
                  <span className="text-sm text-text-secondary">Name</span>
                  <input
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="h-46 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted"
                  />
                </label>
                <label className="flex flex-col gap-8">
                  <span className="text-sm text-text-secondary">Date of birth</span>
                  <input
                    required
                    type="date"
                    value={dob}
                    onChange={(e) => setDob(e.target.value)}
                    className="h-46 rounded-field border border-strong bg-bg-raised px-16 font-mono text-text-primary placeholder:text-text-muted"
                  />
                </label>
              </>
            )}
            <Button type="submit" variant="primary" size="lg" loading={searching}>
              {searching ? "Searching…" : "Search"}
            </Button>
          </form>

          <p className="mt-16 max-w-[66ch] text-sm leading-relaxed text-text-secondary">
            One code, or a name and date of birth. Spelling is never the reason you cannot find a
            patient.
          </p>

          {state.kind === "error" && (
            <p className="mt-24 rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
              {state.message}
            </p>
          )}

          {state.kind === "zero-matches" && (
            <div className="mt-24 flex flex-wrap items-center gap-18">
              <p className="max-w-[58ch] flex-1 text-sm leading-relaxed text-text-secondary">
                A well-formed search that finds nothing is not an error. Register the patient, or add
                a date of birth to narrow a common name.
              </p>
              <Link href="/patients/new" className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}>
                Register new patient
              </Link>
            </div>
          )}

          {state.kind === "results" && (
            <div className="mt-24">
              <div className="mb-6 font-mono text-eyebrow uppercase text-text-tertiary">
                {state.patients.length} {state.patients.length === 1 ? "match" : "matches"}
              </div>
              <div className="border-t border-hairline">
                {state.patients.map((patient) => (
                  <button
                    key={patient.id}
                    onClick={() => router.push(`/patients/${patient.id}`)}
                    className="flex w-full items-center gap-14 border-b border-hairline py-16 text-left transition-colors duration-hover hover:bg-bg-hover"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-base font-medium text-text-primary">{patient.name}</div>
                      <div className="mt-2 font-mono text-mono-meta text-text-tertiary">
                        {patient.patient_code}
                      </div>
                    </div>
                    <span className="whitespace-nowrap text-sm text-text-secondary">
                      {patient.date_of_birth}
                    </span>
                    <span className="hidden whitespace-nowrap text-sm text-text-secondary sm:inline">
                      {patient.gender}
                    </span>
                    <span className="whitespace-nowrap text-sm text-cyan">Open</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
