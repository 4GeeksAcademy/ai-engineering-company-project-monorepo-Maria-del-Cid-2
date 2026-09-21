"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRecord } from "@/lib/records";
import { Button, Input } from "@/components/ui";
import type { RecordCreate } from "@/types";

interface FormErrors {
  full_name?: string;
  email?: string;
  phone?: string;
  position?: string;
  experience_years?: string;
}

export function CandidateForm() {
  const router = useRouter();

  const [formData, setFormData] = useState<RecordCreate>({
    full_name: "",
    email: "",
    phone: "",
    position: "",
    experience_years: 0,
    linkedin_url: "",
    cv_url: "",
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.full_name.trim()) {
      newErrors.full_name = "El nombre es obligatorio";
    }
    if (!formData.email.trim()) {
      newErrors.email = "El email es obligatorio";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = "Email no válido";
    }
    if (!formData.phone.trim()) {
      newErrors.phone = "El teléfono es obligatorio";
    }
    if (!formData.position.trim()) {
      newErrors.position = "El puesto es obligatorio";
    }
    if (
      formData.experience_years === undefined ||
      formData.experience_years < 0
    ) {
      newErrors.experience_years =
        "Los años de experiencia deben ser 0 o más";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setSubmitting(true);
    setSubmitError(null);

    try {
      const payload: RecordCreate = {
        full_name: formData.full_name.trim(),
        email: formData.email.trim(),
        phone: formData.phone.trim(),
        position: formData.position.trim(),
        experience_years: formData.experience_years,
      };

      if (formData.linkedin_url?.trim()) {
        payload.linkedin_url = formData.linkedin_url.trim();
      }
      if (formData.cv_url?.trim()) {
        payload.cv_url = formData.cv_url.trim();
      }

      const created = await createRecord(payload);
      router.push(`/candidates/${created.id}`);
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Error al crear candidatura"
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (field: keyof RecordCreate, value: string | number) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {submitError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">{submitError}</p>
        </div>
      )}

      <Input
        label="Nombre completo *"
        placeholder="Ej: María García López"
        value={formData.full_name}
        onChange={(e) => handleChange("full_name", e.target.value)}
        error={errors.full_name}
      />

      <Input
        label="Email *"
        type="email"
        placeholder="Ej: maria.garcia@email.com"
        value={formData.email}
        onChange={(e) => handleChange("email", e.target.value)}
        error={errors.email}
      />

      <Input
        label="Teléfono *"
        placeholder="Ej: +34 612 345 678"
        value={formData.phone}
        onChange={(e) => handleChange("phone", e.target.value)}
        error={errors.phone}
      />

      <Input
        label="Puesto *"
        placeholder="Ej: Asistente de Dirección"
        value={formData.position}
        onChange={(e) => handleChange("position", e.target.value)}
        error={errors.position}
      />

      <Input
        label="Años de experiencia *"
        type="number"
        min={0}
        step={0.5}
        placeholder="Ej: 5"
        value={formData.experience_years || ""}
        onChange={(e) =>
          handleChange("experience_years", parseFloat(e.target.value) || 0)
        }
        error={errors.experience_years}
      />

      <Input
        label="LinkedIn (opcional)"
        type="url"
        placeholder="https://linkedin.com/in/..."
        value={formData.linkedin_url ?? ""}
        onChange={(e) => handleChange("linkedin_url", e.target.value)}
      />

      <Input
        label="URL del CV (opcional)"
        type="url"
        placeholder="https://..."
        value={formData.cv_url ?? ""}
        onChange={(e) => handleChange("cv_url", e.target.value)}
      />

      <div className="flex items-center gap-3 pt-2">
        <Button type="submit" loading={submitting}>
          Registrar candidatura
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => router.push("/")}
        >
          Cancelar
        </Button>
      </div>
    </form>
  );
}