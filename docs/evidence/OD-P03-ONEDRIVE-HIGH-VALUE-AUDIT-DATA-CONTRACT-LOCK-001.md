TASK_ID: OD-P03-ONEDRIVE-HIGH-VALUE-AUDIT-DATA-CONTRACT-LOCK-001
RESULT: OD_P03_PASS_WITH_GAPS

SOURCE_CONTRACT:
- api: Microsoft 365 Management Activity API (subscription -> bounded content listing -> content blob retrieval -> filtering/normalization)
- content_type: Audit.SharePoint
- auth_resource: https://manage.office.com
- permission: ActivityFeed.Read application permission
- capacity_source_separate: Microsoft Graph Reports; not merged with this audit contract

WORKLOAD_CONTRACT:
- discriminator: Workload structured field
- OneDrive_value: OneDrive
- SharePoint_value: SharePoint
- corroboration: OneDrive records used personal /personal/... SiteUrl/ObjectId semantics; SharePoint records used /sites/SP-Audit-Test semantics
- fail_closed: Missing or unknown Workload excludes the record; no filename/path heuristic or free-text classification

EVENT_GRAIN:
- grain: One persisted row per authoritative audit record Id per tenant
- business_key: (tenant_id, audit_record_id), with audit_record_id = Id
- evidence: Id present and unique in all 171 retrieved sample records; contentId is transport metadata only

COMMON_FIELDS:
- required: tenant_id; audit_record_id; event_time (CreationTime); operation (Operation); workload (Workload); event_category; external_flag; anonymous_flag; collected_at
- optional_nullable_source: actor_upn (UserId); record_type (RecordType); client_ip (ClientIP); object_id (ObjectId); site_url (SiteUrl); source_relative_url (SourceRelativeUrl); source_file_name (SourceFileName); unique_sharing_id (UniqueSharingId); target_user_or_group_name (TargetUserOrGroupName); target_user_or_group_type (TargetUserOrGroupType). Optional fields are nullable and operation-dependent.
- derived: event_category, external_flag, and anonymous_flag from locked operation/structured target semantics only. No fabricated defaults.

ANONYMOUS_SHARING:
- operation: AnonymousLinkCreated
- external: TRUE
- anonymous: TRUE
- persistence_rule: OneDrive record with this operation is EXTERNAL_SHARING and in scope; link identity/recipient correlation is not required. Live evidence also returned SharingLinkScope=Anonymous where present, but it is not the sole proof.

SPECIFIC_EXTERNAL_SHARING:
- proven_operation(s): SharingInvitationCreated and SharingSet
- target_field: TargetUserOrGroupType, with TargetUserOrGroupName as supporting emitted identity
- proven_external_type: Guest
- internal_rule: Member/internal target is external_flag=FALSE and is dropped from the high-value OneDrive dataset
- unknown_rule: Missing or ambiguous target evidence is UNKNOWN/FAIL_CLOSED and is not persisted as a confirmed external-sharing security event. Operation name alone and email-domain comparison are insufficient.

SECURE_LINK:
- correlation_status: DEFERRED_SCHEMA_ENRICHMENT; SecureLinkCreated and AddedToSecureLink were not observed in R3
- production_dependency: None
- classification_rule: Do not classify SecureLinkCreated as external by itself and do not require UniqueSharingId correlation. A secure-link record may enter scope only if an actually proven operation/schema independently carries structured external target evidence; otherwise fail closed.

MALWARE:
- operation: FileMalwareDetected
- documentation_status: SUPPORTED_DOCUMENTED for SharePoint/OneDrive audit
- live_status: LIVE_EVENT_NOT_OBSERVED in the 171-record controlled sample
- persistence_rule: In-scope when Workload=OneDrive and Operation=FileMalwareDetected; persist common authoritative fields, emitted object/file identity, emitted actor/system actor, and CreationTime. Do not invent malware name, severity, or signature fields. No malware test is required.

FILTER_CONTRACT:
- included: OneDrive records where Operation=AnonymousLinkCreated; or SharingInvitationCreated/SharingSet with TargetUserOrGroupType=Guest; or Operation=FileMalwareDetected
- excluded: SharePoint records; internal Member sharing; unknown/ambiguous sharing classification; all unrelated Audit.SharePoint operations; contentId-only or heuristic classifications
- raw_transport_exception: bounded raw transport may be retained only as ingestion evidence; it is not the business dataset and must not be indefinitely persisted by default

DEDUP:
- key: tenant_id + audit_record_id
- repeated_record: IDEMPOTENT / NO DUPLICATE INSERT
- overlap_required: YES; overlapping collection windows are required because delayed arrival was live-proven
- late_arrival: Accept out-of-order and late content within the overlap window; timestamp alone is not identity and watermark must not skip late records
- transport: contentId, contentCreated, expiration, pagination/NextPageUri, and retrieval window are ingestion metadata, not event identity

CAPACITY_CONTRACT:
- unchanged: storage_used, storage_allocated, utilization, LOW/MEDIUM/HIGH/NO_DATA, file_count, report_refresh_date
- source: Microsoft Graph Reports; independent from Audit.SharePoint audit collection

PRIVACY:
- raw_payload: Do not persist full raw AuditData indefinitely by default; retain only bounded transport evidence where operationally required
- minimization: Persist identity, timestamp, operation/category, actor, affected object/file, target classification, anonymous classification, and investigation traceability fields. Do not expose technical IDs in UX merely because stored.

OD_P04_PERSISTENCE_REQUIREMENTS:
- append/event-history semantics, not current-state replacement
- tenant-scoped immutable audit_record_id
- primary uniqueness/idempotency on (tenant_id, audit_record_id)
- nullable optional source fields
- late-arrival and overlap-window safe
- repeated content and repeated records produce no duplicate rows
- no destructive tenant-wide replacement
- separate ingestion metadata from business semantics where practical
- persist only records satisfying the locked filter contract

CLEANUP_REQUIRED:
- ONEDRIVE: notes.txt specific external share; Laporan bulanan.docx Anyone link
- SHAREPOINT: SP-AUDIT-EXTERNAL.txt specific external share; SP-AUDIT-ANONYMOUS.txt Anyone link
- These are test evidence only and are not collector dependencies. Cleanup may occur after contract lock.

GAPS:
- SecureLinkCreated/AddedToSecureLink correlation is not live-proven.
- FileMalwareDetected is documented but not live-observed; detailed malware fields remain unproven.
- R3 proved delayed arrival/overlap need, but did not establish a numeric overlap duration or complete pagination/ordering policy.

BLOCKERS:
- None for the locked OneDrive high-value audit contract or OD-P04 requirements.

DATA_CONTRACT_LOCKED:
YES

READY_FOR_OD_P04:
YES

FILES_CHANGED:
- docs/evidence/OD-P03-ONEDRIVE-HIGH-VALUE-AUDIT-DATA-CONTRACT-LOCK-001.md
- docs/PROJECT_PROGRESS.md
- docs/AI_USAGE_LOG.md

FINAL_STATUS:
OD_P03_PASS_WITH_GAPS
