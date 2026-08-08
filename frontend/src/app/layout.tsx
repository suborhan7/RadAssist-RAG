import type { Metadata } from "next";
import { fontVars } from "@/lib/fonts";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "RadAssist-RAG",
  description: "Retrieval-grounded chest X-ray reporting",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${fontVars} h-full antialiased`}>
      <body className="min-h-full bg-bg-app font-sans text-base text-text-primary">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
