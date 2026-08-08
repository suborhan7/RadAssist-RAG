"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ComponentType } from "react";
import { getCurrentDoctor, logoutDoctor } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import {
  QueueIcon,
  SearchIcon,
  PatientsIcon,
  NewExamIcon,
  WorkspaceIcon,
  ExplainIcon,
  CompareIcon,
  SettingsIcon,
  SignOutIcon,
} from "./rail-icons";

export type DoctorInfo = { full_name: string; bmdc_number?: string | null };

export type NavItem = {
  key: string;
  label: string;
  Icon: ComponentType<{ className?: string }>;
  href: string | null; // null => present but non-navigable (no context id in URL)
  active: boolean;
};

/**
 * "Reading Room" left rail -- 224px, always open (not collapsible: the README
 * records that collapsing was tried and deliberately removed). Present on every
 * app screen; AppShell keeps it off Landing / Sign in / Register.
 *
 * Split into a data container (AppRail) and a pure presentational view
 * (RailView) so the shell can be previewed with stub data without the auth
 * fetch -- the view is what /dev/shell-preview renders, so the preview can't
 * drift from production.
 */
export function AppRail() {
  const router = useRouter();
  const pathname = usePathname();
  const [doctor, setDoctor] = useState<DoctorInfo | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCurrentDoctor()
      .then((d) => {
        if (!cancelled) setDoctor(d ? { full_name: d.full_name, bmdc_number: d.bmdc_number } : null);
      })
      .catch(() => {
        if (!cancelled) setDoctor(null);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  if (!doctor) return null;

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logoutDoctor();
    } finally {
      setLoggingOut(false);
      router.push("/login");
    }
  }

  return (
    <RailView
      doctor={doctor}
      nav={buildNav(pathname)}
      settingsActive={pathname === "/settings"}
      loggingOut={loggingOut}
      onLogout={handleLogout}
    />
  );
}

/**
 * Five of the seven nav destinations are contextual (they need a patient or
 * report id). When the current URL supplies that id the item links and lights;
 * otherwise it renders in the rest style but is non-navigable, so the rail
 * looks complete on every screen without inventing a destination that doesn't
 * exist. (Flagged for review -- the prototype's single-canvas nav sidesteps
 * this because it has no real routing.)
 */
export function buildNav(pathname: string): NavItem[] {
  const patientMatch = pathname.match(/^\/patients\/([^/]+)/);
  const patientId =
    patientMatch && patientMatch[1] !== "search" && patientMatch[1] !== "new" ? patientMatch[1] : null;
  const reportMatch = pathname.match(/^\/reports\/([^/]+)/);
  const reportId = reportMatch ? reportMatch[1] : null;

  const isPatientProfile = patientId != null && /^\/patients\/[^/]+$/.test(pathname);
  const isUpload = patientId != null && /^\/patients\/[^/]+\/upload$/.test(pathname);
  const isWorkspace = reportId != null && /^\/reports\/[^/]+$/.test(pathname);
  const isExplain = reportId != null && /\/explain$/.test(pathname);
  const isCompare = reportId != null && /\/compare$/.test(pathname);

  return [
    { key: "queue", label: "Queue", Icon: QueueIcon, href: "/dashboard", active: pathname === "/dashboard" },
    { key: "find", label: "Find patient", Icon: SearchIcon, href: "/patients/search", active: pathname === "/patients/search" },
    { key: "patients", label: "Patients", Icon: PatientsIcon, href: patientId ? `/patients/${patientId}` : null, active: isPatientProfile },
    { key: "new-exam", label: "New examination", Icon: NewExamIcon, href: patientId ? `/patients/${patientId}/upload` : null, active: isUpload },
    { key: "workspace", label: "Workspace", Icon: WorkspaceIcon, href: reportId ? `/reports/${reportId}` : null, active: isWorkspace },
    { key: "explain", label: "Explainability", Icon: ExplainIcon, href: reportId ? `/reports/${reportId}/explain` : null, active: isExplain },
    { key: "compare", label: "Compare", Icon: CompareIcon, href: reportId ? `/reports/${reportId}/compare` : null, active: isCompare },
  ];
}

/** Pure presentational rail. All data and handlers are injected. */
export function RailView({
  doctor,
  nav,
  settingsActive,
  loggingOut,
  onLogout,
}: {
  doctor: DoctorInfo;
  nav: NavItem[];
  settingsActive: boolean;
  loggingOut: boolean;
  onLogout: () => void;
}) {
  const bmdcLine = doctor.bmdc_number ? `BMDC ${doctor.bmdc_number}` : null;

  return (
    <aside className="sticky top-0 flex h-screen w-rail flex-none flex-col border-r border-hairline bg-bg-app">
      {/* Header: cyan glow dot + wordmark */}
      <div className="flex h-header-bar flex-none items-center gap-12 border-b border-hairline pl-18 pr-12">
        <span className="h-9 w-9 flex-none rounded-full bg-cyan shadow-glow" aria-hidden />
        <span className="text-base font-semibold tracking-[-0.01em] text-text-primary">RadAssist</span>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-3 overflow-auto p-14">
        {nav.map((item) => (
          <RailItem key={item.key} item={item} />
        ))}
      </nav>

      {/* Footer: Settings, Sign out, profile */}
      <div className="flex-none border-t border-hairline p-14">
        <RailItem
          item={{
            key: "settings",
            label: "Settings",
            Icon: SettingsIcon,
            href: "/settings",
            active: settingsActive,
          }}
        />
        <button
          type="button"
          onClick={onLogout}
          disabled={loggingOut}
          className={cn(
            "flex w-full items-center gap-12 rounded-control px-12 py-9 text-sm font-normal text-text-tertiary transition-colors duration-hover hover:bg-bg-hover",
            loggingOut && "opacity-50",
          )}
        >
          <SignOutIcon className="flex-none" />
          <span>{loggingOut ? "Signing out…" : "Sign out"}</span>
        </button>

        {/* Profile -- routes to /settings. Avatar here is display-only. */}
        <Link
          href="/settings"
          className="mt-9 flex items-center gap-12 border-t border-hairline px-12 pb-3 pt-12 transition-colors duration-hover hover:bg-bg-hover"
        >
          <span className="h-[32px] w-[32px] flex-none overflow-hidden rounded-full bg-border" aria-hidden />
          <span className="min-w-0">
            <span className="block truncate text-caption font-medium text-text-primary">{doctor.full_name}</span>
            {bmdcLine && <span className="block font-mono text-mono-meta text-text-tertiary">{bmdcLine}</span>}
          </span>
        </Link>
      </div>
    </aside>
  );
}

function RailItem({ item }: { item: NavItem }) {
  const cls = cn(
    "flex items-center gap-12 rounded-control px-12 py-9 text-sm transition-colors duration-hover",
    item.active
      ? "bg-cyan-wash font-medium text-cyan"
      : "font-normal text-text-secondary hover:bg-bg-hover",
    item.href == null && "cursor-default text-text-muted hover:bg-transparent",
  );
  const inner = (
    <>
      <item.Icon className="flex-none" />
      <span className="truncate">{item.label}</span>
    </>
  );

  if (item.href == null) {
    return (
      <span className={cls} aria-disabled>
        {inner}
      </span>
    );
  }
  return (
    <Link href={item.href} className={cls} aria-current={item.active ? "page" : undefined}>
      {inner}
    </Link>
  );
}
