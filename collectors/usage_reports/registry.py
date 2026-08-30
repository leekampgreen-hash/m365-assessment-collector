"""Inventory and curated normalization for the seven usage reports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Mapping, Sequence

from .csv import CsvSchemaError, parse_report_csv


@dataclass(frozen=True)
class ReportSpec:
    key: str
    name: str
    path: str
    required_columns: tuple[str, ...]
    workload: str
    entity_kind: str


def _spec(key, name, method, required, workload, entity):
    return ReportSpec(key, name, "/v1.0/reports/" + method, tuple(required), workload, entity)


COMMON_USER = ("User Principal Name", "Report Refresh Date")
APPROVED_PERIODS = ("D7", "D30", "D90", "D180")
REPORTS = {
    "office365_active_user": _spec("office365_active_user", "Office 365 Active User Detail", "getOffice365ActiveUserDetail", COMMON_USER, "Microsoft 365", "user"),
    "exchange_email_activity": _spec("exchange_email_activity", "Exchange Email Activity User Detail", "getEmailActivityUserDetail", COMMON_USER, "Exchange", "user"),
    "exchange_mailbox_usage": _spec("exchange_mailbox_usage", "Exchange Mailbox Usage Detail", "getMailboxUsageDetail", COMMON_USER, "Exchange", "user"),
    "onedrive_activity": _spec("onedrive_activity", "OneDrive Activity User Detail", "getOneDriveActivityUserDetail", COMMON_USER, "OneDrive", "user"),
    "teams_user_activity": _spec("teams_user_activity", "Teams User Activity User Detail", "getTeamsUserActivityUserDetail", COMMON_USER, "Teams", "user"),
    "onedrive_account_usage": _spec("onedrive_account_usage", "OneDrive Usage Account Detail", "getOneDriveUsageAccountDetail", ("Report Refresh Date",), "OneDrive", "account"),
    "sharepoint_user_activity": _spec("sharepoint_user_activity", "SharePoint Activity User Detail", "getSharePointActivityUserDetail", COMMON_USER, "SharePoint", "user"),
    "sharepoint_site_usage": _spec("sharepoint_site_usage", "SharePoint Site Usage Detail", "getSharePointSiteUsageDetail", ("Report Refresh Date",), "SharePoint", "site"),
    "teams_user_activity": _spec("teams_user_activity", "Teams User Activity User Detail", "getTeamsUserActivityUserDetail", COMMON_USER, "Teams", "user"),
}

ALIASES = {
    "upn": ("User Principal Name", "UPN"), "refresh": ("Report Refresh Date", "Report Refresh Date"),
    "last_activity": ("Last Activity Date", "Exchange Last Activity Date", "OneDrive Last Activity Date", "SharePoint Last Activity Date"),
    "site_url": ("Site URL", "Site Url"), "site_id": ("Site Id", "Site ID"),
    "display_name": ("Display Name", "Owner Display Name"),
    "owner_upn": ("Owner Principal Name", "User Principal Name", "UPN"),
}


def get_report(key: str) -> ReportSpec:
    try:
        return REPORTS[key]
    except KeyError:
        raise KeyError("unknown usage report: {}".format(key)) from None


def get_adapter(key: str):
    from . import adapters
    adapter = getattr(adapters, key, None)
    if adapter is None:
        raise KeyError("unknown usage report: {}".format(key)) from None
    return adapter


def build_report_path(key: str, period: str = "D7") -> str:
    """Build the Graph function URL using only approved periods."""
    spec = get_report(key)
    if period not in APPROVED_PERIODS:
        raise ValueError("unsupported usage report period")
    return "{}(period='{}')".format(spec.path, period)


def _pick(row: Mapping[str, Any], names: Sequence[str]):
    lowered = {str(k).casefold(): v for k, v in row.items()}
    for name in names:
        if name.casefold() in lowered:
            return lowered[name.casefold()]
    return None


def _identity(row, spec):
    if spec.entity_kind == "user":
        value = _pick(row, ALIASES["upn"])
        if spec.key == "exchange_mailbox_usage":
            return value
        return value or _pick(row, ("Display Name",)) or "masked"
    if spec.entity_kind == "account":
        # Tenant privacy can mask site fields; an owner is a stable account key.
        return _pick(row, ALIASES["owner_upn"])
    site_id = _pick(row, ALIASES["site_id"])
    site_url = _pick(row, ALIASES["site_url"])
    compact_id = "".join(ch for ch in str(site_id or "") if ch.isalnum())
    site_id_usable = bool(site_id) and bool(compact_id) and set(compact_id) != {"0"}
    if site_id_usable:
        return site_id
    # Tenant privacy can mask the site id; the site url is a stable, unique
    # site key in the standard report and serves as the canonical fallback.
    if site_url is not None and str(site_url).strip():
        return site_url
    return None


def _usable_identity(value) -> bool:
    text = "" if value is None else str(value).strip()
    return bool(text) and text.casefold() not in ("masked", "null", "none")


def _as_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(str(value).strip())
        return number
    except (TypeError, ValueError):
        return None


def _as_bool(value):
    """Normalize report deletion flags without treating arbitrary text as true."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().casefold()
    if text in ("true", "1", "yes", "y", "deleted"):
        return True
    if text in ("false", "0", "no", "n", "not deleted", "active"):
        return False
    return None


