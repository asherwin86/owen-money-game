"""Open-world layout for the Food Delivery job.

Towns grow organically around curving main streets with side streets branching off; houses line the streets
at the street's own angle. Curving arterials link the towns, two highways run across the land, and two elevated
freeways cut through, joined by ramps. A winding river is crossed only by bridges. Roads form a graph (nodes with
heights, straight edges). Pure logic with no graphics, in world coordinates.
"""
import heapq
import math
import random

SIZE = 6000.0
CX0, CZ0 = 6000.0, 0.0   # south-west corner of the world (far from the other scenes)
SEED = 20261107
CELL = 100.0             # spatial hash cell for road edges
PITCH = CELL

ROAD_Y = 0.30            # asphalt surface height at ground level
WALK_Y = 0.45
LAWN_Y = 0.0             # the ground houses sit on
GROUND_Y = 0.05          # open ground a car can drive on
DECK_Y = ROAD_Y + 9.0    # freeway deck height
RIVER_W = 80.0
ASPHALT_W = 11.0

DRIVE_LEFT = False       # set True for left-hand traffic

# ---- names ------------------------------------------------------------------------------
WORDS = ['Maple', 'Oak', 'Elm', 'Cedar', 'Birch', 'Pine', 'Willow', 'Aspen', 'Hazel', 'Cherry', 'Walnut', 'Poplar',
         'Spruce', 'Alder', 'Linden', 'Sycamore', 'Magnolia', 'Juniper', 'Hickory', 'Beech', 'Cypress', 'Chestnut',
         'Redwood', 'Dogwood', 'Laurel', 'Sequoia', 'Mulberry', 'Hawthorn', 'Cottonwood', 'Ironwood', 'Larch',
         'Olive', 'Palm', 'Fir', 'Holly', 'Ash', 'Bay', 'Teak', 'Rowan', 'Basswood', 'Tamarack', 'Sassafras',
         'Buckeye', 'Tupelo', 'Hemlock', 'Locust', 'Persimmon', 'Pecan', 'Boxwood', 'Cinnamon', 'Elderberry',
         'Hornbeam', 'Mahogany', 'Nutmeg', 'Oleander', 'Plum', 'Quince', 'Sumac', 'Yew', 'Church', 'Market',
         'Mill', 'Park', 'Lake', 'Hill', 'Station', 'School', 'Garden', 'Spring', 'Meadow', 'Harbor', 'Union',
         'Liberty', 'Jackson', 'Franklin', 'Lincoln', 'Kings', 'Queens', 'Victoria', 'Albert', 'Wellington',
         'Nelson', 'Cromwell', 'Windsor', 'Regent', 'Bishop', 'Abbey', 'Castle', 'Orchard', 'Forest', 'Valley',
         'Summit', 'Ridge', 'Canal', 'Dock', 'Quarry', 'Foundry', 'Albion', 'Bedford', 'Chester', 'Derby', 'Essex',
         'Fulton', 'Grafton', 'Hampton', 'Irving', 'Jefferson', 'Kensington', 'Lexington', 'Madison', 'Norfolk',
         'Oxford', 'Preston', 'Quincy', 'Raleigh', 'Stanton', 'Trenton', 'Sunset', 'Sunrise', 'Prairie', 'Aspen',
         'Brook', 'Creek', 'Fern', 'Glen', 'Heron', 'Ivy', 'Jasmine', 'Kestrel', 'Lilac', 'Marigold', 'Nettle',
         'Osprey', 'Primrose', 'Quail', 'Robin', 'Sparrow', 'Thistle', 'Violet', 'Wren', 'Yarrow', 'Zephyr',
         'Amber', 'Bluebell', 'Clover', 'Daisy', 'Ember', 'Falcon', 'Garnet', 'Harvest', 'Indigo', 'Jade',
         'Kingfisher', 'Lantern', 'Mariner', 'Northern', 'Oriole', 'Pebble', 'Quartz', 'Rustic', 'Saffron',
         'Tulip', 'Umber', 'Vine', 'Willet', 'Birchwood', 'Cranberry', 'Driftwood', 'Elmwood', 'Foxglove']
LOCAL_SUFFIX = ['St', 'Ave', 'Rd', 'Dr', 'Ln', 'Way', 'Pl', 'Ct', 'Terrace']
TOWNS = [
    dict(name='Millbrook', c=(800, 800), r=560, kind='town'),
    dict(name='Oakdale', c=(1400, 2500), r=430, kind='town'),
    dict(name='Eastgate', c=(3400, 700), r=600, kind='town'),
    dict(name='Lakeview', c=(3500, 2300), r=480, kind='town'),
    dict(name='Fairview', c=(5300, 900), r=540, kind='town'),
    dict(name='Stonebridge', c=(5300, 2500), r=470, kind='town'),
    dict(name='Pinehurst', c=(700, 4600), r=560, kind='town'),
    dict(name='Westport', c=(1500, 5500), r=440, kind='town'),
    dict(name='Central City', c=(3700, 4300), r=520, kind='downtown'),
    dict(name='Northgate', c=(5300, 4600), r=540, kind='town'),
    dict(name='Highland', c=(3600, 5600), r=420, kind='town'),
    dict(name='Brookhaven', c=(700, 3000), r=300, kind='town'),
    dict(name='Ashford', c=(1700, 1700), r=230, kind='hamlet'),
    dict(name='Kingsley', c=(4700, 3300), r=230, kind='hamlet'),
    dict(name='Cedar Falls', c=(2000, 4300), r=250, kind='hamlet'),
]

# features in coordinates relative to the south-west corner
RIVER = [(-300, 3900), (900, 3750), (2100, 3250), (3300, 3300), (4500, 3650), (5600, 3500), (6300, 3200)]
FREEWAYS = {
    'i5': ('Interstate 5', [(2240, 0), (2200, 600), (2300, 1400), (2450, 2200), (2580, 2800), (2600, 3250),
                            (2630, 3700), (2650, 4100), (2750, 4700), (2800, 5100), (2870, 5700), (2860, 6000)]),
    'i10': ('Interstate 10', [(6000, 5170), (5600, 5100), (5000, 4980), (4400, 4900), (3900, 4850), (3300, 4950),
                              (2800, 5100)]),
}
HIGHWAYS = [
    ('Route 12', [(0, 1500), (700, 1480), (1500, 1380), (2400, 1500), (3000, 1560), (3700, 1700), (4520, 1620),
                  (5400, 1560), (6000, 1650)], None),
    ('Route 9', [(4410, 0), (4440, 700), (4520, 1620), (4580, 2400), (4540, 3000), (4600, 4400), (4540, 5400),
                 (4480, 6000)], 'Route 9 Bridge'),
]
RESTAURANTS = [
    dict(name="Tony's Pizza",   target=(900, 900),   color=(214, 60, 52)),
    dict(name='Burger Barn',    target=(4000, 700),  color=(240, 150, 40)),
    dict(name='Sushi Zen',      target=(5400, 1000), color=(40, 160, 160)),
    dict(name='Taco Loco',      target=(1400, 2600), color=(80, 180, 80)),
    dict(name='Noodle House',   target=(900, 4700),  color=(235, 200, 50)),
    dict(name='Curry Corner',   target=(3800, 4200), color=(190, 110, 40)),
    dict(name='Grill & Chill',  target=(5300, 4700), color=(140, 80, 190)),
    dict(name='Sweet Treats',   target=(3500, 5700), color=(235, 120, 170)),
]
DEPOT_TARGET = (3300, 800)
DEPOT_NAME = 'Dash Eats Depot'

