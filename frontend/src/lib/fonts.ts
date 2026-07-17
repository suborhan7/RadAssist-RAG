import { IBM_Plex_Sans, IBM_Plex_Mono, Noto_Sans_Bengali } from "next/font/google";

/**
 * §6.3. Plex was drawn for technical documentation and instrument interfaces.
 * Its mono companion is metrically related, so a table can mix a patient name
 * and a patient code without the baseline breaking. Explicitly not Inter.
 */
export const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

export const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

/** Bangla report body sets at 15/29 — conjuncts need more leading than Latin. */
export const notoBengali = Noto_Sans_Bengali({
  subsets: ["bengali"],
  weight: ["400", "500"],
  variable: "--font-bn",
  display: "swap",
});

export const fontVars = `${plexSans.variable} ${plexMono.variable} ${notoBengali.variable}`;
