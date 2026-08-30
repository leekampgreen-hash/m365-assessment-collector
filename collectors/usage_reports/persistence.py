"""Curated current and refresh-date snapshot persistence for usage reports."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

TABLES = {
    "office365_active_user": "core.usage_office365_active_user",
    "exchange_email_activity": "core.usage_exchange_email_activity",
    "exchange_mailbox_usage": "core.usage_exchange_mailbox_usage",
    "onedrive_activity": "core.usage_onedrive_activity",
    "onedrive_account_usage": "core.usage_onedrive_account_usage",
    "sharepoint_user_activity": "core.usage_sharepoint_user_activity",
    "sharepoint_site_usage": "core.usage_sharepoint_site_usage",
    "teams_user_activity": "core.usage_teams_user_activity",
}

BASE_COLUMNS = ("tenant_id", "entity_key", "report_refresh_date", "identity_value", "identity_is_masked", "last_activity_date", "site_url", "display_name", "send_count", "receive_count", "read_count", "meeting_count", "mailbox_item_count", "storage_used", "issue_warning_quota", "prohibit_send_quota", "prohibit_send_receive_quota", "storage_allocated", "file_count", "active_file_count", "viewed_count", "edited_count", "synced_count", "internal_share_count", "external_share_count", "page_view_count", "deleted_date", "is_deleted", "has_archive", "assigned_products", "site_template", "observed_at")
TEAMS_COLUMNS = ("team_chat_message_count", "private_chat_message_count", "call_count")


def write_report_rows(executor: Any, key: str, rows: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]], *, complete: bool = True) -> None:
    table = TABLES.get(key)
    if table is None:
        raise ValueError("unknown usage report: {}".format(key))
    if not complete:
        raise ValueError("usage report acquisition is incomplete; current state was not replaced")
    if not rows:
        return
    tenant_ids = {current.get("tenant_id") for current, _ in rows}
    seen = {}
    for current, _ in rows:
        tenant_id = current.get("tenant_id")
        entity_key = str(current.get("entity_key", "")).strip().casefold()
        business_key = (tenant_id, entity_key)
        seen[business_key] = seen.get(business_key, 0) + 1
    duplicates = [(tenant_id, entity_key, count) for (tenant_id, entity_key), count in seen.items() if count > 1]
    if duplicates:
        tenant_id, entity_key, count = sorted(duplicates, key=str)[0]
        raise ValueError("duplicate usage report business key tenant={} entity={} count={}".format(tenant_id, entity_key, count))
    if None in tenant_ids:
        raise ValueError("usage report row tenant is missing")
    latest_by_tenant = {}
    for current, _ in rows:
        tenant_id = current["tenant_id"]
        refresh = current.get("report_refresh_date")
        if refresh is not None and (tenant_id not in latest_by_tenant or refresh > latest_by_tenant[tenant_id]):
            latest_by_tenant[tenant_id] = refresh
    for tenant_id in tenant_ids:
        executor.execute("DELETE FROM {} WHERE tenant_id = %s AND (report_refresh_date IS NULL OR report_refresh_date <= %s)".format(table), (tenant_id, latest_by_tenant.get(tenant_id)))
    for current, snapshot in rows:
        column_order = BASE_COLUMNS + (TEAMS_COLUMNS if key == "teams_user_activity" else ())
        columns = tuple(column for column in column_order if column in current)
        values = tuple(current[column] for column in columns)
        assignments = ", ".join("{} = EXCLUDED.{}".format(column, column) for column in columns if column not in ("tenant_id", "entity_key"))
        executor.execute("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT (tenant_id, entity_key) DO UPDATE SET {} WHERE {}.report_refresh_date IS NULL OR {}.report_refresh_date <= EXCLUDED.report_refresh_date".format(table, ", ".join(columns), ", ".join("%s" for _ in columns), assignments, table, table), values)
        snapshot_columns = tuple(column for column in column_order if column in snapshot) + ("snapshot_identity",)
        snapshot_values = tuple(snapshot[column] for column in snapshot_columns)
        executor.execute("INSERT INTO {}_snapshot ({}) VALUES ({}) ON CONFLICT (tenant_id, entity_key, report_refresh_date) DO NOTHING".format(table, ", ".join(snapshot_columns), ", ".join("%s" for _ in snapshot_columns)), snapshot_values)
