# PHASE 3 â€” Quick Reference Guide
## Event Instrumentation Points

**Status:** Ready for implementation  
**Total Events:** 14  
**Application:** Talent Pipeline Tracker (backoffice)

---

## 1. AUTH EVENTS (4)

| Event | Component | Location | Trigger | Track When |
|-------|-----------|----------|---------|-----------|
| `login_succeeded` | AuthForm | auth/AuthForm.tsx:70 | Successful sign in | After signIn() completes, before router.replace() |
| `login_failed` | AuthForm | auth/AuthForm.tsx:68 | Failed sign in attempt | In catch block after signIn() error |
| `account_created` | AuthForm | auth/AuthForm.tsx:68 | Account registration success | After registerUser() completes |
| `session_expired` | AuthForm | auth/AuthForm.tsx:113 | Session expired, redirect to login | useEffect when expired={true} prop |

### Code Pattern

```typescript
// login_succeeded
try {
  await signIn(nexovaApi, email, password);
  telemetry.track("login_succeeded", { email });
  router.replace("/");
} catch (error) {
  telemetry.track("login_failed", { email, reason: "..." });
}

// account_created
try {
  await registerUser(nexovaApi, email, password);
  telemetry.track("account_created", { email });
  setRegistered(true);
}
```

---

## 2. INVENTORY EVENTS (2)

| Event | Component | Location | Trigger | Track When |
|-------|-----------|----------|---------|-----------|
| `inbound_order_created` | InboundFormPanel | inventory/InboundFormPanel.tsx | Submit inbound form | After createInbound() succeeds |
| `outbound_order_created` | OutboundFormPanel | inventory/OutboundFormPanel.tsx | Submit outbound form | After createOutbound() succeeds |

### Code Pattern

```typescript
// inbound_order_created
try {
  const created = await createInbound(nexovaApi, form);
  telemetry.track("inbound_order_created", {
    asset_id: form.asset_id,
    quantity: form.quantity,
    office: form.office
  });
  setCreated({...});
}

// outbound_order_created
try {
  const created = await createOutbound(nexovaApi, form);
  telemetry.track("outbound_order_created", {
    asset_id: form.asset_id,
    quantity: form.quantity,
    exit_type: form.exit_type,
    office: form.office
  });
  setCreated({...});
}
```

**Data to Track:**
- âœ… asset_id, quantity, office, exit_type
- âŒ supplier name, assigned_to (PII)

---

## 3. FRONTEND EVENTS (4)

| Event | Location | Trigger | Track When |
|-------|----------|---------|-----------|
| `frontend_render_error` | app/error.tsx | Page render error | In useEffect when error.digest exists |
| `frontend_page_loaded` | app/layout.tsx (hook) | Page navigates/loads | useEffect on pathname/status change |
| `form_validation_failed` | All form components | Form validation fails | In handleSubmit() before submission |
| `section_viewed` | app/layout.tsx (hook) | Route changes | useEffect on pathname change |

### Code Pattern

```typescript
// frontend_render_error (in app/error.tsx)
useEffect(() => {
  if (error.digest) {
    telemetry.track("frontend_render_error", {
      digest: error.digest,
      message: error.message || "Unknown"
    });
  }
}, [error]);

// frontend_page_loaded + section_viewed (in custom hook)
export function useSectionTracking() {
  const pathname = usePathname();
  const { status } = useAuth();
  const telemetry = useTelemetry();
  
  useEffect(() => {
    const section = mapPathnameToSection(pathname);
    telemetry.track("frontend_page_loaded", {
      page_type: section,
      user_authenticated: status === "authenticated"
    });
    telemetry.track("section_viewed", {
      section_name: section,
      user_authenticated: status === "authenticated"
    });
  }, [pathname, status, telemetry]);
}

// form_validation_failed (in all form components)
const errors = validateLoginFields(email, password);
if (Object.keys(errors).length > 0) {
  telemetry.track("form_validation_failed", {
    form_type: "login",
    field_count: Object.keys(errors).length,
    field_names: Object.keys(errors)
  });
  return;
}
```

**Section Mapping:**
- `/` â†’ "candidates"
- `/login`, `/register` â†’ "auth"
- `/inventory/**` â†’ "inventory"
- `/incidents/**` â†’ "incidents"
- `/suppliers` â†’ "suppliers"
- `/account/**` â†’ "profile"

---

## 4. FORM EVENTS (2)

| Event | Component | Location | Trigger | Track When |
|-------|-----------|----------|---------|-----------|
| `form_opened` | Modal-based forms | components/suppliers/SupplierDirectoryPanel.tsx, etc. | Modal/dialog opens | When user clicks "Add", before dialog shows |
| `form_abandoned` | Modal-based forms | Same components | Modal closes without submit | In onClose handler if form was edited |

### Code Pattern

