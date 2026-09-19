#!/usr/bin/env node
/**
 * i18n parity gate — the Bengali dictionary must define exactly the same key
 * set as the English source of truth. A key present in en.ts but missing in
 * bn.ts silently falls back to English at runtime (t() is fault-tolerant), so
 * without this check a screen could ship half-translated and nobody would see
 * an error. Fail the build instead.
 *
 *   node scripts/check-i18n.mjs
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const DICT_DIR = join(process.cwd(), "src", "lib", "i18n", "dictionaries");

/** Extract the quoted keys from a `"…": …,` dictionary file, order-insensitive. */
function keysOf(file) {
  const text = readFileSync(join(DICT_DIR, file), "utf8");
  const keys = new Set();
  // Match keys like  "namespace.key":  ONLY at the start of a line (after
  // indentation). Anchoring to line start avoids matching inline literals such
  // as a plural ternary `? "day" : "days"`, which would otherwise be mistaken
  // for keys and produce phantom parity failures.
  const re = /^[ \t]*"([a-zA-Z0-9_.]+)"\s*:/gm;
  let m;
  while ((m = re.exec(text)) !== null) keys.add(m[1]);
  return keys;
}

const en = keysOf("en.ts");
const bn = keysOf("bn.ts");

const missingInBn = [...en].filter((k) => !bn.has(k)).sort();
const extraInBn = [...bn].filter((k) => !en.has(k)).sort();

if (missingInBn.length === 0 && extraInBn.length === 0) {
  console.log(`i18n parity OK — ${en.size} keys in both en.ts and bn.ts.`);
  process.exit(0);
}

console.error("i18n parity FAILED:");
if (missingInBn.length) console.error(`  Missing in bn.ts (${missingInBn.length}):\n    ${missingInBn.join("\n    ")}`);
if (extraInBn.length) console.error(`  Extra in bn.ts, not in en.ts (${extraInBn.length}):\n    ${extraInBn.join("\n    ")}`);
process.exit(1);
