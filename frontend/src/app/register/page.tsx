"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, registerDoctor } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

/**
 * Register (Phase 13b, restyled Phase 14). design_specification.md has
 * no dedicated doctor self-registration screen -- its §8.6 "Register
 * patient" is a different entity (a PATIENT record, modal, server-generated
 * RA-{YYYY}-{NNNNNN} id -- explicitly NOT reused here per frontend/CLAUDE.md's
 * hard rule). Self-registration (phase13_auth_architecture.md Decision 1)
 * was never in the original design's scope. Rather than inventing a new
 * screen concept, this reuses /login's exact visual vocabulary (lightbox
 * split layout, same primitives) as the lowest-risk extension of an
 * established pattern.
 *
 * Fields match the real Doctor entity (email, password, full_name) --
 * not the design spec's unrelated patient fields (DOB, sex, MRN) and not
 * an invented BMDC-number field (that belongs to a future Settings ·
 * Profile screen, out of Phase 13/14 scope per frontend/CLAUDE.md).
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
      router.push("/dashboard");
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
    <div className="flex min-h-screen">
      <div className="hidden flex-1 flex-col justify-between bg-lightbox px-12 py-16 text-lightbox-ink lg:flex">
        <div>
          <p className="text-eyebrow uppercase text-lightbox-ink-2">RadAssist-RAG</p>
          <h1 className="mt-4 max-w-md text-display text-white">
            Retrieval-grounded chest X-ray reporting.
          </h1>
        </div>
        <p className="max-w-md text-sm text-lightbox-ink-2">
          Every AI draft cites the retrieved cases it was grounded in. 0 reports have ever been
          finalised without a radiologist.
        </p>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center bg-paper px-page py-16">
        <div className="flex w-full max-w-sm flex-col gap-6">
          <div>
            <h2 className="text-h1 text-ink">Create your account</h2>
            <p className="mt-1 text-sm text-ink-2">RadAssist-RAG &middot; Radiologist Workflow</p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-ink-2">Full name</span>
              <input
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-ink-2">Email</span>
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-ink-2">Password</span>
              <input
                required
                type="password"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
              />
            </label>

            <Button type="submit" variant="primary" size="lg" block loading={submitting} className="mt-2">
              {submitting ? "Creating account..." : "Create account"}
            </Button>
          </form>

          {error && (
            <p className="rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
              {error}
            </p>
          )}

          <p className="text-center text-sm text-ink-2">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-ink underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
