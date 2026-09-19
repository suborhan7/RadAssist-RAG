"use client";

import { usePathname } from "next/navigation";
import { CHROMELESS_ROUTES } from "@/lib/chromeless-routes";
import { AppRail } from "./app-rail";

/**
 * The app frame. Landing / Sign in / Register are full-bleed and render their
 * own chrome, so the rail is suppressed there (same exclusion the old
 * AppNavbar carried). Every other route sits inside the rail + scrolling main
 * layout. When AppRail returns null (no authenticated doctor), main simply
 * fills the width and the page handles its own redirect, exactly as before.
 *
 * The route set lives in lib/chromeless-routes.ts because DoctorProvider needs
 * it too and importing this module would close a cycle through AppRail.
 */

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (CHROMELESS_ROUTES.has(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      <AppRail />
      <main className="flex min-w-0 flex-1 flex-col bg-bg-app">{children}</main>
    </div>
  );
}
