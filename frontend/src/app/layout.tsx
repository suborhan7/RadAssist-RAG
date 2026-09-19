import type { Metadata } from "next";
import { cookies } from "next/headers";
import { fontVars } from "@/lib/fonts";
import { AppShell } from "@/components/layout/app-shell";
import { GlobalControls } from "@/components/layout/global-controls";
import { DoctorProvider } from "@/lib/doctor";
import { LanguageProvider } from "@/lib/i18n";
import { LANG_COOKIE, type Lang } from "@/lib/i18n/shared";
import { ThemeProvider } from "@/lib/theme";
import { DEFAULT_THEME, THEME_COOKIE, type Theme } from "@/lib/theme/shared";
import "./globals.css";

export const metadata: Metadata = {
  title: "RadAssist-RAG",
  description: "Retrieval-grounded chest X-ray reporting",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Read both persisted preferences server-side so the very first paint already
  // has the right <html lang>, the right Bengali body font, and the right
  // palette — no flash, no hydration mismatch (each provider is seeded with the
  // same value it reads here). Getting the theme wrong on first paint is the
  // more visible of the two: a reader who chose light would see a full-screen
  // black flash on every navigation.
  const cookieStore = await cookies();
  const lang: Lang = cookieStore.get(LANG_COOKIE)?.value === "bn" ? "bn" : "en";
  const theme: Theme = cookieStore.get(THEME_COOKIE)?.value === "light" ? "light" : DEFAULT_THEME;

  return (
    <html
      lang={lang}
      // Dark is the bare :root default in tokens.css, so it carries no
      // attribute; only light is stamped.
      data-theme={theme === DEFAULT_THEME ? undefined : theme}
      className={`${fontVars} h-full antialiased`}
    >
      <body
        className={`min-h-full bg-bg-app font-sans text-base text-text-primary${lang === "bn" ? " lang-bn" : ""}`}
      >
        <ThemeProvider initial={theme}>
          <LanguageProvider initial={lang}>
            {/* Inside LanguageProvider: DoctorProvider may seed the interface
                language from the doctor's saved default, so it needs setLang. */}
            <DoctorProvider>
              <GlobalControls />
              <AppShell>{children}</AppShell>
            </DoctorProvider>
          </LanguageProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
