"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, searchPatients } from "@/lib/api-client";
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
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-md flex-col gap-6 px-6 py-16">
        <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">Find Patient</h1>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setMode("code")}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${
              mode === "code"
                ? "bg-black text-white dark:bg-white dark:text-black"
                : "border border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            }`}
          >
            By Patient Code
          </button>
          <button
            type="button"
            onClick={() => setMode("name-dob")}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${
              mode === "name-dob"
                ? "bg-black text-white dark:bg-white dark:text-black"
                : "border border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            }`}
          >
            By Name + DOB
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {mode === "code" ? (
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Patient Code
              </span>
              <input
                required
                placeholder="PAT-000001"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="rounded-md border border-zinc-300 px-3 py-2 font-mono dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </label>
          ) : (
            <>
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Name</span>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Date of Birth
                </span>
                <input
                  required
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                />
              </label>
            </>
          )}

          <button
            type="submit"
            disabled={searching}
            className="mt-2 flex h-12 w-full items-center justify-center rounded-lg bg-black px-5 text-base font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            {searching ? "Searching..." : "Search"}
          </button>
        </form>

        {state.kind === "error" && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {state.message}
          </p>
        )}

        {state.kind === "zero-matches" && (
          <p className="rounded-md bg-zinc-100 px-3 py-2 text-sm text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
            No patient found matching that search. This is a well-formed search that
            simply found nothing -- not an error.
          </p>
        )}

        {state.kind === "results" && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {state.patients.length === 1
                ? "1 match found:"
                : `${state.patients.length} matches found -- select one:`}
            </p>
            {state.patients.map((patient) => (
              <button
                key={patient.id}
                onClick={() => router.push(`/patients/${patient.id}`)}
                className="flex flex-col items-start rounded-md border border-zinc-300 px-3 py-2 text-left transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
              >
                <span className="font-medium text-black dark:text-zinc-50">{patient.name}</span>
                <span className="text-sm text-zinc-500 dark:text-zinc-400">
                  {patient.patient_code} &middot; DOB {patient.date_of_birth} &middot; {patient.gender}
                </span>
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
