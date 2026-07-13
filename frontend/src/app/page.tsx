"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api-client";

/**
 * Dashboard (Phase 12 Step 2). Entry point only -- real health-check
 * status (reused from Step 1) plus navigation into Search/Register.
 * Deliberately minimal: this is where a doctor starts, not a feature in
 * itself.
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
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-xl flex-col items-center gap-10 px-6 py-24">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-3xl font-semibold text-black dark:text-zinc-50">
            RadAssist-RAG
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400">
            Radiologist Workflow Dashboard
          </p>
          <p className="text-sm text-zinc-500 dark:text-zinc-500">
            Backend:{" "}
            <span
              className={
                backendStatus === "ok"
                  ? "font-medium text-green-600 dark:text-green-500"
                  : backendStatus === "unreachable"
                    ? "font-medium text-red-600 dark:text-red-500"
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
            className="flex h-14 w-full items-center justify-center rounded-lg bg-black px-5 text-base font-medium text-white transition-colors hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            Find Patient
          </Link>
          <Link
            href="/patients/new"
            className="flex h-14 w-full items-center justify-center rounded-lg border border-zinc-300 px-5 text-base font-medium text-black transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-900"
          >
            Register New Patient
          </Link>
        </div>
      </main>
    </div>
  );
}
