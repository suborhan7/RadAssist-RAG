"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { DiffMarkup } from "@/components/report/report-diff-view";
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
      <div className="flex items-center gap-2">
        <h3 className="text-h3 text-ink">{label}</h3>
        {isEdited && (
          <span
            className="inline-block h-1.5 w-1.5 rounded-full bg-steel-ink"
            title="Edited by doctor"
            aria-label="Edited"
          />
        )}
        {isEdited && <span className="text-eyebrow uppercase text-steel-ink">Edited</span>}
        {saving && <span className="ml-auto text-xs text-ink-3">Saving…</span>}
        {regenerating && <span className="ml-auto text-xs text-ink-3">Regenerating…</span>}
        {canEdit && !editing && !saving && !regenerating && !regenerationPreview && (
          <div className="ml-auto flex items-center gap-3 opacity-0 transition-opacity duration-hover group-hover:opacity-100 group-focus-within:opacity-100">
            {canRegenerate && onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="text-xs text-ink-3 hover:text-steel-ink"
              >
                Regenerate
              </button>
            )}
            <button
              type="button"
              onClick={startEditing}
              className="text-xs text-ink-3 hover:text-steel-ink"
            >
              Edit
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
            "mt-1 w-full resize-y rounded-in border border-steel-bd bg-surface p-2",
            "text-report text-ink focus:ring-2 focus:ring-steel",
          )}
        />
      ) : (
        <p className="mt-1 whitespace-pre-wrap text-report text-ink-2">{value || "(none)"}</p>
      )}

      {regenerationError && (
        <p className="mt-2 rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
          {regenerationError}
        </p>
      )}

      {regenerationPreview && (
        <div className="mt-3 rounded-card border border-steel-bd bg-steel-tint p-tight">
          <h4 className="text-eyebrow uppercase text-steel-ink">Regenerated candidate -- preview</h4>
          {regenerationContextIncomplete && (
            <p className="mt-2 rounded-card border border-caution-bd bg-caution-bg px-3 py-2 text-sm text-caution-ink">
              This report predates full context capture. This candidate was generated from retrieved
              evidence only -- it may not reflect the original questionnaire context.
            </p>
          )}
          <div className="mt-2">
            <DiffMarkup diff={regenerationPreview.diff} />
          </div>
          <div className="mt-3 flex gap-3">
            <button
              type="button"
              onClick={onDiscardRegeneration}
              className="text-xs font-medium text-ink-2 underline decoration-hairline-strong underline-offset-2 hover:text-ink"
            >
              Discard
            </button>
            <button
              type="button"
              onClick={onAcceptRegeneration}
              className="text-xs font-medium text-steel-ink underline decoration-steel-bd underline-offset-2 hover:text-steel"
            >
              Accept
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
