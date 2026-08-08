"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getCurrentDoctor } from "@/lib/api-client";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { Tag } from "@/components/ui/chip";
import { ChestXrayIllustration } from "@/components/ui/chest-xray-illustration";
import { cn } from "@/lib/cn";

const PIPELINE_STAGES = [
  "Chest X-ray",
  "PHI protection",
  "BiomedCLIP",
  "ChromaDB",
  "Similar cases",
  "AI draft",
  "Radiologist review",
];

/**
 * Public Landing page (design_specification.md §8.1, ported to the Reading
 * Room theme in the redesign step 4). "The hero shows proof, not stats": the
 * proof card is a static illustrative example (there is no logged-out report
 * to show), styled the way a real cited sentence would look, not a fabricated
 * live claim. If already authenticated the CTA swaps to the dashboard rather
 * than forcing a redirect. Auth-state logic unchanged.
 */
export default function LandingPage() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    getCurrentDoctor()
      .then((doctor) => setIsAuthenticated(!!doctor))
      .catch(() => setIsAuthenticated(false));
  }, []);

  const primaryHref = isAuthenticated ? "/dashboard" : "/login";
  const primaryLabel = isAuthenticated ? "Go to your dashboard" : "Sign in to your workspace";

  return (
    <div className="flex min-h-screen flex-col bg-bg-app">
      {/* Slim header */}
      <header className="flex h-header-landing flex-none items-center justify-between border-b border-hairline px-30">
        <span className="text-screen-title text-text-primary">
          RadAssist<span className="font-mono text-text-tertiary">-RAG</span>
        </span>
        <Link href={primaryHref} className={cn(BUTTON_BASE, VARIANT.primary, SIZE.sm)}>
          {isAuthenticated ? "Dashboard" : "Sign in"}
        </Link>
      </header>

      {/* Hero */}
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-30 px-30 py-44 lg:flex-row lg:items-center">
        <div className="flex flex-1 flex-col gap-24">
          <h1 className="max-w-xl text-display text-text-primary">
            Evidence-grounded chest X-ray reporting.
          </h1>
          <p className="max-w-md text-prose text-text-secondary">
            Every AI draft is grounded in real, retrieved prior cases. Never generated from nothing,
            and never signed without a radiologist.
          </p>

          {/* Proof card -- one real-looking cited sentence, not a stat row */}
          <div className="max-w-md rounded-panel border border-hairline bg-bg-raised p-20">
            <Tag tone="steel">AI Draft</Tag>
            <p className="mt-14 text-findings text-text-secondary">
              <span className="underline decoration-cyan decoration-dotted underline-offset-4">
                Diffuse interstitial markings are prominent throughout both lungs
              </span>
              <sup className="ml-2 font-mono text-mono-meta text-cyan">1,3</sup>
              {", consistent with "}
              <span className="underline decoration-cyan decoration-dotted underline-offset-4">
                fibrotic change rather than acute infection
              </span>
              <sup className="ml-2 font-mono text-mono-meta text-cyan">1,2,3</sup>.
            </p>
            <div className="mt-14 flex flex-wrap gap-8">
              <Tag tone="steel">CXR-2117 · 97.4%</Tag>
              <Tag tone="steel">CXR-0884 · 95.9%</Tag>
              <Tag tone="steel">CXR-3390 · 94.2%</Tag>
            </div>
            <p className="mt-14 text-sm text-text-tertiary">
              Every underlined statement traces to the retrieved cases that support it.
            </p>
          </div>

          <div className="flex flex-col gap-8">
            <Link href={primaryHref} className={cn(BUTTON_BASE, VARIANT.primary, SIZE.lg, "w-fit")}>
              {primaryLabel}
            </Link>
            <p className="text-sm text-text-tertiary">
              0 reports have ever been finalised without a radiologist.
            </p>
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center overflow-hidden rounded-panel bg-bg-film">
          <ChestXrayIllustration className="h-[420px] w-full" />
        </div>
      </div>

      {/* Pipeline strip */}
      <div className="flex-none border-t border-hairline bg-bg-raised px-30 py-16">
        <div className="mx-auto flex max-w-6xl flex-col gap-12 overflow-x-auto">
          <p className="font-mono text-eyebrow uppercase text-text-tertiary">How a report is grounded</p>
          <div className="flex gap-8">
            {PIPELINE_STAGES.map((stage, i) => {
              const isLast = i === PIPELINE_STAGES.length - 1;
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
        Research prototype. Not for clinical use. Every report requires review by a qualified
        radiologist.
        <br />
        Brac University · Department of Computer Science and Engineering
      </footer>
    </div>
  );
}
