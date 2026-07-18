"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

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
 */
export function EditableReportSection({
  label,
  value,
  isEdited,
  canEdit,
  saving,
  onCommit,
  onDirtyChange,
}: {
  label: string;
  value: string;
  isEdited: boolean;
  canEdit: boolean;
  saving: boolean;
  onCommit: (next: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
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
        {canEdit && !editing && !saving && (
          <button
            type="button"
            onClick={startEditing}
            className="ml-auto text-xs text-ink-3 opacity-0 transition-opacity duration-hover hover:text-steel-ink group-hover:opacity-100 group-focus-within:opacity-100"
          >
            Edit
          </button>
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
    </div>
  );
}
