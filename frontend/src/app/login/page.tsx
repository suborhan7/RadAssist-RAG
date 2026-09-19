"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getHealth, loginDoctor } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { ServiceChip } from "@/components/ui/chip";
import { ChestXrayIllustration } from "@/components/ui/chest-xray-illustration";
import { useT } from "@/lib/i18n";
import type { paths } from "@/lib/generated/api";

type HealthResponse = paths["/health"]["get"]["responses"][200]["content"]["application/json"];
type ServiceStatus = { status: string; detail?: string | null } | null | undefined;

const FIELD = "h-46 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted";

function toChipState(status: string | undefined): "online" | "degraded" | "offline" {
  if (status === "ok") return "online";
  if (status === "degraded") return "degraded";
  return "offline";
}

function serviceValue(service: ServiceStatus): string {
  if (!service) return "n/a";
  return service.detail ?? service.status;
}

/**
 * Login (Phase 13b, ported to the Reading Room theme in the redesign step 4).
 * Split layout: the pure-black film panel left, form right (§6.1 -- the film
 * is the only pure-black surface). The service-status strip is genuinely all
 * four services (ServiceHealthService, §16.1), not fabricated dots. Error copy
 * follows "specific, does not apologise": the real 401 shows "Email or
 * password is incorrect.", never a generic failure. All auth logic unchanged.
 */
export default function LoginPage() {
  const router = useRouter();
  const { t } = useT();
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
      const redirectParam = new URLSearchParams(window.location.search).get("redirect");
      const destination =
        redirectParam && redirectParam.startsWith("/") && !redirectParam.startsWith("//")
          ? redirectParam
          : "/dashboard";
      router.push(destination);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError(t("login.errCredentials"));
      } else {
        setError(err instanceof ApiError ? err.message : t("login.errFailed"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-bg-app">
      {/* Film panel -- the only pure-black surface */}
      <div className="relative hidden flex-1 flex-col justify-between overflow-hidden on-film bg-bg-film px-50 py-44 lg:flex">
        <ChestXrayIllustration className="pointer-events-none absolute inset-0 h-full w-full opacity-50" />
        <div className="relative">
          <p className="font-mono text-eyebrow uppercase text-text-tertiary">RadAssist-RAG</p>
          <h1 className="mt-14 max-w-md text-display text-text-primary">
            {t("login.filmTitle")}
          </h1>
        </div>
        <div className="relative flex flex-col gap-16">
          <p className="max-w-md text-sm leading-relaxed text-text-secondary">
            {t("login.filmBody")}
          </p>
          <div className="max-w-md rounded-panel border border-strong bg-bg-raised px-16 py-14">
            <p className="font-mono text-mono-meta uppercase tracking-[0.14em] text-amber">
              {t("common.researchPrototype")}
            </p>
            <p className="mt-6 text-sm text-text-secondary">
              {t("login.notForClinical")}
            </p>
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="flex flex-1 flex-col items-center justify-center px-30 py-44">
        <div className="flex w-full max-w-sm flex-col gap-24">
          <div>
            <h2 className="text-page-title text-text-primary">{t("login.heading")}</h2>
            <p className="mt-6 text-sm text-text-secondary">{t("login.subtitle")}</p>
          </div>

          <div className="rounded-panel border border-hairline bg-bg-raised px-16 py-6">
            <p className="pt-8 font-mono text-eyebrow uppercase text-text-tertiary">{t("login.systemStatus")}</p>
            {healthUnreachable ? (
              <p className="py-12 text-sm text-amber">{t("login.backendUnreachable")}</p>
            ) : (
              <>
                <ServiceChip name="FastAPI" value={serviceValue(health?.fastapi)} state={toChipState(health?.fastapi?.status)} />
                <ServiceChip name="Ollama" value={serviceValue(health?.ollama)} state={toChipState(health?.ollama?.status)} />
                <ServiceChip name="ChromaDB" value={serviceValue(health?.chromadb)} state={toChipState(health?.chromadb?.status)} />
                <ServiceChip name="GPU" value={serviceValue(health?.gpu)} state={toChipState(health?.gpu?.status)} />
              </>
            )}
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-16">
            <label className="flex flex-col gap-8">
              <span className="text-sm text-text-secondary">{t("common.email")}</span>
              <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={FIELD} />
            </label>

            <label className="flex flex-col gap-8">
              <span className="text-sm text-text-secondary">{t("common.password")}</span>
              <input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={FIELD} />
            </label>

            <Button type="submit" variant="primary" size="lg" block loading={submitting}>
              {submitting ? t("login.signingIn") : t("login.heading")}
            </Button>
          </form>

          {error && (
            <p className="rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
              {error}
            </p>
          )}

          <p className="text-center text-sm text-text-secondary">
            {t("login.noAccount")}{" "}
            <Link href="/register" className="text-cyan transition-colors duration-hover hover:text-text-primary">
              {t("common.register")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
