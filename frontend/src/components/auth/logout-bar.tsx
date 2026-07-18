"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentDoctor, logoutDoctor } from "@/lib/api-client";
import { cn } from "@/lib/cn";

const AUTH_FREE_ROUTES = new Set(["/login", "/register"]);

/**
 * Coverage-check item #1 (screen 19, "Profile menu"): this is deliberately
 * NOT that screen -- no dropdown, no persistent nav rail, none of that
 * scope. It's the smallest real fix for the actual gap found: there was
 * no logout action ANYWHERE in this app (grepped clean). Mounted once in
 * the root layout so it's reachable from every authenticated screen
 * without a shared app shell existing yet -- a single fixed corner
 * control, shown only when a doctor is actually signed in.
 */
export function LogoutBar() {
  const router = useRouter();
  const pathname = usePathname();
  const onAuthFreeRoute = AUTH_FREE_ROUTES.has(pathname);
  const [fetchedName, setFetchedName] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    if (onAuthFreeRoute) return;
    let cancelled = false;
    getCurrentDoctor()
      .then((doctor) => {
        if (!cancelled) setFetchedName(doctor?.full_name ?? null);
      })
      .catch(() => {
        if (!cancelled) setFetchedName(null);
      });
    return () => {
      cancelled = true;
    };
  }, [onAuthFreeRoute]);

  // Derived, not stored -- so a redirect straight to /login after logout
  // never shows a stale name for one render before the effect above
  // would otherwise have cleared it.
  const doctorName = onAuthFreeRoute ? null : fetchedName;

  if (!doctorName) return null;

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logoutDoctor();
    } finally {
      router.push("/login");
    }
  }

  return (
    <div className="fixed right-3 top-3 z-50 flex items-center gap-2 rounded-full border border-hairline-strong bg-surface px-3 py-1.5 text-sm shadow-popover">
      <span className="text-ink-2">{doctorName}</span>
      <button
        type="button"
        onClick={handleLogout}
        disabled={loggingOut}
        className={cn(
          "font-medium text-ink underline decoration-hairline-strong underline-offset-2 hover:text-steel-ink",
          loggingOut && "opacity-50",
        )}
      >
        {loggingOut ? "Signing out..." : "Log out"}
      </button>
    </div>
  );
}
