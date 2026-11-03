/**
 * useFormLifecycleTracking.ts
 *
 * Hook para rastrear el ciclo de vida completo de los formularios:
 * - form_opened: cuando se abre/monta el formulario
 * - form_abandoned: cuando se abandona sin enviar
 *
 * Implementa:
 * - Heartbeat cada 30s para detectar si sigue activo
 * - Detección de abandono por inactividad (60s)
 * - Correlación mediante instance_id único
 */

import { useEffect, useRef, useState } from "react";
import { useTelemetry } from "./useTelemetry";

export interface UseFormLifecycleTrackingOptions {
  formId: string;
  trackOpen?: boolean;
  trackAbandon?: boolean;
  inactivityTimeoutMs?: number; // Default: 60000 (60s)
}

/**
 * Hook para rastrear el ciclo de vida de un formulario
 *
 * @param options - Configuración del tracking
 *
 * @example
 * ```typescript
 * function LoginForm() {
 *   const instanceId = useFormLifecycleTracking({
 *     formId: "login-form",
 *     trackOpen: true,
 *     trackAbandon: true,
 *   });
 *
 *   // Use instanceId if needed for custom tracking
 *   return <form>{...}</form>;
 * }
 * ```
 */
export function useFormLifecycleTracking(
  options: UseFormLifecycleTrackingOptions
): string {
  const {
    formId,
    trackOpen = true,
    trackAbandon = true,
    inactivityTimeoutMs = 60000,
  } = options;

  const telemetry = useTelemetry();

  // Generate unique instance ID for this form opening
  const instanceIdRef = useRef<string>("");
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const inactivityTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastActivityRef = useRef<number>(Date.now());
  const hasAbandonedRef = useRef<boolean>(false);

  // Generate UUID v4 instance ID on mount (matching telemetry-plan.md contract)
  const formOpenTimeRef = useRef<number>(Date.now());
  if (!instanceIdRef.current) {
    instanceIdRef.current = crypto.randomUUID?.() ?? `${formId}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  }

  // Track form_opened on mount
  useEffect(() => {
    if (!trackOpen) return;

    telemetry.track("form_opened", {
      form_id: formId,
      instance_id: instanceIdRef.current,
    });

    // Setup activity tracking
    const handleActivity = () => {
      lastActivityRef.current = Date.now();
    };

    // Listen for form interactions
    const form = document.querySelector(`form[data-form-id="${formId}"]`);
    if (form) {
      form.addEventListener("input", handleActivity);
      form.addEventListener("change", handleActivity);
      form.addEventListener("click", handleActivity);
    }

    // Setup inactivity timer
    const startInactivityTimer = () => {
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);

      inactivityTimerRef.current = setTimeout(() => {
        const timeSinceActivity = Date.now() - lastActivityRef.current;
        if (timeSinceActivity >= inactivityTimeoutMs && !hasAbandonedRef.current) {
          handleFormAbandoned("inactivity_timeout");
        }
      }, inactivityTimeoutMs);
    };

    startInactivityTimer();

    // Heartbeat: reset inactivity timer every 30s to keep form alive
    heartbeatTimerRef.current = setInterval(() => {
      const timeSinceActivity = Date.now() - lastActivityRef.current;
      if (timeSinceActivity < inactivityTimeoutMs && !hasAbandonedRef.current) {
        startInactivityTimer();
      }
    }, 30_000);

    // Setup visibility change listener (tab switch/minimize)
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab went hidden - could be abandoned
        if (!hasAbandonedRef.current) {
          handleFormAbandoned("navigation_away");
        }
      } else {
        // Tab is visible again - reset inactivity timer
        lastActivityRef.current = Date.now();
        startInactivityTimer();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      if (form) {
        form.removeEventListener("input", handleActivity);
        form.removeEventListener("change", handleActivity);
        form.removeEventListener("click", handleActivity);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    };
  }, [formId, trackOpen, inactivityTimeoutMs, telemetry]);

  // Function to handle form abandonment
  const handleFormAbandoned = (reason: string) => {
    if (hasAbandonedRef.current) return;
    hasAbandonedRef.current = true;

    if (trackAbandon) {
      const formOpenTime = formOpenTimeRef.current;
      const timeOpen = formOpenTime ? Date.now() - formOpenTime : 0;
      telemetry.track("form_abandoned", {
        form_id: formId,
        instance_id: instanceIdRef.current,
        abandon_reason: reason,
        time_open_ms: Math.max(timeOpen, 0),
      });
    }

    // Cleanup timers
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
  };

  // Expose function to mark form as successfully submitted (prevents abandon tracking)
  useEffect(() => {
    formSubmittedRegistry.set(instanceIdRef.current, () => {
      hasAbandonedRef.current = true;
    });
    return () => {
      formSubmittedRegistry.delete(instanceIdRef.current);
    };
  }, []);

  return instanceIdRef.current;
}

const formSubmittedRegistry = new Map<string, () => void>();

/**
 * Marca un formulario como enviado exitosamente (previene form_abandoned)
 *
 * Llama esta función después de un envío exitoso para evitar que se emita form_abandoned
 *
 * @param instanceId - ID de instancia del formulario
 *
 * @example
 * ```typescript
 * async function handleSubmit() {
 *   const response = await submitForm();
 *   markFormAsSubmitted(instanceId);
 * }
 * ```
 */
export function markFormAsSubmitted(instanceId: string): void {
  formSubmittedRegistry.get(instanceId)?.();
}
