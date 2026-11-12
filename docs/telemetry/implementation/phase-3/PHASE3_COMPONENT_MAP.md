# Phase 3 â€” Component Instrumentation Map
## Visual Guide to Event Locations

```
uis/backoffice/talent-pipeline-tracker/
â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ layout.tsx                    [âœ“ Add useSectionTracking hook]
â”‚   â”œâ”€â”€ page.tsx                      [â† frontend_page_loaded fires here]
â”‚   â”œâ”€â”€ error.tsx                     [âœ“ Add frontend_render_error tracking]
â”‚   â”œâ”€â”€ global-error.tsx              [â† Global error boundary]
â”‚   â”œâ”€â”€ login/
â”‚   â”‚   â””â”€â”€ page.tsx                  [â† session_expired check]
â”‚   â”œâ”€â”€ register/
â”‚   â”‚   â””â”€â”€ page.tsx                  [â† Account creation flow]
â”‚   â”œâ”€â”€ new/
â”‚   â”‚   â””â”€â”€ page.tsx                  [â† New candidate flow]
â”‚   â”œâ”€â”€ account/
â”‚   â”‚   â”œâ”€â”€ profile/
â”‚   â”‚   â”‚   â””â”€â”€ page.tsx              [â† form_validation_failed]
â”‚   â”‚   â””â”€â”€ change-password/
â”‚   â”‚       â””â”€â”€ page.tsx              [â† form_validation_failed]
â”‚   â”œâ”€â”€ inventory/
â”‚   â”‚   â””â”€â”€ page.tsx                  [â† section_viewed]
â”‚   â”œâ”€â”€ incidents/
â”‚   â”‚   â”œâ”€â”€ manager/
â”‚   â”‚   â”‚   â””â”€â”€ page.tsx              [â† section_viewed]
â”‚   â”‚   â””â”€â”€ analysis/
â”‚   â”‚       â””â”€â”€ page.tsx              [â† section_viewed]
â”‚   â””â”€â”€ suppliers/
â”‚       â””â”€â”€ page.tsx                  [â† section_viewed]
â”‚
â”œâ”€â”€ components/
â”‚   â”œâ”€â”€ auth/
â”‚   â”‚   â”œâ”€â”€ AuthForm.tsx              [âœ“ login_succeeded, login_failed, account_created, session_expired]
â”‚   â”‚   â”œâ”€â”€ AuthProvider.tsx          [â† Session context (no direct tracking)]
â”‚   â”‚   â””â”€â”€ AuthShell.tsx             [â† Logout handler (no direct tracking)]
â”‚   â”‚
â”‚   â”œâ”€â”€ candidates/
â”‚   â”‚   â”œâ”€â”€ CandidateList.tsx         [â† Lists candidates]
â”‚   â”‚   â”œâ”€â”€ CandidateCard.tsx         [â† Individual candidate card]
â”‚   â”‚   â”œâ”€â”€ CandidateDetail.tsx       [âœ“ form_validation_failed (status/stage updates)]
â”‚   â”‚   â””â”€â”€ CandidateForm.tsx         [âœ“ form_validation_failed (create candidate)]
â”‚   â”‚
â”‚   â”œâ”€â”€ inventory/
â”‚   â”‚   â”œâ”€â”€ InboundFormPanel.tsx      [âœ“ inbound_order_created, form_opened, form_abandoned, form_validation_failed]
â”‚   â”‚   â””â”€â”€ OutboundFormPanel.tsx     [âœ“ outbound_order_created, form_opened, form_abandoned, form_validation_failed]
â”‚   â”‚
â”‚   â”œâ”€â”€ incidents/
â”‚   â”‚   â”œâ”€â”€ IncidentManagerPanel.tsx  [âœ“ incident_status_changed, form_opened, form_abandoned, form_validation_failed]
â”‚   â”‚   â””â”€â”€ IncidentAnalysisPanel.tsx [â† Analysis display only]
â”‚   â”‚
â”‚   â”œâ”€â”€ suppliers/
â”‚   â”‚   â””â”€â”€ SupplierDirectoryPanel.tsx[âœ“ supplier_rate_updated, form_opened, form_abandoned, form_validation_failed]
â”‚   â”‚
â”‚   â”œâ”€â”€ profile/
â”‚   â”‚   â””â”€â”€ ProfilePanel.tsx          [âœ“ form_validation_failed]
â”‚   â”‚
â”‚   â”œâ”€â”€ notes/
â”‚   â”‚   â””â”€â”€ NoteSection.tsx           [â† Notes management]
â”‚   â”‚
â”‚   â””â”€â”€ ui/
â”‚       â”œâ”€â”€ Modal.tsx                 [â† Modal wrapper (no tracking here, parent tracks)]
â”‚       â”œâ”€â”€ Button.tsx                [â† Button wrapper]
â”‚       â”œâ”€â”€ Input.tsx                 [â† Input wrapper]
â”‚       â””â”€â”€ ...
â”‚
â”œâ”€â”€ hooks/
â”‚   â”œâ”€â”€ useTelemetry.ts               [â† Already created (Phase 2)]
â”‚   â”œâ”€â”€ useAuth.ts                    [â† Auth hook]
â”‚   â”œâ”€â”€ useRecord.ts                  [â† Candidate hook]
â”‚   â”œâ”€â”€ useRecords.ts                 [â† Candidates list hook]
â”‚   â”œâ”€â”€ useNotes.ts                   [â† Notes hook]
â”‚   â””â”€â”€ useSectionTracking.ts         [âœ“ TO CREATE: frontend_page_loaded + section_viewed]
â”‚
â”œâ”€â”€ lib/
â”‚   â”œâ”€â”€ telemetry/                    [â† Phase 2 complete]
â”‚   â”œâ”€â”€ auth-forms.ts                 [â† Validation functions]
â”‚   â”œâ”€â”€ auth-navigation.ts            [â† Navigation logic]
â”‚   â”œâ”€â”€ records.ts                    [â† API: getRecords, createRecord, etc.]
â”‚   â”œâ”€â”€ inventory.ts                  [â† API: createInbound, createOutbound, etc.]
â”‚   â”œâ”€â”€ incidents-api.ts              [â† API: createIncident, updateIncidentStatus, etc.]
â”‚   â”œâ”€â”€ suppliers-api.ts              [â† API: createSupplier, updateSupplierRate, etc.]
â”‚   â”œâ”€â”€ nexova-api.ts                 [â† Base API client]
â”‚   â””â”€â”€ ...
â”‚
â””â”€â”€ types/
    â”œâ”€â”€ auth.ts                       [â† Auth types]
    â”œâ”€â”€ record.ts                     [â† Candidate types]
    â”œâ”€â”€ inventory.ts                  [â† Inventory types]
    â”œâ”€â”€ incident-manager.ts           [â† Incident types]
    â””â”€â”€ supplier.ts                   [â† Supplier types]
```

