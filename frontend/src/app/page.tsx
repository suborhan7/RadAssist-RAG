"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getCurrentDoctor } from "@/lib/api-client";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { Tag } from "@/components/ui/chip";
import { ChestXrayIllustration } from "@/components/ui/chest-xray-illustration";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";

/**
 * Public Landing page (design_specification.md §8.1, ported to the Reading
 * Room theme in the redesign step 4). "The hero shows proof, not stats": the
 * proof card is a static illustrative example (there is no logged-out report
 * to show), styled the way a real cited sentence would look, not a fabricated
 * live claim. If already authenticated the CTA swaps to the dashboard rather
 * than forcing a redirect. Auth-state logic unchanged.
 */
export default function LandingPage() {
  const { t } = useT();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    getCurrentDoctor()
      .then((doctor) => setIsAuthenticated(!!doctor))
      .catch(() => setIsAuthenticated(false));
  }, []);

  const primaryHref = isAuthenticated ? "/dashboard" : "/login";
  const primaryLabel = isAuthenticated ? t("landing.ctaDashboard") : t("landing.ctaSignIn");

  // Product names (BiomedCLIP, ChromaDB) are never translated; the rest are.
  const pipelineStages = [
    t("landing.stageChestXray"),
    t("landing.stagePhi"),
    "BiomedCLIP",
    "ChromaDB",
    t("landing.stageSimilar"),
    t("landing.stageAiDraft"),
    t("landing.stageReview"),
  ];

  return (
    <div className="flex min-h-screen flex-col bg-bg-app">
      {/* Slim header */}
      <header className="flex h-header-landing flex-none items-center justify-between border-b border-hairline px-30">
        <span className="text-screen-title text-text-primary">
          RadAssist<span className="font-mono text-text-tertiary">-RAG</span>
        </span>
        <Link href={primaryHref} className={cn(BUTTON_BASE, VARIANT.primary, SIZE.sm)}>
          {isAuthenticated ? t("landing.headerCtaDashboard") : t("landing.headerCtaSignIn")}
        </Link>
      </header>

      {/* Hero */}
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-30 px-30 py-44 lg:flex-row lg:items-center">
        <div className="flex flex-1 flex-col gap-24">
          <h1 className="max-w-xl text-display text-text-primary">
            {t("landing.heroTitle")}
          </h1>
          <p className="max-w-md text-prose text-text-secondary">
            {t("landing.heroSubtitle")}
          </p>

          {/* Proof card -- one real-looking cited sentence, not a stat row */}
          <div className="max-w-md rounded-panel border border-hairline bg-bg-raised p-20">
            <Tag tone="steel">{t("landing.aiDraft")}</Tag>
            <p className="mt-14 text-findings text-text-secondary">
              <span className="underline decoration-cyan decoration-dotted underline-offset-4">
                {t("landing.proofPhrase1")}
              </span>
              <sup className="ml-2 font-mono text-mono-meta text-cyan">1,3</sup>
              {t("landing.proofConnective")}
              <span className="underline decoration-cyan decoration-dotted underline-offset-4">
                {t("landing.proofPhrase2")}
              </span>
              <sup className="ml-2 font-mono text-mono-meta text-cyan">1,2,3</sup>.
            </p>
            <div className="mt-14 flex flex-wrap gap-8">
              <Tag tone="steel">CXR-2117 · 97.4%</Tag>
              <Tag tone="steel">CXR-0884 · 95.9%</Tag>
              <Tag tone="steel">CXR-3390 · 94.2%</Tag>
            </div>
            <p className="mt-14 text-sm text-text-tertiary">
              {t("landing.proofTrace")}
            </p>
          </div>

          <div className="flex flex-col gap-8">
            <Link href={primaryHref} className={cn(BUTTON_BASE, VARIANT.primary, SIZE.lg, "w-fit")}>
              {primaryLabel}
            </Link>
            <p className="text-sm text-text-tertiary">
              {t("landing.neverFinalized")}
            </p>
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center overflow-hidden rounded-panel on-film bg-bg-film">
          <ChestXrayIllustration className="h-[420px] w-full" />
        </div>
      </div>

      {/* Pipeline strip */}
      <div className="flex-none border-t border-hairline bg-bg-raised px-30 py-16">
        <div className="mx-auto flex max-w-6xl flex-col gap-12 overflow-x-auto">
          <p className="font-mono text-eyebrow uppercase text-text-tertiary">{t("landing.pipelineTitle")}</p>
          <div className="flex gap-8">
            {pipelineStages.map((stage, i) => {
              const isLast = i === pipelineStages.length - 1;
              return (
                <div
                  key={stage}
                  className={cn(
                    "flex shrink-0 items-center justify-center rounded-field border px-14 py-12 text-center text-sm",
                    isLast
                      ? "border-cyan-line bg-cyan-wash text-cyan"
                      : "border-hairline bg-bg-hover text-text-secondary",
                  )}
                  style={{ flex: isLast ? 1.6 : 1 }}
                >
                  {stage}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="flex-none border-t border-hairline px-30 py-16 text-center text-sm text-text-tertiary">
        {t("landing.footer")}
        <br />
        Brac University · Department of Computer Science and Engineering
      </footer>
    </div>
  );
}
