"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Input } from "@/components/ui";
import { AuthSubmissionGate } from "@/lib/auth-forms";
import { nexovaApi } from "@/lib/nexova-api";
import {
  getPasswordResetErrorMessage,
  PASSWORD_RESET_SUCCESS_REDIRECT,
  requestChangePassword,
  requestForgotPassword,
  requestResetPassword,
  validateChangePasswordFields,
  validateForgotPasswordFields,
  validateResetPasswordFields,
} from "@/lib/password-reset";
import type { PasswordResetFieldErrors } from "@/lib/password-reset";

type PasswordResetMode = "forgot" | "reset" | "change";

interface PasswordResetFormProps {
  mode: PasswordResetMode;
  token?: string;
}

const copy = {
  forgot: {
    eyebrow: "Recuperar acceso",
    title: "¿Has olvidado tu contraseña?",
    description: "Te enviaremos un enlace para crear una contraseña nueva.",
  },
  reset: {
    eyebrow: "Recuperar acceso",
    title: "Crea una contraseña nueva",
    description: "Elige una contraseña nueva para volver a acceder a tu cuenta.",
  },
  change: {
    eyebrow: "Cuenta Nexova",
    title: "Cambiar contraseña",
    description: "Actualiza tu contraseña para mantener tu cuenta protegida.",
  },
} as const;

export function PasswordResetForm({ mode, token = "" }: PasswordResetFormProps) {
  const router = useRouter();
  const gate = useRef(new AuthSubmissionGate());
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<PasswordResetFieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [completed, setCompleted] = useState(false);

  const content = copy[mode];
  const invalidResetLink = mode === "reset" && !token.trim();

  function clearField(field: keyof PasswordResetFieldErrors, value: string) {
    if (field === "email") setEmail(value);
    if (field === "currentPassword") setCurrentPassword(value);
    if (field === "newPassword") setNewPassword(value);
    if (field === "confirmPassword") setConfirmPassword(value);
    setErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors =
      mode === "forgot"
        ? validateForgotPasswordFields(email)
        : mode === "reset"
          ? validateResetPasswordFields(token, newPassword, confirmPassword)
          : validateChangePasswordFields(currentPassword, newPassword, confirmPassword);
    setErrors(nextErrors);
    setSubmitError(null);
    if (Object.keys(nextErrors).length > 0 || !gate.current.tryStart()) return;

    setSubmitting(true);
    try {
      if (mode === "forgot") {
        await requestForgotPassword(nexovaApi, email);
      } else if (mode === "reset") {
        await requestResetPassword(nexovaApi, token, newPassword, confirmPassword);
        router.replace(PASSWORD_RESET_SUCCESS_REDIRECT);
        return;
      } else {
        await requestChangePassword(
          nexovaApi,
          currentPassword,
          newPassword,
          confirmPassword,
        );
        nexovaApi.logout();
        router.replace("/login?changed=1");
        return;
      }
      setCompleted(true);
    } catch (error) {
      setSubmitError(getPasswordResetErrorMessage(error, mode));
    } finally {
      gate.current.finish();
      setSubmitting(false);
    }
  }

  if (invalidResetLink) {
    return (
      <section className="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:px-8">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">
          {content.eyebrow}
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight">Enlace no válido</h1>
        <p className="mt-3 text-sm leading-6 text-brand-anthracite/70">
          Solicita un enlace nuevo para restablecer tu contraseña.
        </p>
        <Link className="mt-6 inline-flex font-semibold text-brand-orange underline" href="/forgot-password">
          Solicitar otro enlace
        </Link>
      </section>
    );
  }

  if (completed) {
    return (
      <section className="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:px-8">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">
          {content.eyebrow}
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight">Solicitud completada</h1>
        <p className="mt-3 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm leading-6 text-green-800" role="status">
          {mode === "forgot"
            ? "Si existe una cuenta asociada, recibirás instrucciones para restablecer la contraseña."
            : "Tu contraseña se ha restablecido correctamente."}
        </p>
        <Link className="mt-6 inline-flex font-semibold text-brand-orange underline" href="/login">
          Ir a iniciar sesión
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">
          {content.eyebrow}
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight">{content.title}</h1>
        <p className="mt-3 text-sm leading-6 text-brand-anthracite/70">{content.description}</p>
      </div>

      <form noValidate onSubmit={submit} aria-busy={submitting} className="mt-8 rounded-lg border border-brand-lightgray bg-white p-5 shadow-sm sm:p-7">
        {submitError && (
          <p className="mb-5 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm leading-5 text-red-800" role="alert">
            {submitError}
          </p>
        )}
        <fieldset disabled={submitting} className="space-y-5">
          {mode === "forgot" && (
            <Input
              id="forgot-password-email"
              label="Correo electrónico"
              type="email"
              name="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              inputMode="email"
              required
              value={email}
              onChange={(event) => clearField("email", event.target.value)}
              error={errors.email}
            />
          )}
          {mode === "change" && (
            <Input
              id="current-password"
              label="Contraseña actual"
              type="password"
              name="currentPassword"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(event) => clearField("currentPassword", event.target.value)}
              error={errors.currentPassword}
            />
          )}
          {mode !== "forgot" && (
            <>
              <Input
                id={`${mode}-new-password`}
                label="Nueva contraseña"
                type="password"
                name="newPassword"
                autoComplete="new-password"
                required
                value={newPassword}
                onChange={(event) => clearField("newPassword", event.target.value)}
                error={errors.newPassword}
              />
              <Input
                id={`${mode}-confirm-password`}
                label="Confirmar nueva contraseña"
                type="password"
                name="confirmPassword"
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(event) => clearField("confirmPassword", event.target.value)}
                error={errors.confirmPassword}
              />
            </>
          )}
          <Button type="submit" loading={submitting} className="w-full sm:w-auto">
            {mode === "forgot" ? "Enviar enlace" : "Guardar contraseña"}
          </Button>
        </fieldset>
      </form>

      {mode === "forgot" || mode === "reset" ? (
        <p className="mt-6 text-sm text-brand-anthracite/70">
          <Link className="font-semibold text-brand-orange underline" href="/login">
            Volver a iniciar sesión
          </Link>
        </p>
      ) : null}
    </section>
  );
}
