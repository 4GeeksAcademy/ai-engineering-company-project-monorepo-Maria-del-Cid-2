"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { Button, Spinner } from "@/components/ui";
import {
  getAccountNavigationLinks,
  logoutAndRedirect,
  requiresAuthentication,
} from "@/lib/auth-navigation";

type DropdownName = "incidents" | "account";

const baseLinkClass =
  "text-sm font-semibold uppercase tracking-[0.12em] text-brand-anthracite/75 transition-colors hover:text-brand-anthracite focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand-orange";
const menuLinkClass =
  "block rounded-md px-3 py-2 text-sm font-semibold text-brand-anthracite/80 transition-colors hover:bg-brand-lightgray/50 hover:text-brand-anthracite focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand-orange";

function Chevron({ open }: { open: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`text-xs transition-transform ${open ? "rotate-180" : ""}`}
    >
      v
    </span>
  );
}

function NavigationLink({
  href,
  children,
  onSelect,
  className = baseLinkClass,
  role,
}: {
  href: string;
  children: ReactNode;
  onSelect: () => void;
  className?: string;
  role?: "menuitem";
}) {
  return (
    <Link href={href} className={className} onClick={onSelect} role={role}>
      {children}
    </Link>
  );
}

function NavigationDropdown({
  id,
  label,
  open,
  onToggle,
  onSelect,
  children,
}: {
  id: string;
  label: string;
  open: boolean;
  onToggle: () => void;
  onSelect: () => void;
  children: ReactNode;
}) {
  return (
    <div className="relative">
      <button
        type="button"
        className={`${baseLinkClass} inline-flex min-h-10 items-center gap-2 rounded-md px-2 py-2`}
        aria-expanded={open}
        aria-controls={id}
        onClick={onToggle}
      >
        {label}
        <Chevron open={open} />
      </button>
      {open && (
        <div
          id={id}
          role="menu"
          className="absolute left-0 top-full z-20 mt-2 min-w-56 rounded-lg border border-brand-lightgray bg-brand-white p-2 shadow-lg"
        >
          <div onClick={onSelect}>{children}</div>
        </div>
      )}
    </div>
  );
}

export function AuthShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { status, logout, validateSession } = useAuth();
  const protectedRoute = requiresAuthentication(pathname);
  const accountNavigationLinks = getAccountNavigationLinks(status);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<DropdownName | null>(null);
  const navigationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (protectedRoute && status === "unauthenticated") {
      router.replace("/login");
    }
  }, [protectedRoute, router, status]);

  useEffect(() => {
    function handleDocumentPointerDown(event: PointerEvent) {
      if (!navigationRef.current?.contains(event.target as Node)) {
        setOpenDropdown(null);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpenDropdown(null);
      setMobileOpen(false);
    }

    document.addEventListener("pointerdown", handleDocumentPointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handleDocumentPointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  function handleLogout() {
    setMobileOpen(false);
    setOpenDropdown(null);
    logoutAndRedirect(logout, (path) => router.replace(path));
  }

  function closeNavigation() {
    setMobileOpen(false);
    setOpenDropdown(null);
  }

  function toggleDropdown(name: DropdownName) {
    setOpenDropdown((current) => (current === name ? null : name));
  }

  function renderIncidentLinks(menuItems = false) {
    return (
      <>
        <NavigationLink href="/incidents" onSelect={closeNavigation} className={menuLinkClass} role={menuItems ? "menuitem" : undefined}>
          Incident Analysis
        </NavigationLink>
        <NavigationLink href="/incidents/manager" onSelect={closeNavigation} className={menuLinkClass} role={menuItems ? "menuitem" : undefined}>
          Incident Manager
        </NavigationLink>
      </>
    );
  }

  function renderAccountLinks(menuItems = false) {
    return (
      <>
        {accountNavigationLinks.map(({ label, href }) => (
          <NavigationLink key={href} href={href} onSelect={closeNavigation} className={menuLinkClass} role={menuItems ? "menuitem" : undefined}>
            {label}
          </NavigationLink>
        ))}
        {status === "authenticated" && (
          <button type="button" role={menuItems ? "menuitem" : undefined} className={`${menuLinkClass} w-full text-left`} onClick={handleLogout}>
            Logout
          </button>
        )}
      </>
    );
  }

  function renderNavigation({ mobile = false }: { mobile?: boolean } = {}) {
    const wrapperClass = mobile
      ? "grid gap-1 border-t border-brand-lightgray px-4 py-4"
      : "hidden items-center gap-1 md:flex";
    return (
      <nav ref={mobile ? undefined : navigationRef} aria-label="Main navigation" className={wrapperClass}>
        <NavigationLink href="/" onSelect={closeNavigation} className={mobile ? menuLinkClass : baseLinkClass}>
          Talent Tracker
        </NavigationLink>
        {mobile ? (
          <div className="border-t border-brand-lightgray/70 pt-2">
            <p className="px-3 py-2 text-xs font-bold uppercase tracking-[0.14em] text-brand-anthracite/50">Incidents</p>
            {renderIncidentLinks()}
          </div>
        ) : (
          <NavigationDropdown
            id="desktop-incidents-menu"
            label="Incidents"
            open={openDropdown === "incidents"}
            onToggle={() => toggleDropdown("incidents")}
            onSelect={closeNavigation}
          >
            {renderIncidentLinks(true)}
          </NavigationDropdown>
        )}
        <NavigationLink href="/suppliers" onSelect={closeNavigation} className={mobile ? menuLinkClass : baseLinkClass}>
          Suppliers
        </NavigationLink>
        {mobile ? (
          <div className="border-t border-brand-lightgray/70 pt-2">
            <p className="px-3 py-2 text-xs font-bold uppercase tracking-[0.14em] text-brand-anthracite/50">
              {status === "authenticated" ? "Profile" : "Account"}
            </p>
            {renderAccountLinks()}
          </div>
        ) : (
          <NavigationDropdown
            id="desktop-account-menu"
            label={status === "authenticated" ? "Profile" : "Account"}
            open={openDropdown === "account"}
            onToggle={() => toggleDropdown("account")}
            onSelect={closeNavigation}
          >
            {renderAccountLinks(true)}
          </NavigationDropdown>
        )}
      </nav>
    );
  }

  return (
    <>
      <header className="sticky top-0 z-50 w-full border-b border-brand-lightgray bg-brand-white/95 backdrop-blur">
        <div ref={navigationRef} className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex min-h-16 items-center gap-3">
          <Link href="/" className="shrink-0 text-lg font-black tracking-tight text-brand-anthracite">
            Nexova
          </Link>
          {renderNavigation()}
          <button
            type="button"
            className="ml-auto inline-flex min-h-10 min-w-10 items-center justify-center rounded-md border border-brand-lightgray text-brand-anthracite hover:bg-brand-lightgray/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-orange md:hidden"
            aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileOpen}
            aria-controls="mobile-navigation"
            onClick={() => setMobileOpen((current) => !current)}
          >
            <span className="sr-only">{mobileOpen ? "Close menu" : "Open menu"}</span>
            <span aria-hidden="true" className="text-xl leading-none">{mobileOpen ? "×" : "☰"}</span>
          </button>
          </div>
          {mobileOpen && (
            <div id="mobile-navigation" className="md:hidden">
              {renderNavigation({ mobile: true })}
            </div>
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