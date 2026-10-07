import type { SessionStatus } from "@/types/auth";

const protectedRoutes = ["/suppliers", "/account/profile"];

export function shouldShowLogout(status: SessionStatus): boolean {
  return status === "authenticated";
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