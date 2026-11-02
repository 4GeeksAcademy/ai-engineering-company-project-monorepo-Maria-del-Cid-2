# Phase 3 — Component Instrumentation Map
## Visual Guide to Event Locations

```
uis/backoffice/talent-pipeline-tracker/
├── app/
│   ├── layout.tsx                    [✓ Add useSectionTracking hook]
│   ├── page.tsx                      [← frontend_page_loaded fires here]
│   ├── error.tsx                     [✓ Add frontend_render_error tracking]
│   ├── global-error.tsx              [← Global error boundary]
│   ├── login/
│   │   └── page.tsx                  [← session_expired check]
│   ├── register/
│   │   └── page.tsx                  [← Account creation flow]
│   ├── new/
│   │   └── page.tsx                  [← New candidate flow]
│   ├── account/
│   │   ├── profile/
│   │   │   └── page.tsx              [← form_validation_failed]
│   │   └── change-password/
│   │       └── page.tsx              [← form_validation_failed]
│   ├── inventory/
│   │   └── page.tsx                  [← section_viewed]
│   ├── incidents/
│   │   ├── manager/
│   │   │   └── page.tsx              [← section_viewed]
│   │   └── analysis/
│   │       └── page.tsx              [← section_viewed]
│   └── suppliers/
│       └── page.tsx                  [← section_viewed]
│
├── components/
│   ├── auth/
│   │   ├── AuthForm.tsx              [✓ login_succeeded, login_failed, account_created, session_expired]
│   │   ├── AuthProvider.tsx          [← Session context (no direct tracking)]
│   │   └── AuthShell.tsx             [← Logout handler (no direct tracking)]
│   │
│   ├── candidates/
│   │   ├── CandidateList.tsx         [← Lists candidates]
│   │   ├── CandidateCard.tsx         [← Individual candidate card]
│   │   ├── CandidateDetail.tsx       [✓ form_validation_failed (status/stage updates)]
│   │   └── CandidateForm.tsx         [✓ form_validation_failed (create candidate)]
│   │
│   ├── inventory/
│   │   ├── InboundFormPanel.tsx      [✓ inbound_order_created, form_opened, form_abandoned, form_validation_failed]
│   │   └── OutboundFormPanel.tsx     [✓ outbound_order_created, form_opened, form_abandoned, form_validation_failed]
│   │
│   ├── incidents/
│   │   ├── IncidentManagerPanel.tsx  [✓ incident_status_changed, form_opened, form_abandoned, form_validation_failed]
│   │   └── IncidentAnalysisPanel.tsx [← Analysis display only]
│   │
│   ├── suppliers/
│   │   └── SupplierDirectoryPanel.tsx[✓ supplier_rate_updated, form_opened, form_abandoned, form_validation_failed]
│   │
│   ├── profile/
│   │   └── ProfilePanel.tsx          [✓ form_validation_failed]
│   │
│   ├── notes/
│   │   └── NoteSection.tsx           [← Notes management]
│   │
│   └── ui/
│       ├── Modal.tsx                 [← Modal wrapper (no tracking here, parent tracks)]
│       ├── Button.tsx                [← Button wrapper]
│       ├── Input.tsx                 [← Input wrapper]
│       └── ...
│
├── hooks/
│   ├── useTelemetry.ts               [← Already created (Phase 2)]
│   ├── useAuth.ts                    [← Auth hook]
│   ├── useRecord.ts                  [← Candidate hook]
│   ├── useRecords.ts                 [← Candidates list hook]
│   ├── useNotes.ts                   [← Notes hook]
│   └── useSectionTracking.ts         [✓ TO CREATE: frontend_page_loaded + section_viewed]
│
├── lib/
│   ├── telemetry/                    [← Phase 2 complete]
│   ├── auth-forms.ts                 [← Validation functions]
│   ├── auth-navigation.ts            [← Navigation logic]
│   ├── records.ts                    [← API: getRecords, createRecord, etc.]
│   ├── inventory.ts                  [← API: createInbound, createOutbound, etc.]
│   ├── incidents-api.ts              [← API: createIncident, updateIncidentStatus, etc.]
│   ├── suppliers-api.ts              [← API: createSupplier, updateSupplierRate, etc.]
│   ├── nexova-api.ts                 [← Base API client]
│   └── ...
│
└── types/
    ├── auth.ts                       [← Auth types]
    ├── record.ts                     [← Candidate types]
    ├── inventory.ts                  [← Inventory types]
    ├── incident-manager.ts           [← Incident types]
    └── supplier.ts                   [← Supplier types]
```

