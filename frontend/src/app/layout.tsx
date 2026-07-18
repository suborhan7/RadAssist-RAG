import type { Metadata } from "next";
import { fontVars } from "@/lib/fonts";
import { LogoutBar } from "@/components/auth/logout-bar";
import "./globals.css";

export const metadata: Metadata = {
  title: "RadAssist-RAG",
  description: "Radiologist Workflow Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${fontVars} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-paper font-sans text-body text-ink">
        <LogoutBar />
        {children}
      </body>
    </html>
  );
}
