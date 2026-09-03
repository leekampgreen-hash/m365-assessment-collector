from datetime import datetime, timezone

from collectors.core.transport import GraphHttpError, GraphTransport

REQUIRED_PERMISSION = "Policy.Read.All"
PATH = "/v1.0/identity/conditionalAccess/namedLocations?$top=100"


def collect_and_persist_entra_named_locations(*, tenant_id: int, transport: GraphTransport, connection):
    observed_at = datetime.now(timezone.utc)
    items = []
    url = PATH
    try:
        while url:
            payload = transport.get_json(url)
            items.extend(payload.get("value", []))
            url = payload.get("@odata.nextLink")
    except GraphHttpError as exc:
        if exc.status in (403, 404):
            return {"locations_fetched": 0, "observed_at": observed_at.isoformat(), "skipped": True, "skip_reason": "named locations unavailable: HTTP {}".format(exc.status)}
        raise
    with connection.cursor() as cur:
        for item in items:
            cur.execute("""INSERT INTO core.entra_named_location (location_id,tenant_id,display_name,location_type,is_trusted,ip_ranges,countries_and_regions,observed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,location_id) DO UPDATE SET display_name=EXCLUDED.display_name,location_type=EXCLUDED.location_type,is_trusted=EXCLUDED.is_trusted,ip_ranges=EXCLUDED.ip_ranges,countries_and_regions=EXCLUDED.countries_and_regions,observed_at=EXCLUDED.observed_at""", (item.get("id"), tenant_id, item.get("displayName"), item.get("@odata.type", "").split(".")[-1], item.get("isTrusted"), item.get("ipRanges"), item.get("countriesAndRegions"), observed_at))
    connection.commit()
    return {"locations_fetched": len(items), "observed_at": observed_at.isoformat()}
