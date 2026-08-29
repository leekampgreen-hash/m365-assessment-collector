"""Named adapter entry points for the seven usage report contracts."""
from .registry import normalize_report_rows


def _adapter(key, content, *, tenant_id, observed_at):
    return normalize_report_rows(key, content, tenant_id=tenant_id, observed_at=observed_at)


def office365_active_user(content, *, tenant_id, observed_at):
    return _adapter("office365_active_user", content, tenant_id=tenant_id, observed_at=observed_at)


def exchange_email_activity(content, *, tenant_id, observed_at):
    return _adapter("exchange_email_activity", content, tenant_id=tenant_id, observed_at=observed_at)


def exchange_mailbox_usage(content, *, tenant_id, observed_at):
    return _adapter("exchange_mailbox_usage", content, tenant_id=tenant_id, observed_at=observed_at)


def onedrive_activity(content, *, tenant_id, observed_at):
    return _adapter("onedrive_activity", content, tenant_id=tenant_id, observed_at=observed_at)


def onedrive_account_usage(content, *, tenant_id, observed_at):
    return _adapter("onedrive_account_usage", content, tenant_id=tenant_id, observed_at=observed_at)


def sharepoint_user_activity(content, *, tenant_id, observed_at):
    return _adapter("sharepoint_user_activity", content, tenant_id=tenant_id, observed_at=observed_at)


def sharepoint_site_usage(content, *, tenant_id, observed_at):
    return _adapter("sharepoint_site_usage", content, tenant_id=tenant_id, observed_at=observed_at)
