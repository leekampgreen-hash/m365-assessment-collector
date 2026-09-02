"""SharePoint sites collector - fetch site URLs from Graph API."""
from __future__ import annotations

import logging
from typing import Any

from collectors.core.transport import GraphTransport
from collectors.persistence import open_database_connection

logger = logging.getLogger(__name__)


def collect_sharepoint_site_urls(*, tenant_id: int, auth_config: Any, dry_run: bool = False, transport: GraphTransport | None = None) -> dict:
    """Fetch all SharePoint sites and update matching usage records."""
    if dry_run:
        return {"mode": "dry-run", "sites_fetched": 0}

    if transport is None:
        raise ValueError("transport is required")

    sites = []
    url = "/v1.0/sites?$select=id,displayName,webUrl,createdDateTime,lastModifiedDateTime&$top=100"
    while url:
        response = transport.get_json(url)
        sites.extend(response.get("value", []))
        url = response.get("@odata.nextLink")

    logger.info("Fetched %d SharePoint sites", len(sites))
    if sites:
        for s in sites[:3]:
            logger.info("Graph site sample: id=%s, displayName=%s, webUrl=%s", s.get("id"), s.get("displayName"), s.get("webUrl"))

    conn = open_database_connection()
    updated = 0
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT entity_key, display_name FROM core.usage_sharepoint_site_usage
                WHERE tenant_id = %s LIMIT 3
            """, (tenant_id,))
            sample_keys = cur.fetchall()
            for r in sample_keys:
                logger.info("DB sample: entity_key=%s, display_name=%s", r[0], r[1])

            for site in sites:
                raw_id = site.get("id", "")
                parts = raw_id.split(",")
                if len(parts) == 3:
                    site_id = parts[1]
                elif len(parts) == 1:
                    site_id = parts[0]
                else:
                    site_id = parts[-1]

                web_url = site.get("webUrl")
                display_name = site.get("displayName")
                if not web_url:
                    continue

                if site_id:
                    cur.execute("""
                        UPDATE core.usage_sharepoint_site_usage
                        SET site_url = %s
                        WHERE tenant_id = %s AND entity_key = %s
                    """, (web_url, tenant_id, site_id))
                    updated += cur.rowcount

                if cur.rowcount == 0 and display_name:
                    cur.execute("""
                        UPDATE core.usage_sharepoint_site_usage
                        SET site_url = %s
                        WHERE tenant_id = %s AND display_name = %s AND site_url IS NULL
                    """, (web_url, tenant_id, display_name))
                    updated += cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("SharePoint sites collector failed")
        raise
    finally:
        conn.close()
    logger.info("Updated %d site_url records", updated)
    return {"sites_fetched": len(sites), "records_updated": updated}
