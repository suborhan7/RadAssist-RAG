"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getHealth, loginDoctor } from "@/lib/api-client";

/**
 * Login (Phase 13b). Split layout per design_specification.md's actual
 * Login section (numbered 8.2 in that document, not 8.1 as
 * frontend/CLAUDE.md's citation says -- a citation slip, not a content
 * conflict, confirmed by reading the section directly): lightbox-style
 * panel left, form right.
 *
 * Service status strip (design spec: "FastAPI, Ollama, ChromaDB, GPU,
 * before authentication") is deliberately reduced to a single real
 * "Backend" check here, reusing the same GET /health call the existing
 * Dashboard (src/app/page.tsx) already makes -- there is no backend
 * endpoint that reports Ollama/ChromaDB/GPU reachability individually
 * (GET /health is liveness-only, per its own docstring), and fabricating
 * three more status dots with no real check behind them would show false
 * information rather than none. Flagged explicitly rather than silently
 * built as a fully-populated strip.
 *
 * Error copy follows the spec's "specific, does not apologise" rule:
 * the real 401 from POST /auth/login (InvalidCredentialsError,
 * deliberately identical for "no such email" and "wrong password", per
 * Phase 13a) is shown as "Email or password is incorrect.", never a
 * generic failure message.
 */
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "unreachable">(
    "checking",
  );

  useEffect(() => {
    getHealth()
      .then((response) => setBackendStatus(response.status === "ok" ? "ok" : "unreachable"))
      .catch(() => setBackendStatus("unreachable"));
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await loginDoctor({ email, password });
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Email or password is incorrect.");
      } else {
        setError(err instanceof ApiError ? err.message : "Login failed.");
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
            <h2 className="text-2xl font-semibold text-black dark:text-zinc-50">Sign in</h2>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              RadAssist-RAG · Radiologist Workflow
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-800 dark:bg-zinc-900">
            <span
              className={
                "h-2 w-2 rounded-full " +
                (backendStatus === "ok"
                  ? "bg-green-500"
                  : backendStatus === "unreachable"
                    ? "bg-red-500"
                    : "bg-zinc-400")
              }
            />
            <span className="text-zinc-700 dark:text-zinc-300">
              Backend:{" "}
              <span className="font-medium">
                {backendStatus === "checking" ? "checking..." : backendStatus}
              </span>
            </span>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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
              {submitting ? "Signing in..." : "Sign in"}
            </button>
          </form>

          {error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
              {error}
            </p>
          )}

          <p className="text-center text-sm text-zinc-600 dark:text-zinc-400">
            No account?{" "}
            <Link href="/register" className="font-medium text-black underline dark:text-zinc-50">
              Register
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