```typescript
// form_opened
function handleOpenModal() {
  telemetry.track("form_opened", { form_type: "add_supplier" });
  setShowModal(true);
}

// form_abandoned
const [fieldsEdited, setFieldsEdited] = useState<Set<string>>(new Set());

function updateField(key, value) {
  setFieldsEdited(prev => new Set(prev).add(key));
  setForm(current => ({ ...current, [key]: value }));
}

function handleModalClose() {
  if (fieldsEdited.size > 0) {
    telemetry.track("form_abandoned", {
      form_type: "add_supplier",
      fields_touched: fieldsEdited.size
    });
  }
  setShowModal(false);
}
```

---

## 5. INCIDENTS EVENTS (1)

| Event | Component | Location | Trigger | Track When |
|-------|-----------|----------|---------|-----------|
| `incident_status_changed` | IncidentManagerPanel | incidents/IncidentManagerPanel.tsx | Status dropdown changes | After updateIncidentStatus() succeeds |

### Code Pattern

```typescript
async function handleStatusChange(incident, newStatus) {
  const oldStatus = incident.status;
  try {
    await updateIncidentStatus(incident.id, newStatus);
    telemetry.track("incident_status_changed", {
      incident_id: incident.id,
      from_status: oldStatus,
      to_status: newStatus
    });
  } catch (error) {
    // handle error
  }
}
```

---

## 6. SUPPLIERS EVENTS (1)

| Event | Component | Location | Trigger | Track When |
|-------|-----------|----------|---------|-----------|
| `supplier_rate_updated` | SupplierDirectoryPanel | suppliers/SupplierDirectoryPanel.tsx | Update monthly rate | After updateSupplierRate() succeeds |

### Code Pattern

```typescript
async function handleRateUpdate(supplier, newRate) {
  try {
    const updated = await updateSupplierRate(supplier.id, newRate);
    telemetry.track("supplier_rate_updated", {
      supplier_id: supplier.id,
      new_rate: newRate,
      currency: supplier.currency
    });
  } catch (error) {
    // handle error
  }
}
```

---

## Implementation Order (Priority)

1. **Auth Events** (1â€“2 hours)
   - Modify: components/auth/AuthForm.tsx
   - Test: login, register, session expiry scenarios

2. **Inventory Events** (1â€“2 hours)
   - Modify: components/inventory/InboundFormPanel.tsx, OutboundFormPanel.tsx
   - Test: Create inbound, create outbound

3. **Frontend Events** (2â€“3 hours)
   - Modify: app/error.tsx, app/layout.tsx
   - Create: hooks/useSectionTracking.ts
   - Modify: All form components (10+ files)
   - Test: Page navigation, form validation, error scenarios

4. **Form Events** (1â€“2 hours)
   - Modify: components/suppliers/SupplierDirectoryPanel.tsx
   - Modify: components/incidents/IncidentManagerPanel.tsx
   - Test: Modal open/close, field editing

5. **Status Change Events** (1 hour)
   - Modify: components/incidents/IncidentManagerPanel.tsx, suppliers/SupplierDirectoryPanel.tsx
   - Test: Status/rate updates

**Total Estimated Time:** 6â€“10 hours

---

## Files to Modify

**Already Imported useTelemetry:**
```
hooks/useTelemetry.ts â† Already exists, ready to use
```

**Files to Modify:**
- components/auth/AuthForm.tsx
- components/inventory/InboundFormPanel.tsx
- components/inventory/OutboundFormPanel.tsx
- components/suppliers/SupplierDirectoryPanel.tsx
- components/incidents/IncidentManagerPanel.tsx
- app/error.tsx
- app/layout.tsx

**New Files to Create:**
- hooks/useSectionTracking.ts

**No Changes Needed:**
- lib/telemetry/ (Phase 2 already complete)
- Backend endpoints (Phase 1 already complete)

---

## Testing Checklist

- [ ] Event fires at correct time
- [ ] Event data matches expected schema
- [ ] No PII in event payload
- [ ] Event does not break component functionality
- [ ] Multiple events queued â†’ batch sent
- [ ] Network tab shows CloudEvents structure
- [ ] Backend receives and logs events
- [ ] Page unload sends remaining events via sendBeacon

---

## Common Pitfalls to Avoid

âŒ **Do NOT:**
- Track before validation (events should reflect actual state)
- Include sensitive data (passwords, full names, phone numbers)
- Call telemetry.track() in every render (use useEffect with deps)
- Ignore telemetry errors (always wrap in try/catch to not break app)
- Track premature (e.g., before API response)

âœ… **DO:**
- Track after successful state changes
- Use minimal data (IDs, status values, counts)
- Use useEffect with proper dependencies
- Log telemetry errors to console but continue
- Verify events in Network tab during testing

---

## Quick Debug Tips

1. **Check if event was queued:**
   ```typescript
   // In browser console:
   telemetry.getQueue() // Shows pending events
   ```

2. **Force flush:**
   ```typescript
   telemetry.flush() // Send queued events immediately
   ```

3. **Network tab:**
   - Filter for `/api/telemetry/events`
   - Check request body for CloudEvents format
   - Verify response is 200 with `{received: N}`

4. **Backend logs:**
   ```bash
   docker logs <backend-container> | grep telemetry
   ```

---

**Next Step:** User approval to begin Phase 3 implementation
