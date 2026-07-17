"use client";

import { useRef, useState } from "react";
import { cn } from "@/lib/cn";

/**
 * design_specification.md §8.9's "PHI reveal slider" -- not in p0-design-system's
 * shipped primitive set (that package explicitly defers anything coupled to a
 * screen's data shape). `originalSrc` MUST be an object URL built from the
 * browser's own in-memory File the doctor selected, never a second upload or
 * a persisted copy -- this system deliberately never stores the raw image
 * (Phase 12's masking invariant), so the only "original" this slider can
 * legitimately show is the one already sitting in this browser tab from the
 * user's own file picker. The printed constraint ("Original shown from this
 * session only. Not stored.") is literally true because of that, not just
 * asserted.
 */
export function PhiRevealSlider({
  maskedSrc,
  originalSrc,
  className,
}: {
  maskedSrc: string;
  originalSrc: string;
  className?: string;
}) {
  const [percent, setPercent] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  function setFromClientX(clientX: number) {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setPercent(Math.min(100, Math.max(0, pct)));
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div
        ref={containerRef}
        className="relative aspect-square w-full select-none overflow-hidden rounded-card bg-lightbox"
        onPointerDown={(e) => {
          dragging.current = true;
          setFromClientX(e.clientX);
        }}
        onPointerMove={(e) => {
          if (dragging.current) setFromClientX(e.clientX);
        }}
        onPointerUp={() => {
          dragging.current = false;
        }}
        onPointerLeave={() => {
          dragging.current = false;
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={maskedSrc} alt="Masked chest X-ray" className="absolute inset-0 h-full w-full object-contain" />
        <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - percent}% 0 0)` }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={originalSrc}
            alt="Original chest X-ray, before masking"
            className="absolute inset-0 h-full w-full object-contain"
          />
        </div>
        <div
          className="absolute inset-y-0 w-0.5 bg-steel"
          style={{ left: `${percent}%` }}
          aria-hidden
        />
        <input
          type="range"
          min={0}
          max={100}
          value={percent}
          onChange={(e) => setPercent(Number(e.target.value))}
          aria-label="Reveal original image beneath the masked copy"
          className="absolute inset-x-2 bottom-2 w-[calc(100%-16px)] accent-steel"
        />
      </div>
      <p className="text-sm text-ink-3">
        Drag to reveal the original beneath the masked copy. Original shown from this session
        only. Not stored.
      </p>
    </div>
  );
}
