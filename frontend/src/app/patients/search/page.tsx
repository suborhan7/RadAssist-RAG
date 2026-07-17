"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, searchPatients } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
        mode === "code"
          ? await searchPatients({ code })
          : await searchPatients({ name, dob });

      setState(results.length === 0 ? { kind: "zero-matches" } : { kind: "results", patients: results });
    } catch (err) {
      // A malformed request (e.g. no usable params) is a real, distinct
      // error from a well-formed search finding zero matches (above) --
      // mirroring the backend's own Phase 11 Step 4 distinction, not
      // collapsed into one generic "search failed" state.
      setState({
        kind: "error",
        message: err instanceof ApiError ? err.message : "Search failed.",
      });
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-paper">
      <main className="flex w-full max-w-md flex-col gap-6 px-page py-16">
        <h1 className="text-h1 text-ink">Find Patient</h1>

        <div className="flex gap-2">
          <Button
            type="button"
            variant={mode === "code" ? "primary" : "secondary"}
            size="sm"
            onClick={() => setMode("code")}
          >
            By Patient Code
          </Button>
          <Button
            type="button"
            variant={mode === "name-dob" ? "primary" : "secondary"}
            size="sm"
            onClick={() => setMode("name-dob")}
          >
            By Name + DOB
          </Button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {mode === "code" ? (
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-ink-2">Patient Code</span>
              <input
                required
                placeholder="PAT-000001"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 font-mono text-ink"
              />
            </label>
          ) : (
            <>
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
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
                />
              </label>
            </>
          )}

          <Button type="submit" variant="primary" size="lg" block loading={searching} className="mt-2">
            {searching ? "Searching..." : "Search"}
          </Button>
        </form>

        {state.kind === "error" && (
          <p className="rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
            {state.message}
          </p>
        )}

        {state.kind === "zero-matches" && (
          <p className="rounded-card border border-hairline bg-sunken px-3 py-2 text-sm text-ink-2">
            No patient found matching that search. This is a well-formed search that simply found
            nothing -- not an error.
          </p>
        )}

        {state.kind === "results" && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-ink-2">
              {state.patients.length === 1
                ? "1 match found:"
                : `${state.patients.length} matches found -- select one:`}
            </p>
            {state.patients.map((patient) => (
              <Card key={patient.id} className="p-0">
                <button
                  onClick={() => router.push(`/patients/${patient.id}`)}
                  className="flex w-full flex-col items-start px-card py-tight text-left transition-colors duration-hover hover:bg-sunken"
                >
                  <span className="font-medium text-ink">{patient.name}</span>
                  <span className="text-sm text-ink-3">
                    {patient.patient_code} &middot; DOB {patient.date_of_birth} &middot;{" "}
                    {patient.gender}
                  </span>
                </button>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
