"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getHealth, loginDoctor } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { ServiceChip } from "@/components/ui/chip";
import { ChestXrayIllustration } from "@/components/ui/chest-xray-illustration";
import type { paths } from "@/lib/generated/api";

type HealthResponse = paths["/health"]["get"]["responses"][200]["content"]["application/json"];
type ServiceStatus = { status: string; detail?: string | null } | null | undefined;

function toChipState(status: string | undefined): "online" | "degraded" | "offline" {
  if (status === "ok") return "online";
  if (status === "degraded") return "degraded";
  return "offline";
}

function serviceValue(service: ServiceStatus): string {
  if (!service) return "--";
  return service.detail ?? service.status;
}

/**
 * Login (Phase 13b, restyled Phase 14, given the real §8.2 treatment
 * under §16.1's reopening). Split layout per design_specification.md's
 * actual Login section (§8.2 in that document, not §8.1 as
 * frontend/CLAUDE.md's citation says -- a citation slip, not a content
 * conflict, confirmed by reading the section directly): the
 * lightbox-black panel left, form right, per §6.1's "Paper & Lightbox"
 * direction (the lightbox is the only dark surface in the product).
 *
 * Service status strip (design spec: "FastAPI, Ollama, ChromaDB, GPU,
 * before authentication") is now genuinely all four -- previously
 * reduced to a single "Backend" check because GET /health had no per-
 * service reachability logic (its own former comment called this "a
 * documented future improvement"); §16.1 built that improvement
 * (ServiceHealthService) rather than fabricate three more status dots
 * with nothing real behind them.
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
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthUnreachable, setHealthUnreachable] = useState(false);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealthUnreachable(true));
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await loginDoctor({ email, password });
      // Read directly from window.location rather than useSearchParams() --
      // avoids the Suspense-boundary requirement that hook imposes, for a
      // value only ever needed once, after a real user submit.
      const redirectParam = new URLSearchParams(window.location.search).get("redirect");
      const destination =
        redirectParam && redirectParam.startsWith("/") && !redirectParam.startsWith("//")
          ? redirectParam
          : "/dashboard";
      router.push(destination);
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
      <div className="relative hidden flex-1 flex-col justify-between overflow-hidden bg-lightbox px-12 py-16 text-lightbox-ink lg:flex">
        <ChestXrayIllustration className="pointer-events-none absolute inset-0 h-full w-full opacity-50" />
        <div className="relative">
          <p className="text-eyebrow uppercase text-lightbox-ink-2">RadAssist-RAG</p>
          <h1 className="mt-4 max-w-md text-display text-white">
            Retrieval-grounded chest X-ray reporting.
          </h1>
        </div>
        <div className="relative flex flex-col gap-4">
          <p className="max-w-md text-sm text-lightbox-ink-2">
            Every AI draft cites the retrieved cases it was grounded in. 0 reports have ever been
            finalised without a radiologist.
          </p>
          <div className="max-w-md rounded-card border border-lightbox-bd bg-lightbox-chrome px-3 py-2">
            <p className="font-mono text-data-sm uppercase text-caution-fill">Research prototype</p>
            <p className="mt-1 text-sm text-lightbox-ink-2">
              Not for clinical use. Every report requires review by a qualified radiologist.
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center bg-paper px-page py-16">
        <div className="flex w-full max-w-sm flex-col gap-6">
          <div>
            <h2 className="text-h1 text-ink">Sign in</h2>
            <p className="mt-1 text-sm text-ink-2">RadAssist-RAG &middot; Radiologist Workflow</p>
          </div>

          <div className="rounded-card border border-hairline bg-surface px-3 py-1">
            <p className="pt-1.5 text-eyebrow uppercase text-ink-3">System status</p>
            {healthUnreachable ? (
              <p className="py-2 text-sm text-critical-ink">Backend unreachable.</p>
            ) : (
              <>
                <ServiceChip name="FastAPI" value={serviceValue(health?.fastapi)} state={toChipState(health?.fastapi?.status)} />
                <ServiceChip name="Ollama" value={serviceValue(health?.ollama)} state={toChipState(health?.ollama?.status)} />
                <ServiceChip name="ChromaDB" value={serviceValue(health?.chromadb)} state={toChipState(health?.chromadb?.status)} />
                <ServiceChip name="GPU" value={serviceValue(health?.gpu)} state={toChipState(health?.gpu?.status)} />
              </>
            )}
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
