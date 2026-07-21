/**
 * Decorative synthetic chest-radiograph illustration -- §16.1's
 * reopening (design_specification.md §8.1 Landing, §8.2 Login), matching
 * the reference mockup's own "fake chest-X-ray" background treatment on
 * both the Landing hero panel and the Login lightbox panel. One shared
 * implementation reused in both places rather than two divergent copies.
 *
 * Purely decorative image data, per §6.2's explicit exception -- its four
 * gradient colors live in tokens.css (--illustration-*), not hardcoded
 * here, so the P0 gate's hex-literal rule (which only exempts real .svg
 * files, not hex embedded in a .tsx component) has nothing to flag.
 */
export function ChestXrayIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 400 500"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <radialGradient id="cxr-vignette" cx="50%" cy="42%" r="60%">
          <stop offset="0%" stopColor="var(--illustration-vignette-center)" />
          <stop offset="100%" stopColor="var(--illustration-vignette-edge)" />
        </radialGradient>
        <linearGradient id="cxr-highlight" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="var(--illustration-highlight-start)" />
          <stop offset="100%" stopColor="var(--illustration-highlight-end)" />
        </linearGradient>
      </defs>

      <rect x="0" y="0" width="400" height="500" fill="url(#cxr-vignette)" />

      {/* Clavicles */}
      <path
        d="M 120 90 Q 160 70 200 78 Q 240 70 280 90"
        stroke="url(#cxr-highlight)"
        strokeWidth="6"
        strokeLinecap="round"
      />

      {/* Spine */}
      {Array.from({ length: 14 }, (_, i) => (
        <rect
          key={i}
          x="192"
          y={95 + i * 24}
          width="16"
          height="16"
          rx="3"
          fill="url(#cxr-highlight)"
          opacity="0.5"
        />
      ))}

      {/* Rib pairs, widest around the middle */}
      {Array.from({ length: 8 }, (_, i) => {
        const y = 110 + i * 28;
        const spread = 70 + Math.sin((i / 7) * Math.PI) * 60;
        return (
          <g key={i} opacity="0.65">
            <path
              d={`M 195 ${y} Q ${195 - spread * 0.6} ${y + 10} ${195 - spread} ${y + 45}`}
              stroke="url(#cxr-highlight)"
              strokeWidth="4"
              strokeLinecap="round"
            />
            <path
              d={`M 205 ${y} Q ${205 + spread * 0.6} ${y + 10} ${205 + spread} ${y + 45}`}
              stroke="url(#cxr-highlight)"
              strokeWidth="4"
              strokeLinecap="round"
            />
          </g>
        );
      })}

      {/* Shoulders */}
      <circle cx="95" cy="120" r="22" fill="url(#cxr-highlight)" opacity="0.3" />
      <circle cx="305" cy="120" r="22" fill="url(#cxr-highlight)" opacity="0.3" />
    </svg>
  );
}
