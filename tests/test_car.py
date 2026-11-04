"""Run with:  python -m unittest discover -s tests   (no window needed)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import citymap as cm
import game_data as gd
import vehicle as vh


class CarTests(unittest.TestCase):
    def test_top_speed_climbs_to_200_kmh(self):
        speeds = [gd.car_top_speed(l) * 3.6 for l in range(gd.MAX_CAR_LEVEL + 1)]
        self.assertAlmostEqual(speeds[0], 100.0, places=1)
        self.assertAlmostEqual(speeds[-1], 200.0, places=1)
        self.assertEqual(speeds, sorted(speeds))
        self.assertAlmostEqual(gd.car_top_speed(99) * 3.6, 200.0, places=1)       # extra levels do not exceed it
        self.assertGreater(gd.car_acceleration(6), gd.car_acceleration(0))
        self.assertEqual(gd.SHOP['car']['max'], gd.MAX_CAR_LEVEL)

    def test_walls_respect_height(self):
        embankment = (0.0, 0.0, 1.0, 0.0, 20.0, 14.0, 0.0, cm.DECK_Y - 0.35)       # solid from the ground up to just under the deck
        rail = (0.0, 0.0, 1.0, 0.0, 20.0, 0.35, cm.DECK_Y - 0.4, cm.DECK_Y + 1.1)
        walls = [embankment, rail]
        self.assertTrue(vh._hits(0.0, 2.0, 0.0, [embankment], cm.ROAD_Y))          # a car on the ground hits the embankment
        self.assertFalse(vh._hits(0.0, 2.0, 0.0, [embankment], cm.DECK_Y))         # a car on the deck drives over it
        self.assertTrue(vh._hits(0.0, 0.3, 0.0, [rail], cm.DECK_Y))                # ...but is stopped by the rail
        self.assertFalse(vh._hits(0.0, 0.3, 0.0, [rail], cm.ROAD_Y))               # a car beneath drives under the rail
        self.assertTrue(vh._hits(0.0, 0.3, 0.0, walls, cm.DECK_Y))


if __name__ == '__main__':
    unittest.main()