KINDS = {
    'local': dict(width=ASPHALT_W, speed=12.0),
    'arterial': dict(width=12.0, speed=20.0),
    'highway': dict(width=26.0, speed=33.0),
    'freeway': dict(width=28.0, speed=50.0),
    'ramp': dict(width=14.0, speed=16.0),
}
ELEVATED_KINDS = ('freeway', 'ramp')


# ---- geometry helpers ------------------------------------------------------------------
def seg_proj(px, pz, ax, az, bx, bz):
    """Distance from a point to a segment and the segment parameter of the closest point."""
    dx, dz = bx - ax, bz - az
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / l2))
    return math.hypot(px - (ax + dx * t), pz - (az + dz * t)), t


def poly_dist(px, pz, pts):
    best = 1e18
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        d, _ = seg_proj(px, pz, ax, az, bx, bz)
        if d < best:
            best = d
    return best


def seg_intersect(p, q, r, s):
    """(t, u) where segments pq and rs cross strictly inside both, or None."""
    d1x, d1z = q[0] - p[0], q[1] - p[1]
    d2x, d2z = s[0] - r[0], s[1] - r[1]
    den = d1x * d2z - d1z * d2x
    if abs(den) < 1e-9:
        return None
    t = ((r[0] - p[0]) * d2z - (r[1] - p[1]) * d2x) / den
    u = ((r[0] - p[0]) * d1z - (r[1] - p[1]) * d1x) / den
    if 0.002 < t < 0.998 and 0.002 < u < 0.998:
        return t, u
    return None


def obb_overlap(a, b):
    """Do two oriented rectangles (cx, cz, tx, tz, hl, hw) overlap? (separating axis test)"""
    for (cx, cz, tx, tz, hl, hw) in (a, b):
        for ax, az in ((tx, tz), (-tz, tx)):
            ca = a[0] * ax + a[1] * az
            cb = b[0] * ax + b[1] * az
            ra = a[4] * abs(a[2] * ax + a[3] * az) + a[5] * abs(-a[3] * ax + a[2] * az)
            rb = b[4] * abs(b[2] * ax + b[3] * az) + b[5] * abs(-b[3] * ax + b[2] * az)
            if abs(ca - cb) > ra + rb:
                return False
    return True


def _smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def resample(pts, step):
    out = [pts[0]]
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        n = max(1, int(math.ceil(math.hypot(bx - ax, bz - az) / step)))
        for k in range(1, n + 1):
            out.append((ax + (bx - ax) * k / n, az + (bz - az) * k / n))
    return out


def lane_offset(e):
    """How far right of an edge's centre line a car drives (capped so ramps and freeway lanes line up)."""
    return min(e.width / 4, 4.5)


def in_city(x, z, margin=0.0):
    return CX0 - margin <= x <= CX0 + SIZE + margin and CZ0 - margin <= z <= CZ0 + SIZE + margin


# ---- graph -----------------------------------------------------------------------------
class Node:
    __slots__ = ('id', 'x', 'z', 'y', 'edges')

    def __init__(self, nid, x, z, y):
        self.id, self.x, self.z, self.y, self.edges = nid, x, z, y, []


class Edge:
    __slots__ = ('id', 'a', 'b', 'kind', 'name', 'width', 'speed', 'ax', 'az', 'bx', 'bz', 'ya', 'yb', 'hump',
                 'length', 'ux', 'uz', 'bridge', 'under', 'links', 'elevated', 'dead', 'town')

    def __init__(self, a, b, kind, name, hump=None, bridge=None, under=False, links=None, town=None):
        self.a, self.b, self.kind, self.name = a, b, kind, name
        props = KINDS[kind]
        self.width, self.speed = props['width'], props['speed']
        self.ax, self.az, self.bx, self.bz = a.x, a.z, b.x, b.z
        self.ya, self.yb = a.y, b.y
        self.hump = hump                       # (peak y, ramp fraction) for bridges that rise from ground level
        self.bridge, self.under, self.links, self.town = bridge, under, links, town
        dx, dz = self.bx - self.ax, self.bz - self.az
        self.length = math.hypot(dx, dz)
        self.ux, self.uz = dx / self.length, dz / self.length
        self.elevated = kind in ELEVATED_KINDS or hump is not None
        self.dead = False
        self.id = -1

    def height(self, t):
        if self.hump is not None:
            peak, f = self.hump
            up = _smooth(t / f) if t < f else (_smooth((1 - t) / f) if t > 1 - f else 1.0)
            return self.ya + (peak - self.ya) * up
        return self.ya + (self.yb - self.ya) * t

    def pos(self, t):
        return (self.ax + (self.bx - self.ax) * t, self.az + (self.bz - self.az) * t, self.height(t))

    def project(self, x, z):
        return seg_proj(x, z, self.ax, self.az, self.bx, self.bz)

    def other(self, node):
        return self.b if node is self.a else self.a


class Lot:
    """A house (or shop) fronting a street. Everything is oriented to the street direction."""
    __slots__ = ('id', 'center', 'tx', 'tz', 'facing', 'w', 'depth', 'body', 'door', 'number', 'street', 'kind',
                 'road_pt', 'curb_pt', 'info', 'edge', 'town', 'rect', 'height')

    @property
    def address(self):
        return f'{self.number} {self.street}'


