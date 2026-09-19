"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ApiError, listPatients } from "@/lib/api-client";
import { ScreenHeader } from "@/components/layout/screen-header";
import { BUTTON_BASE, Button, SIZE, VARIANT } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import type { paths } from "@/lib/generated/api";

type PatientResponse =
  paths["/patients"]["get"]["responses"][200]["content"]["application/json"][number];

const COLS = "grid-cols-[minmax(0,1.6fr)_160px_150px_110px_90px]";

/**
 * Patients directory (Phase 12, additive). The real "Patients" destination: the
 * whole shared registry in one list, with a name-or-ID search. This is the
 * browse path; the exact-match /patients/search (frozen Decision 4) stays as
 * the identity-critical selection flow. Filtering is client-side over the full
 * list loaded from GET /patients — applied on the Search button (or Enter), no
 * date of birth required — and every row shows name + code + DOB + sex so the
 * doctor still verifies identity before opening a profile.
 */
export default function PatientsDirectoryPage() {
  const { t } = useT();
  const [patients, setPatients] = useState<PatientResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState(""); // what's in the box
  const [query, setQuery] = useState(""); // what was last submitted

  useEffect(() => {
    listPatients()
      .then(setPatients)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("directory.errLoad")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    if (!patients) return [];
    const q = query.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter(
      (p) => p.name.toLowerCase().includes(q) || p.patient_code.toLowerCase().includes(q),
    );
  }, [patients, query]);

  function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    setQuery(input);
  }

  function handleClear() {
    setInput("");
    setQuery("");
  }

  return (
    <>
      <ScreenHeader
        title={t("nav.patients")}
        meta={patients ? t("directory.count", { count: patients.length }) : ""}
        actions={
          <Link href="/patients/new" className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}>
            {t("common.registerNewPatient")}
          </Link>
        }
      />

      <div className="flex-1 overflow-auto px-30 pb-30 pt-24">
        <div className="mx-auto max-w-[1100px]">
          {/* Search: name or patient ID, applied on submit. No date of birth. */}
          <form onSubmit={handleSearch} className="mb-24 flex flex-wrap items-center gap-12">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("directory.searchPlaceholder")}
              aria-label={t("directory.searchPlaceholder")}
              className="h-46 min-w-0 flex-1 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted"
            />
            <Button type="submit" variant="primary" size="lg">
              {t("search.search")}
            </Button>
            {query && (
              <Button type="button" variant="secondary" size="lg" onClick={handleClear}>
                {t("directory.clear")}
              </Button>
            )}
          </form>

          {error ? (
            <p className="rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
              {error}
            </p>
          ) : patients === null ? (
            <p className="px-4 py-16 text-sm text-text-tertiary">{t("directory.loading")}</p>
          ) : patients.length === 0 ? (
            <p className="px-4 py-16 text-sm text-text-secondary">{t("directory.empty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <div className="min-w-[720px] border-t border-hairline">
                <div
                  className={cn(
                    "grid gap-14 border-b border-hairline px-4 py-12 font-mono text-eyebrow uppercase text-text-tertiary",
                    COLS,
                  )}
                >
                  <span>{t("search.name")}</span>
                  <span>{t("directory.colId")}</span>
                  <span>{t("search.dob")}</span>
                  <span>{t("newPatient.sex")}</span>
                  <span />
                </div>

                {filtered.length === 0 ? (
                  <p className="px-4 py-16 text-sm text-text-secondary">{t("directory.noMatches")}</p>
                ) : (
                  filtered.map((patient) => (
                    <Link
                      key={patient.id}
                      href={`/patients/${patient.id}`}
                      className={cn(
                        "group grid items-center gap-14 border-b border-hairline px-4 py-14 transition-colors duration-hover last:border-0 hover:bg-bg-hover",
                        COLS,
                      )}
                    >
                      <div className="min-w-0 truncate text-base font-medium text-text-primary">
                        {patient.name}
                      </div>
                      <div className="truncate font-mono text-mono-meta text-text-tertiary">
                        {patient.patient_code}
                      </div>
                      <div className="font-mono text-sm text-text-secondary">{patient.date_of_birth}</div>
                      <div className="text-sm text-text-secondary">{patient.gender}</div>
                      <div className="text-right text-sm text-cyan transition-colors duration-hover group-hover:text-text-primary">
                        {t("common.open")}
                      </div>
                    </Link>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
