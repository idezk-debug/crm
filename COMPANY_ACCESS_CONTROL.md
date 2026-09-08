# Company Access Control & Deletion Workflow

This document describes how the platform handles company access control, deletion requests, and the approval workflow.

## Overview

The platform supports two operational states for companies:

1. **Active**: Company can perform all operations directly (create, update, delete)
2. **Revoked**: Company operations require platform admin approval

## Company Access States

### Active Access (`is_active = True`)

When a company has **active access**:
- Company staff can **delete clients directly** without admin approval
- Company staff can **delete work items directly** without admin approval
- Company staff can **delete staff members directly** without admin approval
- All operations are processed immediately and appear in the system

### Revoked Access (`is_active = False`)

When a company has **revoked access** (either suspended or post-trial expiration):
- **All delete operations from company staff go through admin approval**
- Staff must submit a deletion request with a reason
- Platform owner/admin reviews and approves/rejects the request
- Deletion only completes when admin explicitly approves
- Company cannot perform any administrative actions independently

## Revocation Process

### How Platform Admin Revokes Company Access

1. Platform owner logs into **Platform Dashboard** (`/admin/platform-dashboard/`)
2. Locates company in "Recent Companies" table
3. Clicks **"⚠ Revoke Access"** button (appears as red/warning button)
4. Confirms the action in the popup dialog
5. System displays success message: `✓ Company '[Company Name]' access has been ACTIVATED. They can now perform all operations directly.` OR `⚠ Company '[Company Name]' access has been REVOKED. All their delete requests must now go through admin approval.`
6. Page reloads with updated company status

### How Platform Admin Restores Company Access

1. Navigate to **Platform Dashboard**
2. Locates company in "Recent Companies" table (now shows as "Inactive" status)
3. Clicks **"✓ Activate Access"** button (appears as green/success button)
4. Confirms the action in the popup dialog
5. System displays activation confirmation message
6. Company can immediately resume direct operations

## Deletion Request Workflow

### Staff Requesting Deletion (Active Company)

**Scenario:** Company is ACTIVE - staff request to delete a client/work item

1. Staff clicks delete action on client/work/staff in their company dashboard
2. System checks: `company.is_active == True`
3. **Deletion occurs immediately** - no approval needed
4. No DeletionRequest record is created
5. Related data cascades delete if applicable

### Staff Requesting Deletion (Revoked Company)

**Scenario:** Company is REVOKED - staff request to delete a client/work item

1. Staff clicks delete action on client/work/staff in their company dashboard
2. System checks: `company.is_active == False`
3. **DeletionRequest is created** with status `PENDING`
4. Request includes:
   - `target_type`: `client`, `work`, or `staff`
   - `target_id`: ID of the entity to be deleted
   - `company_id`: Company ID (for routing)
   - `requested_by`: Staff member who requested
   - `reason`: Optional reason provided by staff
   - `status`: `PENDING` (awaiting review)
5. Staff receives message: "Your deletion request has been submitted and is awaiting platform admin approval"
6. Request appears in **Platform Dashboard** under "Pending Company Requests"

### Platform Admin Reviewing Deletion Request

1. Platform owner navigates to **Platform Dashboard**
2. Scrolls to "Pending Company Requests" section
3. Reviews pending requests with columns:
   - **Company**: Which company submitted the request
   - **Type**: What is being deleted (Client/Work/Staff)
   - **Requested By**: Username of staff who made the request
   - **Reason**: Why they want to delete (if provided)
   - **Action**: Approve/Reject buttons
4. Clicks either:
   - **"Approve"** → Deletion is executed, request status changes to `APPROVED`, page reloads
   - **"Reject"** → Deletion is cancelled, request status changes to `REJECTED`, page reloads

### Approval Routing Logic

The system intelligently routes approval based on company status:

```
If DeletionRequest exists:
  If company.is_active == False (revoked):
    → Route to PLATFORM OWNER for approval
  Else if company.is_active == True (active):
    → Route to COMPANY ADMIN for approval
      (This handles staff-level deletions that need company approval)
```

## Entity Deletion Models

The `DeletionRequest` model stores:

- `id`: Primary key
- `company`: Foreign key to Company
- `target_type`: Choice field - `client`, `work`, or `staff`
- `target_id`: ID of entity being deleted
- `requested_by`: User who requested deletion
- `reason`: Optional explanation
- `status`: `PENDING`, `APPROVED`, or `REJECTED`
- `reviewed_by`: Admin who reviewed (null until reviewed)
- `reviewed_at`: Timestamp when reviewed (null until reviewed)

## Automatic Cleanup Process

### Expired Company Removal

Companies are automatically cleaned up when they meet expiration criteria:

**Trigger Conditions:**
- Company trial has EXPIRED + 10 days grace period has passed, AND
- `company.is_active == False` (already revoked), OR
- Company plan has EXPIRED + 10 days grace period has passed, AND
- `company.is_active == False` (already revoked)

