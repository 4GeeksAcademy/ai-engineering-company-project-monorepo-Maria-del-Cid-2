/**
 * LayoutTelemetryProvider.tsx
 *
 * Componente que centraliza el tracking de telemetría a nivel de layout.
 * Emite eventos de frontend_page_loaded y section_viewed basado en navegación.
 */

"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { useTelemetryInit } from "@/hooks/useTelemetry";
import { useSectionTracking } from "@/hooks/useSectionTracking";

/**
 * Provider que inicializa la telemetría en el layout raíz
 * Debe usarse en app/layout.tsx dentro de un client component wrapper
 */
export function LayoutTelemetryProvider() {
  // Initialize telemetry on mount
  useTelemetryInit();

  // Track page load and section view
  useSectionTracking({
    trackPageLoad: true,
    trackSectionView: false,
  });

  return null;
}

/**
 * Hook para mapear rutas a section_id
 * Utilisé para trackear qué sección del backoffice está siendo visualizada
 */
export function useSectionIdFromRoute(pathname: string): string | null {
  // Map Next.js routes to section IDs
  if (pathname.startsWith("/inventory")) {
    if (pathname.includes("/products")) return "inventory-products-list";
    if (pathname.includes("/inbound")) return "inventory-inbound-create";
    if (pathname.includes("/outbound")) return "inventory-outbound-create";
    return "inventory-main";
  }

  if (pathname.startsWith("/incidents")) {
    return "incidents-manager";
  }

  if (pathname.startsWith("/suppliers")) {
    return "suppliers-directory";
  }

  if (pathname.startsWith("/candidates")) {
    return "candidates-pipeline";
  }

  if (pathname.startsWith("/account")) {
    return "account-management";
  }

  return null;
}
