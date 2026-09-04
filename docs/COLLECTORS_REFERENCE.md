# Microsoft 365 Assessment Collector Reference Guide

Dokumen ini merupakan panduan resmi dan kamus referensi untuk seluruh kolektor data Microsoft 365 di dalam arsitektur `graph-agent`. Seluruh 45 endpoint telah terdaftar di [`config/api_inventory.json`](file:///opt/docker/graph-agent/config/api_inventory.json) sebagai *Single Source of Truth (SSOT)*.

---

## 1. Cara Eksekusi CLI (Unified Runner)

Sejak **Tahap 3 & 4**, seluruh kolektor dapat dijalankan menggunakan perintah terpadu:

```bash
# Menggunakan ID Baku (Rekomendasi)
python -m collectors.run_collector --collector <ID_BAKU>

# Menggunakan Alias / Slug
python -m collectors.run_collector --collector <SLUG>

# Mode Uji Coba Offline Aman (Tanpa menghubungi Graph API atau mengubah database)
python -m collectors.run_collector --collector <ID_ATAU_SLUG> --dry-run

# Output format JSON
python -m collectors.run_collector --collector <ID_ATAU_SLUG> --dry-run --json
```

---

## 2. Katalog Lengkap 45 Kolektor Data

### A. Microsoft Entra ID & Governance (20 Kolektor)

| ID Baku | Alias / Slug | Nama Kolektor | Izin Graph (Permissions) | Target Tabel Database |
| :--- | :--- | :--- | :--- | :--- |
| `G01-001` | `users`, `entra_users` | Users | `User.Read.All` | `core.user` |
| `G01-002` | `groups`, `entra_groups` | Groups | `Group.Read.All` | `core.group` |
| `G01-003` | `organization`, `entra_org` | Organization | `Organization.Read.All` | `core.organization` |
| `G01-005` | `directoryAuditLogs`, `directory_audit_logs` | Directory Audit Logs | `AuditLog.Read.All` | `core.audit_event` |
| `G01-006` | `signIns`, `sign_ins` | Sign-in Logs | `AuditLog.Read.All` | `core.signin_log` |
| `G01-007` | `applications` | Applications | `Application.Read.All` | `core.application` |
| `G01-008` | `servicePrincipals`, `service_principals` | Service Principals | `Application.Read.All` | `core.service_principal` |
| `G01-009` | `devices` | Devices | `Device.Read.All` | `core.device` |
| `G01-010` | `administrativeUnits`, `admin_units` | Administrative Units | `AdministrativeUnit.Read.All` | `core.administrative_unit` |
| `G01-011` | `conditionalAccessPolicies`, `ca_policies` | Conditional Access Policies | `Policy.Read.All` | `core.conditional_access_policy` |
| `G01-012` | `namedLocations`, `named_locations` | Conditional Access Named Locations | `Policy.Read.All` | `core.named_location` |
| `G01-013` | `riskyUsers`, `risky_users` | Risky Users | `IdentityRiskyUser.Read.All` | `core.risky_user` |
| `G01-014` | `riskDetections`, `risk_detections` | Risk Detections | `IdentityRiskEvent.Read.All` | `core.risk_detection` |
| `G01-018` | `directoryRoleDefinitions`, `directory_roles`, `entra_roles` | Directory Role Definitions | `RoleManagement.Read.Directory` | `core.directory_role_definition` |
| `G01-019` | `directoryRoleAssignments`, `entra_role_assignments` | Directory Role Assignments | `RoleManagement.Read.Directory` | `core.directory_role_assignment` |
| `G01-021` | `userRegistrationDetails`, `mfa_registration` | User MFA Registration Details | `AuditLog.Read.All` | `core.user_mfa_registration` |
| `ENTRA-GUESTS` | `entra_guests` | Entra Guest User Inventory | `User.Read.All` | `core.entra_guest` |
| `ENTRA-AUTH` | `entra_auth_methods`, `entra_auth` | Entra Authentication Methods | `UserAuthenticationMethod.Read.All` | `core.entra_auth_method` |
| `ENTRA-STALE` | `entra_stale_devices`, `entra_stale` | Entra Stale Device Inventory | `Device.Read.All` | `core.entra_device` |
| `ENTRA-PIM` | `entra_pim` | Entra PIM Assignments | `RoleManagement.Read.Directory` | `core.entra_pim_assignment` |

---

### B. Microsoft Intune Endpoint Management (4 Kolektor)

| ID Baku | Alias / Slug | Nama Kolektor | Izin Graph (Permissions) | Target Tabel Database |
| :--- | :--- | :--- | :--- | :--- |
| `INTUNE-001` | `intune_compliance` | Intune Device Compliance | `DeviceManagementManagedDevices.Read.All` | `core.intune_device` |
| `INTUNE-002` | `intune_enrollment` | Intune Device Enrollment | `DeviceManagementManagedDevices.Read.All` | `core.intune_enrollment` |
| `INTUNE-003` | `intune_compliance_policies` | Intune Compliance Policies | `DeviceManagementConfiguration.Read.All` | `core.intune_compliance_policy` |
| `INTUNE-004` | `intune_mobile_apps` | Intune Mobile Apps | `DeviceManagementApps.Read.All` | `core.intune_mobile_app` |

---

### C. Microsoft Defender & Purview Security (5 Kolektor)

| ID Baku | Alias / Slug | Nama Kolektor | Izin Graph (Permissions) | Target Tabel Database |
| :--- | :--- | :--- | :--- | :--- |
| `DEF-DEV` | `defender_devices`, `def_dev` | Defender Device Threats | `DeviceManagementManagedDevices.Read.All` | `core.defender_threat` |
| `DEF-P02` | `defender_o365`, `defender_alerts`, `def_p02` | Defender for Office 365 Alerts | `SecurityEvents.Read.All` | `core.defender_alert` |
| `DEF-P03` | `defender_cloud_app`, `def_p03` | Defender Cloud App Alerts | `SecurityEvents.Read.All` | `core.defender_cloud_app_alert` |
| `DLP-P01` | `dlp_alerts`, `dlp_p01` | Purview DLP Alerts | `SecurityEvents.Read.All` | `core.dlp_alert` |
| `DLP-P02` | `dlp_labels`, `dlp_p02` | Purview DLP Sensitivity Labels | `InformationProtectionPolicy.Read` | `core.dlp_label` |

---

### D. SharePoint & OneDrive Data (4 Kolektor)

| ID Baku | Alias / Slug | Nama Kolektor | Izin Graph (Permissions) | Target Tabel Database |
| :--- | :--- | :--- | :--- | :--- |
| `OD-AUDIT` | `onedrive_audit`, `od_audit` | OneDrive High-Value Audit | `ActivityFeed.Read` | `core.onedrive_high_value_audit_event` |
| `SP-A01` | `sharepoint_audit`, `sp_audit` | SharePoint High-Value Audit | `ActivityFeed.Read` | `core.sharepoint_high_value_audit_event` |
| `SP-SITES` | `sharepoint_sites`, `sp_sites` | SharePoint Site Inventory | `Sites.Read.All` | `core.sharepoint_site_url` |
| `G01-020` | `sharepointTenantSettings`, `sharepoint_settings`, `sp_settings` | SharePoint Tenant Settings | `SharePointTenantSettings.Read.All` | `core.sharepoint_tenant_settings` |

---

### E. Microsoft 365 Usage & Licensing (9 Kolektor)

| ID Baku | Alias / Slug | Nama Kolektor | Izin Graph (Permissions) | Target Tabel Database |
| :--- | :--- | :--- | :--- | :--- |
| `G01-004` | `subscribedSkus`, `subscribed_skus` | Subscribed SKUs | `LicenseAssignment.Read.All` | `core.subscribed_sku` |
| `USAGE-001` | `office365_active_user`, `usage_001` | Office365 Active User Detail | `Reports.Read.All` | `core.usage_office365_active_user` |
| `TM-001` | `teams_user_activity`, `tm_001` | Teams User Activity Detail | `Reports.Read.All` | `core.usage_teams_user_activity` |
| `USAGE-002` | `exchange_email_activity`, `usage_002` | Exchange Email Activity Detail | `Reports.Read.All` | `core.usage_exchange_email_activity` |
| `USAGE-003` | `exchange_mailbox_usage`, `usage_003` | Exchange Mailbox Usage Detail | `Reports.Read.All` | `core.usage_exchange_mailbox_usage` |
| `USAGE-004` | `onedrive_activity`, `usage_004` | OneDrive Activity Detail | `Reports.Read.All` | `core.usage_onedrive_activity` |
| `USAGE-005` | `onedrive_account_usage`, `usage_005` | OneDrive Usage Account Detail | `Reports.Read.All` | `core.usage_onedrive_account_usage` |
| `USAGE-006` | `sharepoint_user_activity`, `usage_006` | SharePoint Activity User Detail | `Reports.Read.All` | `core.usage_sharepoint_user_activity` |
| `USAGE-007` | `sharepoint_site_usage`, `usage_007` | SharePoint Site Usage Detail | `Reports.Read.All` | `core.usage_sharepoint_site_usage` |

---

### F. Service Health & Messages (3 Kolektor)

| ID Baku | Alias / Slug | Nama Kolektor | Izin Graph (Permissions) | Target Tabel Database |
| :--- | :--- | :--- | :--- | :--- |
| `G01-015` | `serviceHealthOverview` | Service Health Overview | `ServiceHealth.Read.All` | `core.service_health_overview` |
| `G01-016` | `serviceHealthIssues` | Service Health Issues | `ServiceHealth.Read.All` | `core.service_health_issue` |
| `G01-017` | `serviceUpdateMessages` | Service Update Messages | `ServiceMessage.Read.All` | `core.service_update_message` |

---

## 3. Jadwal Otomatis (Scheduler Cron)

Semua kolektor dikelola otomatis oleh service scheduler di [`collectors/scheduler.py`](file:///opt/docker/graph-agent/collectors/scheduler.py):
- **Setiap 1 Jam**: Sign-in logs, Risk detection/scoring, Service Health.
- **Setiap 6 Jam**: Directory data (Users, Groups, Roles, Policies), Intune device compliance, SharePoint sites, Entra guests & auth methods.
- **Setiap 24 Jam**: M365 Usage reports, License & SKU inventory, Defender threat devices & DLP alert inventory, event cleanup (retensi 90 hari).
