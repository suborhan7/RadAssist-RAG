"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, registerDoctor } from "@/lib/api-client";

/**
 * Register (Phase 13b). design_specification.md has no dedicated doctor
 * self-registration screen -- its §8.6 "Register patient" is a different
 * entity (a PATIENT record, modal, server-generated RA-{YYYY}-{NNNNNN}
 * id -- explicitly NOT reused here per frontend/CLAUDE.md's hard rule;
 * doctors keep the real PAT-000001-adjacent convention of using the
 * backend's actual Doctor entity, which has no analogous formatted id at
 * all). Self-registration (phase13_auth_architecture.md Decision 1) was
 * never in the original design's scope. Rather than inventing a new
 * screen concept, this reuses /login's exact visual vocabulary (split
 * lightbox/form layout, same input/button styling) as the lowest-risk
 * extension of an established pattern -- flagged here, not silently
 * presented as if the design spec had specified it.
 *
 * Fields match the real Doctor entity (email, password, full_name) --
 * not the design spec's unrelated patient fields (DOB, sex, MRN) and not
 * an invented BMDC-number field (that belongs to a future Settings ·
 * Profile screen, out of Phase 13 scope per frontend/CLAUDE.md).
 */
export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
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
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("An account with this email already exists.");
      } else {
        setError(err instanceof ApiError ? err.message : "Registration failed.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen font-sans">
      <div className="hidden flex-1 flex-col justify-between bg-black px-12 py-16 text-zinc-50 lg:flex">
        <div>
          <p className="text-sm font-medium tracking-wide text-zinc-400">RadAssist-RAG</p>
          <h1 className="mt-4 max-w-md text-3xl font-semibold">
            Retrieval-grounded chest X-ray reporting.
          </h1>
        </div>
        <p className="max-w-md text-sm text-zinc-500">
          Every AI draft cites the retrieved cases it was grounded in. Nothing is finalised
          without a radiologist.
        </p>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center bg-zinc-50 px-6 py-16 dark:bg-black">
        <div className="flex w-full max-w-sm flex-col gap-6">
          <div>
            <h2 className="text-2xl font-semibold text-black dark:text-zinc-50">
              Create your account
            </h2>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              RadAssist-RAG · Radiologist Workflow
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Full name
              </span>
              <input
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Email</span>
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Password
              </span>
              <input
                required
                type="password"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </label>

            <button
              type="submit"
              disabled={submitting}
              className="mt-2 flex h-12 w-full items-center justify-center rounded-lg bg-black px-5 text-base font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
            >
              {submitting ? "Creating account..." : "Create account"}
            </button>
          </form>

          {error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
              {error}
            </p>
          )}

          <p className="text-center text-sm text-zinc-600 dark:text-zinc-400">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-black underline dark:text-zinc-50">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