---

## Event Flow Diagram

### Auth Events

```
User Action              Component                 Event Tracking           API Call
─────────────────────────────────────────────────────────────────────────────────

LOGIN:
Input email+password  → AuthForm.handleSubmit()
                        ├─ validate()
                        └─ signIn(api)
                           ├─ Success → ✓ login_succeeded → route.replace("/")
                           └─ Error  → ✓ login_failed → setSubmitError()

REGISTER:
Input email+password  → AuthForm.handleSubmit()
                        ├─ validate()
                        └─ registerUser(api)
                           ├─ Success → ✓ account_created → setRegistered(true)
                           └─ Error  → ✓ register_failed (not tracked, shows UI error)

SESSION EXPIRED:
Token expires          → Redirect to /login?expired=1
                        AuthForm (expired prop)
                        ├─ useEffect fires → ✓ session_expired
                        └─ Show message to user
```

### Inventory Events

```
User Action              Component                 Event Tracking           API Call
─────────────────────────────────────────────────────────────────────────────────

CREATE INBOUND:
Fill form → Click Save → InboundFormPanel.submit()
                        ├─ validate()
                        ├─ createInbound(api)
                        │  └─ Success → ✓ inbound_order_created
                        └─ setCreated() → Show message

CREATE OUTBOUND:
Fill form → Click Save → OutboundFormPanel.submit()
                        ├─ validate()
                        ├─ createOutbound(api)
                        │  └─ Success → ✓ outbound_order_created
                        └─ setCreated() → Show message
```

### Frontend Events

```
User Action              Component                 Event Tracking           Notes
─────────────────────────────────────────────────────────────────────────────────

PAGE LOAD/NAVIGATE:
Click route link       → pathname changes
                        useSectionTracking.useEffect()
                        ├─ mapPathnameToSection()
                        ├─ ✓ frontend_page_loaded
                        └─ ✓ section_viewed

FORM VALIDATION FAILS:
User submits form      → Component.handleSubmit()
                        ├─ validate() → errors found
                        ├─ ✓ form_validation_failed
                        └─ Stop submission, show errors

RENDER ERROR:
Component throws       → app/error.tsx boundary catches
                        ├─ error.digest generated
                        ├─ useEffect fires
                        ├─ ✓ frontend_render_error
                        └─ Show error UI + retry button
```

### Form Events

```
User Action              Component                 Event Tracking           Notes
─────────────────────────────────────────────────────────────────────────────────

OPEN MODAL:
Click "Add Supplier"  → handleOpenModal()
                        ├─ ✓ form_opened
                        └─ setShowModal(true) → Modal appears

EDIT FIELD:
Type in form          → updateField()
                        └─ Track field in fieldsEdited Set

CLOSE MODAL (NO SUBMIT):
Click X or ESC        → handleClose()
                        ├─ Check fieldsEdited.size > 0
                        ├─ If true → ✓ form_abandoned
                        └─ setShowModal(false)

SUBMIT FORM:
Fill + Click Save     → handleSubmit()
                        ├─ validate() → success
                        ├─ API call → success
                        ├─ ✓ form_opened (not fired on this path)
                        └─ form_abandoned NOT fired → modal closes
```

### Status Change Events

```
User Action              Component                 Event Tracking           API Call
─────────────────────────────────────────────────────────────────────────────────

UPDATE INCIDENT STATUS:
Click status dropdown → Select new status
                        handleStatusChange()
                        ├─ Capture old status
                        ├─ updateIncidentStatus(api)
                        │  └─ Success → ✓ incident_status_changed
                        └─ Refresh UI

UPDATE SUPPLIER RATE:
Edit rate field       → Focus out or Click Update
                        handleRateUpdate()
                        ├─ Capture old rate
                        ├─ updateSupplierRate(api)
                        │  └─ Success → ✓ supplier_rate_updated
                        └─ Refresh UI
```

---

## Component Dependencies

### Components Requiring useTelemetry Hook

```typescript
// Import pattern (all components):
import { useTelemetry } from "@/hooks";

export function ComponentName() {
  const telemetry = useTelemetry();
  
  // Use telemetry.track() in handlers
  async function handleAction() {
    try {
      // ... action logic ...
      telemetry.track("event_name", { data });
    } catch (error) {
      // ... error handling ...
    }
  }
}
```

