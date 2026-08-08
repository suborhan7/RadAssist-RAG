"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, registerDoctor } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { ChestXrayIllustration } from "@/components/ui/chest-xray-illustration";

const FIELD = "h-46 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted";

/**
 * Register (Phase 13b, ported to the Reading Room theme in the redesign step
 * 4). Reuses /login's exact split vocabulary. Fields match the real Doctor
 * entity (email, password, full_name) -- deliberately NOT the design's
 * BMDC/qualifications fields (those belong to Settings·Profile, per
 * frontend/CLAUDE.md's hard rule). All auth logic unchanged.
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
    <div className="flex min-h-screen bg-bg-app">
      <div className="relative hidden flex-1 flex-col justify-between overflow-hidden bg-bg-film px-50 py-44 lg:flex">
        <ChestXrayIllustration className="pointer-events-none absolute inset-0 h-full w-full opacity-50" />
        <div className="relative">
          <p className="font-mono text-eyebrow uppercase text-text-tertiary">RadAssist-RAG</p>
          <h1 className="mt-14 max-w-md text-display text-text-primary">
            Retrieval-grounded chest X-ray reporting.
          </h1>
        </div>
        <p className="relative max-w-md text-sm leading-relaxed text-text-secondary">
          Every AI draft cites the retrieved cases it was grounded in. 0 reports have ever been
          finalised without a radiologist.
        </p>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center px-30 py-44">
        <div className="flex w-full max-w-sm flex-col gap-24">
          <div>
            <h2 className="text-page-title text-text-primary">Create your account</h2>
            <p className="mt-6 text-sm text-text-secondary">RadAssist-RAG · Radiologist workflow</p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-16">
            <label className="flex flex-col gap-8">
              <span className="text-sm text-text-secondary">Full name</span>
              <input required value={fullName} onChange={(e) => setFullName(e.target.value)} className={FIELD} />
            </label>

            <label className="flex flex-col gap-8">
              <span className="text-sm text-text-secondary">Email</span>
              <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={FIELD} />
            </label>

            <label className="flex flex-col gap-8">
              <span className="text-sm text-text-secondary">Password</span>
              <input
                required
                type="password"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={FIELD}
              />
            </label>

            <Button type="submit" variant="primary" size="lg" block loading={submitting}>
              {submitting ? "Creating account…" : "Create account"}
            </Button>
          </form>

          {error && (
            <p className="rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
              {error}
            </p>
          )}

          <p className="text-center text-sm text-text-secondary">
            Already have an account?{" "}
            <Link href="/login" className="text-cyan transition-colors duration-hover hover:text-text-primary">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
