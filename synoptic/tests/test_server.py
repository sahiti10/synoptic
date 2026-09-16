import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import server


class TestServerHelpers(unittest.TestCase):
    def test_parse_states_from_area_desc_multi(self):
        states = server._parse_states_from_area_desc("Travis, TX; Harris, TX; Orleans, LA")
        self.assertEqual(states, ["TX", "LA"])

    def test_parse_states_from_area_desc_empty(self):
        self.assertEqual(server._parse_states_from_area_desc(""), [])
        self.assertEqual(server._parse_states_from_area_desc(None), [])

    def test_enrich_alert_with_geometry(self):
        row = {
            "id": "A1", "event": "Flood Warning", "severity": "Severe",
            "certainty": "Likely", "urgency": "Expected",
            "headline": "h", "description": "d",
            "area_desc": "Orleans, LA",
            "sent": "2026-09-16T08:00:00Z", "effective": "2026-09-16T08:00:00Z",
            "expires": "2026-09-16T14:00:00Z",
            "geometry_json": '{"type": "Polygon", "coordinates": [[[-91.3,29.8],[-90.6,29.8],[-90.6,30.6],[-91.3,30.6],[-91.3,29.8]]]}',
        }
        enriched = server._enrich_alert(row, outage_by_id={})
        self.assertEqual(enriched["states"], ["LA"])
        self.assertEqual(enriched["state_names"], ["Louisiana"])
        self.assertIsNotNone(enriched["centroid"])
        self.assertAlmostEqual(enriched["centroid"]["lon"], -91.0, delta=0.2)

    def test_enrich_alert_without_geometry(self):
        row = {
            "id": "A2", "event": "Winter Weather Advisory", "severity": "Minor",
            "certainty": "Possible", "urgency": "Future",
            "headline": "h", "description": "d", "area_desc": "Erie, NY",
            "sent": "2026-09-16T07:00:00Z", "effective": "2026-09-16T07:00:00Z",
            "expires": "2026-09-16T20:00:00Z", "geometry_json": None,
        }
        enriched = server._enrich_alert(row, outage_by_id={})
        self.assertEqual(enriched["states"], ["NY"])
        self.assertIsNone(enriched["centroid"])


if __name__ == "__main__":
    unittest.main()
