"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { Button, Spinner } from "@/components/ui";
import {
  getAccountNavigationLinks,
  logoutAndRedirect,
  requiresAuthentication,
  shouldShowLogout,
} from "@/lib/auth-navigation";

export function AuthShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { status, logout, validateSession } = useAuth();
  const protectedRoute = requiresAuthentication(pathname);
  const accountNavigationLinks = getAccountNavigationLinks(status);

  useEffect(() => {
    if (protectedRoute && status === "unauthenticated") {
      router.replace("/login");
    }
  }, [protectedRoute, router, status]);

  function handleLogout() {
    logoutAndRedirect(logout, (path) => router.replace(path));
  }

  return (
    <>
      <header className="sticky top-0 z-50 w-full border-b border-brand-lightgray bg-brand-white/95 backdrop-blur">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
          <Link href="/" className="shrink-0 text-lg font-black tracking-tight text-brand-anthracite">
            Nexova
          </Link>
          <nav
            aria-label="Main navigation"
            className="flex min-w-0 flex-1 items-center gap-3 overflow-x-auto whitespace-nowrap"
          >
            <span className="text-sm text-brand-lightgray" aria-hidden="true">·</span>
            <Link
              href="/"
              className="text-sm font-semibold uppercase tracking-[0.16em] text-brand-anthracite/70 transition-colors hover:text-brand-anthracite"
            >
              Talent Pipeline Tracker
            </Link>
            <span className="text-sm text-brand-lightgray" aria-hidden="true">·</span>
            <Link
              href="/incidents"
              className="text-sm font-semibold uppercase tracking-[0.16em] text-brand-anthracite/70 transition-colors hover:text-brand-anthracite"
            >
              Incident Analysis
            </Link>
            <span className="text-sm text-brand-lightgray" aria-hidden="true">·</span>
            <Link
              href="/incidents/manager"
              className="text-sm font-semibold uppercase tracking-[0.16em] text-brand-anthracite/70 transition-colors hover:text-brand-anthracite"
            >
              Incident Manager
            </Link>
            <span className="text-sm text-brand-lightgray" aria-hidden="true">·</span>
            <Link
              href="/suppliers"
              className="text-sm font-semibold uppercase tracking-[0.16em] text-brand-anthracite/70 transition-colors hover:text-brand-anthracite"
            >
              Supplier Directory
            </Link>
            {accountNavigationLinks.map(({ label, href }) => (
              <span key={href} className="contents">
                <span className="text-sm text-brand-lightgray" aria-hidden="true">·</span>
                <Link
                  href={href}
                  className="text-sm font-semibold uppercase tracking-[0.16em] text-brand-anthracite/70 transition-colors hover:text-brand-anthracite"
                >
                  {label}
                </Link>
              </span>
            ))}
          </nav>
          {shouldShowLogout(status) && (
            <Button
              type="button"
              variant="secondary"
              className="shrink-0 px-3 py-2 text-xs sm:text-sm"
              onClick={handleLogout}
            >
              Logout
            </Button>
          )}
        </div>
      </header>
      <main className="flex-1">
        {protectedRoute && status !== "authenticated" ? (
          <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
            {status === "error" ? (
              <div role="alert" className="space-y-4">
                <p>No se pudo verificar tu sesión.</p>
                <Button type="button" variant="secondary" onClick={() => void validateSession()}>
                  Reintentar
                </Button>
              </div>
            ) : (
              <div role="status" aria-busy="true" className="flex items-center gap-3">
                <Spinner size="sm" />
                <span>Comprobando sesión…</span>
              </div>
            )}
          </section>
        ) : (
          children
        )}
      </main>
    </>
  );
}