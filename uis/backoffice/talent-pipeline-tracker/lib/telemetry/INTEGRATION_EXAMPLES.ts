/**
 * Example: How to integrate TelemetryService in your app.
 *
 * This file shows the recommended patterns for using TelemetryService
 * in your Next.js application.
 */

// ============================================================================
// 1. INITIALIZE IN ROOT LAYOUT (app/layout.tsx)
// ============================================================================

// app/layout.tsx
// "use client";
// import { useTelemetryInit } from "@/hooks/useTelemetry";
//
// export default function RootLayout({ children }) {
//   // Initialize telemetry service once on app mount
//   useTelemetryInit();
//
//   return (
//     <html>
//       <body>{children}</body>
//     </html>
//   );
// }

// ============================================================================
// 2. TRACK EVENTS FROM COMPONENTS
// ============================================================================

// components/auth/LoginForm.tsx
// "use client";
// import { useTelemetry } from "@/hooks/useTelemetry";
// import { useState } from "react";
//
// export function LoginForm() {
//   const telemetry = useTelemetry();
//   const [loading, setLoading] = useState(false);
//
//   const handleLogin = async (email: string, password: string) => {
//     try {
//       setLoading(true);
//       const response = await fetch("/api/auth/login", {
//         method: "POST",
//         body: JSON.stringify({ username: email, password }),
//       });
//
//       if (response.ok) {
//         const data = await response.json();
//         // Track successful login
//         telemetry.track("login_succeeded", {
//           user_uuid: data.user.user_uuid,
//         });
//
//         // Update session context
//         telemetry.updateSession({
//           userUuid: data.user.user_uuid,
//           isAuthenticated: true,
//         });
//       } else {
//         // Track failed login
//         telemetry.track("login_failed", {
//           user_uuid: email, // Can use email as identifier for failed attempts
//           failure_reason: "invalid_credentials",
//         });
//       }
//     } finally {
//       setLoading(false);
//     }
//   };
//
//   return (
//     <form onSubmit={(e) => {
//       e.preventDefault();
//       const formData = new FormData(e.currentTarget);
//       handleLogin(
//         formData.get("email") as string,
//         formData.get("password") as string
//       );
//     }}>
//       {/* form fields */}
//     </form>
//   );
// }

// ============================================================================
// 3. TRACK PAGE LOADS
// ============================================================================

// components/PageLoadTracker.tsx
// "use client";
// import { useTelemetry } from "@/hooks/useTelemetry";
// import { usePathname, useSearchParams } from "next/navigation";
// import { useEffect } from "react";
//
// export function PageLoadTracker() {
//   const telemetry = useTelemetry();
//   const pathname = usePathname();
//   const searchParams = useSearchParams();
//
//   useEffect(() => {
//     const startTime = performance.now();
//
//     // Wait for page to be fully loaded
//     const handleLoad = () => {
//       const pageLoadMs = Math.round(performance.now() - startTime);
//       telemetry.track("frontend_page_loaded", {
//         path: pathname,
//         page_load_ms: pageLoadMs,
//       });
//     };
//
//     window.addEventListener("load", handleLoad);
//     return () => window.removeEventListener("load", handleLoad);
//   }, [pathname, telemetry]);
//
//   return null;
// }

// ============================================================================
// 4. TRACK FORM SUBMISSION
// ============================================================================

// hooks/useFormTracking.ts
// "use client";
// import { useCallback, useId } from "react";
// import { useTelemetry } from "./useTelemetry";
//
// export function useFormTracking(formId: string) {
//   const telemetry = useTelemetry();
//   const instanceId = useId(); // Unique per form instance
//
//   const trackValidationError = useCallback(
//     (field: string, error: string) => {
//       telemetry.track("form_validation_failed", {
//         form_id: formId,
//         field,
//         validation_error: error,
//         instance_id: instanceId,
//       });
//     },
//     [telemetry, formId, instanceId]
//   );
//
//   const trackSuccess = useCallback(() => {
//     telemetry.track("inbound_order_created", {
//       // ... payload
//       instance_id: instanceId, // Link to form opening
//     });
//   }, [telemetry, instanceId]);
//
//   return { trackValidationError, trackSuccess };
// }

// ============================================================================
// 5. TRACK SECTION VIEWS
// ============================================================================

// components/InventorySection.tsx
// "use client";
// import { useTelemetry } from "@/hooks/useTelemetry";
// import { useEffect } from "react";
//
// export function InventorySection() {
//   const telemetry = useTelemetry();
//   const startTime = useRef(Date.now());
//
//   useEffect(() => {
//     return () => {
//       const timeOnSection = Date.now() - startTime.current;
//       telemetry.track("section_viewed", {
//         section_id: "inventory-products-list",
//         time_on_section_ms: timeOnSection,
//       });
//     };
//   }, [telemetry]);
//
//   return (
//     <div>
//       {/* Inventory content */}
//     </div>
//   );
// }

// ============================================================================
// 6. ERROR TRACKING
// ============================================================================

// components/ErrorBoundary.tsx
// import { useTelemetry } from "@/hooks/useTelemetry";
//
// export function ErrorBoundary({ children }: { children: React.ReactNode }) {
//   const telemetry = useTelemetry();
//
//   useEffect(() => {
//     const handler = (event: ErrorEvent) => {
//       telemetry.track("frontend_render_error", {
//         component: "ErrorBoundary",
//         error_type: event.error?.name || "Unknown",
//         error_message: event.error?.message || event.message,
//       });
//     };
//
//     window.addEventListener("error", handler);
//     return () => window.removeEventListener("error", handler);
//   }, [telemetry]);
//
//   return <>{children}</>;
// }

export const telemetryExamples = {
  note: "See code comments above for complete integration examples.",
};
