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
 * Public Landing page (design_specification.md §8.1) -- newly built
 * under §16.1's reopening. Previously did not exist at all: `/` was the
 * Dashboard, and no public marketing/entry route was ever built despite
 * §8.1 specifying one. The Dashboard moved to `/dashboard`; this is a
 * genuinely public route (proxy.ts's PUBLIC_PATHS), reachable logged out.
 *
 * Per §8.1 verbatim: "The hero shows proof, not stats." A three-stat row
 * was rejected there in favor of one real grounded sentence with citation
 * styling -- this page's "proof card" is a static illustrative example
 * (not live data; there is no logged-out report to show), styled the way
 * a real cited sentence would look, not a fabricated live claim.
 *
 * If already authenticated, the CTA swaps to "Go to your Dashboard"
 * rather than forcing a redirect -- avoids redirect-loop edge cases and
 * matches how AppNavbar already conditionally renders on auth state.
 */
export default function LandingPage() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    getCurrentDoctor()
      .then((doctor) => setIsAuthenticated(!!doctor))
      .catch(() => setIsAuthenticated(false));
  }, []);

  const primaryHref = isAuthenticated ? "/dashboard" : "/login";
  const primaryLabel = isAuthenticated ? "Go to your Dashboard" : "Sign in to your workspace";

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      {/* Slim header */}
      <header className="flex h-topbar items-center justify-between border-b border-hairline px-page">
        <span className="text-h3 text-ink">
          RadAssist<span className="font-mono text-ink-3">-RAG</span>
        </span>
        <Link href={primaryHref} className={cn(BUTTON_BASE, VARIANT.primary, SIZE.sm)}>
          {isAuthenticated ? "Dashboard" : "Sign in"}
        </Link>
      </header>

      {/* Hero */}
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-12 px-page py-16 lg:flex-row lg:items-center">
        <div className="flex flex-1 flex-col gap-6">
          <h1 className="max-w-lg text-hero text-ink">
            Evidence-grounded chest X-ray reporting.
          </h1>
          <p className="max-w-md text-ink-2">
            Every AI draft is grounded in real, retrieved prior cases -- not generated from
            nothing, and never signed without a radiologist.
          </p>

          {/* Proof card -- one real-looking cited sentence, not a stat row */}
          <div className="max-w-md rounded-card border border-hairline bg-surface p-card">
            <Tag tone="steel">AI Draft</Tag>
            <p className="mt-3 text-report text-ink-2">
              <span className="underline decoration-steel decoration-dotted underline-offset-4">
                Diffuse interstitial markings are prominent throughout both lungs
              </span>
              <sup className="ml-0.5 font-mono text-data-sm text-steel-ink">1,3</sup>
              {", consistent with "}
              <span className="underline decoration-steel decoration-dotted underline-offset-4">
                fibrotic change rather than acute infection
              </span>
              <sup className="ml-0.5 font-mono text-data-sm text-steel-ink">1,2,3</sup>.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Tag tone="steel">CXR-2117 &middot; 97.4%</Tag>
              <Tag tone="steel">CXR-0884 &middot; 95.9%</Tag>
              <Tag tone="steel">CXR-3390 &middot; 94.2%</Tag>
            </div>
            <p className="mt-3 text-sm text-ink-3">
              Every underlined statement traces to the retrieved cases that support it.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Link href={primaryHref} className={cn(BUTTON_BASE, VARIANT.primary, SIZE.lg, "w-fit")}>
              {primaryLabel}
            </Link>
            <p className="text-sm text-ink-3">0 reports have ever been finalised without a radiologist.</p>
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center overflow-hidden rounded-card bg-lightbox">
          <ChestXrayIllustration className="h-[420px] w-full" />
        </div>
      </div>

      {/* Pipeline strip */}
      <div className="border-t border-hairline bg-surface px-page py-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 overflow-x-auto">
          <p className="text-eyebrow uppercase text-ink-3">How a report is grounded</p>
          <div className="flex gap-2">
            {PIPELINE_STAGES.map((stage, i) => {
              const isLast = i === PIPELINE_STAGES.length - 1;
              return (
                <div
                  key={stage}
                  className={cn(
                    "flex shrink-0 items-center justify-center rounded-card border px-3 py-2 text-center text-sm",
                    isLast
                      ? "border-steel-bd bg-steel-tint text-steel-ink"
                      : "border-hairline bg-sunken text-ink-2",
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
      <footer className="border-t border-hairline px-page py-6 text-center text-sm text-ink-3">
        Research prototype. Not for clinical use. Every report requires review by a qualified
        radiologist.
        <br />
        Brac University &middot; Department of Computer Science and Engineering
      </footer>
    </div>
  );
}
