import type { Config } from "tailwindcss";

/**
 * Tokens are CSS custom properties (src/styles/tokens.css) and Tailwind only
 * *names* them. Nothing here restates a value — a second source of truth for
 * colour is exactly how V1 drifted (design_specification.md §15).
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    // `colors` is REPLACED, not extended: Tailwind's default palette would
    // reintroduce ~250 non-semantic colours and make `bg-blue-500` reachable.
    colors: {
      transparent: "transparent",
      current: "currentColor",
      paper: "var(--paper)",
      surface: "var(--surface)",
      sunken: "var(--sunken)",
      hairline: "var(--hairline)",
      "hairline-strong": "var(--hairline-strong)",
      ink: { DEFAULT: "var(--ink)", 2: "var(--ink-2)", 3: "var(--ink-3)" },
      steel: {
        DEFAULT: "var(--steel)",
        hover: "var(--steel-hover)",
        tint: "var(--steel-tint)",
        bd: "var(--steel-bd)",
        ink: "var(--steel-ink)",
        deep: "var(--brand-deep)",
      },
      caution: {
        DEFAULT: "var(--caution-fill)",
        bg: "var(--caution-bg)",
        bd: "var(--caution-bd)",
        ink: "var(--caution-ink)",
      },
      stable: {
        DEFAULT: "var(--stable)",
        bg: "var(--stable-bg)",
        bd: "var(--stable-bd)",
        ink: "var(--stable-ink)",
      },
      critical: {
        DEFAULT: "var(--critical)",
        bg: "var(--critical-bg)",
        bd: "var(--critical-bd)",
        ink: "var(--critical-ink)",
      },
      lightbox: {
        DEFAULT: "var(--lightbox)",
        chrome: "var(--lightbox-chrome)",
        bd: "var(--lightbox-bd)",
        ink: "var(--lightbox-ink)",
        "ink-2": "var(--lightbox-ink-2)",
        "ink-3": "var(--lightbox-ink-3)",
      },
      white: "#FFFFFF", // lightbox foreground only
    },
    // Component padding is three tokens (§6.4). Layout spacing is 4-based.
    spacing: {
      0: "0px", px: "1px", 0.5: "2px", 1: "4px", 1.5: "6px", 2: "8px",
      2.5: "10px", 3: "12px", 3.5: "14px", 4: "16px", 5: "20px", 6: "24px",
      8: "32px", 10: "40px", 12: "48px", 14: "56px", 16: "64px",
      card: "var(--pad-card)", tight: "var(--pad-tight)", page: "var(--pad-page)",
    },
    borderRadius: {
      none: "0", in: "var(--r-in)", btn: "var(--r-btn)",
      card: "var(--r-card)", modal: "var(--r-modal)", full: "999px",
    },
    // Only these three. --shadow-popover/--shadow-modal are deleted (§6.5).
    boxShadow: { none: "none", e1: "var(--e1)", e2: "var(--e2)", e3: "var(--e3)" },
    fontFamily: {
      sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      bn: ["var(--font-bn)", "var(--font-sans)", "sans-serif"],
    },
    // §6.3. 11px is the floor — nothing smaller is expressible.
    fontSize: {
      hero:    ["44px", { lineHeight: "50px", letterSpacing: "-0.025em", fontWeight: "600" }],
      display: ["28px", { lineHeight: "34px", letterSpacing: "-0.02em",  fontWeight: "600" }],
      h1:      ["22px", { lineHeight: "28px", letterSpacing: "-0.015em", fontWeight: "600" }],
      h2:      ["18px", { lineHeight: "24px", letterSpacing: "-0.01em",  fontWeight: "600" }],
      h3:      ["15px", { lineHeight: "20px", letterSpacing: "-0.005em", fontWeight: "600" }],
      body:    ["14px", { lineHeight: "21px" }],
      report:  ["15px", { lineHeight: "26px" }],
      "report-bn": ["15px", { lineHeight: "29px" }], // conjuncts need the leading
      sm:      ["13px", { lineHeight: "18px" }],
      label:   ["12px", { lineHeight: "16px", letterSpacing: "0.005em", fontWeight: "500" }],
      eyebrow: ["11px", { lineHeight: "14px", letterSpacing: "0.06em",  fontWeight: "600" }],
      data:    ["13px", { lineHeight: "18px" }],
      "data-sm": ["11px", { lineHeight: "14px", fontWeight: "500" }],
    },
    extend: {
      transitionDuration: { hover: "var(--t-hover)", state: "var(--t-state)", panel: "var(--t-panel)" },
      transitionTimingFunction: { panel: "var(--ease)" },
      backgroundImage: {
        // Ownership texture (§9) — redundant to the chip, and now visible.
        hatch: "repeating-linear-gradient(135deg, transparent, transparent 8px, var(--hatch) 8px, var(--hatch) 16px)",
      },
      width: {
        sidebar: "var(--sidebar)", "sidebar-rail": "var(--sidebar-rail)",
        "report-col": "var(--report-col)", "evidence-rail": "var(--evidence-rail)",
        "rail-collapsed": "var(--rail-collapsed)", drawer: "var(--drawer)",
      },
      height: {
        topbar: "var(--topbar)", "context-bar": "var(--context-bar)",
        "finalize-bar": "var(--finalize-bar)",
      },
    },
  },
  plugins: [],
};
export default config;
