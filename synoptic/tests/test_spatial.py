import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spatial_utils


class TestSpatialUtils(unittest.TestCase):
    def test_haversine_known_distance(self):
        # NYC to LA is roughly 3936 km
        d = spatial_utils.haversine_km(-74.0060, 40.7128, -118.2437, 34.0522)
        self.assertTrue(3800 < d < 4100, f"Unexpected distance: {d}")

    def test_haversine_zero_for_same_point(self):
        d = spatial_utils.haversine_km(-97.0, 30.0, -97.0, 30.0)
        self.assertAlmostEqual(d, 0.0, places=6)

    def test_point_in_polygon_inside(self):
        square = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        self.assertTrue(spatial_utils.point_in_polygon((0, 0), square))

    def test_point_in_polygon_outside(self):
        square = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        self.assertFalse(spatial_utils.point_in_polygon((5, 5), square))

    def test_point_in_multipolygon_polygon_type(self):
        geometry = {"type": "Polygon", "coordinates": [[(-1, -1), (1, -1), (1, 1), (-1, 1)]]}
        self.assertTrue(spatial_utils.point_in_multipolygon((0, 0), geometry))
        self.assertFalse(spatial_utils.point_in_multipolygon((10, 10), geometry))

    def test_point_in_multipolygon_multipolygon_type(self):
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [[(-1, -1), (1, -1), (1, 1), (-1, 1)]],
                [[(9, 9), (11, 9), (11, 11), (9, 11)]],
            ],
        }
        self.assertTrue(spatial_utils.point_in_multipolygon((10, 10), geometry))
        self.assertFalse(spatial_utils.point_in_multipolygon((50, 50), geometry))

    def test_geometry_centroid_polygon(self):
        geometry = {"type": "Polygon", "coordinates": [[(0, 0), (2, 0), (2, 2), (0, 2)]]}
        cx, cy = spatial_utils.geometry_centroid(geometry)
        self.assertAlmostEqual(cx, 1.0)
        self.assertAlmostEqual(cy, 1.0)

    def test_bbox_of_polygon(self):
        ring = [(-3, 1), (5, -2), (2, 8)]
        bbox = spatial_utils.bbox_of_polygon(ring)
        self.assertEqual(bbox, (-3, -2, 5, 8))


if __name__ == "__main__":
    unittest.main()
