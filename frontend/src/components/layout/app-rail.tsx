"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ComponentType } from "react";
import { logoutDoctor } from "@/lib/api-client";
import { useDoctor } from "@/lib/doctor";
import { useT } from "@/lib/i18n";
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
  label: string; // an i18n key (e.g. "nav.queue"); translated at render in RailItem
  Icon: ComponentType<{ className?: string }>;
  href: string;
  active: boolean;
  /**
   * i18n key for "what this item needs before it can take you anywhere",
   * set when the item has no report/patient in context and is therefore
   * routing to a chooser rather than straight to the destination. Rendered
   * as the title so hovering explains the redirect instead of surprising
   * the reader with it.
   */
  requiresKey?: string;
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
  // The /auth/me fetch this component used to own now lives on DoctorProvider,
  // so the rail, the upload flow and Settings share one result instead of three
  // independent requests per navigation.
  const { doctor: currentDoctor } = useDoctor();
  const [loggingOut, setLoggingOut] = useState(false);

  const doctor: DoctorInfo | null = currentDoctor
    ? { full_name: currentDoctor.full_name, bmdc_number: currentDoctor.bmdc_number }
    : null;

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
 * report id).
 *
 * These used to render as inert `<span>`s whenever the id was missing --
 * styled almost identically to a live item, and silent on click. On the two
 * most-used screens (the queue and Find patient) that left four of seven rail
 * items dead, and a tester reported exactly that: "the icons are
 * non-clickable/unresponsive". A nav item that looks like a nav item must go
 * somewhere.
 *
 * So every item now routes. When the id is present it goes straight to the
 * destination; when it isn't, it goes to the screen where you pick the missing
 * thing -- New examination sends you to patient search, and the three
 * report-scoped views send you to the queue, which is the list of reports.
 * `requiresKey` carries the reason so the item can say what it's doing instead
 * of appearing to misfire.
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

  // Where a report-scoped item goes when no report is in context: the queue,
  // which is the list of reports to choose from.
  const PICK_REPORT = "/dashboard";
  const PICK_PATIENT = "/patients/search";

  return [
    { key: "queue", label: "nav.queue", Icon: QueueIcon, href: "/dashboard", active: pathname === "/dashboard" },
    { key: "find", label: "nav.find", Icon: SearchIcon, href: "/patients/search", active: pathname === "/patients/search" },
    { key: "patients", label: "nav.patients", Icon: PatientsIcon, href: "/patients", active: pathname === "/patients" || isPatientProfile },
    {
      key: "new-exam",
      label: "nav.newExam",
      Icon: NewExamIcon,
      href: patientId ? `/patients/${patientId}/upload` : PICK_PATIENT,
      active: isUpload,
      requiresKey: patientId ? undefined : "nav.requiresPatient",
    },
    {
      key: "workspace",
      label: "nav.workspace",
      Icon: WorkspaceIcon,
      href: reportId ? `/reports/${reportId}` : PICK_REPORT,
      active: isWorkspace,
      requiresKey: reportId ? undefined : "nav.requiresReport",
    },
    {
      key: "explain",
      label: "nav.explain",
      Icon: ExplainIcon,
      href: reportId ? `/reports/${reportId}/explain` : PICK_REPORT,
      active: isExplain,
      requiresKey: reportId ? undefined : "nav.requiresReport",
    },
    {
      key: "compare",
      label: "nav.compare",
      Icon: CompareIcon,
      href: reportId ? `/reports/${reportId}/compare` : PICK_REPORT,
      active: isCompare,
      requiresKey: reportId ? undefined : "nav.requiresReport",
    },
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
  const { t } = useT();
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
            label: "nav.settings",
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
          <span>{loggingOut ? t("nav.signingOut") : t("nav.signOut")}</span>
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
  const { t } = useT();
  // An item routing to a chooser is dimmed a step, so the rail still reads as
  // "these three are about the report you have open" -- but it is a real link
  // either way, never a decoration that swallows the click.
  const cls = cn(
    "flex items-center gap-12 rounded-control px-12 py-9 text-sm transition-colors duration-hover",
    item.active
      ? "bg-cyan-wash font-medium text-cyan"
      : item.requiresKey
        ? "font-normal text-text-muted hover:bg-bg-hover hover:text-text-secondary"
        : "font-normal text-text-secondary hover:bg-bg-hover",
  );

  return (
    <Link
      href={item.href}
      className={cls}
      aria-current={item.active ? "page" : undefined}
      title={item.requiresKey ? t(item.requiresKey) : undefined}
    >
      <item.Icon className="flex-none" />
      <span className="truncate">{t(item.label)}</span>
    </Link>
  );
}
