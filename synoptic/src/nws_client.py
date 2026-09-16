"""
nws_client.py
-------------
Client for the National Weather Service (NWS) active-alerts API.
Uses only `urllib.request` from the standard library -- no `requests`
package required.

Docs: https://www.weather.gov/documentation/services-web-api
"""

import json
import time
import urllib.error
import urllib.request

from config import (
    NWS_ALERTS_ENDPOINT,
    NWS_STATES,
    NWS_USER_AGENT,
    REQUEST_TIMEOUT_SECONDS,
    MAX_RETRIES,
)


def _get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": NWS_USER_AGENT,
            "Accept": "application/geo+json",
        },
    )
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_error = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def fetch_active_alerts(states=None):
    """
    Fetch active alerts as a list of simplified dicts, ready for db.upsert_alert.
    If `states` is falsy, pulls all active US alerts (can be large).
    """
    states = states if states is not None else NWS_STATES
    all_features = []

    if states:
        for state in states:
            url = f"{NWS_ALERTS_ENDPOINT}?area={state}"
            data = _get_json(url)
            all_features.extend(data.get("features", []))
    else:
        data = _get_json(NWS_ALERTS_ENDPOINT)
        all_features.extend(data.get("features", []))

    return [_simplify_feature(f) for f in all_features]


def _simplify_feature(feature: dict) -> dict:
    props = feature.get("properties", {})
    geometry = feature.get("geometry")
    return {
        "id": props.get("id") or feature.get("id"),
        "event": props.get("event"),
        "severity": props.get("severity") or "Unknown",
        "certainty": props.get("certainty"),
        "urgency": props.get("urgency"),
        "area_desc": props.get("areaDesc"),
        "headline": props.get("headline"),
        "description": (props.get("description") or "")[:4000],
        "sent": props.get("sent"),
        "effective": props.get("effective"),
        "expires": props.get("expires"),
        "geometry_json": json.dumps(geometry) if geometry else None,
        "fetched_at": None,  # filled in by the ETL pipeline
    }
