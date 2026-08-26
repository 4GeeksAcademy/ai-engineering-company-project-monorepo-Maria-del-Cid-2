"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRecords } from "@/hooks";
import { CandidateList } from "@/components/candidates";
import { FilterBar, SearchBar } from "@/components/filters";
import { Pagination, Button, Spinner } from "@/components/ui";

function HomePageContent() {
  const {
    records,
    total,
    page,
    totalPages,
    loading,
    error,
    statusFilter,
    stageFilter,
    searchFilter,
    setStatusFilter,
    setStageFilter,
    setSearchFilter,
    clearFilters,
    setPage,
  } = useRecords();

  // Estado local para el input de búsqueda (respuesta inmediata en el campo)
  const [searchInput, setSearchInput] = useState(searchFilter);

  // Sincronizar searchInput si la URL cambia externamente (ej. botón "Limpiar")
  useEffect(() => {
    setSearchInput(searchFilter);
  }, [searchFilter]);

  // Debounce: actualiza la URL 350ms después de que el usuario deja de escribir
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== searchFilter) {
        setSearchFilter(searchInput);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput, searchFilter, setSearchFilter]);

  const handleClearFilters = useCallback(() => {
    setSearchInput("");
    clearFilters();
  }, [clearFilters]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-brand-anthracite">
            Candidaturas
          </h1>
          <p className="mt-1 text-sm text-brand-anthracite/70">
            Proceso de selección — Asistente de Dirección
          </p>
        </div>
        <Link href="/new">
          <Button>+ Nueva candidatura</Button>
        </Link>
      </div>

      {/* Filters + Search */}
      <div className="mt-8 space-y-4">
        <SearchBar value={searchInput} onChange={setSearchInput} />
        <FilterBar
          status={statusFilter}
          stage={stageFilter}
          onStatusChange={setStatusFilter}
          onStageChange={setStageFilter}
          onClear={handleClearFilters}
        />
      </div>

      {/* Results count */}
      {!loading && !error && (
        <p className="mt-6 text-xs font-medium uppercase tracking-[0.12em] text-brand-anthracite/50">
          {total} resultado{total !== 1 ? "s" : ""}
        </p>
      )}

      {/* List */}
      <div className="mt-4">
        <CandidateList records={records} loading={loading} error={error} />
      </div>

      {/* Pagination */}
      <div className="mt-6">
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          total={total}
          onPageChange={setPage}
        />
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      }
    >
      <HomePageContent />
    </Suspense>
  );
}
