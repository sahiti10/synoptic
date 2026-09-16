"""
outage_simulation.py
---------------------
Two things happen here, mirroring the "population-level impact analysis"
and "outage simulations" from the project description:

1. impact_for_alert(): for a given alert (with optional GeoJSON geometry),
   determine which reference cities (src/population.py) are inside the
   alert polygon, or close to its centroid when no polygon is present,
   and sum up the population considered "affected".

2. simulate_outage(): turn severity + affected population into a simple,
   transparent risk score and a simulated count of customers without
   power. This is a heuristic simulation, not a utility-grade model --
   it exists to demonstrate the pipeline end-to-end and to give the
   dashboard something meaningful to visualize.
"""

import re

from config import SEVERITY_WEIGHTS, MAX_OUTAGE_PENETRATION
from src import spatial_utils
from src.population import cities_in_states

# Keywords in the alert description that bump the outage risk score,
# because they correlate with utility infrastructure damage.
HIGH_IMPACT_KEYWORDS = [
    "downed power lines", "power outages", "widespread damage",
    "destructive winds", "significant tree damage", "structural damage",
    "life-threatening", "catastrophic",
]

NEAR_ALERT_RADIUS_KM = 60  # used when an alert has no polygon geometry


def impact_for_alert(alert: dict, candidate_states=None):
    """
    Returns a list of dicts: {city, state, distance_km, inside_polygon,
    population_affected} for cities considered impacted by this alert.
    """
    import json as _json

    geometry = _json.loads(alert["geometry_json"]) if alert.get("geometry_json") else None
    candidates = cities_in_states(candidate_states)

    results = []
    if geometry:
        centroid_lon, centroid_lat = spatial_utils.geometry_centroid(geometry)
        for name, state, lon, lat, pop in candidates:
            inside = spatial_utils.point_in_multipolygon((lon, lat), geometry)
            dist = spatial_utils.haversine_km(lon, lat, centroid_lon, centroid_lat)
            if inside or dist <= NEAR_ALERT_RADIUS_KM:
                results.append({
                    "city": name, "state": state, "distance_km": round(dist, 1),
                    "inside_polygon": 1 if inside else 0,
                    "population_affected": pop if inside else int(pop * 0.5),
                })
    else:
        # No polygon on this alert -- fall back to matching the alert's
        # free-text area description against known state/city names.
        area_desc = (alert.get("area_desc") or "").lower()
        for name, state, lon, lat, pop in candidates:
            if name.lower() in area_desc or state.lower() in area_desc:
                results.append({
                    "city": name, "state": state, "distance_km": None,
                    "inside_polygon": 0,
                    "population_affected": int(pop * 0.3),
                })

    return results


def simulate_outage(alert: dict, impacted_rows):
    """
    Heuristic outage-risk simulation combining NWS severity with keyword
    signals from the alert description and the population footprint
    computed by impact_for_alert().
    """
    severity = alert.get("severity") or "Unknown"
    base_weight = SEVERITY_WEIGHTS.get(severity, SEVERITY_WEIGHTS["Unknown"])

    description = (alert.get("description") or "").lower()
    keyword_hits = sum(1 for kw in HIGH_IMPACT_KEYWORDS if kw in description)
    keyword_bonus = min(keyword_hits * 0.05, 0.25)

    urgency_bonus = 0.1 if (alert.get("urgency") or "").lower() == "immediate" else 0.0

    risk_score = min(base_weight + keyword_bonus + urgency_bonus, 1.0)

    total_population = sum(r["population_affected"] for r in impacted_rows) if impacted_rows else 0
    simulated_customers_out = int(total_population * risk_score * MAX_OUTAGE_PENETRATION)

    return {
        "alert_id": alert["id"],
        "event": alert.get("event"),
        "severity": severity,
        "total_population_affected": total_population,
        "risk_score": round(risk_score, 3),
        "simulated_customers_out": simulated_customers_out,
    }
