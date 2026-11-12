# PHASE 3 â€” Instrumentation Points Mapping
## Talent Pipeline Tracker (backoffice)

**Document:** Comprehensive mapping of telemetry event instrumentation points  
**Application:** `uis/backoffice/talent-pipeline-tracker/`  
**Date:** 2026-11-02  
**Status:** Ready for Phase 3 implementation

---

## Table of Contents

1. [Auth Events](#auth-events)
2. [Inventory Events](#inventory-events)
3. [Frontend Events](#frontend-events)
4. [Form Events](#form-events)
5. [Incidents Events](#incidents-events)
6. [Suppliers Events](#suppliers-events)
7. [Implementation Checklist](#implementation-checklist)

---

## Auth Events

### 1. Event: `login_succeeded`

**Trigger:** User successfully logs in

**Location:** [components/auth/AuthForm.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/auth/AuthForm.tsx#L60-L70)

**Component:** `AuthForm` (mode: "login")

**Function:** `handleSubmit()` â†’ `signIn()` (success path)

**Code Location Details:**
- File: `components/auth/AuthForm.tsx`
- Lines: 60â€“72 (handleSubmit function)
- State managed by: `setSubmitting()`, `setSubmitError()`
- Success condition: `signIn()` completes without exception

**Data Available:**
```typescript
{
  email: string,           // User email (already submitted)
  user_id?: number,        // From session response (if available)
  timestamp: string        // RFC 3339 (auto-generated)
}
```

**Integration Point:**
```typescript
// In handleSubmit(), after signIn() succeeds and router.replace("/"):
await telemetry.track("login_succeeded", {
  email: email,  // Already captured in state
  // No PII exposure â€” email is necessary for event identification
});
```

**Test Cases:**
- Valid email + password â†’ successful login â†’ event fired
- Event contains email only (no password)
- Event fired BEFORE page navigation

---

### 2. Event: `login_failed`

**Trigger:** User attempts login but fails (invalid credentials, network error, server error)

**Location:** [components/auth/AuthForm.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/auth/AuthForm.tsx#L60-L72)

**Component:** `AuthForm` (mode: "login")

**Function:** `handleSubmit()` â†’ `signIn()` (error path)

**Code Location Details:**
- File: `components/auth/AuthForm.tsx`
- Lines: 68â€“69 (catch block)
- State managed by: `setSubmitError(error)`, `setSubmitting(false)`
- Failure condition: `signIn()` throws exception or validation fails

**Data Available:**
```typescript
{
  email: string,           // User email (attempted login)
  reason: string,          // Error type (invalid_credentials, network_error, server_error, etc.)
  timestamp: string        // RFC 3339 (auto-generated)
}
```

**Integration Point:**
```typescript
// In handleSubmit(), in the catch block after signIn() fails:
const reason = error instanceof NexovaApiError 
  ? (error.status === 401 ? "invalid_credentials" : "server_error")
  : "network_error";

await telemetry.track("login_failed", {
  email: email,
  reason: reason
});
```

**Test Cases:**
- Valid email + wrong password â†’ login_failed fired with reason: "invalid_credentials"
- Network error â†’ login_failed fired with reason: "network_error"
- Server error (500) â†’ login_failed fired with reason: "server_error"
- Event contains reason but NOT password

---

### 3. Event: `account_created`

**Trigger:** User successfully creates a new account during registration

**Location:** [components/auth/AuthForm.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/auth/AuthForm.tsx#L60-L80)

**Component:** `AuthForm` (mode: "register")

**Function:** `handleSubmit()` â†’ `registerUser()` (success path)

**Code Location Details:**
- File: `components/auth/AuthForm.tsx`
- Lines: 66â€“68 (register success path)
- State managed by: `setRegistered(true)`, `setSubmitting(false)`
- Success condition: `registerUser()` completes without exception

**Data Available:**
```typescript
{
  email: string,           // New user email
  timestamp: string        // RFC 3339 (auto-generated)
}
```

**Integration Point:**
```typescript
// In handleSubmit(), after registerUser() succeeds:
await telemetry.track("account_created", {
  email: email
});

// Also set the UI state to show success message:
setRegistered(true);
```

**Test Cases:**
- Valid email + password + confirm password match â†’ account_created fired
- User sees success message
- User can proceed to login
- Event fired BEFORE success message is shown

---

### 4. Event: `session_expired`

**Trigger:** User's session has expired and they are redirected to login with `?expired=1`

**Location:** [app/login/page.tsx](../../../../uis/backoffice/talent-pipeline-tracker/app/login/page.tsx)

**Component:** `AuthForm` (mode: "login" with `expired={true}`)

**Code Location Details:**
- File: `app/login/page.tsx`
- Lines: 10â€“13 (check for expired query param)
- File: `components/auth/AuthForm.tsx`
- Lines: 113â€“119 (render expired message)
- Status message shown but no form submission

**Data Available:**
```typescript
{
  // Minimal data â€” this is a UI state event
  timestamp: string        // RFC 3339 (auto-generated)
}
```

**Integration Point:**
```typescript
// In AuthForm.tsx component render, when expired={true}:
// Fire event when component first renders with expired flag
useEffect(() => {
  if (expired && isHydrated) {
    telemetry.track("session_expired", {});
  }
}, [expired, isHydrated]);
```

**Test Cases:**
- User is logged in
- Token expires (manually set token to null or wait for expiry)
- Page redirect to `/login?expired=1`
- Event fired when page loads
- User sees "Tu sesiÃ³n ha expirado" message

---

### 5. Auth Context: Session Management

**Session Validation Location:** [components/auth/AuthProvider.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/auth/AuthProvider.tsx)

**Details:**
- SessionSnapshot stored in context with: `status`, `user`, `error`
- `useAuth()` hook provides access to `logout()`, `validateSession()`
- Session maintained via `nexovaApi.subscribe()` pattern

**Not instrumented separately** (covered by login_succeeded, login_failed, session_expired)

---

## Inventory Events

### 1. Event: `inbound_order_created`

**Trigger:** User submits a form to create an inbound order (received goods)

**Location:** [components/inventory/InboundFormPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/inventory/InboundFormPanel.tsx)

**Component:** `InboundFormPanel`

**Function:** `submit()` (form submission handler)

**Code Location Details:**
- File: `components/inventory/InboundFormPanel.tsx`
- Lines: ~100â€“120 (handleSubmit / async submit function)
- State managed by: `setSaving(true)`, `setSaving(false)`
- Success condition: `createInbound()` completes without exception
- Success UI: `setCreated()` shows confirmation message

**Form Fields:**
```typescript
{
  asset_id: number,          // Product ID
  quantity: number,           // Quantity received
  supplier: string,           // Supplier name
  office: "Valencia" | "Miami" // Office location
}
```

**Data Available for Event:**
```typescript
{
  asset_id: number,
  quantity: number,
  office: "Valencia" | "Miami",
  // supplier name NOT included (could be PII or sensitive)
  timestamp: string           // RFC 3339 (auto-generated)
}
```

**Integration Point:**
```typescript
// In InboundFormPanel.tsx, in the submit() handler after createInbound() succeeds:
try {
  const created = await createInbound(nexovaApi, form);
  
  // Track the event
  telemetry.track("inbound_order_created", {
    asset_id: form.asset_id,
    quantity: form.quantity,
    office: form.office
  });
  
  setCreated({
    id: created.id,
    productName: selectedProduct?.name || "Unknown",
    quantity: form.quantity
  });
} catch (error) {
  // Track failure separately if needed
}
```

**Test Cases:**
- Fill form with valid data â†’ submit â†’ inbound_order_created fired
- Event contains asset_id, quantity, office
- Event does NOT contain supplier name
- Success message shows after event
- Multiple submissions â†’ multiple events

---

### 2. Event: `outbound_order_created`

**Trigger:** User submits a form to create an outbound order (goods assigned or consumed)

**Location:** [components/inventory/OutboundFormPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/inventory/OutboundFormPanel.tsx)

**Component:** `OutboundFormPanel`

**Function:** `submit()` (form submission handler)

**Code Location Details:**
- File: `components/inventory/OutboundFormPanel.tsx`
- Lines: ~100â€“120 (handleSubmit / async submit function)
- State managed by: `setSaving(true)`, `setSaving(false)`
- Success condition: `createOutbound()` completes without exception
- Success UI: `setCreated()` shows confirmation message

**Form Fields:**
```typescript
{
  asset_id: number,                    // Product ID
  quantity: number,                     // Quantity exiting
  exit_type: "allocation" | "consumption", // Why goods are leaving
  assigned_to?: string,                 // Person name (for allocation)
  office: "Valencia" | "Miami"          // Office location
}
```

**Data Available for Event:**
```typescript
{
  asset_id: number,
  quantity: number,
  exit_type: "allocation" | "consumption",
  office: "Valencia" | "Miami",
  // assigned_to NOT included (PII â€” person name)
  timestamp: string                    // RFC 3339 (auto-generated)
}
```

**Integration Point:**
```typescript
// In OutboundFormPanel.tsx, in the submit() handler after createOutbound() succeeds:
try {
  const created = await createOutbound(nexovaApi, form);
  
  // Track the event
  telemetry.track("outbound_order_created", {
    asset_id: form.asset_id,
    quantity: form.quantity,
    exit_type: form.exit_type,
    office: form.office
  });
  
  setCreated({
    id: created.id,
    productName: selectedProduct?.name || "Unknown",
    quantity: form.quantity,
    exitType: form.exit_type
  });
} catch (error) {
  // Track failure separately if needed
}
```

**Test Cases:**
- Fill form with "allocation" â†’ submit â†’ outbound_order_created fired with exit_type: "allocation"
- Fill form with "consumption" â†’ submit â†’ outbound_order_created fired with exit_type: "consumption"
- Event does NOT contain assigned_to name
- Success message shows after event
- Multiple submissions â†’ multiple events

---

## Frontend Events

### 1. Event: `frontend_render_error`

**Trigger:** A rendering error occurs in a page route

**Location:** [app/error.tsx](../../../../uis/backoffice/talent-pipeline-tracker/app/error.tsx)

**Component:** `Error` (Next.js error boundary)

**Code Location Details:**
- File: `app/error.tsx`
- Lines: 8â€“19 (useEffect that logs errors)
- This is the **per-page error boundary** (not global)
- Triggered when a component in a route throws during render

**Data Available:**
```typescript
{
  digest: string,           // Error ID generated by Next.js
  message?: string,         // Error message (if available)
  // Actual error object NOT sent (no stack traces)
  timestamp: string         // RFC 3339 (auto-generated)
}
```

**Integration Point:**
```typescript
// In app/error.tsx, in the useEffect:
useEffect(() => {
  if (error.digest) {
    // Track the error event
    telemetry.track("frontend_render_error", {
      digest: error.digest,
      message: error.message || "Unknown render error"
    });
    
    // Also log to console for debugging (existing behavior)
    console.error("[Nexova] Render error", { digest: error.digest });
  }
}, [error]);
```

**Test Cases:**
- Component throws during render
- error.tsx boundary catches it
- frontend_render_error event fired with digest
- User sees error message + retry button

---

### 2. Event: `frontend_page_loaded`

**Trigger:** A page successfully loads and renders

**Location:** [app/page.tsx](../../../../uis/backoffice/talent-pipeline-tracker/app/page.tsx) (and other route pages)

**Component:** Each page component

**Code Location Details:**
- File: `app/page.tsx` (home/candidates list)
- File: `app/candidates/[id]/page.tsx` (candidate detail)
- File: `app/login/page.tsx` (login form)
- File: `app/register/page.tsx` (register form)
- File: `app/new/page.tsx` (create candidate form)
- File: `app/account/profile/page.tsx` (profile)
- etc.

**Data Available:**
```typescript
{
  page_type: string,        // "candidates_list" | "candidate_detail" | "login" | "register" | etc.
  user_authenticated: boolean, // Whether user is logged in
  timestamp: string         // RFC 3339 (auto-generated)
}
```

**Integration Point:**

**Strategy 1:** Root layout hook (captures all pages)
```typescript
// In app/layout.tsx or a custom hook like hooks/usePageTracking.ts:
useEffect(() => {
  // Determine page type from pathname or route metadata
  const pageType = determinePageType(pathname);
  const isAuthenticated = status === "authenticated";
  
  telemetry.track("frontend_page_loaded", {
    page_type: pageType,
    user_authenticated: isAuthenticated
  });
}, [pathname, status]);
```

**Strategy 2:** Per-page instrumentation (more granular)
```typescript
// In app/page.tsx (candidates list):
useEffect(() => {
  telemetry.track("frontend_page_loaded", {
    page_type: "candidates_list",
    user_authenticated: status === "authenticated"
  });
}, [status]);

// In app/candidates/[id]/page.tsx (candidate detail):
useEffect(() => {
  telemetry.track("frontend_page_loaded", {
    page_type: "candidate_detail",
    user_authenticated: status === "authenticated"
  });
}, [status]);
```

**Recommended:** Strategy 1 (centralized, easier to maintain)

**Test Cases:**
- Navigate to home page â†’ frontend_page_loaded fired with page_type: "candidates_list"
- Navigate to login â†’ frontend_page_loaded fired with page_type: "login"
- Navigate to candidate detail â†’ frontend_page_loaded fired with page_type: "candidate_detail"
- user_authenticated reflects actual auth status
- Event fires after route transition completes

---

### 3. Event: `form_validation_failed`

**Trigger:** User submits a form with validation errors (fields required, invalid format, etc.)

**Location:** Multiple form components:
- [components/auth/AuthForm.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/auth/AuthForm.tsx) (login/register)
- [components/candidates/CandidateForm.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/candidates/CandidateForm.tsx) (create candidate)
- [components/inventory/InboundFormPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/inventory/InboundFormPanel.tsx) (inbound order)
- [components/inventory/OutboundFormPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/inventory/OutboundFormPanel.tsx) (outbound order)
- [components/incidents/IncidentManagerPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/incidents/IncidentManagerPanel.tsx) (create incident)
- [components/suppliers/SupplierDirectoryPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/suppliers/SupplierDirectoryPanel.tsx) (add supplier)

**Component:** Any form with validation

**Code Location Details (AuthForm as example):**
- File: `components/auth/AuthForm.tsx`
- Lines: 52â€“60 (validateLoginFields / validateRegistrationFields)
- Lines: 55â€“56 (check if errors exist before submission)
- State: `setErrors(nextErrors)`

**Data Available:**
```typescript
{
  form_type: string,        // "login" | "register" | "candidate" | "inbound_order" | "outbound_order" | "incident" | "supplier"
  field_count: number,      // How many fields had errors
  field_names: string[],    // Which fields failed (e.g., ["email", "password"])
  timestamp: string         // RFC 3339 (auto-generated)
}
```

**Integration Point (AuthForm example):**
```typescript
// In handleSubmit(), when validation fails:
const nextErrors = isLogin
  ? validateLoginFields(email, password)
  : validateRegistrationFields(email, password, confirmPassword);

setErrors(nextErrors);

// Track validation failure
if (Object.keys(nextErrors).length > 0) {
  const failedFields = Object.keys(nextErrors);
  telemetry.track("form_validation_failed", {
    form_type: isLogin ? "login" : "register",
    field_count: failedFields.length,
    field_names: failedFields
  });
  return; // Don't proceed with submission
}
```

**Integration Point (CandidateForm example):**
```typescript
// In CandidateForm.tsx handleSubmit():
const validate = (): boolean => {
  const newErrors: FormErrors = {};
  // ... validation logic ...
  setErrors(newErrors);
  
  if (Object.keys(newErrors).length > 0) {
    const failedFields = Object.keys(newErrors);
    telemetry.track("form_validation_failed", {
      form_type: "candidate",
      field_count: failedFields.length,
      field_names: failedFields
    });
    return false;
  }
  return true;
};
```

**Test Cases:**
- Submit login form with empty email â†’ form_validation_failed with field_names: ["email"]
- Submit register form with mismatched passwords â†’ form_validation_failed with field_names: ["confirmPassword"]
- Submit candidate form with missing multiple fields â†’ form_validation_failed with field_count: 3+
- Validation errors shown to user immediately
- Event contains field names but NOT field values (no PII)

---

### 4. Event: `section_viewed`

**Trigger:** User navigates to or views a major section/page of the application

**Location:** Multiple page components:
- [app/page.tsx](../../../../uis/backoffice/talent-pipeline-tracker/app/page.tsx) (candidates list)
- [app/login/page.tsx](../../../../uis/backoffice/talent-pipeline-tracker/app/login/page.tsx) (authentication)
- [app/inventory/page.tsx](../../../../uis/backoffice/talent-pipeline-tracker/app/inventory/products/page.tsx) (inventory management)
- [app/incidents/manager/page.tsx](../../../../uis/backoffice/talent-pipeline-tracker/app/incidents/manager/page.tsx) (incident manager)
- [app/suppliers/page.tsx](../../../../uis/backoffice/talent-pipeline-tracker/app/suppliers/page.tsx) (supplier directory)
- [app/account/profile/page.tsx](../../../../uis/backoffice/talent-pipeline-tracker/app/account/profile/page.tsx) (user profile)

**Component:** Route pages or layout

**Code Location Details:**
- File: `app/page.tsx` (section: "candidates")
- File: `app/login/page.tsx` (section: "auth")
- File: `app/inventory/page.tsx` (section: "inventory")
- File: `app/incidents/manager/page.tsx` (section: "incidents")
- File: `app/suppliers/page.tsx` (section: "suppliers")

**Data Available:**
```typescript
{
  section_name: string,      // "candidates" | "auth" | "inventory" | "incidents" | "suppliers" | "profile"
  user_authenticated: boolean, // Whether user is logged in
  timestamp: string          // RFC 3339 (auto-generated)
}
```

**Integration Point (centralized in layout or hook):**
```typescript
// Create a custom hook: hooks/useSectionTracking.ts
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { useTelemetry } from "@/hooks";

export function useSectionTracking() {
  const pathname = usePathname();
  const { status } = useAuth();
  const telemetry = useTelemetry();
  
  useEffect(() => {
    let sectionName = "unknown";
    
    if (pathname === "/") sectionName = "candidates";
    else if (pathname.startsWith("/login")) sectionName = "auth";
    else if (pathname.startsWith("/register")) sectionName = "auth";
    else if (pathname.startsWith("/inventory")) sectionName = "inventory";
    else if (pathname.startsWith("/incidents")) sectionName = "incidents";
    else if (pathname.startsWith("/suppliers")) sectionName = "suppliers";
    else if (pathname.startsWith("/account")) sectionName = "profile";
    
    telemetry.track("section_viewed", {
      section_name: sectionName,
      user_authenticated: status === "authenticated"
    });
  }, [pathname, status, telemetry]);
}

// Then call in app/layout.tsx:
export default function RootLayout({ children }) {
  useSectionTracking();
  // ...
}
```

**Test Cases:**
- Navigate to home (candidates list) â†’ section_viewed with section_name: "candidates"
- Navigate to /inventory â†’ section_viewed with section_name: "inventory"
- Navigate to /incidents/manager â†’ section_viewed with section_name: "incidents"
- Navigate to /suppliers â†’ section_viewed with section_name: "suppliers"
- user_authenticated reflects actual auth status
- Event fires on every route change

---

## Form Events

### 1. Event: `form_opened`

**Trigger:** User opens a modal or form dialog for data entry

**Location:** Components with modal/dialog forms:
- [components/inventory/InboundFormPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/inventory/InboundFormPanel.tsx) (if wrapped in modal)
- [components/inventory/OutboundFormPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/inventory/OutboundFormPanel.tsx) (if wrapped in modal)
- [components/suppliers/SupplierDirectoryPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/suppliers/SupplierDirectoryPanel.tsx) (Modal for add supplier)
- [components/incidents/IncidentManagerPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/incidents/IncidentManagerPanel.tsx) (Modal for create incident)

**Component:** Any component using `Modal` component or `<dialog>` element

**Code Location Details:**
- File: `components/ui/Modal.tsx` (Modal component)
- File: `components/suppliers/SupplierDirectoryPanel.tsx` (uses Modal)
- File: `components/inventory/InboundFormPanel.tsx` (form panel)

**Data Available:**
```typescript
{
  form_type: string,        // "add_supplier" | "create_incident" | "inbound_order" | "outbound_order"
  timestamp: string         // RFC 3339 (auto-generated)
}
```

**Integration Point (via Modal component or parent):**

**Strategy 1:** In parent component when modal opens
```typescript
// In SupplierDirectoryPanel.tsx:
const [showAddSupplierModal, setShowAddSupplierModal] = useState(false);

function handleOpenModal() {
  telemetry.track("form_opened", {
    form_type: "add_supplier"
  });
  setShowAddSupplierModal(true);
}
```

**Strategy 2:** In Modal component itself (generic)
```typescript
// In components/ui/Modal.tsx:
useEffect(() => {
  if (open) {
    telemetry.track("form_opened", {
      form_type: title.toLowerCase() // Use modal title as form type
    });
  }
}, [open, title, telemetry]);
```

**Recommended:** Strategy 1 (more explicit, easier to control)

**Test Cases:**
- Click "Add supplier" button â†’ form_opened fires with form_type: "add_supplier"
- Click "Create incident" button â†’ form_opened fires with form_type: "create_incident"
- Modal/dialog appears on screen
- Event fires BEFORE form is visible to user

---

### 2. Event: `form_abandoned`

**Trigger:** User closes a form/modal without submitting data

**Location:** Components with modal/dialog forms (same as form_opened)

**Component:** Modal-based forms

**Code Location Details:**
- File: `components/ui/Modal.tsx` (Modal onClose handler)
- File: `components/suppliers/SupplierDirectoryPanel.tsx` (Modal close)
- File: `components/incidents/IncidentManagerPanel.tsx` (Modal close)

**Data Available:**
```typescript
{
  form_type: string,        // Same as form_opened
  fields_touched: number,   // How many fields were edited (0 = pristine)
  timestamp: string         // RFC 3339 (auto-generated)
}
```

**Integration Point:**

**Strategy 1:** Track touched fields in form state
```typescript
// In SupplierDirectoryPanel.tsx (SupplierForm component):
const [form, setForm] = useState<SupplierCreatePayload>({...});
const [fieldsEdited, setFieldsEdited] = useState<Set<string>>(new Set());

function updateField<K extends keyof SupplierCreatePayload>(
  key: K, 
  value: SupplierCreatePayload[K]
) {
  // Track that this field was edited
  setFieldsEdited(prev => new Set(prev).add(key));
  setForm(current => ({ ...current, [key]: value }));
}

// Modal closes without submission
function handleClose() {
  if (fieldsEdited.size > 0) {
    telemetry.track("form_abandoned", {
      form_type: "add_supplier",
      fields_touched: fieldsEdited.size
    });
  }
  setShowModal(false);
  // Reset form state
}
```

**Test Cases:**
- Open "Add supplier" modal â†’ click X to close â†’ form_abandoned fires
- Open "Create incident" modal, edit 1 field â†’ close â†’ form_abandoned with fields_touched: 1
- Open modal but immediately close (pristine form) â†’ form_abandoned with fields_touched: 0 (or not fired if fields_touched === 0)
- Form successfully submitted â†’ form_abandoned NOT fired
- Event fires when modal closes via:
  - Close button (X)
  - ESC key
  - Click outside modal (backdrop)
  - But NOT when form is submitted

---

## Incidents Events

### 1. Event: `incident_status_changed`

**Trigger:** User updates an incident's status from one value to another

**Location:** [components/incidents/IncidentManagerPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/incidents/IncidentManagerPanel.tsx)

**Component:** `IncidentManagerPanel`

**Code Location Details:**
- File: `components/incidents/IncidentManagerPanel.tsx`
- Lines: ~200â€“250 (status update section / dropdown)
- Function called: `updateIncidentStatus(id, newStatus)`
- State managed by: Loading state during update

**Status Values:**
```typescript
type IncidentManagerStatus = "open" | "in_progress" | "resolved" | "closed";
```

**Data Available:**
```typescript
{
  incident_id: number,      // The incident being updated
  from_status: string,      // Previous status
  to_status: string,        // New status
  timestamp: string         // RFC 3339 (auto-generated)
}
```

**Integration Point:**
```typescript
// In IncidentManagerPanel.tsx, when user changes incident status:
// Assuming there's a UI control (dropdown, buttons, etc.) for status change

async function handleStatusChange(incident: Incident, newStatus: IncidentManagerStatus) {
  const oldStatus = incident.status;
  
  try {
    await updateIncidentStatus(incident.id, newStatus);
    
    // Track the status change
    telemetry.track("incident_status_changed", {
      incident_id: incident.id,
      from_status: oldStatus,
      to_status: newStatus
    });
    
    // Update UI to show new status
    // ... refresh incident list or detail view ...
  } catch (error) {
    // Handle error
  }
}
```

**Test Cases:**
- Incident is in "open" status
- User clicks dropdown and selects "in_progress"
- incident_status_changed fires with from_status: "open", to_status: "in_progress"
- Incident detail updates to show new status
- Multiple status changes â†’ multiple events

---

## Suppliers Events

### 1. Event: `supplier_rate_updated`

**Trigger:** User updates a supplier's monthly rate

**Location:** [components/suppliers/SupplierDirectoryPanel.tsx](../../../../uis/backoffice/talent-pipeline-tracker/components/suppliers/SupplierDirectoryPanel.tsx)

**Component:** `SupplierDirectoryPanel`

**Code Location Details:**
- File: `components/suppliers/SupplierDirectoryPanel.tsx`
- Lines: ~150â€“200 (rate update section)
- Function called: `updateSupplierRate(id, monthly_rate)`
- State managed by: Form input + submit handler

**Data Available:**
```typescript
{
  supplier_id: number,      // The supplier being updated
  new_rate: number,         // New monthly rate (numeric)
  currency: string,         // Currency code ("EUR" | "USD")
  timestamp: string         // RFC 3339 (auto-generated)
}
```

**Integration Point:**
```typescript
// In SupplierDirectoryPanel.tsx, when user updates supplier rate:
// Assuming there's a form or inline editor for rate

async function handleRateUpdate(supplier: Supplier, newRate: number) {
  try {
    const updated = await updateSupplierRate(supplier.id, newRate);
    
    // Track the rate update
    telemetry.track("supplier_rate_updated", {
      supplier_id: supplier.id,
      new_rate: newRate,
      currency: supplier.currency // Already known from supplier object
    });
    
    // Update supplier in list
    // ... refresh supplier list or detail view ...
  } catch (error) {
    // Handle error
  }
}
```

**Test Cases:**
- View supplier in directory
- Edit monthly_rate from 500 to 750
- Click Save/Update
- supplier_rate_updated fires with supplier_id, new_rate: 750, currency
- Supplier list updates to show new rate
- Multiple updates â†’ multiple events

---

## Implementation Checklist

### Phase 3 Implementation Steps

- [ ] **Auth Events (4 events)**
  - [ ] `login_succeeded` â€” After successful signIn()
  - [ ] `login_failed` â€” Catch block in handleSubmit()
  - [ ] `account_created` â€” After registerUser() success
  - [ ] `session_expired` â€” useEffect in AuthForm with expired prop

- [ ] **Inventory Events (2 events)**
  - [ ] `inbound_order_created` â€” After createInbound() success
  - [ ] `outbound_order_created` â€” After createOutbound() success

- [ ] **Frontend Events (4 events)**
  - [ ] `frontend_render_error` â€” In app/error.tsx useEffect
  - [ ] `frontend_page_loaded` â€” Centralized hook in layout
  - [ ] `form_validation_failed` â€” In all form handleSubmit validation checks
  - [ ] `section_viewed` â€” useEffect on pathname change

- [ ] **Form Events (2 events)**
  - [ ] `form_opened` â€” When modal/form opens
  - [ ] `form_abandoned` â€” When modal closes without submission

- [ ] **Incidents Events (1 event)**
  - [ ] `incident_status_changed` â€” After updateIncidentStatus() success

- [ ] **Suppliers Events (1 event)**
  - [ ] `supplier_rate_updated` â€” After updateSupplierRate() success

**Total Events to Instrument: 14**

---

## Code Quality Standards for Phase 3

1. **No PII Exposure:**
   - âœ… Email in login_succeeded/login_failed (necessary for identification)
   - âœ… Email in account_created (necessary for identification)
   - âŒ Passwords, tokens, API keys
   - âŒ Personal names (assigned_to in outbound orders, supplier contacts)
   - âŒ Phone numbers, addresses
   - âŒ Sensitive form data (CV URLs, LinkedIn URLs â€” use generic identifiers)

2. **Timing & Ordering:**
   - Events fire AFTER validation succeeds but BEFORE API calls in some cases
   - Events fire AFTER API success confirmation (no premature firing)
   - Events fire BEFORE UI state changes when possible (e.g., page navigation)

3. **TypeScript Compliance:**
   - All telemetry.track() calls use specific event types from telemetry-types.ts
   - All data passed matches the event's data schema
   - No `any` types in event tracking code

4. **Testing:**
   - Each event has at least 1 test case
   - Events tested for:
     - Firing at correct time
     - Contains correct data
     - Does NOT fire on failure paths (or fires different event)
     - Data is not exposed/logged to console

5. **Error Handling:**
   - telemetry.track() wrapped in try/catch (telemetry should not break app)
   - If telemetry fails, error logged but app continues
   - No blocking on telemetry completion

---

## Migration Checklist from Phase 2 to Phase 3

**Phase 2 Deliverables (Frontend Service):**
- âœ… TelemetryService singleton
- âœ… Queue + batching
- âœ… Retry logic with exponential backoff
- âœ… sendBeacon integration
- âœ… useTelemetry() hook

**Phase 3 Prerequisites:**
- âœ… Backend telemetry endpoint ready (Phase 1)
- âœ… Frontend service ready (Phase 2)
- âœ… All 14 events defined in telemetry-types.ts
- âœ… Event allowlist configured in TelemetryService

**Phase 3 Work:**
1. Create new branch for Phase 3 instrumentation
2. Add useTelemetry hook calls to each component
3. Implement each event per checklist above
4. Run tests for each modified component
5. End-to-end test: User action â†’ Event queued â†’ Batch sent â†’ Backend received
6. Verify CloudEvents structure in network tab
7. Verify no PII in events
8. Create PR with all changes

---

## Files to Modify in Phase 3

### Auth Components
- `components/auth/AuthForm.tsx` â€” Add login_succeeded, login_failed, account_created events
- `app/login/page.tsx` â€” Ensure session_expired event fires

### Inventory Components
- `components/inventory/InboundFormPanel.tsx` â€” Add inbound_order_created event
- `components/inventory/OutboundFormPanel.tsx` â€” Add outbound_order_created event

### Frontend Events
- `app/error.tsx` â€” Add frontend_render_error event
- Create `hooks/useSectionTracking.ts` â€” Add frontend_page_loaded, section_viewed events
- `app/layout.tsx` â€” Import and call useSectionTracking
- All form components â€” Add form_validation_failed events

### Form Events
- `components/suppliers/SupplierDirectoryPanel.tsx` â€” Add form_opened, form_abandoned, supplier_rate_updated events
- `components/incidents/IncidentManagerPanel.tsx` â€” Add form_opened, form_abandoned, incident_status_changed events

### Tests
- Create `tests/telemetry-integration.test.mjs` â€” Integration tests for all events
- Existing component tests â€” Add telemetry assertions

---

## Dependencies

**Already Available:**
- âœ… `lib/telemetry/telemetry-service.ts` (TelemetryService singleton)
- âœ… `lib/telemetry/telemetry-types.ts` (Event types)
- âœ… `hooks/useTelemetry.ts` (React hook for tracking)
- âœ… Backend endpoint: `POST /api/telemetry/events`

**New Files to Create:**
- `hooks/useSectionTracking.ts` â€” Centralized section tracking
- `tests/telemetry-integration.test.mjs` â€” E2E tests

**Modified Files:**
- See "Files to Modify in Phase 3" section above

---

## Deployment Ready

**Blockers for Production:** None identified

**Warnings:** None identified

**Recommendations:**
1. Implement events in priority order:
   - Priority 1 (Auth, Inventory): Most critical business logic
   - Priority 2 (Frontend Events): Observability
   - Priority 3 (Form Events): User behavior detail
   - Priority 4 (Status Changes): Operational tracking

2. Test end-to-end before deploying:
   - Fire event in frontend
   - Verify queued in TelemetryService
   - Wait for batch or manual flush
   - Check Network tab (POST to /api/telemetry/events)
   - Verify backend receives and logs

3. Monitor first week:
   - Check logs for telemetry events received
   - Verify CloudEvents validation passes
   - No PII exposed in logs

---

## Questions & Clarifications

**Q: Should we track failed API calls (e.g., inbound_order_created fails)?**  
A: Track separately as optional negative events if required (not in Phase 3 scope currently)

**Q: Should form_abandoned track form values?**  
A: No â€” track only field count and which fields were touched (names), not values

**Q: Should we track page unload (beforeunload)?**  
A: Handled automatically via sendBeacon in TelemetryService (Phase 2)

**Q: What about manual filtering or sorting on the candidates list?**  
A: Not in scope for Phase 3 (covered under section_viewed â†’ querystring changes)

---

**Document Status:** âœ… Ready for Phase 3 Implementation  
**Created:** 2026-11-02  
**Next Step:** Awaiting user approval to begin Phase 3 instrumentation
