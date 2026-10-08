import type { SessionStatus } from "@/types/auth";

const protectedRoutes = ["/suppliers", "/account/profile", "/account/change-password"];

export interface AccountNavigationLink {
  label: string;
  href: string;
}

const unauthenticatedLinks: AccountNavigationLink[] = [
  { label: "Login", href: "/login" },
  { label: "Create Account", href: "/register" },
];

const authenticatedLinks: AccountNavigationLink[] = [
  { label: "My Profile", href: "/account/profile" },
  { label: "Change Password", href: "/account/change-password" },
];

export function shouldShowLogout(status: SessionStatus): boolean {
  return status === "authenticated";
}

export function getAccountNavigationLinks(
  status: SessionStatus,
): AccountNavigationLink[] {
  if (status === "unauthenticated") return unauthenticatedLinks;
  if (status === "authenticated") return authenticatedLinks;
  return [];
}

export function requiresAuthentication(pathname: string): boolean {
  return protectedRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
}

export function logoutAndRedirect(
  logout: () => void,
  redirect: (path: string) => void,
): void {
  logout();
  redirect("/login");
}