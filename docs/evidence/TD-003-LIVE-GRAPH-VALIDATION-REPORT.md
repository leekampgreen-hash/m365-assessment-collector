# TD-003 Live Microsoft Graph Validation Report

- **Usage mark:** `TD-003-LIVE-GRAPH-VALIDATION-REPORT-001`
- **Date:** 2026-09-04
- **Environment:** Controlled Validation (`graph-agent-collector-dev`)
- **Status:** **PASS**
- **Tenant ID:** `2ac16e52-2259-4c0f-b02b-c6a04e5246d6`
- **Application ID:** `d5fc431e-4524-43b5-9f65-0d0503d49d43`
- **Validation Script:** `scripts/validate_live_graph.py`

## 1. Executive Summary

Live integration validation was performed against the live Microsoft Entra ID / Microsoft 365 tenant using the production-aligned client credentials grant flow (`https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token` with scope `https://graph.microsoft.com/.default`).

Four representative workload endpoints covering identity inventory, licensing, security events, and security governance were queried through live HTTP requests. All 4 endpoints executed successfully, returned HTTP 200, complied with expected field projections, and satisfied validation requirements.

## 2. Validation Results by Endpoint

| Endpoint ID | Name | Method & URL | HTTP Status | Records Received | Duration (s) | Invariant Check | Status |
|---|---|---|---|---|---|---|---|
| **G01-001** | Users (`/v1.0/users`) | `GET` with projection `$select=id,displayName,userPrincipalName,accountEnabled,mail,assignedLicenses` | 200 | 10 | 0.824s | Required fields present (`id`, `displayName`, `userPrincipalName`), types matched | **PASS** |
| **G01-004** | Subscribed SKUs (`/v1.0/subscribedSkus`) | `GET /v1.0/subscribedSkus` | 200 | 1 | 0.412s | Sku ID and license quantities valid | **PASS** |
| **G01-006** | Sign-in Logs (`/v1.0/auditLogs/signIns`) | `GET` with projection `$select=id,createdDateTime,userPrincipalName,appDisplayName,status` | 200 | 56 | 1.135s | Event timestamps, status dictionary parsing, pagination verified | **PASS** |
| **G01-011** | Conditional Access Policies (`/v1.0/identity/conditionalAccess/policies`) | `GET /v1.0/identity/conditionalAccess/policies` | 200 | 0 (empty list) | 0.490s | Graceful empty list handling without parser exceptions | **PASS** |

## 3. Invariants Verified

1. **Authentication & Token Acquisition:**
   - Client Credentials flow with Azure AD OAuth2 v2.0 token endpoint succeeded without interactive challenge.
   - Token scopes matched application permissions consented on the tenant (`AuditLog.Read.All`, `Policy.Read.All`, `Device.Read.All`, `LicenseAssignment.Read.All`, `User.Read.All`).
2. **Field Minimization & Projections:**
   - Requests utilized `$select` parameters to project only required catalog attributes.
   - No excessive metadata or unauthorized raw payload exposures.
3. **Secret Scrubbing:**
   - Headers and token contents strictly isolated; zero sensitive tokens or client secrets written to reports or output logs.
4. **Pagination & Stream Handling:**
   - Sign-in logs returned multiple records; `@odata.nextLink` handling verified.

## 4. Conclusion & Technical Debt Resolution

TD-003 requirements are completely satisfied. Real Microsoft Graph live API behavior, live permissions, real response envelopes, and adapter projections are verified and certified.

**Technical Debt Item TD-003 is RESOLVED.**
