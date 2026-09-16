#!/usr/bin/env python3
"""
seed_demo_data.py
------------------
Loads realistic *synthetic* alerts and social posts into the local
database, then builds the dashboard -- with zero network calls.

Useful for:
  - previewing the dashboard immediately after cloning, before deciding
    whether to hit the live NWS/Mastodon APIs
  - offline demos, CI, or environments without internet access

Run from the project root:
    python scripts/seed_demo_data.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db, outage_simulation, sentiment, dashboard

DEMO_ALERTS = [
    {
        "id": "DEMO-ALERT-1", "event": "Tornado Warning", "severity": "Extreme",
        "certainty": "Observed", "urgency": "Immediate",
        "area_desc": "Harris, TX; Fort Bend, TX",
        "headline": "Tornado Warning for Harris and Fort Bend counties",
        "description": ("A confirmed tornado was located near downtown. Downed power lines "
                         "and significant tree damage. Life-threatening situation."),
        "sent": "2026-09-16T09:00:00-05:00", "effective": "2026-09-16T09:00:00-05:00",
        "expires": "2026-09-16T10:00:00-05:00",
        "geometry_json": json.dumps({
            "type": "Polygon",
            "coordinates": [[[-95.9, 29.4], [-95.0, 29.4], [-95.0, 30.1], [-95.9, 30.1], [-95.9, 29.4]]],
        }),
        "fetched_at": "2026-09-16T09:05:00Z",
    },
    {
        "id": "DEMO-ALERT-2", "event": "Flood Warning", "severity": "Severe",
        "certainty": "Likely", "urgency": "Expected",
        "area_desc": "Orleans, LA; East Baton Rouge, LA",
        "headline": "Flood Warning for southern Louisiana",
        "description": "Widespread damage possible from flash flooding.",
        "sent": "2026-09-16T08:00:00-05:00", "effective": "2026-09-16T08:00:00-05:00",
        "expires": "2026-09-16T14:00:00-05:00",
        "geometry_json": json.dumps({
            "type": "Polygon",
            "coordinates": [[[-91.3, 29.8], [-90.6, 29.8], [-90.6, 30.6], [-91.3, 30.6], [-91.3, 29.8]]],
        }),
        "fetched_at": "2026-09-16T08:05:00Z",
    },
    {
        "id": "DEMO-ALERT-3", "event": "Winter Weather Advisory", "severity": "Minor",
        "certainty": "Possible", "urgency": "Future",
        "area_desc": "Erie, NY", "headline": "Winter Weather Advisory for Erie county",
        "description": "Light snow expected overnight.",
        "sent": "2026-09-16T07:00:00-05:00", "effective": "2026-09-16T07:00:00-05:00",
        "expires": "2026-09-16T20:00:00-05:00",
        "geometry_json": None, "fetched_at": "2026-09-16T07:05:00Z",
    },
]

DEMO_POSTS = [
    {"id": "p1", "hashtag": "tornado", "author": "user1",
     "content": "<p>Tornado just hit downtown, power is out and it's terrifying.</p>",
     "created_at": "2026-09-16T09:10:00Z", "url": "#", "fetched_at": "2026-09-16T09:10:00Z"},
    {"id": "p2", "hashtag": "storm", "author": "user2",
     "content": "<p>Everyone on my street is safe, thankful for our neighbors helping out.</p>",
     "created_at": "2026-09-16T09:15:00Z", "url": "#", "fetched_at": "2026-09-16T09:15:00Z"},
    {"id": "p3", "hashtag": "flooding", "author": "user3",
     "content": "<p>Streets flooded near downtown, roads dangerous, please avoid the area.</p>",
     "created_at": "2026-09-16T08:20:00Z", "url": "#", "fetched_at": "2026-09-16T08:20:00Z"},
    {"id": "p4", "hashtag": "weather", "author": "user4",
     "content": "<p>Clear skies here, calm evening.</p>",
     "created_at": "2026-09-16T07:40:00Z", "url": "#", "fetched_at": "2026-09-16T07:40:00Z"},
]


def seed():
    db.init_db()
    with db.get_connection() as conn:
        for a in DEMO_ALERTS:
            db.upsert_alert(conn, a)
        for p in DEMO_POSTS:
            label, score = sentiment.score_text(p["content"])
            p["sentiment_label"], p["sentiment_score"] = label, score
            db.upsert_post(conn, p)

    with db.get_connection() as conn:
        for a in DEMO_ALERTS:
            impacted = outage_simulation.impact_for_alert(a, candidate_states=["TX", "LA", "NY"])
            for row in impacted:
                db.insert_impact(conn, {"alert_id": a["id"], **row})
            outage_row = outage_simulation.simulate_outage(a, impacted)
            outage_row["generated_at"] = a["fetched_at"]
            db.upsert_outage(conn, outage_row)

    path = dashboard.build_dashboard()
    print(f"[seed_demo_data] Demo data loaded and dashboard built: {path}")


if __name__ == "__main__":
    seed()
