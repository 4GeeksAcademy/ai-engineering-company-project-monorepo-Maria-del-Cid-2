"use client";

import { useEffect } from "react";

type RenderError = Error & {
  digest?: string;
};

const pageStyle = {
  minHeight: "100vh",
  background: "#ffffff",
  color: "#1f2328",
  fontFamily: "Arial, Helvetica, sans-serif",
  padding: "2rem 1rem",
};

const panelStyle = {
  maxWidth: "48rem",
  margin: "10vh auto 0",
  border: "1px solid #e5e7eb",
  borderRadius: "1rem",
  padding: "3rem",
  boxShadow: "0 8px 24px rgba(31, 35, 40, 0.08)",
};

export default function GlobalError({
  error,
  reset,
}: {
  error: RenderError;
  reset: () => void;
}) {
  useEffect(() => {
    if (error.digest) {
      console.error("[Nexova] Global render error", { digest: error.digest });
    }
  }, [error]);

  return (
    <html lang="es">
      <body style={pageStyle}>
        <main>
          <section aria-labelledby="global-error-title" style={panelStyle}>
            <p style={{ color: "#f97316", fontSize: "0.875rem", fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase" }}>
              Nexova
            </p>
            <h1 id="global-error-title" style={{ fontSize: "2rem", lineHeight: 1.2, margin: "1rem 0 0", fontWeight: 800 }}>
              Ha ocurrido un problema inesperado
            </h1>
            <p style={{ color: "rgba(31, 35, 40, 0.7)", lineHeight: 1.75, margin: "1rem 0 0", maxWidth: "36rem" }}>
              La aplicación no ha podido cargar correctamente. Puedes reintentar o volver al inicio.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginTop: "2rem" }}>
              <button
                type="button"
                onClick={reset}
                style={{ background: "#f97316", border: 0, borderRadius: "999px", color: "#ffffff", cursor: "pointer", fontSize: "0.875rem", fontWeight: 700, padding: "0.7rem 1.25rem" }}
              >
                Reintentar
              </button>
              <a
                href="/"
                style={{ border: "1px solid #e5e7eb", borderRadius: "999px", color: "#1f2328", fontSize: "0.875rem", fontWeight: 600, padding: "0.7rem 1.25rem", textDecoration: "none" }}
              >
                Volver al inicio
              </a>
            </div>
          </section>
        </main>
      </body>
    </html>
  );
}