class FeatureIndex:
    """Fast 'what barrier is near this point' for the river, freeways and ramps."""
    CELL = 150.0

    def __init__(self):
        self.cells = {}

    def add(self, kind, ax, az, bx, bz, half):
        pad = half + 40
        c = self.CELL
        for cx in range(int((min(ax, bx) - pad) // c), int((max(ax, bx) + pad) // c) + 1):
            for cz in range(int((min(az, bz) - pad) // c), int((max(az, bz) + pad) // c) + 1):
                self.cells.setdefault((cx, cz), []).append((kind, ax, az, bx, bz, half))

    def near(self, x, z):
        return self.cells.get((int(x // self.CELL), int(z // self.CELL)), ())

    def margin(self, x, z):
        """Smallest clearance (distance minus half width) to any feature near the point."""
        best = 1e9
        for kind, ax, az, bx, bz, half in self.near(x, z):
            d, _ = seg_proj(x, z, ax, az, bx, bz)
            best = min(best, d - half)
        return best

    def hits(self, x, z, margins):
        """Set of feature kinds closer than their margin (distance < half + margins[kind])."""
        out = set()
        for kind, ax, az, bx, bz, half in self.near(x, z):
            d, _ = seg_proj(x, z, ax, az, bx, bz)
            if d < half + margins[kind]:
                out.add(kind)
        return out


NODE_MARGIN = {'water': 18.0, 'freeway': 18.0, 'ramp': 14.0}
EDGE_MARGIN = {'water': 8.0, 'freeway': 6.0, 'ramp': 4.0}


class World:
    def __init__(self, seed=SEED):
        self.rng = random.Random(seed)
        self.nodes, self.edges = [], []
        self.edge_cells, self.node_cells = {}, {}
        self.features = FeatureIndex()
        self.freeway_nodes = {}
        self.river = [(CX0 + x, CZ0 + z) for x, z in RIVER]
        self._pieces = {}
        self.walls, self.wall_cells = [], {}
        self.lots, self.by_address, self.restaurants = [], {}, []
        self.towns = []
        self.depot = None
        self.forest = []
        self.junctions = set()
        self.ramp_specs = []
        self._names = set()
        self._lot_cells = {}
        self._build_features()
        self._build_highways()
        for spec in TOWNS:
            self._build_town(spec)
        self._build_arterials()
        self._build_ramps()
        self._finalize_graph()
        self._find_junctions()
        self._build_lots()
        self._place_specials()
        self._build_forest()
        self._build_walls()

    # ---- nodes / edges ----------------------------------------------------------------
    def _node(self, x, z, y=ROAD_Y):
        n = Node(len(self.nodes), x, z, y)
        self.nodes.append(n)
        self.node_cells.setdefault((int(x // 60), int(z // 60)), []).append(n)
        return n

    def _nodes_near(self, x, z, r):
        out = []
        for gx in range(int((x - r) // 60), int((x + r) // 60) + 1):
            for gz in range(int((z - r) // 60), int((z + r) // 60) + 1):
                for n in self.node_cells.get((gx, gz), ()):
                    if n.edges or n.y != ROAD_Y or True:
                        if math.hypot(n.x - x, n.z - z) <= r:
                            out.append(n)
        return out

    def _register(self, e):
        pad = e.width / 2 + 4
        for cx in range(int((min(e.ax, e.bx) - pad - CX0) // CELL), int((max(e.ax, e.bx) + pad - CX0) // CELL) + 1):
            for cz in range(int((min(e.az, e.bz) - pad - CZ0) // CELL), int((max(e.az, e.bz) + pad - CZ0) // CELL) + 1):
                self.edge_cells.setdefault((cx, cz), []).append(e)

    def _add_edge(self, a, b, kind, name, **kw):
        if a is b:
            return None
        e = Edge(a, b, kind, name, **kw)
        e.id = len(self.edges)
        self.edges.append(e)
        a.edges.append(e)
        b.edges.append(e)
        self._register(e)
        return e

    def _kill(self, e):
        e.dead = True
        if e in e.a.edges:
            e.a.edges.remove(e)
        if e in e.b.edges:
            e.b.edges.remove(e)

    def _edges_near(self, x, z, r=0.0):
        """Live edges whose cells touch the point's neighbourhood."""
        seen, out = set(), []
        cx0, cz0 = int((x - r - CX0) // CELL), int((z - r - CZ0) // CELL)
        cx1, cz1 = int((x + r - CX0) // CELL), int((z + r - CZ0) // CELL)
        for gx in range(cx0, cx1 + 1):
            for gz in range(cz0, cz1 + 1):
                for e in self.edge_cells.get((gx, gz), ()):
                    if not e.dead and e.id not in seen:
                        seen.add(e.id)
                        out.append(e)
        return out

    def _name(self, kind='local'):
        for _ in range(500):
            n = f'{self.rng.choice(WORDS)} {self.rng.choice(LOCAL_SUFFIX)}'
            if n not in self._names:
                self._names.add(n)
                return n
        n = f'{self.rng.choice(WORDS)} {self.rng.randint(2, 99)} Rd'
        self._names.add(n)
        return n

    # ---- features: river and freeways -----------------------------------------------------
    def _build_features(self):
        for (ax, az), (bx, bz) in zip(self.river, self.river[1:]):
            self.features.add('water', ax, az, bx, bz, RIVER_W / 2)
        for fid, (name, pts) in FREEWAYS.items():
            world_pts = resample([(CX0 + x, CZ0 + z) for x, z in pts], 110.0)
            nodes = []
            for x, z in world_pts:
                key = (round(x), round(z))
                n = next((m for m in self._nodes_near(x, z, 2) if m.y == DECK_Y), None) or self._node(x, z, DECK_Y)
                nodes.append(n)
            self.freeway_nodes[fid] = nodes
            for a, b in zip(nodes, nodes[1:]):
                if a is not b:
                    self._add_edge(a, b, 'freeway', name)
                    self.features.add('freeway', a.x, a.z, b.x, b.z, KINDS['freeway']['width'] / 2)

    # ---- generic road building -------------------------------------------------------------
    def _crossings(self, a, b):
        """Which barriers lie between two nodes (sampled along the segment)."""
        out = set()
        length = math.hypot(b.x - a.x, b.z - a.z)
        n = max(2, int(length // 8))
        for s in range(1, n):
            t = s / n
            if t * length < 22 or (1 - t) * length < 22:
                continue
            out |= self.features.hits(a.x + (b.x - a.x) * t, a.z + (b.z - a.z) * t, EDGE_MARGIN)
        return out

    def _split(self, e, t):
        """Cut a plain ground edge in two at t and return the new node (or an existing one very close)."""
        x, z, _ = e.pos(t)
        near = [n for n in self._nodes_near(x, z, 7.0) if n is not e.a and n is not e.b and n.y == ROAD_Y]
        if near:
            return near[0]
        n = self._node(x, z, ROAD_Y)
        a, b = e.a, e.b
        self._kill(e)
        self._add_edge(a, n, e.kind, e.name, town=e.town)
        self._add_edge(n, b, e.kind, e.name, town=e.town)
        return n

    def _link_ground(self, a, b, kind, name, town=None):
        """Add a plain ground edge a-b, turning every crossing with an existing ground road into a junction."""
        hits = []
        for e in self._edges_near((a.x + b.x) / 2, (a.z + b.z) / 2, math.hypot(b.x - a.x, b.z - a.z) / 2 + 20):
            if e.elevated or e.under or e.a in (a, b) or e.b in (a, b):
                continue
            res = seg_intersect((a.x, a.z), (b.x, b.z), (e.ax, e.az), (e.bx, e.bz))
            if res:
                hits.append((res[0], e, res[1]))
        hits.sort(key=lambda h: h[0])
        prev = a
        for t, e, u in hits:
            if e.dead:
                continue
            x_node = self._split(e, u)
            if x_node is not prev and x_node is not b:
                self._add_edge(prev, x_node, kind, name, town=town)
                prev = x_node
        self._add_edge(prev, b, kind, name, town=town)

    def _road_node(self, p, snap=9.0):
        if isinstance(p, Node):
            return p
        near = self._nodes_near(p[0], p[1], snap)
        near = [n for n in near if n.y == ROAD_Y]
        if near:
            return min(near, key=lambda n: math.hypot(n.x - p[0], n.z - p[1]))
        return self._node(p[0], p[1], ROAD_Y)

    def add_road(self, pts, kind, name, bridge_name=None, step=90.0, town=None):
        """Lay a road along a polyline. Barriers: water needs a bridge name, freeways are passed underneath,
        ramp corridors are never crossed. Crossings with other ground roads become junctions."""
        raw = []
        for p in pts:
            raw.append(p)
        # resample only between plain coordinates; Node entries stay as they are
        pts2 = []
        for i, p in enumerate(raw):
            if i and not isinstance(p, Node) and not isinstance(raw[i - 1], Node):
                pts2.extend(resample([raw[i - 1], p], step)[1:])
            else:
                pts2.append(p)
        prev = None
        for p in pts2:
            if isinstance(p, Node):
                x, z = p.x, p.z
            else:
                x, z = p
            if not in_city(x, z, 350):
                prev = None
                continue
            if not isinstance(p, Node) and self.features.hits(x, z, NODE_MARGIN):
                continue
            n = self._road_node(p)
            if prev is not None and n is not prev:
                self._road_edge(prev, n, kind, name, bridge_name, town)
            prev = n
        return prev

    def _road_edge(self, a, b, kind, name, bridge_name, town):
        cross = self._crossings(a, b)
        if 'ramp' in cross:
            return
        hump = bridge = None
        under = False
        if 'water' in cross:
            if bridge_name is None:
                return
            length = math.hypot(b.x - a.x, b.z - a.z)
            peak = ROAD_Y + (5.0 if kind == 'highway' else 4.5)
            hump = (peak, min(0.34, 85.0 / length))
            bridge = bridge_name
        if 'freeway' in cross:
            if kind not in ('highway', 'arterial'):
                return
            under = True
        if hump is not None or under:
            self._add_edge(a, b, kind, name, hump=hump, bridge=bridge, under=under, town=town)
        else:
            self._link_ground(a, b, kind, name, town)

    # ---- highways ---------------------------------------------------------------------------
    def _build_highways(self):
        for name, pts, bridge in HIGHWAYS:
            self.add_road([(CX0 + x, CZ0 + z) for x, z in pts], 'highway', name, bridge_name=bridge, step=100.0)

    # ---- towns ----------------------------------------------------------------------------------
    def _point_ok(self, x, z, town, own_nodes=(), clearance=42.0):
        if not in_city(x, z, -20):
            return False
        cx, cz = town['center']
        if math.hypot(x - cx, z - cz) > town['r']:
            return False
        if self.features.margin(x, z) < 44:
            return False
        for e in self._edges_near(x, z, clearance):
            if e.a in own_nodes or e.b in own_nodes:
                continue
            d, _ = e.project(x, z)
            if d < clearance + (e.width - ASPHALT_W) / 2:
                return False
        return True

    def _grow_street(self, town, start, heading, length, name, step=36.0, turn=3.5, own=None, kind='local'):
        """Grow a curving street from a node; returns the nodes it created (start first)."""
        rng = self.rng
        chain = [start]
        own_nodes = set(own or ()) | {start}
        for n in start.edges:
            own_nodes.add(n.other(start))
        cur, h = start, heading
        for k in range(int(length / step)):
            h += math.radians(rng.gauss(0, turn))
            nx, nz = cur.x + math.sin(h) * step, cur.z + math.cos(h) * step
            if not self._point_ok(nx, nz, town, own_nodes):
                break
            # close a loop onto a nearby street instead of running alongside it
            if k >= 2:
                near = [n for n in self._nodes_near(nx, nz, 26.0) if n.y == ROAD_Y and n not in own_nodes and n.edges
                        and all(e.kind == 'local' for e in n.edges)]
                if near:
                    tgt = min(near, key=lambda n: math.hypot(n.x - nx, n.z - nz))
                    if math.hypot(tgt.x - cur.x, tgt.z - cur.z) > 20:
                        self._link_ground(cur, tgt, kind, name, town['name'])
                        break
            n = self._node(nx, nz, ROAD_Y)
            before = len(self.edges)
            self._link_ground(cur, n, kind, name, town['name'])
            chain.append(n)
            own_nodes.add(n)
            cur = n
        return chain

    def _build_town(self, spec):
        rng = self.rng
        cx, cz = CX0 + spec['c'][0], CZ0 + spec['c'][1]
        town = dict(name=spec['name'], center=(cx, cz), r=spec['r'], kind=spec['kind'], ends=[], nodes=[])
        self.towns.append(town)
        if self.features.margin(cx, cz) < 50:
            return
        centre = self._node(cx, cz, ROAD_Y)
        theta = rng.uniform(0, math.tau)
        spine_name = self._name()
        town_len = town['r'] * 0.95
        a = self._grow_street(town, centre, theta, town_len, spine_name, turn=2.5)
        b = self._grow_street(town, centre, theta + math.pi, town_len, spine_name, turn=2.5, own=a)
        spine = list(reversed(b[1:])) + a
        town['ends'] = [spine[0], spine[-1]]
        dense = spec['kind'] == 'downtown'
        gap_lo, gap_hi = (70, 110) if dense else (90, 150)
        streets = []
        # side streets along the spine
        s_acc = rng.uniform(40, 90)
        side = 1
        idx_len = 0.0
        for i in range(1, len(spine) - 1):
            idx_len += math.hypot(spine[i].x - spine[i - 1].x, spine[i].z - spine[i - 1].z)
            if idx_len < s_acc:
                continue
            idx_len, s_acc = 0.0, rng.uniform(gap_lo, gap_hi)
            node = spine[i]
            tang = math.atan2(spine[i + 1].x - spine[i - 1].x, spine[i + 1].z - spine[i - 1].z)
            sides = (1, -1) if rng.random() < .35 else (side,)
            side = -side
            for sd in sides:
                heading = tang + sd * (math.pi / 2 + math.radians(rng.uniform(-18, 18)))
                dist = math.hypot(node.x - cx, node.z - cz)
                length = rng.uniform(120, 360) * (1 - .35 * dist / town['r']) * (.8 if dense else 1.0)
                if length < 60:
                    continue
                chain = self._grow_street(town, node, heading, length, self._name(), turn=4.0)
                if len(chain) >= 3:
                    streets.append((chain, heading))
        # branches off the side streets
        for chain, heading in streets:
            last = 0.0
            for k in range(2, len(chain) - 1):
                last += 36
                if last < 64 or rng.random() > .62:
                    continue
                last = 0.0
                sd = rng.choice((1, -1))
                tang = math.atan2(chain[k + 1].x - chain[k - 1].x, chain[k + 1].z - chain[k - 1].z)
                sub = self._grow_street(town, chain[k], tang + sd * (math.pi / 2 + math.radians(rng.uniform(-15, 15))),
                                        rng.uniform(100, 260), self._name(), turn=4.5)
                if len(sub) >= 4 and rng.random() < .75:
                    j = rng.randint(2, len(sub) - 2)
                    t2 = math.atan2(sub[j + 1].x - sub[j - 1].x, sub[j + 1].z - sub[j - 1].z) if j + 1 < len(sub) else tang
                    self._grow_street(town, sub[j], t2 + rng.choice((1, -1)) * math.pi / 2, rng.uniform(60, 140),
                                      self._name(), turn=5.0)
        town['nodes'] = spine

    # ---- arterials linking towns ---------------------------------------------------------------
    def _curve(self, a, b, bulge, n=None):
        """Smooth curve between two points (quadratic Bezier with a sideways bulge)."""
        mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        dx, dz = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dz)
        cx, cz = mx - dz / d * bulge * d, mz + dx / d * bulge * d
        n = n or max(4, int(d / 90))
        out = []
        for i in range(n + 1):
            t = i / n
            out.append(((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * cx + t * t * b[0],
                        (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * cz + t * t * b[1]))
        return out

    def _build_arterials(self):
        rng = self.rng
        towns = [t for t in self.towns if t['ends']]
        pairs = []
        for i, a in enumerate(towns):
            for j in range(i + 1, len(towns)):
                b = towns[j]
                d = math.hypot(a['center'][0] - b['center'][0], a['center'][1] - b['center'][1])
                pairs.append((d, i, j))
        pairs.sort()
        parent = list(range(len(towns)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        chosen, extra = [], []
        for d, i, j in pairs:
            if find(i) != find(j):
                parent[find(i)] = find(j)
                chosen.append((i, j))
            elif d < 2300 and len(extra) < 10:
                extra.append((i, j))
        for i, j in chosen + extra:
            a, b = towns[i], towns[j]
            na, nb = min(((x, y) for x in a['ends'] for y in b['ends']),
                         key=lambda p: math.hypot(p[0].x - p[1].x, p[0].z - p[1].z))
            d = math.hypot(na.x - nb.x, na.z - nb.z)
            bridge = f'{rng.choice(WORDS)} Bridge'
            pts = self._curve((na.x, na.z), (nb.x, nb.z), rng.uniform(.06, .16) * rng.choice((-1, 1)))
            road_name = self._name()
            for suffix_fix in ('Rd',):
                road_name = road_name.rsplit(' ', 1)[0] + ' Rd'
            self.add_road([na] + pts[1:-1] + [nb], 'arterial', road_name, bridge_name=bridge, step=80.0)

    # ---- ramps ---------------------------------------------------------------------------------
    def _ramp_clear(self, g, f):
        """Is the low part of a ramp from ground node g to deck node f free of other ground roads?"""
        length = math.hypot(f.x - g.x, f.z - g.z)
        n = max(4, int(length // 10))
        for s in range(1, n):
            t = s / n
            h = ROAD_Y + (DECK_Y - ROAD_Y) * t
            x, z = g.x + (f.x - g.x) * t, g.z + (f.z - g.z) * t
            if h - ROAD_Y > 7.5:
                break
            for e in self._edges_near(x, z, 30):
                if e.elevated or e.a is g or e.b is g:
                    continue
                d, _ = e.project(x, z)
                if d < e.width / 2 + 9 + (0 if t > .12 else -9):
                    return False
        return True

    @staticmethod
    def _ramp_angle_ok(f, g, d):
        """Ramps must leave the freeway at a shallow angle (within about 50 degrees of its direction)."""
        rx, rz = (f.x - g.x) / d, (f.z - g.z) / d
        fe = [e for e in f.edges if e.kind == 'freeway']
        return bool(fe) and max(abs(e.ux * rx + e.uz * rz) for e in fe) > .64

    def _build_ramps(self):
        """Join the freeways to the highways and arterials near them: ramps at spaced interchanges."""
        main = [n for n in self.nodes if n.y == ROAD_Y and n.edges and not any(e.elevated for e in n.edges)
                and all(e.kind in ('highway', 'arterial') for e in n.edges)]
        cands = []
        for fid, nodes in self.freeway_nodes.items():
            for f in nodes:
                for g in main:
                    d = math.hypot(f.x - g.x, f.z - g.z)
                    if 230 < d < 620 and self._ramp_angle_ok(f, g, d):
                        cands.append((d + (0 if any(e.kind == 'highway' for e in g.edges) else 60), fid, f, g))
        cands.sort(key=lambda c: c[0])
        used_f, used_g, made = [], [], []
        per_free = {fid: 0 for fid in self.freeway_nodes}
        for d, fid, f, g in cands:
            if len(made) >= 12 or per_free[fid] >= 7:
                continue
            if any(math.hypot(f.x - o.x, f.z - o.z) < 420 for o in used_f if o is not f) or f in used_f:
                continue
            if any(math.hypot(g.x - o.x, g.z - o.z) < 300 for o in used_g):
                continue
            if self.features.hits(g.x, g.z, {'water': 40, 'freeway': 40, 'ramp': 20}) or not self._ramp_clear(g, f):
                continue
            low = g.edges[0].name
            e = self._add_edge(g, f, 'ramp', FREEWAYS[fid][0] + ' ramp', links=(low, FREEWAYS[fid][0]))
            self.features.add('ramp', g.x, g.z, f.x, f.z, KINDS['ramp']['width'] / 2)
            self.ramp_specs.append((fid, f, g))
            used_f.append(f)
            used_g.append(g)
            made.append(e)
            per_free[fid] += 1

    # ---- finishing the graph -------------------------------------------------------------------
    def _finalize_graph(self):
        live = [e for e in self.edges if not e.dead]
        self.edges = live
        seen, best = set(), []
        for n in self.nodes:
            if n.id in seen or not n.edges:
                continue
            comp, stack = [], [n]
            seen.add(n.id)
            while stack:
                cur = stack.pop()
                comp.append(cur)
                for e in cur.edges:
                    o = e.other(cur)
                    if o.id not in seen:
                        seen.add(o.id)
                        stack.append(o)
            if len(comp) > len(best):
                best = comp
        keep = {n.id for n in best}
        self.edges = [e for e in self.edges if e.a.id in keep]
        self.nodes = [n for n in self.nodes if n.id in keep]
        for k, e in enumerate(self.edges):
            e.id = k
        for k, n in enumerate(self.nodes):
            n.id = k
        edge_set = set(self.edges)
        for n in self.nodes:
            n.edges = [e for e in n.edges if e in edge_set]
        self.edge_cells = {}
        for e in self.edges:
            self._register(e)
        for e in self.edges:                                  # the freeway where it crosses the river
            if e.kind == 'freeway' and poly_dist((e.ax + e.bx) / 2, (e.az + e.bz) / 2, self.river) < RIVER_W / 2 + 14:
                e.bridge = 'Harbor Bridge'
        self.node_cells = {}
        for n in self.nodes:
            self.node_cells.setdefault((int(n.x // 60), int(n.z // 60)), []).append(n)
        self.ramp_specs = [(fid, f, g) for fid, f, g in self.ramp_specs if f in set(self.nodes) and g in set(self.nodes)]
        for t in self.towns:
            t['ends'] = [n for n in t['ends'] if n in set(self.nodes)]

    def _find_junctions(self):
        """Nodes where a ramp merges into a freeway (or two freeways meet): the deck rails open up there."""
        self.junctions = set()
        for n in self.nodes:
            kinds = [e.kind for e in n.edges]
            if ('ramp' in kinds and 'freeway' in kinds) or kinds.count('freeway') >= 3:
                self.junctions.add(n.id)

    @staticmethod
    def rail_min_rise(e):
        """Rails start once the deck is this high above the road (later on ramps, so entering one is forgiving)."""
        return 2.6 if e.kind == 'ramp' else 1.2

    def rail_ok(self, e, tm):
        """False where deck rails would block a merge (near ramp/freeway junctions)."""
        for node, d in ((e.a, tm * e.length), (e.b, (1 - tm) * e.length)):
            if node.id in self.junctions and d < (55 if e.kind == "freeway" else 38):
                return False
        return True

    # ---- lots (houses) -------------------------------------------------------------------------
    def _chains(self):
        """Group local/arterial edges by street name into ordered node chains."""
        by_name = {}
        for e in self.edges:
            if e.kind in ('local', 'arterial') and not e.elevated and not e.under:
                by_name.setdefault(e.name, []).append(e)
        out = []
        for name, edges in by_name.items():
            adj = {}
            for e in edges:
                adj.setdefault(e.a.id, []).append(e)
                adj.setdefault(e.b.id, []).append(e)
            used = set()
            starts = [nid for nid, es in adj.items() if len(es) == 1] + list(adj)
            for nid in starts:
                if all(e.id in used for e in adj[nid]):
                    continue
                cur = nid
                chain = []
                node_by_id = {}
                for e in edges:
                    node_by_id[e.a.id], node_by_id[e.b.id] = e.a, e.b
                guard = 0
                while guard < 400:
                    guard += 1
                    nxt = next((e for e in adj[cur] if e.id not in used), None)
                    if nxt is None:
                        break
                    used.add(nxt.id)
                    node = node_by_id[cur]
                    sgn = 1 if nxt.a is node else -1
                    chain.append((nxt, sgn))
                    cur = nxt.b.id if sgn == 1 else nxt.a.id
                if chain:
                    out.append((name, chain))
        return out

    def _lot_clear(self, lot_obb, corners, front_name, near_edges):
        cx, cz = lot_obb[0], lot_obb[1]
        if self.features.margin(cx, cz) < 26:
            return False
        for px, pz in corners:
            if self.features.margin(px, pz) < 14:
                return False
            for e in near_edges:
                if e.name == front_name:
                    continue
                if min(e.ax, e.bx) - 40 > px or max(e.ax, e.bx) + 40 < px or min(e.az, e.bz) - 40 > pz or max(e.az, e.bz) + 40 < pz:
                    continue
                d, _ = e.project(px, pz)
                margin = {'highway': 16, 'arterial': 7}.get(e.kind, 5)
                if d < e.width / 2 + margin:
                    return False
        for gx in range(int((cx - 30) // 60), int((cx + 30) // 60) + 1):
            for gz in range(int((cz - 30) // 60), int((cz + 30) // 60) + 1):
                for other in self._lot_cells.get((gx, gz), ()):
                    if abs(other[0] - cx) < 40 and abs(other[1] - cz) < 40 and obb_overlap(lot_obb, other):
                        return False
        return True

    def _build_lots(self):
        rng = random.Random(SEED + 3)
        town_by_name = {t['name']: t for t in self.towns}
        for name, chain in self._chains():
            # polyline of the street with cumulative distance
            pts = []
            for e, sgn in chain:
                a, b = (e.a, e.b) if sgn == 1 else (e.b, e.a)
                if not pts:
                    pts.append((a.x, a.z, e, sgn, 0.0))
                pts.append((b.x, b.z, e, sgn, pts[-1][4] + e.length))
            total = pts[-1][4]
            if total < 50:
                continue
            kind0 = chain[0][0].kind
            town = town_by_name.get(chain[0][0].town)
            if kind0 == 'arterial' and town is None:
                continue
            xs = [p[0] for p in pts]
            zs = [p[1] for p in pts]
            near_edges = self._edges_near((min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2,
                                          max(max(xs) - min(xs), max(zs) - min(zs)) / 2 + 60)
            for side in (1, -1):
                s = rng.uniform(14, 26)
                while s < total - 14:
                    w = rng.uniform(16, 24) if kind0 == 'local' else rng.uniform(22, 34)
                    sc = s + w / 2
                    if sc > total - 10:
                        break
                    # position on the polyline
                    k = 1
                    while k < len(pts) - 1 and pts[k][4] < sc:
                        k += 1
                    x0, z0, _, _, s0 = pts[k - 1]
                    x1, z1, e, sgn, s1 = pts[k]
                    t = (sc - s0) / max(s1 - s0, 1e-6)
                    px, pz = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
                    seg_len = math.hypot(x1 - x0, z1 - z0)
                    tx, tz = (x1 - x0) / seg_len, (z1 - z0) / seg_len
                    nx, nz = -tz * side, tx * side                   # towards the lot
                    ok = self._place_lot(rng, name, e, town, kind0, side, sc, px, pz, tx, tz, nx, nz, w, near_edges)
                    s += w + rng.uniform(1, 5) if ok else w * .5
        self.deliverable = [l for l in self.lots if l.kind in ('house', 'shop')]

    def _place_lot(self, rng, street, e, town, kind0, side, sc, px, pz, tx, tz, nx, nz, w, near_edges):
        half = e.width / 2
        front = half + 2.5
        lot_depth = 22.0 if kind0 == 'local' else 26.0
        setback = rng.uniform(5.5, 8.5)
        depth = 11.0 if kind0 == 'local' else 14.0
        cx, cz = px + nx * (front + lot_depth / 2), pz + nz * (front + lot_depth / 2)
        hl, hw = w / 2, lot_depth / 2
        obb = (cx, cz, tx, tz, hl, hw)
        corners = [(cx + tx * a * hl + nx * b * hw, cz + tz * a * hl + nz * b * hw) for a in (-1, 1) for b in (-1, 1)]
        if town is not None and math.hypot(cx - town['center'][0], cz - town['center'][1]) > town['r'] * 1.12:
            return False
        if not self._lot_clear(obb, corners + [(cx, cz)], street, near_edges):
            return False
        lot = Lot()
        lot.id = len(self.lots)
        lot.street, lot.edge, lot.town = street, e, town['name'] if town else None
        fx, fz = -nx, -nz
        lot.facing = (fx, fz)
        lot.tx, lot.tz = tx, tz
        lot.w, lot.depth = w, depth
        lot.rect = obb
        lot.center = (cx, cz)
        lot.door = (px + nx * (front + setback), pz + nz * (front + setback))
        lot.body = (px + nx * (front + setback + depth / 2), pz + nz * (front + setback + depth / 2), tx, tz,
                    max(6.0, w / 2 - 2.5), depth / 2)
        lot.road_pt = (px, pz)
        lot.curb_pt = (px + nx * 3.5, pz + nz * 3.5)
        lot.number = 100 + 10 * int(sc / 10) + (1 if side > 0 else 2)
        lot.info = None
        lot.height = 0.0
        if town and town['kind'] == 'downtown':
            lot.kind = 'shop'
        elif kind0 == 'arterial':
            lot.kind = 'shop'
        else:
            lot.kind = 'house'
        key = (lot.street, lot.number)
        if key in self.by_address:
            return False
        self.lots.append(lot)
        self.by_address[key] = lot
        for gx in range(int((cx - hl - hw) // 60), int((cx + hl + hw) // 60) + 1):
            for gz in range(int((cz - hl - hw) // 60), int((cz + hl + hw) // 60) + 1):
                self._lot_cells.setdefault((gx, gz), []).append(obb)
        return True

    def _place_specials(self):
        used = set()

        def nearest(target, towns=None):
            tx, tz = CX0 + target[0], CZ0 + target[1]
            best, bd = None, 1e18
            for lot in self.lots:
                if lot.kind != 'house' or lot.id in used or lot.w < 19:
                    continue
                d = math.hypot(lot.center[0] - tx, lot.center[1] - tz)
                if d < bd:
                    best, bd = lot, d
            used.add(best.id)
            return best

        for r in RESTAURANTS:
            lot = nearest(r['target'])
            lot.kind, lot.info = 'restaurant', r
            lot.body = self._venue_body(lot)
            self.restaurants.append((r, lot))
        self.depot = nearest(DEPOT_TARGET)
        self.depot.kind = 'depot'
        self.depot.body = self._venue_body(self.depot)
        self.deliverable = [l for l in self.lots if l.kind in ('house', 'shop')]

    def _venue_body(self, lot):
        px, pz = lot.road_pt
        nx, nz = -lot.facing[0], -lot.facing[1]
        half = lot.edge.width / 2
        front = half + 2.5
        setback, depth = 7.0, 14.0
        lot.door = (px + nx * (front + setback), pz + nz * (front + setback))
        lot.depth = depth
        return (px + nx * (front + setback + depth / 2), pz + nz * (front + setback + depth / 2), lot.tx, lot.tz,
                max(7.0, lot.w / 2 - 2.0), depth / 2)

    # ---- countryside trees ----------------------------------------------------------------------
    def _build_forest(self):
        rng = random.Random(SEED + 9)
        trees = []
        for _ in range(170):
            cx, cz = CX0 + rng.uniform(0, SIZE), CZ0 + rng.uniform(0, SIZE)
            if any(math.hypot(cx - t['center'][0], cz - t['center'][1]) < t['r'] * .8 for t in self.towns):
                continue
            if self.features.margin(cx, cz) < 30:
                continue
            rad = rng.uniform(50, 170)
            for _ in range(rng.randint(30, 110)):
                a, r = rng.uniform(0, math.tau), abs(rng.gauss(0, rad * .55))
                x, z = cx + math.cos(a) * r, cz + math.sin(a) * r
                if not in_city(x, z, 0) or self.features.margin(x, z) < 14:
                    continue
                if any(d < e.width / 2 + 9 for e in self._edges_near(x, z, 14) for d in (e.project(x, z)[0],)):
                    continue
                trees.append((x, z))
        self.forest = trees

    # ---- walls / pieces -----------------------------------------------------------------------
    def _add_wall(self, cx, cz, ux, uz, hl, hw, y0, y1):
        w = (cx, cz, ux, uz, hl, hw, y0, y1)
        self.walls.append(w)
        ex = abs(ux) * hl + abs(uz) * hw + 3
        ez = abs(uz) * hl + abs(ux) * hw + 3
        c = 40.0
        for gx in range(int((cx - ex) // c), int((cx + ex) // c) + 1):
            for gz in range(int((cz - ez) // c), int((cz + ez) // c) + 1):
                self.wall_cells.setdefault((gx, gz), []).append(w)

    def pieces(self, e):
        """Segments (t0, t1, viaduct) of an elevated edge, about 10 m each."""
        if e.id in self._pieces:
            return self._pieces[e.id]
        n = max(1, int(math.ceil(e.length / 10.0)))
        out = []
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            x, z, h = e.pos((t0 + t1) / 2)
            viaduct = False
            if self._over_water(x, z):
                viaduct = True
            elif h >= ROAD_Y + 6.5 and self._over_ground_road(x, z, e):
                viaduct = True
            out.append((t0, t1, viaduct))
        self._pieces[e.id] = out
        return out

    def pillars(self, e):
        """(x, z, height) of the support pillars under the viaduct pieces of an elevated edge."""
        out = []
        lx, lz = -e.uz, e.ux
        for t0, t1, viaduct in self.pieces(e):
            tm = (t0 + t1) / 2
            if not viaduct or int(tm * 100) % 3:
                continue
            x, z, h = e.pos(tm)
            if h - ROAD_Y < 1.2:
                continue
            for s in (-1, 1):
                off = s * (e.width / 2 - 3.5)
                px, pz = x + lx * off, z + lz * off
                if not self._over_ground_road(px, pz, e, margin=2.5):
                    out.append((px, pz, h - 1.3))
        return out

    def _over_water(self, x, z):
        return poly_dist(x, z, self.river) < RIVER_W / 2 + 14

    def _over_ground_road(self, x, z, skip, margin=14.0):
        for e in self.edge_cells.get(self._cell(x, z), ()):
            if e is skip or e.elevated:
                continue
            d, _ = e.project(x, z)
            if d < e.width / 2 + margin:
                return True
        return False

    def _build_walls(self):
        for lot in self.lots:
            cx, cz, tx, tz, hl, hw = lot.body
            self._add_wall(cx, cz, tx, tz, hl, hw, 0.0, 10.0)
        for e in self.edges:
            if e.elevated:
                self._structure_walls(e)
            elif e.kind == 'highway':
                self._median_walls(e)

    def _structure_walls(self, e):
        lx, lz = -e.uz, e.ux
        for t0, t1, viaduct in self.pieces(e):
            tm = (t0 + t1) / 2
            x, z, h = e.pos(tm)
            hl = e.length * (t1 - t0) / 2
            rise = h - ROAD_Y
            if rise < 1.2:
                continue
            if rise >= self.rail_min_rise(e) and self.rail_ok(e, tm):
                for s in (-1, 1):
                    off = s * (e.width / 2 - 0.35)
                    self._add_wall(x + lx * off, z + lz * off, e.ux, e.uz, hl + 0.1, 0.35, h - 0.4, h + 1.1)
            if not viaduct:
                self._add_wall(x, z, e.ux, e.uz, hl + 0.1, e.width / 2, 0.0, h - 0.35)
        for px, pz, ph in self.pillars(e):
            self._add_wall(px, pz, e.ux, e.uz, 0.9, 0.9, 0.0, ph)

    def _median_walls(self, e):
        n = max(1, int(math.ceil(e.length / 10.0)))
        for k in range(n):
            t = (k + .5) / n
            d = e.length * t
            if d < 26 and self._junction(e.a) or e.length - d < 26 and self._junction(e.b):
                continue
            x, z, _ = e.pos(t)
            self._add_wall(x, z, e.ux, e.uz, e.length / n / 2 + .1, .5, 0.0, 1.3)

    @staticmethod
    def _junction(node):
        return len(node.edges) > 2

    # ---- queries -------------------------------------------------------------------------------
    def _cell(self, x, z):
        return (int((x - CX0) // CELL), int((z - CZ0) // CELL))

    def surface(self, x, z, y_hint):
        """(height, edge) of the road under a point at the level nearest y_hint, or (None, None)."""
        best, bs = None, 3.2
        for e in self.edge_cells.get(self._cell(x, z), ()):
            d, t = e.project(x, z)
            if d <= e.width * 0.5 + 1.5:
                h = e.height(t)
                s = abs(h - y_hint)
                if s < bs:
                    bs, best = s, (h, e)
        return best if best else (None, None)

    def walls_near(self, x, z):
        return self.wall_cells.get((int(x // 40.0), int(z // 40.0)), ())

    def in_water(self, x, z):
        return poly_dist(x, z, self.river) < RIVER_W / 2

    def nearest_edge_point(self, x, z, y_hint=None, reach=2):
        """(edge, t, distance) of the closest road, preferring the level near y_hint."""
        cx, cz = self._cell(x, z)
        best, bs = None, 1e18
        for r in range(reach + 1):
            for gx in range(cx - r, cx + r + 1):
                for gz in range(cz - r, cz + r + 1):
                    if max(abs(gx - cx), abs(gz - cz)) != r:
                        continue
                    for e in self.edge_cells.get((gx, gz), ()):
                        d, t = e.project(x, z)
                        score = d + (0.8 * abs(e.height(t) - y_hint) if y_hint is not None else 0.0)
                        if score < bs:
                            bs, best = score, (e, t, d)
            if best is not None and bs < r * CELL * 0.7:
                break
        return best

    def road_label(self, x, z, y=None):
        h, e = self.surface(x, z, y if y is not None else ROAD_Y)
        if e is None:
            hit = self.nearest_edge_point(x, z, y)
            e = hit[0] if hit and hit[2] < 40 else None
        if e is None:
            return 'Off road'
        tag = {'freeway': ' (freeway)', 'highway': ' (highway)', 'ramp': ''}.get(e.kind, '')
        if e.bridge:
            return e.bridge
        return e.name + tag

    def town_at(self, x, z):
        for t in self.towns:
            if math.hypot(x - t['center'][0], z - t['center'][1]) < t['r']:
                return t['name']
        return None

    def find_address(self, text):
        """'214 Maple Ave' -> Lot or None."""
        try:
            num, name = text.strip().split(' ', 1)
            return self.by_address.get((name, int(num)))
        except ValueError:
            return None

    def random_house(self, rng, near=None, min_dist=300.0, max_dist=1400.0):
        for _ in range(300):
            lot = rng.choice(self.deliverable)
            if near is None:
                return lot
            d = math.hypot(lot.curb_pt[0] - near[0], lot.curb_pt[1] - near[1])
            if min_dist <= d <= max_dist:
                return lot
        return rng.choice(self.deliverable)


City = World
