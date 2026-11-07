"""Run with:  python -m unittest discover -s tests   (no window needed)"""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import citymap as cm
import gps


def components(world, ok=lambda e: True):
    seen, comps = set(), []
    for n in world.nodes:
        if n.id in seen:
            continue
        stack, comp = [n], []
        seen.add(n.id)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for e in cur.edges:
                if ok(e) and e.other(cur).id not in seen:
                    seen.add(e.other(cur).id)
                    stack.append(e.other(cur))
        comps.append(comp)
    return comps


class WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = cm.World()

    def test_size_and_addresses(self):
        w = self.w
        self.assertGreater(len(w.deliverable), 1500)
        self.assertEqual(len(w.by_address), len(w.lots))              # every address is unique
        self.assertEqual(len(w.restaurants), len(cm.RESTAURANTS))
        self.assertIsNotNone(w.depot)

    def test_address_round_trip(self):
        rng = random.Random(1)
        edge_set = set(self.w.edges)
        for _ in range(800):
            lot = rng.choice(self.w.lots)
            self.assertIs(self.w.find_address(lot.address), lot)
            self.assertIn(lot.edge, edge_set)

    def test_one_connected_world(self):
        self.assertEqual(len(components(self.w)), 1)

    def test_not_a_grid(self):
        """Streets point every which way and houses are turned to face their street."""
        w = self.w
        angles = {round((math.degrees(math.atan2(e.ux, e.uz)) % 90) / 15) for e in w.edges if e.kind == 'local'}
        self.assertGreaterEqual(len(angles), 5)                        # headings spread across the compass
        turned = sum(1 for l in w.lots if min(abs(l.tx), abs(l.tz)) > .2)
        self.assertGreater(turned / len(w.lots), .4)                   # lots are rotated, not axis-aligned
        for l in w.lots[:300]:
            self.assertAlmostEqual(l.facing[0] ** 2 + l.facing[1] ** 2, 1.0, places=3)

    def test_houses_never_sit_on_roads_or_water(self):
        w = self.w
        for lot in w.lots:
            cx, cz = lot.body[0], lot.body[1]
            self.assertFalse(w.in_water(cx, cz))
            self.assertIsNone(w.surface(cx, cz, cm.ROAD_Y)[1], lot.address)

    def test_river_can_only_be_crossed_on_bridges(self):
        comps = components(self.w, lambda e: not e.bridge)
        self.assertGreaterEqual(len(comps), 2)                         # without bridges the banks are cut apart
        names = {e.bridge for e in self.w.edges if e.bridge}
        self.assertIn('Route 9 Bridge', names)
        self.assertIn('Harbor Bridge', names)
        self.assertGreaterEqual(len(names), 5)

    def test_freeways_only_connect_through_ramps(self):
        for n in self.w.nodes:
            kinds = {e.kind for e in n.edges}
            if 'freeway' in kinds:
                self.assertLessEqual(kinds, {'freeway', 'ramp'})
        ramps = [e for e in self.w.edges if e.kind == 'ramp']
        self.assertGreaterEqual(len(ramps), 6)
        for r in ramps:
            self.assertGreater(r.b.y - r.a.y, 8.0)                      # climbs from the ground up to the deck
            self.assertGreater(r.length, 200)

    def test_underpasses_exist_and_cross_beneath_freeways(self):
        under = [e for e in self.w.edges if e.under]
        self.assertGreaterEqual(len(under), 4)
        x, z, _ = under[0].pos(.5)
        ground, _ = self.w.surface(x, z, cm.ROAD_Y)
        self.assertAlmostEqual(ground, cm.ROAD_Y, places=1)

    def test_surface_picks_the_level_the_car_is_on(self):
        fw = self.w.freeway_nodes['i5'][5]
        deck, e1 = self.w.surface(fw.x, fw.z, cm.DECK_Y)
        self.assertEqual(e1.kind, 'freeway')
        self.assertAlmostEqual(deck, cm.DECK_Y, places=1)

    def test_bridge_rises_above_the_water(self):
        e = next(e for e in self.w.edges if e.bridge == 'Route 9 Bridge')
        self.assertGreater(e.height(.5), cm.ROAD_Y + 4)
        self.assertAlmostEqual(e.height(0.0), cm.ROAD_Y, places=2)
        x, z, _ = e.pos(.5)
        self.assertTrue(self.w.in_water(x, z))                         # the middle of the span really is over water

    def test_embankment_blocks_ground_cars_but_not_the_deck(self):
        solid = [w for w in self.w.walls if w[6] == 0.0 and w[5] > 10]  # wide boxes starting at the ground
        self.assertTrue(solid)
        for _, _, _, _, _, _, y0, y1 in solid:
            if y1 > 3:
                self.assertLess(y1, cm.DECK_Y)                          # always below the deck surface


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = cm.World()

    def plan(self, a, b):
        return gps.plan(self.w, (a.curb_pt[0], a.curb_pt[1], cm.ROAD_Y), b.curb_pt, (0, 1))

    def test_every_sampled_house_is_routable(self):
        rng = random.Random(3)
        for _ in range(40):
            a, b = rng.choice(self.w.deliverable), rng.choice(self.w.deliverable)
            r = self.plan(a, b)
            self.assertIsNotNone(r)
            straight = math.hypot(a.curb_pt[0] - b.curb_pt[0], a.curb_pt[1] - b.curb_pt[1])
            self.assertGreaterEqual(r.length, straight - 30)

    def test_every_restaurant_is_reachable_from_the_depot(self):
        for _, lot in self.w.restaurants:
            self.assertIsNotNone(self.plan(self.w.depot, lot))

    def test_crossing_the_river_uses_a_bridge(self):
        south = [l for l in self.w.deliverable if l.curb_pt[1] < cm.CZ0 + 2800]
        north = [l for l in self.w.deliverable if l.curb_pt[1] > cm.CZ0 + 4300]
        rng = random.Random(8)
        for _ in range(6):
            r = self.plan(rng.choice(south), rng.choice(north))
            self.assertTrue(any(k == 'bridge' for _, k, _ in r.steps), r.steps)

    def test_freeway_trips_use_ramps_and_say_so(self):
        w = self.w
        ramp = next(e for e in w.edges if e.kind == 'ramp' and e.links[1] == 'Interstate 5' and e.a.y < 1)
        far = max(w.deliverable, key=lambda l: abs(l.curb_pt[1] - ramp.a.z))
        near = min(w.deliverable, key=lambda l: math.hypot(l.curb_pt[0] - ramp.a.x, l.curb_pt[1] - ramp.a.z))
        r = self.plan(near, far)
        kinds = [k for _, k, _ in r.steps]
        self.assertIn('ramp', kinds)
        self.assertIn('merge', kinds)
        self.assertTrue(any(p[2] > cm.ROAD_Y + 8 for p in r.pts))      # the route really goes up onto the deck

    def test_route_following_and_rerouting(self):
        a, b = self.w.lots[50], self.w.lots[len(self.w.lots) - 50]
        nav = gps.Navigator(self.w)
        nav.set_target(b.curb_pt, b.address)
        nav.update(.1, a.curb_pt[0], a.curb_pt[1], cm.ROAD_Y, (0, 1))
        self.assertIsNotNone(nav.instruction())
        v = nav.version
        nav.update(2.0, a.curb_pt[0] + 500, a.curb_pt[1] + 300, cm.ROAD_Y, (0, 1))      # far off the route
        self.assertGreater(nav.version, v)

    def test_a_curving_street_is_not_a_turn(self):
        """Following one street round a bend gives no 'turn' instruction."""
        w = self.w
        a, b = w.depot, w.restaurants[0][1]
        r = self.plan(a, b)
        names = [t for _, k, t in r.steps if k in ('left', 'right')]
        for text in names:
            self.assertIn('onto', text)


if __name__ == '__main__':
    unittest.main()
