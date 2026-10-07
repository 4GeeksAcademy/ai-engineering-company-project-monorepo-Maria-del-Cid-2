"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, useSyncExternalStore } from "react";
import { Button, Input } from "@/components/ui";
import {
  AuthSubmissionGate,
  getAuthErrorMessage,
  registerUser,
  signIn,
  validateLoginFields,
  validateRegistrationFields,
} from "@/lib/auth-forms";
import { nexovaApi } from "@/lib/nexova-api";
import type { AuthFieldErrors, AuthFormMode } from "@/lib/auth-forms";

interface AuthFormProps {
  mode: AuthFormMode;
  expired?: boolean;
}

const subscribeToNothing = () => () => {};
const getClientHydrationSnapshot = () => true;
const getServerHydrationSnapshot = () => false;

export function AuthForm({ mode, expired = false }: AuthFormProps) {
  const router = useRouter();
  const isHydrated = useSyncExternalStore(
    subscribeToNothing,
    getClientHydrationSnapshot,
    getServerHydrationSnapshot,
  );
  const gate = useRef(new AuthSubmissionGate());
  const isLogin = mode === "login";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<AuthFieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [registered, setRegistered] = useState(false);

  function updateField(field: keyof AuthFieldErrors, value: string) {
    if (field === "email") setEmail(value);
    if (field === "password") setPassword(value);
    if (field === "confirmPassword") setConfirmPassword(value);
    setErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = isLogin
      ? validateLoginFields(email, password)
      : validateRegistrationFields(email, password, confirmPassword);
    setErrors(nextErrors);
    setSubmitError(null);
    if (Object.keys(nextErrors).length > 0 || !gate.current.tryStart()) return;

    setSubmitting(true);
    try {
      if (isLogin) {
        await signIn(nexovaApi, email, password);
        router.replace("/");
      } else {
        await registerUser(nexovaApi, email, password);
        setRegistered(true);
      }
    } catch (error) {
      setSubmitError(getAuthErrorMessage(error, mode));
    } finally {
      gate.current.finish();
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto grid min-h-[calc(100svh-4rem)] w-full max-w-6xl place-items-center px-4 py-8 sm:px-6 lg:px-8">
      <section className="grid w-full overflow-hidden rounded-lg border border-brand-lightgray bg-white shadow-sm md:grid-cols-[0.85fr_1.15fr]">
        <div className="flex min-h-56 flex-col justify-between bg-brand-anthracite p-7 text-white sm:p-10 md:min-h-[500px]">
          <p className="text-sm font-bold uppercase tracking-[0.16em]">
            Nexova <span className="text-brand-orange">/</span> Backoffice
          </p>
          <div className="py-8 md:py-0">
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">
              Acceso interno
            </p>
            <h2 className="max-w-sm text-3xl font-bold leading-tight sm:text-4xl">
              Herramientas para el trabajo de cada día.
            </h2>
            <p className="mt-4 max-w-sm text-sm leading-6 text-white/70">
              Selección y operaciones, en un mismo espacio de trabajo.
            </p>
          </div>
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-white/50">
            Valencia · Miami
          </p>
        </div>

        <div className="flex items-center p-6 sm:p-10 lg:p-14">
          <div className="mx-auto w-full max-w-md">
            <p className="text-sm font-semibold text-brand-orange">
              {isLogin ? "Accede a tu espacio" : "Nuevo acceso"}
            </p>
            <h1 className="mt-2 text-2xl font-bold text-brand-anthracite sm:text-3xl">
              {isLogin ? "Iniciar sesión" : "Crear una cuenta"}
            </h1>
            <p className="mt-2 text-sm leading-6 text-brand-anthracite/65">
              {isLogin
                ? "Introduce tus credenciales para continuar."
                : "Registra tu correo electrónico para acceder al backoffice."}
            </p>

            {expired && isLogin && (
              <p
                role="status"
                className="mt-6 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
              >
                Tu sesión ha expirado. Inicia sesión de nuevo para continuar.
              </p>
            )}

            {registered && !isLogin ? (
              <div
                role="status"
                className="mt-8 rounded-md border border-green-300 bg-green-50 p-5"
              >
                <h2 className="font-semibold text-green-900">
                  Cuenta creada correctamente
                </h2>
                <p className="mt-2 text-sm leading-6 text-green-800">
                  Ya puedes iniciar sesión con el correo y la contraseña que registraste.
                </p>
                <Link
                  href="/login"
                  className="mt-4 inline-flex font-semibold text-brand-orange underline decoration-2 underline-offset-4 hover:text-orange-700 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand-orange"
                >
                  Ir a iniciar sesión
                </Link>
              </div>
            ) : !isHydrated ? (
              <div
                role="status"
                aria-live="polite"
                aria-busy="true"
                className="mt-8 min-h-64 rounded-md border border-brand-lightgray bg-brand-white"
              >
                <span className="sr-only">Preparando formulario…</span>
              </div>
            ) : (
              <form
                noValidate
                onSubmit={handleSubmit}
                aria-busy={submitting}
                className="mt-8 space-y-5"
              >
                {submitError && (
                  <p
                    role="alert"
                    className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm leading-5 text-red-800"
                  >
                    {submitError}
                  </p>
                )}

                <fieldset disabled={submitting} className="space-y-5">
                  <Input
                    id="auth-email"
                    label="Correo electrónico"
                    type="email"
                    name="email"
                    autoComplete="email"
                    autoCapitalize="none"
                    spellCheck={false}
                    inputMode="email"
                    required
                    value={email}
                    onChange={(event) => updateField("email", event.target.value)}
                    error={errors.email}
                  />

                  <Input
                    id="auth-password"
                    label="Contraseña"
                    type="password"
                    name="password"
                    autoComplete={isLogin ? "current-password" : "new-password"}
                    required
                    value={password}
                    onChange={(event) => updateField("password", event.target.value)}
                    error={errors.password}
                  />

                  {!isLogin && (
                    <Input
                      id="auth-confirm-password"
                      label="Confirmar contraseña"
                      type="password"
                      name="confirmPassword"
                      autoComplete="new-password"
                      required
                      value={confirmPassword}
                      onChange={(event) =>
                        updateField("confirmPassword", event.target.value)
                      }
                      error={errors.confirmPassword}
                    />
                  )}

                  <Button
                    type="submit"
                    loading={submitting}
                    className="w-full rounded-md py-3"
                  >
                    {isLogin ? "Iniciar sesión" : "Crear cuenta"}
                  </Button>
                </fieldset>
              </form>
            )}

            {!registered && (
              <p className="mt-7 text-sm text-brand-anthracite/70">
                {isLogin ? "¿Aún no tienes cuenta?" : "¿Ya tienes cuenta?"}{" "}
                <Link
                  href={isLogin ? "/register" : "/login"}
                  className="font-semibold text-brand-orange underline decoration-2 underline-offset-4 hover:text-orange-700 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand-orange"
                >
                  {isLogin ? "Regístrate" : "Inicia sesión"}
                </Link>
              </p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}