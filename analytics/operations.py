"""Business analytics over already-persisted, normalized Collector rows.

This module deliberately knows nothing about Graph clients or acquisition.  A
caller supplies mappings keyed by the persisted table's short name, or uses
``from_connection`` which issues only the fixed read-only statements below.
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
from typing import Any, Mapping


TABLES = (
    "users", "office365_active_user", "exchange_email_activity",
    "exchange_mailbox_usage", "onedrive_activity", "onedrive_account_usage",
    "onedrive_account_capacity",
    "sharepoint_user_activity", "sharepoint_site_usage", "license_assignments",
    "subscribed_sku",
)
USAGE_TABLES = (
    "office365_active_user", "exchange_email_activity", "exchange_mailbox_usage",
    "onedrive_activity", "onedrive_account_usage", "sharepoint_user_activity",
    "sharepoint_site_usage",
)
CAPACITY_VIEW_TABLES = ("exchange_mailbox_capacity", "onedrive_account_capacity")


def _rows(source: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    value = source.get(name, ())
    return [dict(row) for row in value]


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _observed(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except (TypeError, ValueError):
        return None


def _refresh(rows: list[dict[str, Any]]) -> str | None:
    values = [_date(row.get("report_refresh_date")) for row in rows]
    values = [value for value in values if value is not None]
    return max(values).isoformat() if values else None


def _metric(value: Any, rows: list[dict[str, Any]], *, status: str = "READY",
            missing: str | None = None, period: str | None = None) -> dict[str, Any]:
    return {
        "value": value,
        "source_refresh_date": _refresh(rows),
        "source_period": period,
        "status": status,
        "missing_dependency": missing,
    }


def _capacity_status(rows: list[dict[str, Any]]) -> str:
    return "READY" if rows else "DATA_DEPENDENCY_UNAVAILABLE"


def _number(row: Mapping[str, Any], *names: str) -> int | float | None:
    for name in names:
        value = row.get(name)
        if value is not None:
            try:
                if isinstance(value, str):
                    return float(value) if "." in value else int(value)
                from decimal import Decimal
                if isinstance(value, Decimal):
                    return int(value) if value == value.to_integral_value() else float(value)
                return int(value) if isinstance(value, bool) else value
            except (TypeError, ValueError, ArithmeticError):
                return None
    return None


def _onedrive_account_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep account evidence that is explicitly non-deleted or unflagged."""
    result = []
    for row in rows:
        deleted = _deleted(row.get("is_deleted"))
        if deleted is False or ("is_deleted" not in row or row.get("is_deleted") is None):
            result.append(row)
    return result


def _onedrive_non_deleted(row: Mapping[str, Any]) -> bool:
    deleted = _deleted(row.get("is_deleted"))
    return deleted is False or ("is_deleted" not in row or row.get("is_deleted") is None)


def _deleted(value: Any) -> bool | None:
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


def _evidence_status(row: Mapping[str, Any], workload: str, as_of: date) -> str:
    activity_date = _date(row.get("last_activity_date"))
    if activity_date is not None:
        return "utilized" if (as_of - activity_date).days < 30 else "explicitly_inactive"
    fields = {
        "onedrive_activity": ("viewed_count", "synced_count"),
        "exchange_email_activity": ("send_count", "receive_count", "read_count", "meeting_count"),
        "sharepoint_user_activity": ("viewed_count", "edited_count", "synced_count", "page_view_count"),
    }.get(workload, ())
    values = [_number(row, field) for field in fields if row.get(field) is not None]
    if not values:
        return "insufficient_evidence"
    return "utilized" if any(value > 0 for value in values) else "explicitly_inactive"


def _key(row: Mapping[str, Any]) -> str | None:
    # Usage persistence retains the source identity separately from its table
    # key.  Prefer that common UPN value; entity_key is report-table identity,
    # not a directory identity contract.
    value = row.get("user_principal_name") or row.get("identity_value") or row.get("entity_key")
    return str(value).strip().casefold() if value and str(value).strip().casefold() not in {"masked", "null", "none"} else None


def _directory_key(row: Mapping[str, Any]) -> str | None:
    """Return the persisted report-compatible directory identity only."""
    value = row.get("user_principal_name")
    return str(value).strip().casefold() if value and str(value).strip().casefold() not in {"masked", "null", "none"} else None


def _user_ref(key: str | None, masked: bool = False) -> str:
    if not key or masked:
        return "masked"
    return "user-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


