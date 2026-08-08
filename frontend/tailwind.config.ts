import type { Config } from "tailwindcss";

/**
 * "Reading Room" theme. Tokens are CSS custom properties
 * (src/styles/tokens.css) and Tailwind only *names* them — nothing here
 * restates a value. A second source of truth for colour is how V1 drifted.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    // `colors` is REPLACED, not extended: Tailwind's default palette would
    // reintroduce ~250 non-semantic colours and make `bg-blue-500` reachable.
    // Two accents only — cyan (retrieval/interaction) and amber (attention/risk).
    colors: {
      transparent: "transparent",
      current: "currentColor",
      bg: {
        page: "var(--bg-page)",
        app: "var(--bg-app)",
        raised: "var(--bg-raised)",
        hover: "var(--bg-hover)",
        "hover-alt": "var(--bg-hover-alt)",
        film: "var(--bg-film)",
      },
      border: {
        DEFAULT: "var(--border-hairline)",
        hairline: "var(--border-hairline)",
        strong: "var(--border-strong)",
      },
      text: {
        primary: "var(--text-primary)",
        secondary: "var(--text-secondary)",
        tertiary: "var(--text-tertiary)",
        muted: "var(--text-muted)",
      },
      cyan: {
        DEFAULT: "var(--accent-cyan)",
        ink: "var(--accent-cyan-ink)",
        wash: "var(--accent-cyan-wash)",
        line: "var(--accent-cyan-line)",
      },
      amber: {
        DEFAULT: "var(--accent-amber)",
        ink: "var(--accent-amber-ink)",
        wash: "var(--accent-amber-wash)",
        line: "var(--accent-amber-line)",
      },
    },
    // The spacing values the mock uses (tokens.css). Both padding and gap
    // draw from here; there is no arbitrary px. `0`, `px`, and `full` are
    // kept as structural utilities. Numeric keys match the pixel value, so
    // p-11 => padding: var(--space-11) => 11px.
    spacing: {
      0: "0px",
      px: "1px",
      2: "var(--space-2)",
      3: "var(--space-3)",
      4: "var(--space-4)",
      5: "var(--space-5)",
      6: "var(--space-6)",
      7: "var(--space-7)",
      8: "var(--space-8)",
      9: "var(--space-9)",
      10: "var(--space-10)",
      11: "var(--space-11)",
      12: "var(--space-12)",
      13: "var(--space-13)",
      14: "var(--space-14)",
      15: "var(--space-15)",
      16: "var(--space-16)",
      18: "var(--space-18)",
      20: "var(--space-20)",
      22: "var(--space-22)",
      24: "var(--space-24)",
      26: "var(--space-26)",
      28: "var(--space-28)",
      30: "var(--space-30)",
      34: "var(--space-34)",
      36: "var(--space-36)",
      38: "var(--space-38)",
      44: "var(--space-44)",
      46: "var(--space-46)",
      50: "var(--space-50)",
      56: "var(--space-56)",
      70: "var(--space-70)",
      74: "var(--space-74)",
    },
    borderRadius: {
      none: "0",
      thumb: "var(--r-thumb)",
      chip: "var(--r-chip)",
      control: "var(--r-control)",
      "btn-sm": "var(--r-btn-sm)",
      field: "var(--r-field)",
      panel: "var(--r-panel)",
      full: "var(--r-full)",
    },
    // No shadows anywhere except the logo dot glow.
    boxShadow: { none: "none", glow: "var(--glow)" },
    fontFamily: {
      // Space Grotesk = all UI/prose · IBM Plex Mono = identifiers/eyebrows/
      // metrics · Noto Sans Bengali = Bangla report text only.
      sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      bn: ["var(--font-bn)", "var(--font-sans)", "sans-serif"],
    },
    // Roles from the README type scale. 10.5px is the floor and is reserved
    // for mono eyebrows; no UI text below 13px otherwise.
    fontSize: {
      display:  ["62px", { lineHeight: "1.05", letterSpacing: "-0.03em",  fontWeight: "600" }],
      "page-title": ["34px", { lineHeight: "1.1", letterSpacing: "-0.025em", fontWeight: "600" }],
      section:  ["26px", { lineHeight: "1.2", letterSpacing: "-0.02em",  fontWeight: "600" }],
      panel:    ["22px", { lineHeight: "1.25", letterSpacing: "-0.02em",  fontWeight: "600" }],
      "screen-title": ["16px", { lineHeight: "1.3", fontWeight: "600" }],
      impression:      ["23px", { lineHeight: "38px", letterSpacing: "-0.01em", fontWeight: "500" }],
      "impression-report": ["19px", { lineHeight: "33px", fontWeight: "500" }],
      findings:    ["16px", { lineHeight: "30px", fontWeight: "400" }],
      "findings-bn": ["16px", { lineHeight: "34px", fontWeight: "400" }],
      prose:   ["15px", { lineHeight: "1.65" }],
      base:    ["15px", { lineHeight: "1.5" }],
      sm:      ["14px", { lineHeight: "1.5" }],
      "sm-tight": ["13.5px", { lineHeight: "1.5" }],
      caption: ["13px", { lineHeight: "1.6" }],
      chip:    ["12.5px", { lineHeight: "1.2" }], // status/ownership pills, owner-chip meta

      // mono eyebrow — the 10.5px floor, uppercase, tracked
      eyebrow: ["10.5px", { lineHeight: "1.3", letterSpacing: "0.14em", fontWeight: "500" }],
      "eyebrow-11": ["11px", { lineHeight: "1.3", letterSpacing: "0.14em", fontWeight: "500" }],
      "mono-meta": ["11px", { lineHeight: "1.4" }],
      "mono-meta-lg": ["12.5px", { lineHeight: "1.4" }],
      metric:  ["44px", { lineHeight: "1", letterSpacing: "-0.04em", fontWeight: "500" }],
      // Secondary mono stat — dashboard queue metrics, the register screen's
      // assigned-id readout. Smaller sibling of `metric`, same mono treatment.
      "metric-sm": ["30px", { lineHeight: "1", letterSpacing: "-0.03em", fontWeight: "500" }],
      "citation": ["11px", { lineHeight: "1" }],
    },
    extend: {
      transitionDuration: { hover: "var(--t-hover)", state: "var(--t-state)", panel: "var(--t-panel)" },
      transitionTimingFunction: { panel: "var(--ease)" },
      backgroundImage: {
        // Ownership texture — redundant to the owner chip, tuned for dark.
        hatch: "repeating-linear-gradient(135deg, transparent, transparent 8px, var(--hatch) 8px, var(--hatch) 16px)",
      },
      width: {
        rail: "var(--rail)",
        "report-col": "var(--report-col)",
        "evidence-panel": "var(--evidence-panel)",
        "explain-panel": "var(--explain-panel)",
      },
      height: {
        "header-bar": "var(--header-bar)",
        "header-landing": "var(--header-landing)",
      },
      keyframes: {
        // The only two keyframes in the product.
        "rr-flow": { "0%": { transform: "translateX(-320%)" }, "100%": { transform: "translateX(320%)" } },
        "rr-blink": { "0%,100%": { opacity: "1" }, "50%": { opacity: ".3" } },
      },
      animation: {
        "rr-flow": "rr-flow 1.1s linear infinite",
        "rr-blink": "rr-blink 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