**Cleanup Process:**
1. Run management command: `python manage.py cleanup_expired_companies`
2. System identifies all expired, revoked companies past grace period
3. For each company:
   - Deletes all DeletionRequest records (cascades)
   - Deletes all Client records (and their related Work items)
   - Deletes all Staff records
   - Deletes all WorkFile records
   - Deletes the Company record itself
4. Console output shows success/warning messages with company names

**Scheduling:**
- Can be scheduled via cron job: `0 0 * * * cd /path/to/project && python manage.py cleanup_expired_companies`
- Or scheduled via Celery beat task
- Recommended: Run daily at off-peak hours (e.g., 2 AM)

## Message Indicators

### Success Messages (Green Toast)

- `✓ Company '[Name]' access has been ACTIVATED. They can now perform all operations directly.`
- `✓ Deletion request approved and executed.`

### Warning Messages (Yellow Toast)

- `⚠ Company '[Name]' access has been REVOKED. All their delete requests must now go through admin approval.`

### Error Messages (Red Toast)

- `Only platform owner can manage company access.`
- `Unauthorized deletion request review.`

## Access Control Checks

### Who Can Toggle Company Access?

- ✅ **Platform Owner (Superuser)** - Can revoke/activate any company
- ❌ **Company Admin** - Cannot toggle any company access
- ❌ **Staff/Client** - Cannot access company management features

### Who Can Approve Deletion Requests?

- ✅ **Platform Owner** - Can approve requests from revoked companies
- ✅ **Company Admin** - Can approve staff-level deletions within their company (when active)
- ❌ **Staff/Client** - Cannot approve any deletion requests

### Who Can Submit Deletion Requests?

- ✅ **Company Staff** - Can request deletion when company is revoked
- ✅ **Company Staff** - Can delete directly when company is active (if not staff-level)
- ❌ **Clients** - Cannot delete (read-only access to works)

## Database State Examples

### Example 1: Active Company - Direct Deletion

```
Company: ABC Corp
  is_active = True
  has_active_access() = True

Action: Staff deletes Client "Acme Inc"
→ Client record deleted immediately
→ No DeletionRequest created
→ Deletion appears in system immediately
```

### Example 2: Revoked Company - Request-Based Deletion

```
Company: ABC Corp (Suspended)
  is_active = False
  has_active_access() = False

Action: Staff tries to delete Client "Acme Inc"
→ DeletionRequest created with:
   - status = PENDING
   - reviewed_by = null
   - reviewed_at = null
→ Staff sees "Request submitted for admin approval"
→ Client record still exists

Admin Action: Reviews & Approves
→ DeletionRequest.status = APPROVED
→ DeletionRequest.reviewed_by = platform_owner
→ Client record deleted
→ Company is notified of approval
```

### Example 3: Expired Company Auto-Cleanup

```
Company: Expired Corp
  plan_expires_at = "2024-12-01"
  is_active = False
  trial_ends_at = null

Current Date: 2024-12-15 (14 days after expiration)

`cleanup_expired_companies` runs:
→ Company identified as "expired + past grace period"
→ All related records deleted (DeletionRequests, Clients, Work, Staff, WorkFiles)
→ Company record deleted
→ Database cleanup complete
```

## Troubleshooting

### "I submitted a deletion request but nothing changed"

**Check:**
1. Is your company in revoked state? (`is_active = False`)
2. Has platform admin reviewed it yet?
3. Go to Platform Dashboard → Pending Company Requests section

**Solution:** Have platform admin check the pending requests and approve/reject explicitly.

### "I don't see the Pending Requests section"

**Check:**
1. Are you logged in as platform owner (superuser)?
2. Have any deletion requests been submitted?

**Solution:** Only platform owner sees Platform Dashboard. Staff see different views based on role.

### "Deletion happened but I didn't approve it"

**Check:**
1. Was company active at time of deletion?
2. Was it initiated by company admin (not staff)?

**Solution:** Active companies perform direct deletions without approval. This is by design.

## API/Database Queries

### Get Revoked Companies

```python
from MyApp.models import Company

revoked = Company.objects.filter(is_active=False)
```

### Get Pending Deletion Requests

```python
from MyApp.models import DeletionRequest

pending = DeletionRequest.objects.filter(status=DeletionRequest.STATUS_PENDING)
```

### Check Company Status

```python
company = Company.objects.get(id=1)
is_active = company.has_active_access()  # Returns True/False
```

### Get Deletion Requests for a Company

```python
from MyApp.models import DeletionRequest

requests = DeletionRequest.objects.filter(
    company_id=company.id,
    status=DeletionRequest.STATUS_PENDING
)
```

---

**Last Updated:** 2024  
**Maintained By:** Development Team
