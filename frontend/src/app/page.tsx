"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, getDashboardStats, getHealth } from "@/lib/api-client";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import type { paths } from "@/lib/generated/api";

type DashboardStatsResponse =
  paths["/dashboard/stats"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Dashboard (Phase 12 Step 2, real ownership counts added Phase 15).
 * Deliberately minimal: this is where a doctor starts, not a feature in
 * itself -- the design spec's full four-tile layout (§8.3: today's
 * examinations, awaiting-review queue, recent activity table) is not
 * built, since none of that data exists yet (no review-queue concept,
 * no "generated today" filter). What IS built is real, not invented:
 * GET /dashboard/stats (Phase 15) returns actual counts, replacing the
 * design spec's placeholder "38 of 142" style stat with the doctor's
 * genuine reports/patients vs. the shared registry's totals.
 *
 * Navigation actions use next/link styled with Button's own class recipe
 * (BUTTON_BASE/VARIANT/SIZE, exported for this reason) rather than the
 * Button component itself -- Button renders a real <button>, and nesting
 * an <a> inside one is invalid HTML/keyboard-navigation semantics.
 */
export default function Home() {
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "unreachable">(
    "checking",
  );
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then((response) => setBackendStatus(response.status === "ok" ? "ok" : "unreachable"))
      .catch(() => setBackendStatus("unreachable"));

    getDashboardStats()
      .then(setStats)
      .catch((err) => {
        // Not logged in (401) is expected before /login -- shown as "sign
        // in to see your stats," not a hard error banner on the Dashboard.
        if (err instanceof ApiError && err.status === 401) {
          setStatsError(null);
        } else {
          setStatsError(err instanceof ApiError ? err.message : "Failed to load dashboard stats.");
        }
      });
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center bg-paper">
      <main className="flex w-full max-w-xl flex-col items-center gap-10 px-page py-24">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-display text-ink">RadAssist-RAG</h1>
          <p className="text-ink-2">Radiologist Workflow Dashboard</p>
          <p className="text-sm text-ink-3">
            Backend:{" "}
            <span
              className={
                backendStatus === "ok"
                  ? "font-medium text-stable"
                  : backendStatus === "unreachable"
                    ? "font-medium text-critical"
                    : "font-medium"
              }
            >
              {backendStatus}
            </span>
          </p>
        </div>

        {stats && (
          <div className="grid w-full grid-cols-2 gap-4">
            <Card className="p-card text-center">
              <p className="text-eyebrow uppercase text-ink-3">Your reports</p>
              <p className="mt-1 text-h1 text-ink">
                {stats.my_reports}{" "}
                <span className="text-sm font-normal text-ink-3">of {stats.total_reports}</span>
              </p>
            </Card>
            <Card className="p-card text-center">
              <p className="text-eyebrow uppercase text-ink-3">Your patients</p>
              <p className="mt-1 text-h1 text-ink">
                {stats.my_patients}{" "}
                <span className="text-sm font-normal text-ink-3">of {stats.total_patients}</span>
              </p>
            </Card>
          </div>
        )}
        {statsError && (
          <p className="rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
            {statsError}
          </p>
        )}

        <div className="flex w-full flex-col gap-4">
          <Link
            href="/patients/search"
            className={cn(BUTTON_BASE, VARIANT.primary, SIZE.lg, "w-full")}
          >
            Find Patient
          </Link>
          <Link
            href="/patients/new"
            className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.lg, "w-full")}
          >
            Register New Patient
          </Link>
          <Link
            href="/settings"
            className={cn(BUTTON_BASE, VARIANT.ghost, SIZE.md, "w-full")}
          >
            Settings
          </Link>
        </div>
      </main>
    </div>
  );
}
