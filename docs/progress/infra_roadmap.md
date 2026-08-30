# INFRA-P02 — Scheduled Email Report

Status: PLANNED
Priority: HIGH

## Purpose

Send daily/weekly email summary to IT admins with:

- Executive summary of findings
- Top 5 security items requiring attention
- MFA coverage percentage
- License utilization highlights
- Inactive user count

## Design

### Email trigger options

- Daily at 8:00 AM tenant timezone
- Weekly Monday morning summary
- Alert-based: when new CRITICAL finding detected

### Email content (HTML)

- Header: Microsoft 365 Operations Intelligence
- Section 1: Executive Summary (findings count by severity)
- Section 2: Top Security Findings (max 5, color coded)
- Section 3: Quick Stats (MFA %, inactive users, license util%)
- Section 4: "View Dashboard" CTA button

### Technical approach

- SMTP via Python `smtplib` or SendGrid API
- HTML email template (Jinja2)
- Recipient list in `.env`: `REPORT_EMAIL_TO`
- Scheduler triggers email job (Phase 3 — after data fresh)
- Unsubscribe link for compliance

### Dependencies

- INFRA-P01 scheduler (complete)
- All security API endpoints (complete)
- SMTP credentials or SendGrid API key

### New env vars needed

```text
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
REPORT_EMAIL_TO (comma-separated)
REPORT_SCHEDULE=daily|weekly
REPORT_ENABLED=true|false
```

## Acceptance criteria (when implemented)

- Email sent on schedule
- HTML renders correctly in Gmail, Outlook
- Contains real data from API
- Unsubscribe mechanism works
- No sensitive data (no UPNs, no raw IDs)
