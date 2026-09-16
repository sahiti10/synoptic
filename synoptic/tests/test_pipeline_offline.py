"""
Exercises the full pipeline (DB -> impact analysis -> outage simulation ->
dashboard rendering) using synthetic alert/post data, so it runs completely
offline -- no NWS or Mastodon network calls. This is what a fresh clone can
run to sanity-check the install with zero setup and zero internet access.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

# Redirect DB/output paths to a temp dir BEFORE importing modules that read them.
_TMP_DIR = tempfile.mkdtemp(prefix="synoptic_test_")
config.DB_PATH = os.path.join(_TMP_DIR, "test_synoptic.db")
config.DASHBOARD_PATH = os.path.join(_TMP_DIR, "test_dashboard.html")

from src import db, outage_simulation, sentiment, dashboard  # noqa: E402


SAMPLE_ALERT = {
    "id": "TEST-ALERT-1",
    "event": "Severe Thunderstorm Warning",
    "severity": "Severe",
    "certainty": "Observed",
    "urgency": "Immediate",
    "area_desc": "Travis, TX; Harris, TX",
    "headline": "Severe Thunderstorm Warning for Travis and Harris counties",
    "description": "Downed power lines and significant tree damage are likely.",
    "sent": "2026-09-16T10:00:00-05:00",
    "effective": "2026-09-16T10:00:00-05:00",
    "expires": "2026-09-16T12:00:00-05:00",
    "geometry_json": json.dumps({
        "type": "Polygon",
        "coordinates": [[
            [-98.2, 29.0], [-96.5, 29.0], [-96.5, 30.6], [-98.2, 30.6], [-98.2, 29.0]
        ]],
    }),
    "fetched_at": "2026-09-16T10:05:00Z",
}

SAMPLE_POST = {
    "id": "TEST-POST-1",
    "hashtag": "storm",
    "author": "test_user",
    "content": "<p>Power is out and it's scary out here, stay safe everyone.</p>",
    "created_at": "2026-09-16T10:10:00Z",
    "url": "https://example.test/post/1",
    "sentiment_label": None,
    "sentiment_score": None,
    "fetched_at": "2026-09-16T10:10:00Z",
}


class TestOfflinePipeline(unittest.TestCase):
    def test_full_flow(self):
        db.init_db()

        with db.get_connection() as conn:
            db.upsert_alert(conn, SAMPLE_ALERT)

            label, score = sentiment.score_text(SAMPLE_POST["content"])
            post = dict(SAMPLE_POST)
            post["sentiment_label"] = label
            post["sentiment_score"] = score
            db.upsert_post(conn, post)

        with db.get_connection() as conn:
            impacted = outage_simulation.impact_for_alert(SAMPLE_ALERT, candidate_states=["TX"])
            self.assertTrue(len(impacted) > 0, "Expected at least one impacted city inside the test polygon")

            for row in impacted:
                db.insert_impact(conn, {"alert_id": SAMPLE_ALERT["id"], **row})

            outage_row = outage_simulation.simulate_outage(SAMPLE_ALERT, impacted)
            outage_row["generated_at"] = SAMPLE_ALERT["fetched_at"]
            db.upsert_outage(conn, outage_row)

        self.assertGreater(outage_row["risk_score"], 0)
        self.assertGreaterEqual(outage_row["simulated_customers_out"], 0)

        # Dashboard should render without error and produce a non-trivial file.
        path = dashboard.build_dashboard()
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            html_content = f.read()
        self.assertIn("Synoptic", html_content)
        self.assertIn("Severe Thunderstorm Warning", html_content)
        self.assertGreater(len(html_content), 2000)


if __name__ == "__main__":
    unittest.main()
