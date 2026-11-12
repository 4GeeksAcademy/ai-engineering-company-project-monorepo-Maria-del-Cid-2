# Form Validation Patterns - Telemetry Integration Guide

## Overview
This document catalogs all form components in the backoffice talent-pipeline-tracker, their validation methods, error handling patterns, and where to emit `form_validation_failed` events for Phase 3 telemetry instrumentation.

---

## 1. Form Components Overview

| Component | Location | Type | Primary Purpose |
|-----------|----------|------|-----------------|
| **AuthForm** | `components/auth/AuthForm.tsx` | Auth | Login & Registration |
| **PasswordResetForm** | `components/auth/PasswordResetForm.tsx` | Auth | Password management |
| **CandidateForm** | `components/candidates/CandidateForm.tsx` | Business | Create candidate records |
| **InboundFormPanel** | `components/inventory/InboundFormPanel.tsx` | Business | Record inbound inventory |
| **OutboundFormPanel** | `components/inventory/OutboundFormPanel.tsx` | Business | Record outbound inventory |

---

## 2. Detailed Pattern Analysis

### 2.1 AuthForm (Login & Registration)

**File:** [`components/auth/AuthForm.tsx`](../../uis/backoffice/talent-pipeline-tracker/components/auth/AuthForm.tsx#L1-L100)

#### Validation Pattern
```typescript
// Validation functions are in lib/auth-forms.ts
validateLoginFields(email, password): AuthFieldErrors
validateRegistrationFields(email, password, confirmPassword): AuthFieldErrors
```

#### Error Handling Pattern
```typescript
const [errors, setErrors] = useState<AuthFieldErrors>({});

// On field change: clear error for that field
function updateField(field: keyof AuthFieldErrors, value: string) {
  setErrors((current) => ({ ...current, [field]: undefined }));
  setSubmitError(null);
}

// On submit: validate and set errors
function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
  const nextErrors = isLogin
    ? validateLoginFields(email, password)
    : validateRegistrationFields(email, password, confirmPassword);
  setErrors(nextErrors);
  if (Object.keys(nextErrors).length > 0 || !gate.current.tryStart()) return;
}
```

#### Current Telemetry
âœ… Already implemented:
- `login_succeeded` - tracked after successful sign-in
- `login_failed` - tracked on auth error
- `account_created` - tracked after successful registration
- `session_expired` - tracked when session expires

#### Where to Add form_validation_failed
**Location:** Line 75-79 in `handleSubmit` function
```typescript
async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
  event.preventDefault();
  const nextErrors = isLogin
    ? validateLoginFields(email, password)
    : validateRegistrationFields(email, password, confirmPassword);
  setErrors(nextErrors);
  setSubmitError(null);
  
  // ðŸ”´ ADD HERE: Track validation failures
  if (Object.keys(nextErrors).length > 0) {
    telemetry.track("form_validation_failed", {
      form_name: isLogin ? "login" : "register",
      field_errors: Object.keys(nextErrors), // e.g., ["email", "password"]
      form_mode: mode,
    });
    if (!gate.current.tryStart()) return;
    return;
  }
  // ... rest of submit
}
```

---

### 2.2 PasswordResetForm

**File:** [`components/auth/PasswordResetForm.tsx`](../../uis/backoffice/talent-pipeline-tracker/components/auth/PasswordResetForm.tsx#L1-L100)

#### Validation Pattern
```typescript
// Three modes: "forgot", "reset", "change"
validateForgotPasswordFields(email): PasswordResetFieldErrors
validateResetPasswordFields(token, newPassword, confirmPassword): PasswordResetFieldErrors
validateChangePasswordFields(currentPassword, newPassword, confirmPassword): PasswordResetFieldErrors
```

#### Error Handling Pattern
```typescript
const [errors, setErrors] = useState<PasswordResetFieldErrors>({});

function clearField(field: keyof PasswordResetFieldErrors, value: string) {
  // Update field state
  setErrors((current) => ({ ...current, [field]: undefined }));
  setSubmitError(null);
}

async function submit(event: React.FormEvent<HTMLFormElement>) {
  event.preventDefault();
  const nextErrors = mode === "forgot"
    ? validateForgotPasswordFields(email)
    : mode === "reset"
      ? validateResetPasswordFields(token, newPassword, confirmPassword)
      : validateChangePasswordFields(currentPassword, newPassword, confirmPassword);
  setErrors(nextErrors);
  if (Object.keys(nextErrors).length > 0 || !gate.current.tryStart()) return;
}
```

#### Where to Add form_validation_failed
**Location:** Line 72-78 in `submit` function
```typescript
async function submit(event: React.FormEvent<HTMLFormElement>) {
  event.preventDefault();
  const nextErrors = mode === "forgot"
    ? validateForgotPasswordFields(email)
    : mode === "reset"
      ? validateResetPasswordFields(token, newPassword, confirmPassword)
      : validateChangePasswordFields(currentPassword, newPassword, confirmPassword);
  setErrors(nextErrors);
  setSubmitError(null);
  
  // ðŸ”´ ADD HERE: Track validation failures
  if (Object.keys(nextErrors).length > 0) {
    telemetry.track("form_validation_failed", {
      form_name: "password_reset",
      reset_mode: mode, // "forgot" | "reset" | "change"
      field_errors: Object.keys(nextErrors),
    });
    if (!gate.current.tryStart()) return;
    return;
  }
  // ... rest of submit
}
```

---

### 2.3 CandidateForm

**File:** [`components/candidates/CandidateForm.tsx`](../../uis/backoffice/talent-pipeline-tracker/components/candidates/CandidateForm.tsx#L1-L150)

#### Validation Pattern
```typescript
interface FormErrors {
  full_name?: string;
  email?: string;
  phone?: string;
  position?: string;
  experience_years?: string;
}

const validate = (): boolean => {
  const newErrors: FormErrors = {};
  
  if (!formData.full_name.trim())
    newErrors.full_name = "El nombre es obligatorio";
  if (!formData.email.trim())
    newErrors.email = "El email es obligatorio";
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email))
    newErrors.email = "Email no vÃ¡lido";
  if (!formData.phone.trim())
    newErrors.phone = "El telÃ©fono es obligatorio";
  if (!formData.position.trim())
    newErrors.position = "El puesto es obligatorio";
  if (formData.experience_years === undefined || formData.experience_years < 0)
    newErrors.experience_years = "Los aÃ±os de experiencia deben ser 0 o mÃ¡s";
  
  setErrors(newErrors);
  return Object.keys(newErrors).length === 0;
};
```

#### Error Handling Pattern
```typescript
const [errors, setErrors] = useState<FormErrors>({});

const handleChange = (field: keyof RecordCreate, value: string | number) => {
  setFormData((prev) => ({ ...prev, [field]: value }));
  // Clear error on field change
  if (errors[field as keyof FormErrors]) {
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  }
};

const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  if (!validate()) return; // Returns early if errors found
  
  // Process form...
};
```

#### Current Telemetry
âŒ Not yet implemented - ready for Phase 3

#### Where to Add form_validation_failed
**Location:** Line 65 in `handleSubmit` function
```typescript
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  
  // ðŸ”´ ADD HERE: Track validation failures
  if (!validate()) {
    telemetry.track("form_validation_failed", {
      form_name: "candidate_form",
      field_errors: Object.keys(errors),
      fields_with_values: {
        full_name: !!formData.full_name.trim(),
        email: !!formData.email.trim(),
        phone: !!formData.phone.trim(),
        position: !!formData.position.trim(),
        experience_years: formData.experience_years !== undefined,
      },
    });
    return;
  }

  setSubmitting(true);
  // ... rest of submit
};
```

---

### 2.4 InboundFormPanel (Inventory Entry)

**File:** [`components/inventory/InboundFormPanel.tsx`](../../uis/backoffice/talent-pipeline-tracker/components/inventory/InboundFormPanel.tsx#L1-L150)

#### Validation Pattern
```typescript
// No explicit validate() function - validation is implicit via form state
interface AssetEntryCreate {
  asset_id: 0;
  quantity: 0;
  supplier: "";
  office: "Valencia";
}

// Validation checks:
// - Product must be selected (asset_id > 0)
// - Quantity must be > 0
// - Supplier must not be empty
// - Office is pre-set
```

#### Error Handling Pattern
```typescript
const [error, setError] = useState<string | null>(null);
const [form, setForm] = useState<AssetEntryCreate>(EMPTY_FORM);

function updateField<K extends keyof AssetEntryCreate>(
  key: K,
  value: AssetEntryCreate[K],
) {
  setCreated(null);
  setError(null); // Clear previous error
  setForm((current) => ({ ...current, [key]: value }));
}

async function submit(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  setSaving(true);
  setError(null);
  setCreated(null);
  
  const payload: AssetEntryCreate = {
    ...form,
    quantity: Number(form.quantity),
  };
  
  try {
    const createdOrder = await createInbound(nexovaApi, payload);
    // Track success
    telemetry.track("inbound_order_created", {
      product_id: payload.asset_id,
      quantity: payload.quantity,
      office: payload.office,
    });
  } catch (requestError) {
    setError(inventoryErrorMessage(requestError, "No se pudo registrar la entrada.") ?? "");
  }
}
```

#### Current Telemetry
âœ… Already implemented:
- `inbound_order_created` - tracked after successful creation

#### Where to Add form_validation_failed
**Location:** Client-side validation would be needed before `createInbound()` call
```typescript
async function submit(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  
  // ðŸ”´ ADD CLIENT-SIDE VALIDATION HERE
  const validationErrors: string[] = [];
  if (!form.asset_id || form.asset_id === 0) validationErrors.push("product");
  if (!form.quantity || Number(form.quantity) <= 0) validationErrors.push("quantity");
  if (!form.supplier?.trim()) validationErrors.push("supplier");
  
  if (validationErrors.length > 0) {
    telemetry.track("form_validation_failed", {
      form_name: "inbound_form",
      field_errors: validationErrors,
      inventory_entry_type: "inbound",
    });
    setError("Por favor, completa todos los campos requeridos.");
    return;
  }
  
  setSaving(true);
  setError(null);
  // ... rest of submit
}
```

---

### 2.5 OutboundFormPanel (Inventory Exit)

**File:** [`components/inventory/OutboundFormPanel.tsx`](../../uis/backoffice/talent-pipeline-tracker/components/inventory/OutboundFormPanel.tsx#L1-L150)

#### Validation Pattern
```typescript
interface AssetExitCreate {
  asset_id: 0;
  quantity: 0;
  exit_type: "allocation" | "consumption";
  assigned_to: "";
  office: "Valencia";
}

// Validation rules via useMemo:
const insufficientStock = useMemo(
  () => Boolean(selectedProduct) && quantity > 0 && quantity > available,
  [selectedProduct, quantity, available],
);

const canSubmit = useMemo(
  () =>
    Boolean(selectedProduct) &&
    quantity > 0 &&
    !insufficientStock &&
    (form.exit_type === "consumption" || assigneeText !== ""),
  [selectedProduct, quantity, insufficientStock, form.exit_type, assigneeText],
);
```

#### Error Handling Pattern
```typescript
const [error, setError] = useState<string | null>(null);
const [form, setForm] = useState<AssetExitCreate>(EMPTY_FORM);

function updateField<K extends keyof AssetExitCreate>(
  key: K,
  value: AssetExitCreate[K],
) {
  setCreated(null);
  setError(null);
  setForm((current) => ({ ...current, [key]: value }));
}

async function submit(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  
  // Client-side guard: never send a request that would be rejected by stock.
  if (insufficientStock) return;
  
  setSaving(true);
  setError(null);
  setCreated(null);
  
  try {
    const createdOrder = await createOutbound(nexovaApi, payload);
    telemetry.track("outbound_order_created", {
      product_id: payload.asset_id,
      quantity: payload.quantity,
      exit_type: payload.exit_type,
      office: payload.office,
    });
  } catch (requestError) {
    setError(inventoryErrorMessage(requestError, "No se pudo registrar la salida.") ?? "");
  }
}
```

#### Current Telemetry
âœ… Already implemented:
- `outbound_order_created` - tracked after successful creation

#### Where to Add form_validation_failed
**Location:** Before the `submit` call or in `updateField` when validation fails
```typescript
async function submit(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  
  const payload: AssetExitCreate = {
    ...form,
    quantity,
    assigned_to: form.exit_type === "consumption" ? null : assigneeText,
  } as AssetExitCreate;
  
  // ðŸ”´ ADD HERE: Track validation failures
  if (insufficientStock) {
    telemetry.track("form_validation_failed", {
      form_name: "outbound_form",
      field_errors: ["quantity"],
      inventory_entry_type: "outbound",
      reason: "insufficient_stock",
      requested_quantity: quantity,
      available_stock: available,
    });
    setError("Stock insuficiente para esta cantidad.");
    return;
  }
  
  if (!selectedProduct || quantity <= 0) {
    telemetry.track("form_validation_failed", {
      form_name: "outbound_form",
      field_errors: !selectedProduct ? ["product"] : ["quantity"],
      inventory_entry_type: "outbound",
    });
    return;
  }
  
  if (form.exit_type === "allocation" && !assigneeText) {
    telemetry.track("form_validation_failed", {
      form_name: "outbound_form",
      field_errors: ["assigned_to"],
      inventory_entry_type: "outbound",
      exit_type: form.exit_type,
    });
    setError("Debes especificar a quiÃ©n se asigna el inventario.");
    return;
  }
  
  setSaving(true);
  // ... rest of submit
}
```

---

## 3. Common Patterns Summary

### Pattern 1: Validation Function Approach
**Used by:** AuthForm, PasswordResetForm
- Dedicated validation functions return error object
- Validation runs on form submit
- Errors cleared on field change

### Pattern 2: Inline Validation Approach
**Used by:** CandidateForm
- Validation logic inside component (single `validate()` method)
- Errors stored in React state
- Individual field validation messages

### Pattern 3: Derived State Validation
**Used by:** InboundFormPanel, OutboundFormPanel
- Validation via `useMemo` computed values
- No explicit error state (errors inferred from form state)
- Submit disabled via `canSubmit` flag

---

## 4. Telemetry Integration Checklist

For each form component, add `form_validation_failed` event in this order:

### Phase 3a: Authentication Forms
- [ ] AuthForm - track login/register validation failures
- [ ] PasswordResetForm - track password validation failures

### Phase 3b: Business Forms
- [ ] CandidateForm - track candidate data validation failures
- [ ] InboundFormPanel - add client-side validation + tracking
- [ ] OutboundFormPanel - add client-side validation + tracking

### Event Schema: form_validation_failed
```typescript
track("form_validation_failed", {
  // Required
  form_name: "login" | "register" | "password_reset" | "candidate_form" | "inbound_form" | "outbound_form",
  field_errors: string[], // Which fields failed? e.g., ["email", "password"]
  
  // Optional: Context-specific fields
  form_mode?: "login" | "register" | "forgot" | "reset" | "change", // For multi-mode forms
  reset_mode?: "forgot" | "reset" | "change",
  inventory_entry_type?: "inbound" | "outbound",
  exit_type?: "allocation" | "consumption",
  reason?: "insufficient_stock" | "email_invalid" | "password_mismatch" | etc,
  
  // Optional: Diagnostic data
  fields_with_values?: Record<string, boolean>, // Which fields had content?
  requested_quantity?: number,
  available_stock?: number,
});
```

---

## 5. Where to Import useTelemetry

All forms already have or should add:
```typescript
import { useTelemetry } from "@/hooks/useTelemetry";

export function ComponentName() {
  const telemetry = useTelemetry();
  // ... component code
}
```

---

## 6. Files to Modify in Phase 3

1. `components/auth/AuthForm.tsx` - Add tracking in `handleSubmit`
2. `components/auth/PasswordResetForm.tsx` - Add tracking in `submit`
3. `components/candidates/CandidateForm.tsx` - Add tracking in `handleSubmit`
4. `components/inventory/InboundFormPanel.tsx` - Add client-side validation + tracking
5. `components/inventory/OutboundFormPanel.tsx` - Add client-side validation + tracking

---

## 7. Testing Considerations

When implementing Phase 3, verify:
- âœ… Validation failures emit `form_validation_failed` events
- âœ… Only validation failures are tracked (not network errors)
- âœ… Event includes relevant field and context information
- âœ… Multiple validation errors are captured in single event
- âœ… Clearing a field error removes it from future events
- âœ… Successful submission does NOT emit validation failure event

---

## 8. Related Documentation

- [PHASE2_TELEMETRY_FRONTEND.md](implementation/phase-2/PHASE2_TELEMETRY_FRONTEND.md) - Frontend service architecture
- [PHASES_1_2_SUMMARY.md](implementation/PHASES_1_2_SUMMARY.md) - Overall telemetry roadmap
- [TelemetryService Integration Examples](../../uis/backoffice/talent-pipeline-tracker/lib/telemetry/INTEGRATION_EXAMPLES.ts) - Code examples
