import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Nexova — Talent Pipeline Tracker",
  description:
    "Gestión de candidaturas para procesos de selección de Nexova",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-brand-white text-brand-anthracite">
        <header className="sticky top-0 z-50 w-full border-b border-brand-lightgray bg-brand-white/95 backdrop-blur">
          <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
            <span className="text-lg font-black tracking-tight text-brand-anthracite">
              Nexova
            </span>
            <span className="text-sm text-brand-lightgray">·</span>
            <span className="text-sm font-semibold uppercase tracking-[0.16em] text-brand-anthracite/70">
              Talent Pipeline Tracker
            </span>
          </div>
        </header>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
