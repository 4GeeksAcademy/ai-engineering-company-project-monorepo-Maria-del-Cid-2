/**
 * useSectionTracking.ts
 *
 * Hook para instrumentar eventos de telemetría relacionados con navegación y secciones.
 *
 * Eventos emitidos:
 * - frontend_page_loaded: Cuando la página se carga o cambia de ruta
 * - section_viewed: Cuando se visualiza una sección específica
 *
 * Uso:
 * ```typescript
 * // En app/layout.tsx
 * useSectionTracking();
 *
 * // Opcionalmente, para secciones específicas:
 * useSectionTracking({ sectionId: "inventory-products-list" });
 * ```
 */

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { useTelemetry } from "./useTelemetry";

export interface UseSectionTrackingOptions {
  sectionId?: string;
  trackPageLoad?: boolean;
  trackSectionView?: boolean;
}

/**
 * Hook para trackear eventos de navegación y visualización de secciones
 *
 * @param options - Configuración del tracking
 */
export function useSectionTracking(
  options: UseSectionTrackingOptions = {}
): void {
  const {
    sectionId,
    trackPageLoad = true,
    trackSectionView = true,
  } = options;

  const telemetry = useTelemetry();
  const pathname = usePathname();
  const pageStartTimeRef = useRef<number>(Date.now());
  const sectionStartTimeRef = useRef<number>(Date.now());

  // Track frontend_page_loaded
  useEffect(() => {
    if (!trackPageLoad) return;

    const startTime = pageStartTimeRef.current;

    // Wait for page to be fully loaded
    const handlePageLoad = () => {
      const pageLoadMs = Math.round(Date.now() - startTime);

      telemetry.track("frontend_page_loaded", {
        path: pathname,
        page_load_ms: Math.min(pageLoadMs, 60000), // Cap at 60s to avoid outliers
      });
    };

    // Use performance API if available
    if (typeof window !== "undefined" && window.performance) {
      if (document.readyState === "complete") {
        // Page already loaded
        const pageLoadMs = Math.round(Date.now() - startTime);
        telemetry.track("frontend_page_loaded", {
          path: pathname,
          page_load_ms: Math.min(pageLoadMs, 60000),
        });
      } else {
        // Wait for page load
        window.addEventListener("load", handlePageLoad, { once: true });
        return () => {
          window.removeEventListener("load", handlePageLoad);
        };
      }
    }

    pageStartTimeRef.current = Date.now();
  }, [pathname, trackPageLoad, telemetry]);

  // Track section_viewed
  useEffect(() => {
    if (!trackSectionView) return;
    if (!sectionId) return;

    const startTime = sectionStartTimeRef.current;

    // Track section view when component mounts
    telemetry.track("section_viewed", {
      section_id: sectionId,
      time_on_section_ms: 0, // Will be updated on unmount
    });

    // On unmount, track time spent in section
    return () => {
      const timeOnSectionMs = Math.round(Date.now() - startTime);
      telemetry.track("section_viewed", {
        section_id: sectionId,
        time_on_section_ms: timeOnSectionMs,
      });
    };
  }, [sectionId, trackSectionView, telemetry]);
}

/**
 * Hook para trackear tiempo en secciones específicas
 *
 * Emite section_viewed al montar y desmontarse el componente
 *
 * @param sectionId - ID único de la sección
 *
 * @example
 * ```typescript
 * function InventoryProductsPage() {
 *   useTrackSectionView("inventory-products-list");
 *   return <div>Inventory Products</div>;
 * }
 * ```
 */
export function useTrackSectionView(sectionId: string): void {
  useSectionTracking({
    sectionId,
    trackPageLoad: false,
    trackSectionView: true,
  });
}

/**
 * Hook para trackear carga de página
 *
 * Emite frontend_page_loaded cuando la página se carga
 *
 * @example
 * ```typescript
 * function InventoryPage() {
 *   useTrackPageLoad();
 *   return <div>Inventory</div>;
 * }
 * ```
 */
export function useTrackPageLoad(): void {
  useSectionTracking({
    trackPageLoad: true,
    trackSectionView: false,
  });
}
