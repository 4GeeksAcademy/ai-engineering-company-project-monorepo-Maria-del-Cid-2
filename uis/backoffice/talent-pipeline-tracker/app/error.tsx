"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui";

type RenderError = Error & {
  digest?: string;
};

export default function Error({
  error,
  reset,
}: {
  error: RenderError;
  reset: () => void;
}) {
  useEffect(() => {
    if (error.digest) {
      console.error("[Nexova] Render error", { digest: error.digest });
    }
  }, [error]);

  return (
    <main className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-3xl items-center px-4 py-16 sm:px-6 lg:px-8">
      <section
        aria-labelledby="error-title"
        className="w-full rounded-2xl border border-brand-lightgray bg-brand-white p-8 shadow-sm sm:p-12"
      >
        <p className="text-sm font-bold uppercase tracking-[0.14em] text-brand-orange">
          Nexova
        </p>
        <h1 id="error-title" className="mt-4 text-3xl font-black tracking-tight text-brand-anthracite">
          No hemos podido cargar esta página
        </h1>
        <p className="mt-4 max-w-xl text-base leading-7 text-brand-anthracite/70">
          Ha ocurrido un problema inesperado. Puedes intentarlo de nuevo o volver al inicio.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button type="button" onClick={reset}>
            Reintentar
          </Button>
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-full border border-brand-lightgray bg-brand-white px-5 py-2.5 text-sm font-semibold text-brand-anthracite transition-colors hover:bg-brand-lightgray/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-orange"
          >
            Volver al inicio
          </Link>
        </div>
      </section>
    </main>
  );
}