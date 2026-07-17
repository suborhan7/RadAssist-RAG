"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getHealth, loginDoctor } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

/**
 * Login (Phase 13b, restyled Phase 14). Split layout per
 * design_specification.md's actual Login section (§8.2 in that document,
 * not §8.1 as frontend/CLAUDE.md's citation says -- a citation slip, not
 * a content conflict, confirmed by reading the section directly): the
 * lightbox-black panel left, form right, per §6.1's "Paper & Lightbox"
 * direction (the lightbox is the only dark surface in the product).
 *
 * Service status strip (design spec: "FastAPI, Ollama, ChromaDB, GPU,
 * before authentication") is deliberately reduced to a single real
 * "Backend" check here, reusing the same GET /health call the existing
 * Dashboard (src/app/page.tsx) already makes -- there is no backend
 * endpoint that reports Ollama/ChromaDB/GPU reachability individually
 * (GET /health is liveness-only, per its own docstring), and fabricating
 * three more status dots with no real check behind them would show false
 * information rather than none.
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
            <h2 className="text-h1 text-ink">Sign in</h2>
            <p className="mt-1 text-sm text-ink-2">RadAssist-RAG &middot; Radiologist Workflow</p>
          </div>

          <div className="flex items-center gap-2 rounded-card border border-hairline bg-surface px-3 py-2 text-sm">
            <span
              className={
                "h-1.5 w-1.5 rounded-full " +
                (backendStatus === "ok"
                  ? "bg-stable"
                  : backendStatus === "unreachable"
                    ? "bg-critical"
                    : "bg-ink-3")
              }
            />
            <span className="text-ink-2">
              Backend:{" "}
              <span className="font-medium text-ink">
                {backendStatus === "checking" ? "checking..." : backendStatus}
              </span>
            </span>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
              />
            </label>

            <Button type="submit" variant="primary" size="lg" block loading={submitting} className="mt-2">
              {submitting ? "Signing in..." : "Sign in"}
            </Button>
          </form>

          {error && (
            <p className="rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
              {error}
            </p>
          )}

          <p className="text-center text-sm text-ink-2">
            No account?{" "}
            <Link href="/register" className="font-medium text-ink underline">
              Register
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
