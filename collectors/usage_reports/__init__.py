"""Microsoft 365 usage report acquisition and normalization."""

from .csv import CsvSchemaError, parse_report_csv
from .registry import APPROVED_PERIODS, REPORTS, ReportSpec, build_report_path, get_adapter, get_report, normalize_report_rows
from .transport import (
    UsageReportHttpError,
    UsageReportNetworkError,
    UsageReportResponse,
    UsageReportTransport,
    build_usage_report_http_open,
)

__all__ = [
    "APPROVED_PERIODS", "CsvSchemaError", "REPORTS", "ReportSpec", "UsageReportHttpError",
    "UsageReportNetworkError", "UsageReportResponse", "UsageReportTransport",
    "build_report_path", "build_usage_report_http_open", "get_adapter", "get_report", "normalize_report_rows", "parse_report_csv",
]
