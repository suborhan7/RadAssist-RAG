#!/usr/bin/env node
/**
 * P0 gate — design_specification.md §13.
 *
 * "Zero hex literals outside the radiograph SVG. Zero padding values outside
 *  the three tokens. --e1/2/3 only."
 *
 * This exists because V1 shipped a documented design system that nothing
 * consumed: six tokens were declared and never wired up, and every banner
 * invented its own border colour by hand (§15.2). A spec that is not enforced
 * is a suggestion. Run in CI; fail the build.
 *
 *   node scripts/check-design-tokens.mjs
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, extname, relative } from "node:path";

const ROOT = process.cwd();
const SRC = join(ROOT, "src");

/** The only file permitted to contain hex. */
const TOKEN_FILE = "src/styles/tokens.css";
/** Image data, not UI chrome. */
const IMAGE_EXT = new Set([".svg"]);

const RULES = [
  {
    id: "hex-literal",
    why: "Colour must come from a token. See §6.2.",
    test: (line) => line.match(/#[0-9a-fA-F]{3,8}\b/g),
    skip: (f) => f === TOKEN_FILE || IMAGE_EXT.has(extname(f)),
  },
  {
    id: "raw-padding",
    why: "Component padding is --pad-card / --pad-tight / --pad-page only. See §6.4.",
    // p-[13px] · padding:11px · padding: "13px" · paddingLeft: '10px'
    // All three syntaxes bypass the scale, and the JSX-object form is the one
    // that actually caused the drift, so it must not have a hole.
    test: (line) => line.match(/\bp[xytrbl]?-\[[^\]]+\]|padding[A-Za-z]*\s*:\s*["'`]?\s*\d+px/g),
    skip: (f) => f === TOKEN_FILE,
  },
  {
    id: "dead-shadow-token",
    why: "--shadow-popover / --shadow-modal are deleted. Use --e1/--e2/--e3. See §6.5.",
    test: (line) => line.match(/--shadow-(popover|modal)/g),
  },
  {
    id: "below-type-floor",
    why: "11px is the floor. Nothing smaller ships. See §6.3, §9.",
    test: (line) => line.match(/font-size:\s*([0-9]|10)px|text-\[([0-9]|10)px\]/g),
    skip: (f) => f === TOKEN_FILE,
  },
  {
    id: "forbidden-word-confidence",
    why: "The measure is agreement among retrieved cases, not calibrated confidence. See §10.3.",
    // Only what ships to the user. Comments must stay free to explain *why*
    // the word is banned — a gate that forbids documenting its own rationale
    // is how rationale gets lost.
    test: (line) => (isComment(line) ? null : line.match(/\bconfidence\b/gi)),
  },
  {
    id: "outline-none",
    why: "Focus is never removed. See §9.",
    test: (line) => line.match(/outline:\s*none|outline-none/g),
  },
  {
    id: "tailwind-default-palette",
    why: "Only semantic colours exist. bg-blue-500 is not a decision. See §6.2.",
    test: (line) =>
      line.match(/\b(bg|text|border|ring)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/g),
  },
];

/** Comment lines document intent; they do not ship. */
const isComment = (line) => /^\s*(\/\/|\/\*|\*|#)/.test(line);

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === "node_modules" || e === ".next" || e.startsWith(".")) continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if ([".ts", ".tsx", ".css", ".js", ".jsx"].includes(extname(p))) out.push(p);
  }
  return out;
}

let failures = 0;
const files = walk(SRC);
for (const abs of files) {
  const rel = relative(ROOT, abs).split("\\").join("/");
  const lines = readFileSync(abs, "utf8").split("\n");
  lines.forEach((line, i) => {
    if (line.includes("design-token-allow")) return; // deliberate, documented escape
    for (const r of RULES) {
      if (r.skip?.(rel, line)) continue;
      const hits = r.test(line);
      if (hits) {
        failures++;
        console.error(`\x1b[31m✗\x1b[0m ${rel}:${i + 1}  [${r.id}]  ${hits.join(", ")}`);
        console.error(`  ${r.why}`);
      }
    }
  });
}

console.log(`\nscanned ${files.length} files in src/`);
if (failures) {
  console.error(`\x1b[31m${failures} violation(s). P0 gate FAILED.\x1b[0m`);
  process.exit(1);
}
console.log(`\x1b[32m0 violations. P0 gate passed.\x1b[0m`);
