"""Small strict CSV boundary for Microsoft report downloads."""
from __future__ import annotations

import csv
import io
from typing import Dict, Iterable, Mapping, Optional, Sequence


class CsvSchemaError(ValueError):
    def __init__(self, message: str, *, classification: str = "REPORT_SCHEMA_INVALID"):
        self.classification = classification
        super().__init__(message)


def parse_report_csv(content: bytes | str, required: Sequence[str], optional: Iterable[str] = ()) -> list[Dict[str, Optional[str]]]:
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CsvSchemaError("report CSV is not valid UTF-8") from exc
    elif isinstance(content, str):
        text = content
    else:
        raise TypeError("CSV content must be bytes or text")
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        headers = reader.fieldnames or []
    except csv.Error as exc:
        raise CsvSchemaError("malformed report CSV header") from exc
    normalized = {h.strip().casefold(): h for h in headers if h is not None}
    missing = [name for name in required if name.casefold() not in normalized]
    if missing:
        raise CsvSchemaError("report CSV missing required column(s): {}".format(", ".join(missing)))
    allowed = set(normalized)
    allowed.update(name.casefold() for name in optional)
    rows = []
    try:
        for row in reader:
            if None in row and row[None]:
                raise CsvSchemaError("report CSV contains extra fields")
            rows.append({key: (value if value != "" else None) for key, value in row.items() if key is not None})
    except csv.Error as exc:
        raise CsvSchemaError("malformed report CSV row") from exc
    return rows