---

## Event Flow Diagram

### Auth Events

```
User Action              Component                 Event Tracking           API Call
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

LOGIN:
Input email+password  â†’ AuthForm.handleSubmit()
                        â”œâ”€ validate()
                        â””â”€ signIn(api)
                           â”œâ”€ Success â†’ âœ“ login_succeeded â†’ route.replace("/")
                           â””â”€ Error  â†’ âœ“ login_failed â†’ setSubmitError()

REGISTER:
Input email+password  â†’ AuthForm.handleSubmit()
                        â”œâ”€ validate()
                        â””â”€ registerUser(api)
                           â”œâ”€ Success â†’ âœ“ account_created â†’ setRegistered(true)
                           â””â”€ Error  â†’ âœ“ register_failed (not tracked, shows UI error)

SESSION EXPIRED:
Token expires          â†’ Redirect to /login?expired=1
                        AuthForm (expired prop)
                        â”œâ”€ useEffect fires â†’ âœ“ session_expired
                        â””â”€ Show message to user
```

### Inventory Events

```
User Action              Component                 Event Tracking           API Call
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

CREATE INBOUND:
Fill form â†’ Click Save â†’ InboundFormPanel.submit()
                        â”œâ”€ validate()
                        â”œâ”€ createInbound(api)
                        â”‚  â””â”€ Success â†’ âœ“ inbound_order_created
                        â””â”€ setCreated() â†’ Show message

CREATE OUTBOUND:
Fill form â†’ Click Save â†’ OutboundFormPanel.submit()
                        â”œâ”€ validate()
                        â”œâ”€ createOutbound(api)
                        â”‚  â””â”€ Success â†’ âœ“ outbound_order_created
                        â””â”€ setCreated() â†’ Show message
```

### Frontend Events