class OperationsAnalyticsQueryService:
    """Build sanitized analytics from persisted normalized rows."""

    def __init__(self, rows: Mapping[str, Any], *, as_of: date | str | None = None):
        self.rows = rows
        self.as_of = _date(as_of) or date.today()
        self.users = _rows(rows, "users")
        self.tables = {}
        for name in USAGE_TABLES:
            values = _rows(rows, name)
            by_tenant: dict[Any, list[dict[str, Any]]] = {}
            for row in values:
                by_tenant.setdefault(row.get("tenant_id"), []).append(row)
            selected = []
            for tenant_rows in by_tenant.values():
                observed = [_observed(row.get("observed_at")) for row in tenant_rows]
                observed = [value for value in observed if value is not None]
                newest = max(observed) if observed else None
                selected.extend(row for row in tenant_rows if newest is None or _observed(row.get("observed_at")) == newest)
            self.tables[name] = selected
        # The authoritative Exchange capacity view is already the newest
        # current generation per tenant (filtered in SQL); it is the single
        # derived-data contract for capacity reporting, so it is consumed
        # directly without re-deriving utilization/usage_level in Python.
        self.tables["exchange_mailbox_capacity"] = _rows(rows, "exchange_mailbox_capacity")
        self.tables["onedrive_account_capacity"] = _rows(rows, "onedrive_account_capacity")

    @classmethod
    def from_connection(cls, connection: Any, tenant_id: int, *, as_of: date | str | None = None):
        """Load only approved persisted tables; never invokes an acquisition API."""
        names = {
            "users": 'SELECT tenant_id, user_id, source_object_id, user_principal_name, display_name, account_enabled FROM core."user" WHERE tenant_id = %s',
            "license_assignments": 'SELECT a.tenant_id, a.user_id, a.sku_id, u.user_principal_name FROM core.user_license_assignment a JOIN core."user" u ON u.tenant_id = a.tenant_id AND u.user_id = a.user_id WHERE a.tenant_id = %s',
            "subscribed_sku": "SELECT sku_id, sku_part_number, consumed_units, prepaid_units, capability_status, last_observed_at FROM core.subscribed_sku WHERE tenant_id = %s",
            "exchange_mailbox_capacity": "SELECT tenant_id, identity_value, user_principal_name, user_ref, identity_is_masked, storage_used, mailbox_capacity, utilization_percent, usage_level, report_refresh_date, last_activity_date FROM analytics.exchange_mailbox_capacity WHERE tenant_id = %s",
            "onedrive_account_capacity": "SELECT tenant_id, entity_key, identity_value, user_ref, identity_is_masked, storage_used, storage_allocated, utilization_percent, usage_level, file_count, report_refresh_date FROM analytics.onedrive_account_capacity WHERE tenant_id = %s",
        }
        names.update({name: "SELECT current_rows.* FROM core.usage_{0} current_rows JOIN (SELECT tenant_id, MAX(observed_at) AS observed_at FROM core.usage_{0} WHERE tenant_id = %s GROUP BY tenant_id) newest ON newest.tenant_id = current_rows.tenant_id AND newest.observed_at = current_rows.observed_at WHERE current_rows.tenant_id = %s".format(name) for name in USAGE_TABLES})
        loaded: dict[str, list[dict[str, Any]]] = {}
        for name, sql in names.items():
            cursor = connection.cursor()
            # The newest-generation usage tables take (tenant_id, tenant_id);
            # all other fixed queries take a single tenant_id.
            cursor.execute(sql, (tenant_id, tenant_id) if name in USAGE_TABLES else (tenant_id,))
            description = [item[0] for item in cursor.description]
            loaded[name] = [dict(zip(description, row)) for row in cursor.fetchall()]
        return cls(loaded, as_of=as_of)

    def _all_usage(self) -> list[dict[str, Any]]:
        return [row for values in self.tables.values() for row in values]

    def _adoption(self, name: str, *, fields: tuple[str, ...] = ()) -> dict[str, Any]:
        rows = self.tables[name]
        if not rows:
            unavailable = _metric(None, rows, status="DATA_DEPENDENCY_UNAVAILABLE", missing=name)
            return {"active_users": unavailable, "inactive_users": unavailable, "adoption_rate": unavailable}
        directory = {key for row in self.users if (key := _directory_key(row))}
        keyed = {key: row for row in rows if (key := _key(row)) and key in directory}
        statuses = {key: _evidence_status(row, name, self.as_of) for key, row in keyed.items()}
        active = {key for key, status in statuses.items() if status == "utilized"}
        inactive = {key for key, status in statuses.items() if status == "explicitly_inactive"}
        applicable = len(directory) if self.users else None
        result = {
            "active_users": _metric(len(active) if active or inactive else None, rows,
                                     status="READY" if active or inactive else "DATA_DEPENDENCY_UNAVAILABLE",
                                     missing=None if active or inactive else "activity evidence"),
            "inactive_users": _metric(len(inactive) if active or inactive else None, rows,
                                       status="READY" if active or inactive else "DATA_DEPENDENCY_UNAVAILABLE",
                                       missing=None if active or inactive else "activity evidence"),
            "applicable_users": _metric(applicable, self.users, status="READY" if self.users else "DATA_DEPENDENCY_UNAVAILABLE", missing=None if self.users else "core user data"),
            "adoption_rate": _metric(round(len(active) / applicable * 100, 2) if applicable and (active or inactive) else None, rows,
                                      status="READY" if active or inactive else "DATA_DEPENDENCY_UNAVAILABLE",
                                      missing=None if active or inactive else "activity evidence"),
        }
        for field in fields:
            values = [_number(row, field) for row in rows]
            values = [value for value in values if value is not None]
            result[field] = _metric(sum(values) if values else None, rows,
                                    status="READY" if values else "DATA_DEPENDENCY_UNAVAILABLE",
                                    missing=None if values else field)
        return result

    def _recent_activity(self, row: Mapping[str, Any], days: int = 30) -> bool:
        activity_date = _date(row.get("last_activity_date"))
        if activity_date is not None:
            return (self.as_of - activity_date).days < days
        return _evidence_status(row, "", self.as_of) == "utilized"

    def tenant_summary(self) -> dict[str, Any]:
        users = self.users
        office = self.tables["office365_active_user"]
        def count(value: int | None, source: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
            return _metric(value, source, **kwargs)
        enabled = sum(row.get("account_enabled") is True for row in users)
        disabled = sum(row.get("account_enabled") is False for row in users)
        directory = {_directory_key(row) for row in users if _directory_key(row)}
        active = {_key(row) for row in office if _key(row) in directory and self._recent_activity(row)}
        user_status = "READY" if users else "DATA_DEPENDENCY_UNAVAILABLE"
        user_missing = None if users else "core user data"
        return {
            "total_users": count(len(users) if users else None, users, status=user_status, missing=user_missing),
            "enabled_users": count(enabled if users else None, users, status=user_status, missing=user_missing),
            "disabled_users": count(disabled if users else None, users, status=user_status, missing=user_missing),
            "active_m365_users": count(len(active) if users and office else None, office, status="READY" if users and office else "DATA_DEPENDENCY_UNAVAILABLE", missing=None if users and office else "core user data or office365_active_user"),
            "inactive_m365_users": count(len({k for k in (_key(r) for r in users) if k} - active) if users and office else None, office, status="READY" if users and office else "DATA_DEPENDENCY_UNAVAILABLE", missing=None if users and office else "core user data or office365_active_user"),
            "exchange_active_users": self.exchange_adoption()["active_users"],
            "onedrive_active_users": self.onedrive_adoption()["active_users"],
            "sharepoint_active_users": self.sharepoint_user_adoption()["active_users"],
        }

    def inactivity_candidates(self) -> list[dict[str, Any]]:
        by_user: dict[str, dict[str, Any]] = {}
        for row in self.users:
            key = _directory_key(row)
            if key:
                by_user[key] = {"key": key, "account_enabled": row.get("account_enabled"), "workloads": {}}
        for name, rows in self.tables.items():
            if name in ("onedrive_account_usage",):
                continue
            for row in rows:
                key = _key(row)
                if key in by_user:
                    by_user[key]["workloads"][name] = row
        output = []
        for item in by_user.values():
            dates = [_date(row.get("last_activity_date")) for row in item["workloads"].values()]
            dates = [value for value in dates if value]
            latest = max(dates) if dates else None
            age = (self.as_of - latest).days if latest else None
            classes = {str(days): ("inactive" if age is not None and age >= days else "active" if age is not None else "unknown") for days in (30, 60, 90)}
            output.append({"user_ref": _user_ref(item["key"]), "account_enabled": item["account_enabled"], "license_state": "unknown", "latest_activity_date": latest.isoformat() if latest else None, "inactivity_30_60_90": classes, "multi_workload_inactive": bool(item["workloads"]) and all(not self._recent_activity(row) for row in item["workloads"].values())})
        return output

    def exchange_capacity(self) -> dict[str, Any]:
        # The authoritative analytical view is the single derived-data contract:
        # utilization_percent and usage_level come from SQL, never recomputed here.
        view_rows = self.tables["exchange_mailbox_capacity"]
        raw_rows = self.tables["exchange_mailbox_usage"]
        buckets = {"low": 0, "medium": 0, "high": 0, "no_data": 0}
        capacity_status = _capacity_status(view_rows)
        details = []
        for row in view_rows:
            level = str(row.get("usage_level") or "NO_DATA").casefold()
            level = level if level in buckets else "no_data"
            buckets[level] += 1
            details.append({
                "identity_value": row.get("identity_value") or row.get("user_principal_name"),
                "user_principal_name": row.get("user_principal_name") or row.get("identity_value"),
                "user_ref": row.get("user_ref") or "masked",
                "storage_used": _number(row, "storage_used"),
                "mailbox_capacity": _number(row, "mailbox_capacity"),
                "utilization_percent": _number(row, "utilization_percent"),
                "usage_level": level,
                "report_refresh_date": (_date(row.get("report_refresh_date")).isoformat()
                                         if _date(row.get("report_refresh_date")) else None),
            })
        return {
            "capacity_usage": buckets,
            "data_last_refreshed": _refresh(view_rows) or _refresh(raw_rows),
            "mailbox_capacity_risk": _metric(buckets["high"], view_rows,
                                              status=capacity_status,
                                              missing=None if view_rows else "analytics.exchange_mailbox_capacity"),
            "total_storage_used": sum(v for v in (_number(r, "storage_used") for r in view_rows) if v is not None) if view_rows else None,
            "total_mailbox_items": sum(v for v in (_number(r, "mailbox_item_count") for r in raw_rows) if v is not None) if raw_rows else None,
            "mailboxes": details,
        }

    def exchange_adoption(self) -> dict[str, Any]:
        # Exchange basic usage is deliberately grounded in mailbox evidence;
        # email activity counts remain exposed only as legacy source metrics.
        mailbox = self.tables["exchange_mailbox_usage"]
        email = self.tables["exchange_email_activity"]
        if mailbox:
            active_rows = [row for row in mailbox
                           if _deleted(row.get("is_deleted")) is False
                           and _date(row.get("last_activity_date")) is not None]
            inactive_rows = [row for row in mailbox
                             if _deleted(row.get("is_deleted")) is False
                             and _date(row.get("last_activity_date")) is None]
            active = _metric(len({_key(row) or "row:{}".format(index)
                                  for index, row in enumerate(active_rows)}), mailbox)
            inactive = _metric(len({_key(row) or "row:{}".format(index)
                                    for index, row in enumerate(inactive_rows)}), mailbox)
            applicable = len({_key(row) or "row:{}".format(index)
                              for index, row in enumerate(mailbox)
                              if _deleted(row.get("is_deleted")) is False})
            result = {
                "capacity_usage": self.exchange_capacity()["capacity_usage"],
                "data_last_refreshed": self.exchange_capacity()["data_last_refreshed"],
                "mailbox_capacity_risk": self.exchange_capacity()["mailbox_capacity_risk"],
                "mailbox_details": self.exchange_capacity()["mailboxes"],
                "active_users": active,
                "inactive_users": inactive,
                "applicable_users": _metric(applicable, mailbox),
                "adoption_rate": _metric(round(active["value"] / applicable * 100, 2) if applicable else None, mailbox),
            }
            last_dates = [_date(row.get("last_activity_date")) for row in active_rows]
            result["last_activity"] = _metric(max(last_dates).isoformat() if last_dates else None, mailbox,
                                               status="READY" if last_dates else "DATA_DEPENDENCY_UNAVAILABLE",
                                               missing=None if last_dates else "last_activity_date")
            storage = [_number(row, "storage_used") for row in mailbox]
            items = [_number(row, "mailbox_item_count") for row in mailbox]
            result["mailbox_usage"] = _metric({
                "total_storage_used": sum(value for value in storage if value is not None) if any(value is not None for value in storage) else None,
                "mailbox_item_count": sum(value for value in items if value is not None) if any(value is not None for value in items) else None,
            }, mailbox, status="READY" if any(value is not None for value in storage + items) else "DATA_DEPENDENCY_UNAVAILABLE",
            missing=None if any(value is not None for value in storage + items) else "mailbox metrics")
        else:
            unavailable = _metric(None, mailbox, status="DATA_DEPENDENCY_UNAVAILABLE", missing="exchange_mailbox_usage")
            result = {"active_users": unavailable, "inactive_users": unavailable,
                      "applicable_users": unavailable, "adoption_rate": unavailable,
                       "last_activity": unavailable, "mailbox_usage": unavailable,
                        "capacity_usage": {"low": 0, "medium": 0, "high": 0, "no_data": 0}, "mailbox_capacity_risk": _metric(None, mailbox, status="DATA_DEPENDENCY_UNAVAILABLE", missing="analytics.exchange_mailbox_capacity"), "data_last_refreshed": None, "mailbox_details": []}

        legacy = self._adoption("exchange_email_activity", fields=("send_count", "receive_count", "read_count"))
        result.update({field: legacy[field] for field in ("send_count", "receive_count", "read_count")})
        return result

    def onedrive_adoption(self) -> dict[str, Any]:
        activity = self.tables["onedrive_activity"]
        accounts = self.tables["onedrive_account_usage"]
        capacity = self.tables["onedrive_account_capacity"]
        usable_activity = [row for row in activity if _onedrive_non_deleted(row)]
        active_keys = {_key(row) for row in usable_activity
                       if _key(row) and _date(row.get("last_activity_date")) is not None}
        active_users = _metric(len(active_keys) if activity else None, activity,
                               status="READY" if activity else "DATA_DEPENDENCY_UNAVAILABLE",
                               missing=None if activity else "onedrive_activity")

        usable_accounts = _onedrive_account_rows(capacity)
        account_activity = [row for row in usable_accounts
                            if _date(row.get("last_activity_date")) is not None]
        active_accounts = _metric(len(account_activity) if accounts else None, accounts,
                                  status="READY" if accounts else "DATA_DEPENDENCY_UNAVAILABLE",
                                  missing=None if accounts else "onedrive_account_usage")
        dates = [_date(row.get("last_activity_date"))
                 for row in usable_activity + usable_accounts]
        dates = [value for value in dates if value is not None]
        latest = _metric(max(dates).isoformat() if dates else None,
                         activity + accounts,
                         status="READY" if dates else "DATA_DEPENDENCY_UNAVAILABLE",
                         missing=None if dates else "last_activity_date")

        def numeric_field(name: str) -> tuple[list[int | float | None], bool]:
            values = []
            malformed = False
            for row in usable_accounts:
                if row.get(name) is not None:
                    value = _number(row, name)
                    malformed |= value is None
                    values.append(value)
            return values, malformed

        storage, storage_malformed = numeric_field("storage_used")
        files, files_malformed = numeric_field("file_count")
        has_storage = any(value is not None for value in storage)
        has_files = any(value is not None for value in files)
        total_storage = sum(storage) if has_storage and not storage_malformed and all(value is not None for value in storage) else None
        total_files = sum(files) if has_files and not files_malformed and all(value is not None for value in files) else None
        utilization_values = [_number(row, "utilization_percent") for row in usable_accounts]
        utilization = (sum(value for value in utilization_values if value is not None) / len([value for value in utilization_values if value is not None])
                       if any(value is not None for value in utilization_values) else None)
        metrics_status = "READY" if capacity else "DATA_DEPENDENCY_UNAVAILABLE"
        metrics_missing = None if capacity else "onedrive_account_capacity"
        result = {
            "active_users": active_users,
            "active_accounts": active_accounts,
            "latest_activity": latest,
            "total_storage_used": _metric(total_storage, accounts, status=metrics_status, missing=metrics_missing),
            "total_file_count": _metric(total_files, accounts, status=metrics_status, missing=metrics_missing),
            "storage_utilization": _metric(utilization, accounts,
                                            status=metrics_status,
                                            missing=metrics_missing),
            # Retain the generic legacy source-metric fields.
            "viewed_count": _metric(sum(value for value in (_number(r, "viewed_count") for r in activity) if value is not None), activity) if any(_number(r, "viewed_count") is not None for r in activity) else _metric(None, activity, status="DATA_DEPENDENCY_UNAVAILABLE", missing="viewed_count"),
            "synced_count": _metric(sum(value for value in (_number(r, "synced_count") for r in activity) if value is not None), activity) if any(_number(r, "synced_count") is not None for r in activity) else _metric(None, activity, status="DATA_DEPENDENCY_UNAVAILABLE", missing="synced_count"),
        }
        directory = {_directory_key(user): user for user in self.users if _directory_key(user)}
        account_details = []
        for account in usable_accounts:
            key = _key(account)
            user = directory.get(key)
            account_details.append({
                "display_name": user.get("display_name") if user else None,
                "user_principal_name": (user.get("user_principal_name") if user else None) or account.get("user_principal_name") or account.get("identity_value"),
                "user_ref": account.get("user_ref") or _user_ref(key, masked=bool(account.get("identity_is_masked"))),
                "storage_used": _number(account, "storage_used"),
                "storage_allocated": _number(account, "storage_allocated"),
                "utilization_percent": _number(account, "utilization_percent"),
                "usage_level": str(account.get("usage_level") or "NO_DATA").casefold(),
                "file_count": _number(account, "file_count"),
                "report_refresh_date": (_date(account.get("report_refresh_date")).isoformat()
                                      if _date(account.get("report_refresh_date")) else None),
            })
        buckets = {"low": 0, "medium": 0, "high": 0, "no_data": 0}
        for account in usable_accounts:
            level = str(account.get("usage_level") or "NO_DATA").casefold()
            buckets[level if level in buckets else "no_data"] += 1
        result["capacity_usage"] = buckets
        result["data_last_refreshed"] = _refresh(capacity)
        result["account_usage"] = _metric({
            "storage_used": total_storage,
            "file_count": total_files,
        }, accounts, status=metrics_status, missing=metrics_missing)
        result["account_details"] = account_details
        return result


    def sharepoint_user_adoption(self) -> dict[str, Any]:
        rows = self.tables["sharepoint_user_activity"]
        usable = [row for row in rows if _onedrive_non_deleted(row)]
        active_keys = {_key(row) for row in usable
                       if _key(row) and _date(row.get("last_activity_date")) is not None}
        active = _metric(len(active_keys) if rows else None, rows,
                         status="READY" if rows else "DATA_DEPENDENCY_UNAVAILABLE",
                         missing=None if rows else "sharepoint_user_activity")
        return {
            "active_users": active,
            "inactive_users": _metric(None, rows, status="DATA_DEPENDENCY_UNAVAILABLE", missing="inactive user semantics not in contract"),
            "adoption_rate": _metric(None, rows, status="DATA_DEPENDENCY_UNAVAILABLE", missing="directory denominator not in contract"),
        }

    def sharepoint_site_adoption(self) -> dict[str, Any]:
        rows = self.tables["sharepoint_site_usage"]
        usable = [row for row in rows if _onedrive_non_deleted(row)]
        active = [row for row in usable if _date(row.get("last_activity_date")) is not None]
        dates = [_date(row.get("last_activity_date")) for row in active]
        dates = [value for value in dates if value is not None]

        def numeric(name: str) -> tuple[list[int | float | None], bool]:
            values, malformed = [], False
            for row in usable:
                if row.get(name) is not None:
                    value = _number(row, name)
                    malformed |= value is None
                    values.append(value)
            return values, malformed

        storage, storage_bad = numeric("storage_used")
        files, files_bad = numeric("file_count")
        allocated, allocation_bad = numeric("storage_allocated")
        complete_allocation = bool(allocated) and not allocation_bad and all(value is not None and value > 0 for value in allocated)
        total_storage = sum(storage) if storage and not storage_bad and all(value is not None for value in storage) else None
        total_files = sum(files) if files and not files_bad and all(value is not None for value in files) else None
        total_allocated = sum(allocated) if complete_allocation else None
        utilization = total_storage / total_allocated if total_storage is not None and total_allocated else None
        status = "READY" if rows else "DATA_DEPENDENCY_UNAVAILABLE"
        missing = None if rows else "sharepoint_site_usage"
        return {
            "active_sites": _metric(len(active) if rows else None, rows, status=status, missing=missing),
            "latest_activity": _metric(max(dates).isoformat() if dates else None, rows,
                                        status=status if dates or rows else "DATA_DEPENDENCY_UNAVAILABLE",
                                        missing=missing if not rows else (None if dates else "last_activity_date")),
            "total_storage_used": _metric(total_storage, rows, status=status, missing=missing),
            "total_file_count": _metric(total_files, rows, status=status, missing=missing),
            "storage_utilization": _metric(utilization, rows, status=status, missing=missing),
        }

    def cross_workload_user_status(self) -> list[dict[str, Any]]:
        assignments = _rows(self.rows, "license_assignments")
        skus = {str(row.get("sku_id")): row for row in _rows(self.rows, "subscribed_sku") if row.get("sku_id") is not None}
        by_user: dict[Any, list[dict[str, Any]]] = {}
        for assignment in assignments:
            by_user.setdefault(assignment.get("user_id"), []).append(assignment)
        workload_names = {
            "exchange": "exchange_mailbox_usage",
            "onedrive": "onedrive_activity",
            "sharepoint": "sharepoint_user_activity",
        }
        result = []
        for user in self.users:
            key = _directory_key(user)
            user_assignments = by_user.get(user.get("user_id"), [])
            assigned_skus = []
            for assignment in user_assignments:
                sku_id = assignment.get("sku_id")
                sku = skus.get(str(sku_id))
                assigned_skus.append({"sku_id": sku_id, "sku_part_number": sku.get("sku_part_number") if sku else None})
            item: dict[str, Any] = {
                "user_ref": _user_ref(key),
                # Human-readable identity is exposed alongside the opaque
                # user_ref. Canonical joins remain keyed by user_principal_name
                # and user_id only; these fields never participate in joins.
                "display_name": user.get("display_name"),
                "user_principal_name": user.get("user_principal_name"),
                "licensed": "YES" if user_assignments else "NO",
                "assigned_sku_count": len(user_assignments),
                "assigned_skus": assigned_skus,
            }
            for output_name, table_name in workload_names.items():
                matches = []
                for row in self.tables[table_name]:
                    row_key = _key(row)
                    if key and row_key == key and row.get("tenant_id", user.get("tenant_id")) == user.get("tenant_id") and not row.get("identity_is_masked"):
                        matches.append(row)
                dated_active = [row for row in matches if _deleted(row.get("is_deleted")) is False and _date(row.get("last_activity_date"))]
                deleted = [row for row in matches if _deleted(row.get("is_deleted")) is True]
                explicit_inactive = [row for row in matches if _deleted(row.get("is_deleted")) is False and not _date(row.get("last_activity_date"))]
                if dated_active:
                    status = "ACTIVE"
                    latest = max(_date(row.get("last_activity_date")) for row in dated_active)
                elif deleted or explicit_inactive:
                    status = "INACTIVE"
                    latest = None
                else:
                    status = "UNKNOWN"
                    latest = None
                item[f"{output_name}_status"] = status
                item[f"{output_name}_last_activity"] = latest.isoformat() if latest else None
                if output_name == "exchange":
                    capacity = self.exchange_capacity()
                    capacity_row = next((detail for detail in capacity["mailboxes"] if detail["user_ref"] == item["user_ref"]), None)
                    item["exchange_report_refresh_date"] = max((_date(row.get("report_refresh_date")) for row in matches if _date(row.get("report_refresh_date"))), default=None)
                    item["exchange_storage_used"] = capacity_row["storage_used"] if capacity_row else None
                    item["exchange_mailbox_capacity"] = capacity_row["mailbox_capacity"] if capacity_row else None
                    item["exchange_utilization_percent"] = capacity_row["utilization_percent"] if capacity_row else None
                    item["exchange_usage_level"] = capacity_row["usage_level"] if capacity_row else "no_data"
            result.append(item)
        return result

    def standard_kpi_summary(self) -> dict[str, Any]:
        users = self.users
        assignments = _rows(self.rows, "license_assignments")
        licensed_user_ids = {row.get("user_id") for row in assignments}
        licensed_users = sum(row.get("user_id") in licensed_user_ids for row in users)
        tenant_metric = lambda value, source=users: _metric(value, source, status="READY" if source else "DATA_DEPENDENCY_UNAVAILABLE", missing=None if source else "core user data")

        sku_rows = _rows(self.rows, "subscribed_sku")
        attention_statuses = {"warning", "suspended", "lockedout"}
        attention_sku_ids = {
            sku_id for sku_id in {
                str(row.get("sku_id")) for row in sku_rows if row.get("sku_id") is not None
            }
            if any(
                str(row.get("sku_id")) == sku_id
                and str(row.get("capability_status") or "").strip().casefold() in attention_statuses
                for row in sku_rows
            )
        }
        license_attention = _metric(
            len(attention_sku_ids), sku_rows,
            status="READY" if sku_rows else "DATA_DEPENDENCY_UNAVAILABLE",
            missing=None if sku_rows else "core.subscribed_sku",
        )
        assignments_by_sku: dict[Any, set[Any]] = {}
        for assignment in assignments:
            assignments_by_sku.setdefault(assignment.get("sku_id"), set()).add(assignment.get("user_id"))
        licenses = {}
        for sku in sku_rows:
            sku_id = sku.get("sku_id")
            purchased = _number(sku, "prepaid_units", "purchased_units")
            consumed = _number(sku, "consumed_units")
            available = purchased - consumed if purchased is not None and consumed is not None else None
            key = str(sku.get("sku_part_number") or sku_id)
            licenses[key] = {
                "purchased_units": purchased,
                "consumed_units": consumed,
                "available_units": available,
                "utilization_percent": round(consumed / purchased * 100, 2) if purchased not in (None, 0) and consumed is not None else None,
                "assigned_user_count": len(assignments_by_sku.get(sku_id, set())),
            }

        correlation = self.cross_workload_user_status()
        counts = {workload: {status: 0 for status in ("ACTIVE", "INACTIVE", "UNKNOWN")} for workload in ("exchange", "onedrive", "sharepoint")}
        exactly = {1: 0, 2: 0, 3: 0}
        inactive_complete = 0
        unknown_evidence = 0
        for user in correlation:
            statuses = [user[workload + "_status"] for workload in counts]
            for workload, status in zip(counts, statuses):
                counts[workload][status] += 1
            active_count = statuses.count("ACTIVE")
            if active_count in exactly:
                exactly[active_count] += 1
            if all(status == "INACTIVE" for status in statuses):
                inactive_complete += 1
            if "UNKNOWN" in statuses:
                unknown_evidence += 1

        exchange = self.exchange_adoption()
        onedrive = self.onedrive_adoption()
        sharepoint_user = self.sharepoint_user_adoption()
        sharepoint = self.sharepoint_site_adoption()
        return {
            "tenant": {"total_users": tenant_metric(len(users) if users else None), "licensed_users": tenant_metric(licensed_users if users else None), "unlicensed_users": tenant_metric(len(users) - licensed_users if users else None)},
            "license_attention_count": license_attention["value"],
            "license": licenses,
            "exchange": {"active_users": _metric(counts["exchange"]["ACTIVE"], self.tables["exchange_mailbox_usage"]), "inactive_users": _metric(counts["exchange"]["INACTIVE"], self.tables["exchange_mailbox_usage"]), "unknown_users": _metric(counts["exchange"]["UNKNOWN"], self.tables["exchange_mailbox_usage"]), "latest_activity": exchange["last_activity"], "capacity_usage": exchange["capacity_usage"], "mailbox_capacity_risk": exchange["mailbox_capacity_risk"], "data_last_refreshed": exchange["data_last_refreshed"], "mailbox_details": exchange["mailbox_details"], "total_storage_used": _metric(exchange["mailbox_usage"]["value"].get("total_storage_used") if exchange["mailbox_usage"]["value"] else None, self.tables["exchange_mailbox_usage"]), "total_mailbox_item_count": _metric(exchange["mailbox_usage"]["value"].get("mailbox_item_count") if exchange["mailbox_usage"]["value"] else None, self.tables["exchange_mailbox_usage"])},
            "onedrive": {"active_users": _metric(counts["onedrive"]["ACTIVE"], self.tables["onedrive_activity"]), "inactive_users": _metric(counts["onedrive"]["INACTIVE"], self.tables["onedrive_activity"]), "unknown_users": _metric(counts["onedrive"]["UNKNOWN"], self.tables["onedrive_activity"]), **{key: onedrive[key] for key in ("latest_activity", "total_storage_used", "total_file_count", "storage_utilization")}},
            "sharepoint": {"active_users": _metric(counts["sharepoint"]["ACTIVE"], self.tables["sharepoint_user_activity"]), "inactive_users": _metric(counts["sharepoint"]["INACTIVE"], self.tables["sharepoint_user_activity"]), "unknown_users": _metric(counts["sharepoint"]["UNKNOWN"], self.tables["sharepoint_user_activity"]), **{key: sharepoint[key] for key in ("active_sites", "latest_activity", "total_storage_used", "total_file_count", "storage_utilization")}},
            "cross_workload": {"active_all_3": exactly[3], "active_exactly_2": exactly[2], "active_exactly_1": exactly[1], "inactive_all_complete_evidence": inactive_complete, "users_with_unknown_evidence": unknown_evidence},
        }

    def license_utilization(self) -> dict[str, Any]:
        assignments = _rows(self.rows, "license_assignments")
        if not assignments:
            unavailable = _metric(None, _rows(self.rows, "subscribed_sku"), status="DATA_DEPENDENCY_UNAVAILABLE", missing="per-user license assignment data")
            return {"entitled_users": unavailable, "utilized_users": unavailable, "apparently_unused_entitlement_candidates": unavailable, "utilization_percentage": unavailable}
        directory = {_directory_key(row) for row in self.users if _directory_key(row)}
        entitled = {_key(row) for row in assignments if _key(row) in directory}
        usage = {key: [] for key in entitled}
        for row in self._all_usage():
            key = _key(row)
            if key in usage:
                usage[key].append(row)
        statuses = {
            key: [_evidence_status(row, self._workload_for_row(row), self.as_of) for row in values]
            for key, values in usage.items()
        }
        utilized = {key for key, values in statuses.items() if "utilized" in values}
        review = {key for key, values in statuses.items() if "explicitly_inactive" in values and "utilized" not in values}
        insufficient = entitled - utilized - review
        return {"entitled_users": _metric(len(entitled), assignments), "utilized_users": _metric(len(utilized), assignments), "apparently_unused_entitlement_candidates": _metric(len(review), assignments), "insufficient_evidence_users": _metric(len(insufficient), assignments), "utilization_percentage": _metric(round(len(utilized) / len(entitled) * 100, 2) if entitled else None, assignments)}

    def _workload_for_row(self, row: Mapping[str, Any]) -> str:
        for name, values in self.tables.items():
            if row in values:
                return name
        return ""

    def build(self) -> dict[str, Any]:
        workload_missing = [name for name in ("office365_active_user", "exchange_email_activity", "onedrive_activity", "sharepoint_user_activity") if not self.tables[name]]
        return {
            "tenant_summary": self.tenant_summary(),
            "adoption_summary": {"exchange": self.exchange_adoption(), "onedrive": self.onedrive_adoption(), "sharepoint_user": self.sharepoint_user_adoption()},
            "inactive_user_candidates": self.inactivity_candidates(),
            "exchange_adoption": self.exchange_adoption(), "onedrive_adoption": self.onedrive_adoption(), "sharepoint_user_adoption": self.sharepoint_user_adoption(),
            "license_utilization": self.license_utilization(),
            "data_quality": {"source_freshness_exposed": True, "identity_masking_exposed": True, "missing_workload_data": workload_missing, "missing_entitlement_data": not bool(_rows(self.rows, "license_assignments")), "partial_tenant_coverage": bool(workload_missing), "identity_joins": self.identity_join_quality()},
            "limitations": {"sharepoint_site_analytics_status": "IDENTITY_UNAVAILABLE", "sharepoint_site_stale_conclusion": None, "site_rows_used_for_conclusions": False},
        }

    def identity_join_quality(self) -> dict[str, dict[str, int]]:
        """Expose aggregate join evidence without returning identities."""
        directory = {_directory_key(row) for row in self.users if _directory_key(row)}
        result = {}
        for name, rows in self.tables.items():
            if name == "onedrive_account_usage":
                continue
            workload = {_key(row) for row in rows if _key(row)}
            result[name] = {
                "matched": len(workload & directory),
                "unmatched_directory": len(directory - workload),
                "unmatched_workload": len(workload - directory),
            }
        return result
