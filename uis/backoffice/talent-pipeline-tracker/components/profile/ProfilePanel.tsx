"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { Button, Input, Spinner, Textarea } from "@/components/ui";
import { nexovaApi } from "@/lib/nexova-api";
import { getMyProfile, updateMyProfile } from "@/lib/profile-api";
import type { ProfileUpdatePayload } from "@/lib/profile-api";
import type { UserProfile } from "@/types/auth";

const emptyProfile: ProfileUpdatePayload = {
  name: "",
  phone: "",
  address: "",
};

function profileFields(profile: UserProfile | null): ProfileUpdatePayload {
  return {
    name: profile?.name ?? "",
    phone: profile?.phone ?? "",
    address: profile?.address ?? "",
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "No se pudo completar la solicitud. Inténtalo de nuevo.";
}

export function ProfilePanel() {
  const { status, updateProfile, validateSession } = useAuth();
  const [fields, setFields] = useState<ProfileUpdatePayload>(emptyProfile);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [profileMissing, setProfileMissing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    setSaveError(null);
    setSaved(false);
    try {
      const profile = await getMyProfile(nexovaApi);
      setFields(profileFields(profile));
      setProfileMissing(profile === null);
    } catch (error) {
      setLoadError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (status !== "authenticated") return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadProfile();
  }, [loadProfile, status]);

  function changeField(field: keyof ProfileUpdatePayload, value: string) {
    setFields((current) => ({ ...current, [field]: value }));
    setSaved(false);
    setSaveError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const profile = await updateMyProfile(nexovaApi, fields);
      updateProfile(profile);
      setFields(profileFields(profile));
      setProfileMissing(false);
      setSaved(true);
    } catch (error) {
      setSaveError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  if (status === "loading") {
    return (
      <div className="mx-auto flex max-w-3xl items-center justify-center px-4 py-16" aria-busy="true">
        <Spinner />
        <span className="sr-only">Comprobando sesión</span>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return (
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-black">Mi perfil</h1>
        <p className="mt-3 text-sm text-brand-anthracite/70">
          Inicia sesión para consultar y editar tu perfil.
        </p>
        <Link className="mt-5 inline-flex font-semibold text-brand-orange underline" href="/login">
          Ir a iniciar sesión
        </Link>
      </section>
    );
  }

  if (status === "error") {
    return (
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-black">Mi perfil</h1>
        <p className="mt-3 text-sm text-red-700" role="alert">
          No se pudo comprobar tu sesión. {" "}
          <button className="font-semibold underline" onClick={() => void validateSession()}>
            Reintentar
          </button>
        </p>
      </section>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">
          Cuenta Nexova
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight">Mi perfil</h1>
        <p className="mt-3 text-sm leading-6 text-brand-anthracite/70">
          Consulta y actualiza tus datos de contacto.
        </p>
      </div>

      {loading ? (
        <div className="mt-8 flex items-center gap-3" role="status" aria-busy="true">
          <Spinner size="sm" />
          <span className="text-sm text-brand-anthracite/70">Cargando perfil…</span>
        </div>
      ) : loadError ? (
        <section className="mt-8 rounded-lg border border-red-200 bg-red-50 p-5">
          <p className="text-sm text-red-800" role="alert">{loadError}</p>
          <Button type="button" variant="secondary" className="mt-4" onClick={() => void loadProfile()}>
            Reintentar
          </Button>
        </section>
      ) : (
        <section className="mt-8 rounded-lg border border-brand-lightgray bg-white p-5 shadow-sm sm:p-7">
          {profileMissing && (
            <p className="mb-5 text-sm text-brand-anthracite/70" role="status">
              Aún no tienes un perfil. Completa estos datos para guardarlo.
            </p>
          )}

          <form onSubmit={submit} aria-busy={saving}>
            {saveError && (
              <p className="mb-5 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
                {saveError}
              </p>
            )}
            {saved && (
              <p className="mb-5 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800" role="status">
                Perfil guardado correctamente.
              </p>
            )}

            <fieldset disabled={saving} className="space-y-5">
              <Input
                id="profile-name"
                name="name"
                label="Nombre"
                autoComplete="name"
                value={fields.name}
                onChange={(event) => changeField("name", event.target.value)}
              />
              <Input
                id="profile-phone"
                name="phone"
                label="Teléfono"
                type="tel"
                autoComplete="tel"
                value={fields.phone}
                onChange={(event) => changeField("phone", event.target.value)}
              />
              <div className="flex flex-col gap-1">
                <label htmlFor="profile-address" className="text-sm font-medium text-zinc-700">
                  Dirección
                </label>
                <Textarea
                  id="profile-address"
                  name="address"
                  autoComplete="street-address"
                  value={fields.address}
                  onChange={(event) => changeField("address", event.target.value)}
                />
              </div>
              <Button type="submit" loading={saving}>
                Guardar perfil
              </Button>
            </fieldset>
          </form>
        </section>
      )}
    </div>
  );
}