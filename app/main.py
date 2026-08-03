"""Small Microsoft Graph API explorer.

Examples:
    python main.py users
    python main.py groups --select id,displayName --output groups.json
    python main.py users/{user-id}/memberOf --no-paginate
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import msal
import requests
from dotenv import load_dotenv


load_dotenv()
GRAPH_ROOT = "https://graph.microsoft.com"
DEFAULT_OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/output"))


class GraphClient:
    def __init__(self) -> None:
        tenant_id = os.getenv("TENANT_ID")
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        if not all((tenant_id, client_id, client_secret)):
            raise RuntimeError("TENANT_ID, CLIENT_ID, and CLIENT_SECRET must be configured")

        authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.app = msal.ConfidentialClientApplication(
            client_id, authority=authority, client_credential=client_secret
        )
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _token(self) -> str:
        result = self.app.acquire_token_for_client(
            scopes=[f"{GRAPH_ROOT}/.default"]
        )
        if "access_token" not in result:
            detail = result.get("error_description", result)
            raise RuntimeError(f"Microsoft Graph authentication failed: {detail}")
        return result["access_token"]

    def get(self, path: str, params: dict[str, str], paginate: bool = True) -> Any:
        url = path if path.startswith("http") else f"{GRAPH_ROOT}/v1.0/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self._token()}"}
        pages: list[dict[str, Any]] = []

        while url:
            response = self.session.get(url, headers=headers, params=params, timeout=60)
            if not response.ok:
                try:
                    detail = response.json()
                except ValueError:
                    detail = response.text
                raise RuntimeError(f"Graph returned HTTP {response.status_code}: {detail}")
            payload = response.json()
            if not isinstance(payload, dict):
                return payload
            pages.append(payload)
            url = payload.get("@odata.nextLink") if paginate else None
            params = {}

        if len(pages) == 1 and "value" not in pages[0]:
            return pages[0]
        items = [item for page in pages for item in page.get("value", [])]
        result = dict(pages[0])
        result["value"] = items
        result.pop("@odata.nextLink", None)
        result["_pages"] = len(pages)
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test any Microsoft Graph v1.0 GET endpoint")
    parser.add_argument("endpoint", help="Path such as users, groups, or users/{id}/memberOf")
    parser.add_argument("--select", help="Comma-separated $select fields")
    parser.add_argument("--filter", dest="odata_filter", help="$filter expression")
    parser.add_argument("--search", help="$search expression")
    parser.add_argument("--top", type=int, help="$top value")
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE", help="Extra query parameter; repeatable")
    parser.add_argument("--output", help="Output filename; defaults to endpoint name in /output")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--no-paginate", action="store_true", help="Only request the first page")
    return parser.parse_args()


def write_output(data: Any, args: argparse.Namespace) -> Path:
    path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / f"{args.endpoint.strip('/').replace('/', '_')}.{args.format}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "csv":
        rows = data.get("value", []) if isinstance(data, dict) else data
        fields = sorted({key for row in rows if isinstance(row, dict) for key in row})
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    else:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    params = {"$select": args.select} if args.select else {}
    if args.odata_filter:
        params["$filter"] = args.odata_filter
    if args.search:
        params["$search"] = args.search
    if args.top:
        params["$top"] = str(args.top)
    for item in args.param:
        if "=" not in item:
            raise ValueError(f"Invalid --param {item!r}; use KEY=VALUE")
        key, value = item.split("=", 1)
        params[key] = value

    data = GraphClient().get(args.endpoint, params, paginate=not args.no_paginate)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Saved to {write_output(data, args)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, requests.RequestException) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
