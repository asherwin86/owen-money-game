"""Run with:  python -m unittest discover -s tests   (no window needed)"""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import citymap as cm
import gps


class CityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = cm.City()

    def test_size_and_addresses(self):
        c = self.city
        self.assertGreater(len(c.deliverable), 5000)
        self.assertEqual(len(c.by_address), len(c.lots))            # every address is unique
        self.assertEqual(len(c.restaurants), len(cm.RESTAURANTS))
        self.assertIsNotNone(c.depot)

    def test_address_round_trip_and_geometry(self):
        rng = random.Random(1)
        for _ in range(1500):
            lot = rng.choice(self.city.lots)
            self.assertIs(self.city.find_address(lot.address), lot)
            self.assertTrue(cm.on_road(*lot.curb_pt))               # the drop-off spot is on the road
            bx0, bz0, bx1, bz1 = lot.body
            self.assertFalse(cm.on_road((bx0 + bx1) / 2, (bz0 + bz1) / 2))


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = cm.City()

    def test_routes_follow_roads_and_are_short(self):
        rng = random.Random(3)
        for _ in range(200):
            a, b = rng.choice(self.city.lots), rng.choice(self.city.lots)
            r = gps.plan(a.curb_pt, b.curb_pt, heading=(0, 1))
            self.assertIsNotNone(r)
            for p, q in zip(r.pts, r.pts[1:]):
                self.assertTrue(abs(p[0] - q[0]) < 1e-6 or abs(p[1] - q[1]) < 1e-6)   # axis aligned = on a road
            manhattan = abs(a.curb_pt[0] - b.curb_pt[0]) + abs(a.curb_pt[1] - b.curb_pt[1])
            self.assertLess(r.length, manhattan + 400)

    def test_navigator_reroutes_and_describes(self):
        a, b = self.city.lots[100], self.city.lots[3000]
        nav = gps.Navigator()
        nav.set_target(b.curb_pt, b.address)
        nav.update(.1, a.curb_pt[0], a.curb_pt[1], (0, 1))
        self.assertIsNotNone(nav.instruction())
        v = nav.version
        nav.update(2.0, a.curb_pt[0] + 90, a.curb_pt[1] + 90, (0, 1))      # far off the route
        self.assertGreater(nav.version, v)


if __name__ == '__main__':
    unittest.main()
