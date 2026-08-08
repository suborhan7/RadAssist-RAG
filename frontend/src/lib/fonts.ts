import { Space_Grotesk, IBM_Plex_Mono, Noto_Sans_Bengali } from "next/font/google";

/**
 * "Reading Room" typography. Three families:
 *
 * - Space Grotesk (400/500/600/700) -- all UI and prose. New in this theme;
 *   replaces IBM Plex Sans as --font-sans.
 * - IBM Plex Mono (400/500) -- identifiers, eyebrows, timings, metrics,
 *   percentages. Metrically companionable so a table can mix a patient name
 *   and a patient code without the baseline breaking.
 * - Noto Sans Bengali (400/500) -- Bangla report body only; sets looser
 *   (16/34) because conjuncts need more leading than Latin.
 */
export const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

export const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const notoBengali = Noto_Sans_Bengali({
  subsets: ["bengali"],
  weight: ["400", "500"],
  variable: "--font-bn",
  display: "swap",
});

export const fontVars = `${spaceGrotesk.variable} ${plexMono.variable} ${notoBengali.variable}`;
