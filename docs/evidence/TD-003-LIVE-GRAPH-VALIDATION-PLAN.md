# TD-003 Live Microsoft Graph Validation Plan

- **Usage mark:** `TD-003-LIVE-GRAPH-VALIDATION-PLAN-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Purpose:** `VALIDATION_DESIGN`
- **Status:** `DOCUMENTED / PLANNED`

## 1. Objective

Validate real tenant Microsoft Graph behavior against the assumptions established by the offline validation for G01-002 through G01-012. The validation must confirm application-permission behavior, live response shape, optional and nullable fields, pagination, and the compatibility of each approved adapter projection with real tenant data.

This is a validation plan only. It does not authorize changes to collectors, adapters, registry metadata, persistence, or database migrations.

## 2. Validation Scope

### Identity Event

| Endpoint | Graph path | Permission | Approved projection focus |
|---|---|---|---|
| G01-006 Sign-ins | `GET /v1.0/auditLogs/signIns` | `AuditLog.Read.All` | `id`, `createdDateTime`, `userId`, `userDisplayName`, `userPrincipalName`, `appDisplayName`, `status` |
| G01-005 Directory Audit | `GET /v1.0/auditLogs/directoryAudits` | `AuditLog.Read.All` | `id`, `activityDateTime`, `activityDisplayName`, `category`, `result`, `loggedByService` |

### Security Configuration

| Endpoint | Graph path | Permission | Approved projection focus |
|---|---|---|---|
| G01-011 Conditional Access | `GET /v1.0/identity/conditionalAccess/policies` | `Policy.Read.All` | `id`, `displayName`, `state`, `createdDateTime`, `modifiedDateTime` |
| G01-012 Named Locations | `GET /v1.0/identity/conditionalAccess/namedLocations` | `Policy.Read.All` | `id`, `displayName`, `createdDateTime`, `modifiedDateTime` |

### Inventory

| Endpoint | Graph path | Permission | Approved projection focus |
|---|---|---|---|
| G01-009 Devices | `GET /v1.0/devices` | `Device.Read.All` | `id`, `deviceId`, `accountEnabled`, `operatingSystem`, `operatingSystemVersion`, `trustType`, `approximateLastSignInDateTime` |
| G01-004 Subscribed SKUs | `GET /v1.0/subscribedSkus` | `LicenseAssignment.Read.All` | `id`, `skuId`, `skuPartNumber`, `capabilityStatus`, `consumedUnits`, `prepaidUnits`, `servicePlans` |

The live run must use the endpoint's configured application authentication, approved query projection, and pagination settings. It must not broaden the requested field set merely to obtain additional evidence.

## 3. Validation Steps

For each endpoint in scope:

1. Authenticate using Microsoft Graph application permission with a controlled tenant and the permission listed above.
2. Execute the existing collector through its normal runtime path.
3. Capture real Graph response metadata without retaining raw sensitive payloads.
4. Compare the observed response envelope and approved fields against the approved offline projection.
5. Validate field types, including nested fields and scalar conversions such as `status` and `prepaidUnits` where applicable.
6. Validate nullable behavior for fields that are absent or null in real tenant responses.
7. Validate pagination by exercising all returned pages and recording whether `@odata.nextLink` is present, followed, and terminated correctly.
8. Validate adapter mapping from the approved live response shape to the expected normalized record shape, including exclusion of unapproved fields.
9. Record a pass or blocker for the endpoint and preserve only the evidence listed below.

## 4. Expected Evidence

Capture the following metadata for every endpoint run:

- endpoint and HTTP method
- UTC timestamp of the request or validation run
- permission used
- HTTP status/result classification
- record count and page count
- sample schema metadata, including observed field names, value types, and nullable/absent status for approved fields
- pagination metadata, including whether a next link was observed and the number of pages followed
- adapter mapping result and any field-level discrepancy

Do not store:

- credentials
- access or refresh tokens
- client secrets, certificates, or other secrets
- raw sensitive Graph payloads

Evidence should use redacted metadata or synthetic representative values. Any tenant identifiers included in operational metadata must be minimized or redacted according to the controlled-tenant evidence procedure.

## 5. Success Criteria

An endpoint is **PASS** only if all of the following are true:

- endpoint responds successfully
- required application permission works
- observed schema matches the approved projection and expected envelope
- field types and nullable behavior match the adapter assumptions
- pagination behavior is handled correctly when applicable
- adapter assumptions are valid for the live response

TD-003 is complete only when every endpoint in the validation scope has a recorded result, with discrepancies either resolved through an approved follow-up or explicitly accepted as a documented blocker. A live result does not replace the existing offline test suite.

## 6. Known Limitations

- Requires a controlled tenant.
- Requires consented permissions.
- Tenant data volume and configuration affect observed field presence and pagination.
- Does not replace automated tests.
- This plan does not itself execute live Graph calls or establish credentials.
