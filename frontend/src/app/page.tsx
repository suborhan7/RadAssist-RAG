"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api-client";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { cn } from "@/lib/cn";

/**
 * Dashboard (Phase 12 Step 2). Entry point only -- real health-check
 * status (reused from Step 1) plus navigation into Search/Register.
 * Deliberately minimal: this is where a doctor starts, not a feature in
 * itself.
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

  useEffect(() => {
    getHealth()
      .then((response) => setBackendStatus(response.status === "ok" ? "ok" : "unreachable"))
      .catch(() => setBackendStatus("unreachable"));
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
        </div>
      </main>
    </div>
  );
}