```
User Action              Component                 Event Tracking           Notes
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

PAGE LOAD/NAVIGATE:
Click route link       â†’ pathname changes
                        useSectionTracking.useEffect()
                        â”œâ”€ mapPathnameToSection()
                        â”œâ”€ âœ“ frontend_page_loaded
                        â””â”€ âœ“ section_viewed

FORM VALIDATION FAILS:
User submits form      â†’ Component.handleSubmit()
                        â”œâ”€ validate() â†’ errors found
                        â”œâ”€ âœ“ form_validation_failed
                        â””â”€ Stop submission, show errors

RENDER ERROR:
Component throws       â†’ app/error.tsx boundary catches
                        â”œâ”€ error.digest generated
                        â”œâ”€ useEffect fires
                        â”œâ”€ âœ“ frontend_render_error
                        â””â”€ Show error UI + retry button
```

### Form Events

```
User Action              Component                 Event Tracking           Notes
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

OPEN MODAL:
Click "Add Supplier"  â†’ handleOpenModal()
                        â”œâ”€ âœ“ form_opened
                        â””â”€ setShowModal(true) â†’ Modal appears

EDIT FIELD:
Type in form          â†’ updateField()
                        â””â”€ Track field in fieldsEdited Set

CLOSE MODAL (NO SUBMIT):
Click X or ESC        â†’ handleClose()
                        â”œâ”€ Check fieldsEdited.size > 0
                        â”œâ”€ If true â†’ âœ“ form_abandoned
                        â””â”€ setShowModal(false)

SUBMIT FORM:
Fill + Click Save     â†’ handleSubmit()
                        â”œâ”€ validate() â†’ success
                        â”œâ”€ API call â†’ success
                        â”œâ”€ âœ“ form_opened (not fired on this path)
                        â””â”€ form_abandoned NOT fired â†’ modal closes
```

### Status Change Events

```
User Action              Component                 Event Tracking           API Call
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

UPDATE INCIDENT STATUS:
Click status dropdown â†’ Select new status
                        handleStatusChange()
                        â”œâ”€ Capture old status
                        â”œâ”€ updateIncidentStatus(api)
                        â”‚  â””â”€ Success â†’ âœ“ incident_status_changed
                        â””â”€ Refresh UI

UPDATE SUPPLIER RATE:
Edit rate field       â†’ Focus out or Click Update
                        handleRateUpdate()
                        â”œâ”€ Capture old rate
                        â”œâ”€ updateSupplierRate(api)
                        â”‚  â””â”€ Success â†’ âœ“ supplier_rate_updated
                        â””â”€ Refresh UI
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

âœ… Already configured in Phase 2

---

## Testing Checklist by Event

### Auth Events
- [ ] Login with valid credentials â†’ login_succeeded logged
- [ ] Login with invalid password â†’ login_failed logged
- [ ] Register new account â†’ account_created logged
- [ ] Manual token expiry â†’ /login?expired=1 â†’ session_expired logged
- [ ] All auth events contain email (no password)

### Inventory Events
- [ ] Create inbound order â†’ inbound_order_created logged
- [ ] Create outbound order â†’ outbound_order_created logged
- [ ] Event data: asset_id, quantity, office (no supplier name)
- [ ] Invalid form â†’ form_validation_failed (not _created)

### Frontend Events
- [ ] Navigate to each route â†’ frontend_page_loaded + section_viewed logged
- [ ] Render error â†’ error.tsx â†’ frontend_render_error logged
- [ ] Form with validation errors â†’ form_validation_failed logged
- [ ] All events have correct page_type and section_name values

### Form Events
- [ ] Click "Add Supplier" â†’ form_opened logged
- [ ] Edit field â†’ close modal â†’ form_abandoned logged with fields_touched count
- [ ] Submit form â†’ form_abandoned NOT logged
- [ ] Modal opened and events track via parent, not Modal.tsx itself

### Status Change Events
- [ ] Change incident status â†’ incident_status_changed logged with from/to status
- [ ] Update supplier rate â†’ supplier_rate_updated logged with new rate
- [ ] Event contains IDs and values (no sensitive info)

---

## Next Steps

1. **Create useSectionTracking.ts** (if doesn't exist)
2. **Modify AuthForm.tsx** â†’ Auth events
3. **Modify inventory panels** â†’ Inventory events
4. **Modify app/error.tsx** â†’ Render error event
5. **Modify app/layout.tsx** â†’ Import tracking hook
6. **Modify form components** â†’ Validation failure events
7. **Modify SupplierDirectoryPanel.tsx** â†’ Form + supplier events
8. **Modify IncidentManagerPanel.tsx** â†’ Form + incident events
9. **Test each event** â†’ Verify in Network tab
10. **End-to-end test** â†’ Full user journey
11. **Code review** â†’ No PII, proper timing, TypeScript compliance
12. **Deploy** â†’ Phase 3 ready for merge

---

**Status:** âœ… Mapping Complete â€” Ready to Begin Implementation