def normalize_report_rows(key: str, content: bytes | str, *, tenant_id: int, observed_at: str) -> list[tuple[dict, dict]]:
    spec = get_report(key)
    rows = parse_report_csv(content, spec.required_columns)
    output = []
    for row in rows:
        refresh = _pick(row, ("Report Refresh Date",))
        if not refresh:
            raise CsvSchemaError("report refresh date is blank", classification="SCHEMA_CONTRACT_FAILURE")
        try:
            date.fromisoformat(str(refresh).strip())
        except (TypeError, ValueError):
            raise CsvSchemaError("report refresh date is malformed", classification="SCHEMA_CONTRACT_FAILURE") from None
        refresh = str(refresh).strip()
        identity = _identity(row, spec)
        if not _usable_identity(identity):
            raise CsvSchemaError("identity unavailable; report is masked or lacks a stable entity key",
                                 classification="ENTITY_IDENTITY_UNAVAILABLE")
        current = {
            "tenant_id": tenant_id, "entity_key": str(identity).strip().casefold(),
            "report_key": key, "report_refresh_date": refresh, "observed_at": observed_at,
            "identity_value": str(identity).strip(), "identity_is_masked": str(identity).strip().casefold() == "masked",
        }
        for field, names in {
            "last_activity_date": ALIASES["last_activity"], "site_url": ALIASES["site_url"],
            "display_name": ALIASES["display_name"],
        }.items():
            current[field] = _pick(row, names)
        metric_names = {
            "send_count": ("Send Count", "Send Count (Last Activity)"),
            "team_chat_message_count": ("Team Chat Message Count",),
            "private_chat_message_count": ("Private Chat Message Count",),
            "call_count": ("Call Count",),
            "receive_count": ("Receive Count", "Receive Count (Last Activity)"),
            "read_count": ("Read Count",), "meeting_count": ("Meeting Count",),
            "mailbox_item_count": ("Item Count", "Mailbox Item Count"),
            "storage_used": ("Storage Used (Byte)", "Storage Used (Bytes)", "Storage Used"),
            "issue_warning_quota": ("Issue Warning Quota", "Issue Warning Quota (Byte)", "Issue Warning Quota (Bytes)"),
            "prohibit_send_quota": ("Prohibit Send Quota", "Prohibit Send Quota (Byte)", "Prohibit Send Quota (Bytes)"),
            "prohibit_send_receive_quota": ("Prohibit Send/Receive Quota", "Prohibit Send/Receive Quota (Byte)", "Prohibit Send/Receive Quota (Bytes)"),
            "storage_allocated": ("Storage Allocated (Byte)", "Storage Allocated (Bytes)", "Storage Allocated"),
            "file_count": ("File Count", "Files"), "active_file_count": ("Active File Count", "Active Files"),
            "viewed_count": ("Viewed Or Edited File Count", "Viewed Count"),
            "edited_count": ("Edited File Count", "Edited Count"),
            "meeting_count": ("Meeting Count",),
            "synced_count": ("Synced File Count", "Synced Count"),
            "internal_share_count": ("Internal Shared File Count", "Internal Sharing Count"),
            "external_share_count": ("External Shared File Count", "External Sharing Count"),
            "page_view_count": ("Page View Count",), "deleted_date": ("Deleted Date",),
            "is_deleted": ("Is Deleted", "Deleted"), "has_archive": ("Has Archive", "Archive Mailbox"),
            "assigned_products": ("Assigned Products", "Assigned Product Names"),
            "site_template": ("Site Template",),
        }
        for field, names in metric_names.items():
            current[field] = _pick(row, names)
        current["user_principal_name"] = _pick(row, ALIASES["upn"])
        for field in ("storage_used", "issue_warning_quota", "prohibit_send_quota", "prohibit_send_receive_quota", "team_chat_message_count", "private_chat_message_count", "call_count", "meeting_count"):
            current[field] = _as_number(current[field])

        if key in ("exchange_mailbox_usage", "onedrive_activity", "onedrive_account_usage", "teams_user_activity"):
            raw_deleted = current["is_deleted"]
            current["is_deleted"] = _as_bool(raw_deleted)
            # OneDrive KPIs fail closed when the source flag is malformed.
            if key.startswith("onedrive_") and raw_deleted is not None and current["is_deleted"] is None:
                current["is_deleted"] = True
        snapshot = dict(current)
        snapshot["snapshot_identity"] = "{}:{}:{}".format(tenant_id, current["entity_key"], refresh)
        output.append((current, snapshot))
    return output
