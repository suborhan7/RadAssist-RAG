"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getCurrentDoctor, logoutDoctor } from "@/lib/api-client";
import { cn } from "@/lib/cn";

// "/" is the public Landing page and already renders its own slim
// header (with its own Sign in/Dashboard link) -- AppNavbar would be a
// redundant second header there.
const AUTH_FREE_ROUTES = new Set(["/", "/login", "/register"]);

/**
 * Persistent authenticated navbar -- §16.1's reopening (real, concrete
 * gap: this app previously had no navbar anywhere, only LogoutBar's
 * floating corner pill). Subsumes LogoutBar's own auth-check/route-
 * exclusion logic rather than running both side by side; logout-bar.tsx
 * is deleted once this replaces its one mount point in layout.tsx.
 *
 * Settings moves here (a doctor-name menu containing Settings + Log out)
 * out of the Dashboard's Quick Actions card, where it had no business
 * sitting next to clinical actions like "Register New Patient."
 */
export function AppNavbar() {
  const router = useRouter();
  const pathname = usePathname();
  const onAuthFreeRoute = AUTH_FREE_ROUTES.has(pathname);
  const [fetchedName, setFetchedName] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (!menuOpen) return;
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  const doctorName = onAuthFreeRoute ? null : fetchedName;

  if (!doctorName) return null;

  async function handleLogout() {
    setMenuOpen(false);
    setLoggingOut(true);
    try {
      await logoutDoctor();
    } finally {
      // This component is mounted once in the root layout and never
      // unmounts across the logout -> login -> re-authenticated
      // navigation (Next.js App Router layouts persist across route
      // changes) -- without resetting this, the next session would
      // inherit the stale `true` from this click.
      setLoggingOut(false);
      router.push("/login");
    }
  }

  return (
    <header className="sticky top-0 z-50 flex h-topbar items-center justify-between border-b border-hairline bg-surface px-page">
      <Link href="/dashboard" className="text-h3 text-ink">
        RadAssist<span className="font-mono text-ink-3">-RAG</span>
      </Link>

      <div ref={menuRef} className="relative">
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          className="flex items-center gap-2 rounded-full border border-hairline-strong bg-surface px-3 py-1.5 text-sm hover:bg-sunken"
        >
          <span className="text-ink-2">{doctorName}</span>
        </button>

        {menuOpen && (
          <div className="absolute right-0 top-full mt-2 w-44 rounded-card border border-hairline bg-surface p-1 shadow-e2">
            <Link
              href="/settings"
              onClick={() => setMenuOpen(false)}
              className="block rounded-in px-3 py-2 text-sm text-ink-2 hover:bg-sunken hover:text-ink"
            >
              Settings
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              disabled={loggingOut}
              className={cn(
                "block w-full rounded-in px-3 py-2 text-left text-sm text-ink-2 hover:bg-sunken hover:text-ink",
                loggingOut && "opacity-50",
              )}
            >
              {loggingOut ? "Signing out..." : "Log out"}
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
