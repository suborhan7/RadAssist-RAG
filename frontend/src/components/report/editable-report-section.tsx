"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { DiffMarkup } from "@/components/report/report-diff-view";
import { useT } from "@/lib/i18n";
import type { SectionDiff } from "@/lib/report-diff";

/**
 * Phase 17 Step 7: one of the report's five independently editable
 * sections (Clinical History, Technique, Findings, Impression,
 * Recommendation), rendered as part of the continuous document per
 * Phase 14's visual language -- not a form. Also used (with canEdit=false)
 * for the two AI-set/read-only sections (Examination, Disclaimer), so the
 * whole document uses one component regardless of editability, rather
 * than two parallel rendering paths that could visually drift.
 *
 * Keyboard model: Tab moves between sections (each is focusable when
 * editable and not already being edited); Enter on a focused, non-editing
 * section starts editing it; inside the textarea, Enter commits and
 * Shift+Enter inserts a newline (multi-line prose needs a way to add
 * lines); Escape cancels and reverts to the last-saved value. A ref-based
 * guard (not a state flag) prevents Enter's commit and the textarea's
 * subsequent blur-triggered commit from both firing -- state updates are
 * async and blur can still see a stale "editing" closure otherwise,
 * which would double-PATCH.
 *
 * The "Edited" indicator is a subtle dot + label-color shift, never a
 * badge/banner/colored border -- this project's tokens reserve strong
 * color/border treatment for real semantic states (validation, ownership),
 * not per-field metadata.
 *
 * Phase 19: "Regenerate" is a second per-section affordance, alongside
 * "Edit" -- both gated on the same canEdit permission (regenerating IS a
 * form of editing, per phase19_section_regeneration_architecture.md
 * Decision 3). Regeneration is two steps, never one atomic write
 * (Decision 1): `onRegenerate` only PRODUCES a candidate (via the parent,
 * which owns the actual API call and the resulting diff computation --
 * this component only renders whatever SectionDiff it's given); nothing
 * is persisted until the doctor explicitly clicks Accept, which reuses
 * the exact same onCommit() path a hand-typed edit already uses. Discard
 * fires no request at all. The diff preview reuses DiffMarkup (Phase 18
 * extraction) rather than a second word-diff rendering.
 */
export function EditableReportSection({
  label,
  value,
  isEdited,
  canEdit,
  saving,
  onCommit,
  onDirtyChange,
  canRegenerate = false,
  regenerating = false,
  regenerationPreview = null,
  regenerationContextIncomplete = false,
  regenerationError = null,
  onRegenerate,
  onAcceptRegeneration,
  onDiscardRegeneration,
}: {
  label: string;
  value: string;
  isEdited: boolean;
  canEdit: boolean;
  saving: boolean;
  onCommit: (next: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
  canRegenerate?: boolean;
  regenerating?: boolean;
  regenerationPreview?: SectionDiff | null;
  regenerationContextIncomplete?: boolean;
  regenerationError?: string | null;
  onRegenerate?: () => void;
  onAcceptRegeneration?: () => void;
  onDiscardRegeneration?: () => void;
}) {
  const { t } = useT();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const commitGuardRef = useRef(false);

  useEffect(() => {
    if (editing) textareaRef.current?.focus();
  }, [editing]);

  useEffect(() => {
    onDirtyChange?.(editing && draft !== value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing, draft, value]);

  function startEditing() {
    if (!canEdit || saving) return;
    commitGuardRef.current = false;
    setDraft(value);
    setEditing(true);
  }

  function commit() {
    if (commitGuardRef.current) return;
    commitGuardRef.current = true;
    setEditing(false);
    if (draft !== value) onCommit(draft);
  }

  function cancel() {
    commitGuardRef.current = true;
    setDraft(value);
    setEditing(false);
  }

  return (
    <div
      className="group relative py-3 first:pt-0 last:pb-0"
      tabIndex={canEdit && !editing ? 0 : undefined}
      onKeyDown={(e) => {
        if (!editing && canEdit && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          startEditing();
        }
      }}
      onDoubleClick={startEditing}
    >
      <div className="flex items-center gap-8">
        <h3 className="font-mono text-eyebrow uppercase text-text-tertiary">{label}</h3>
        {isEdited && (
          <span
            className="inline-block h-5 w-5 rounded-full bg-cyan"
            title={t("report.editedByDoctor")}
            aria-label={t("report.editedAria")}
          />
        )}
        {isEdited && <span className="font-mono text-eyebrow uppercase text-cyan">{t("report.edited")}</span>}
        {saving && <span className="ml-auto text-caption text-text-tertiary">{t("report.saving")}</span>}
        {regenerating && <span className="ml-auto text-caption text-text-tertiary">{t("report.regenerating")}</span>}
        {canEdit && !editing && !saving && !regenerating && !regenerationPreview && (
          <div className="ml-auto flex items-center gap-14 opacity-0 transition-opacity duration-hover group-hover:opacity-100 group-focus-within:opacity-100">
            {canRegenerate && onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="font-mono text-eyebrow uppercase tracking-[0.14em] text-text-tertiary transition-colors duration-hover hover:text-cyan"
              >
                {t("report.regenerate")}
              </button>
            )}
            <button
              type="button"
              onClick={startEditing}
              className="text-caption text-text-tertiary transition-colors duration-hover hover:text-cyan"
            >
              {t("report.edit")}
            </button>
          </div>
        )}
      </div>

      {editing ? (
        <textarea
          ref={textareaRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              commit();
            } else if (e.key === "Escape") {
              e.preventDefault();
              cancel();
            }
          }}
          onBlur={commit}
          rows={3}
          className={cn(
            "mt-8 w-full resize-y rounded-field border border-cyan-line bg-bg-raised p-12",
            "text-findings text-text-primary",
          )}
        />
      ) : (
        <p className="mt-8 whitespace-pre-wrap text-findings text-text-secondary">{value || t("compare.none")}</p>
      )}

      {regenerationError && (
        <p className="mt-8 rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
          {regenerationError}
        </p>
      )}

      {regenerationPreview && (
        <div className="mt-14 rounded-panel border border-cyan-line bg-cyan-wash p-14">
          <h4 className="font-mono text-eyebrow uppercase text-cyan">{t("report.candidateNotApplied")}</h4>
          {regenerationContextIncomplete && (
            <p className="mt-8 rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
              {t("report.contextIncomplete")}
            </p>
          )}
          <div className="mt-8">
            <DiffMarkup diff={regenerationPreview.diff} />
          </div>
          <div className="mt-14 flex items-center gap-14">
            <button
              type="button"
              onClick={onAcceptRegeneration}
              className={cn(BUTTON_BASE, VARIANT.primary, SIZE.sm)}
            >
              {t("report.accept")}
            </button>
            <button
              type="button"
              onClick={onDiscardRegeneration}
              className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.sm)}
            >
              {t("report.discard")}
            </button>
            <span className="ml-auto text-caption text-text-tertiary">{t("report.discardNote")}</span>
          </div>
        </div>
      )}
    </div>
  );
}