### Components Using useSectionTracking

```typescript
// In app/layout.tsx:
import { useSectionTracking } from "@/hooks";

export default function RootLayout({ children }) {
  useSectionTracking(); // Call once at top level
  return (
    <html>
      <body>
        <AuthProvider>
          <AuthShell>{children}</AuthShell>
        </AuthProvider>
      </body>
    </html>
  );
}
```

---

## Form Validation Events by Component

| Component | File | Event | Fired When |
|-----------|------|-------|-----------|
| Login Form | components/auth/AuthForm.tsx | form_validation_failed | Email/password invalid |
| Register Form | components/auth/AuthForm.tsx | form_validation_failed | Email/password/confirm invalid |
| Candidate Form | components/candidates/CandidateForm.tsx | form_validation_failed | Full name/email/phone invalid |
| Candidate Detail (Status) | components/candidates/CandidateDetail.tsx | form_validation_failed | (Usually not, status is dropdown) |
| Inbound Order | components/inventory/InboundFormPanel.tsx | form_validation_failed | Asset/quantity/office invalid |
| Outbound Order | components/inventory/OutboundFormPanel.tsx | form_validation_failed | Asset/quantity/exit_type invalid |
| Profile | components/profile/ProfilePanel.tsx | form_validation_failed | (Usually not, all fields optional) |
| Change Password | app/account/change-password/page.tsx | form_validation_failed | Current/new/confirm password invalid |
| Create Incident | components/incidents/IncidentManagerPanel.tsx | form_validation_failed | Title/category/status invalid |
| Add Supplier | components/suppliers/SupplierDirectoryPanel.tsx | form_validation_failed | Name/country/rate invalid |

---

## Event Allowlist

All events must be in the allowlist in TelemetryService:

```typescript
// From lib/telemetry/telemetry-service.ts (Phase 2)

private ALLOWED_EVENTS = new Set([
  "login_succeeded",
  "login_failed",
  "account_created",
  "session_expired",
  "inbound_order_created",
  "outbound_order_created",
  "frontend_render_error",
  "frontend_page_loaded",
  "form_validation_failed",
  "section_viewed",
  "form_opened",
  "form_abandoned",
  "incident_status_changed",
  "supplier_rate_updated"
]);
```

✅ Already configured in Phase 2

---

## Testing Checklist by Event

### Auth Events
- [ ] Login with valid credentials → login_succeeded logged
- [ ] Login with invalid password → login_failed logged
- [ ] Register new account → account_created logged
- [ ] Manual token expiry → /login?expired=1 → session_expired logged
- [ ] All auth events contain email (no password)

### Inventory Events
- [ ] Create inbound order → inbound_order_created logged
- [ ] Create outbound order → outbound_order_created logged
- [ ] Event data: asset_id, quantity, office (no supplier name)
- [ ] Invalid form → form_validation_failed (not _created)

### Frontend Events
- [ ] Navigate to each route → frontend_page_loaded + section_viewed logged
- [ ] Render error → error.tsx → frontend_render_error logged
- [ ] Form with validation errors → form_validation_failed logged
- [ ] All events have correct page_type and section_name values

### Form Events
- [ ] Click "Add Supplier" → form_opened logged
- [ ] Edit field → close modal → form_abandoned logged with fields_touched count
- [ ] Submit form → form_abandoned NOT logged
- [ ] Modal opened and events track via parent, not Modal.tsx itself

### Status Change Events
- [ ] Change incident status → incident_status_changed logged with from/to status
- [ ] Update supplier rate → supplier_rate_updated logged with new rate
- [ ] Event contains IDs and values (no sensitive info)

---

## Next Steps

1. **Create useSectionTracking.ts** (if doesn't exist)
2. **Modify AuthForm.tsx** → Auth events
3. **Modify inventory panels** → Inventory events
4. **Modify app/error.tsx** → Render error event
5. **Modify app/layout.tsx** → Import tracking hook
6. **Modify form components** → Validation failure events
7. **Modify SupplierDirectoryPanel.tsx** → Form + supplier events
8. **Modify IncidentManagerPanel.tsx** → Form + incident events
9. **Test each event** → Verify in Network tab
10. **End-to-end test** → Full user journey
11. **Code review** → No PII, proper timing, TypeScript compliance
12. **Deploy** → Phase 3 ready for merge

---

**Status:** ✅ Mapping Complete — Ready to Begin Implementation
