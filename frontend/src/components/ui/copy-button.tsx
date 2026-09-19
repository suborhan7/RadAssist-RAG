"use client";

import { useEffect, useState } from "react";
import { CheckIcon, CopyIcon } from "@/components/layout/rail-icons";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";

/**
 * Copy-to-clipboard control for generated text, in the shape people already
 * know from chat assistants: a quiet button that confirms in place rather than
 * firing a toast. The label swaps to "Copied" for two seconds and reverts.
 *
 * It never claims a success it did not get. `navigator.clipboard` needs a
 * secure context, and although http://localhost qualifies, a denied permission
 * or an older browser still rejects -- so the failure path says so instead of
 * showing the tick anyway. A control that lies about having copied is worse
 * than one that admits it could not.
 */
export function CopyButton({
  text,
  className,
  labelledBy,
}: {
  text: string;
  className?: string;
  /** Optional context for the accessible name, e.g. the question that was asked. */
  labelledBy?: string;
}) {
  const { t } = useT();
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (state === "idle") return;
    const timer = setTimeout(() => setState("idle"), 2000);
    return () => clearTimeout(timer);
  }, [state]);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
  }

  const label =
    state === "copied" ? t("common.copied") : state === "failed" ? t("common.copyFailed") : t("common.copy");

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={labelledBy ? `${label} — ${labelledBy}` : label}
      // Announce the outcome to screen readers, which cannot see the icon swap.
      aria-live="polite"
      className={cn(
        "flex items-center gap-8 rounded-control px-10 py-6 text-sm transition-colors duration-hover",
        state === "copied"
          ? "text-cyan"
          : state === "failed"
            ? "text-amber"
            : "text-text-tertiary hover:bg-bg-hover hover:text-text-primary",
        className,
      )}
    >
      {state === "copied" ? <CheckIcon className="flex-none" /> : <CopyIcon className="flex-none" />}
      <span>{label}</span>
    </button>
  );
}
