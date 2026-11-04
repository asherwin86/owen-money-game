"""Open-world layout for the Food Delivery job.

A local street grid is cut by a winding river, two elevated freeways, two highways and some arterials.
Roads form a graph (nodes with heights, straight edges). You can only cross the river on bridges, and only
cross a freeway through an underpass or by taking ramps. Pure logic with no graphics, in world coordinates.
"""
import heapq
import math
import random

NB = 60                  # grid blocks per side
PITCH = 100.0            # grid line spacing
ROAD_W = 16.0            # local road including sidewalks (block inset)
ASPHALT_W = 12.0
LOT_DEPTH = 20.0
SETBACK = 6.0
CX0, CZ0 = 6000.0, 0.0   # south-west corner of the world (far from the other scenes)
SIZE = NB * PITCH
SEED = 20261105

ROAD_Y = 0.30            # asphalt surface height at ground level
WALK_Y = 0.45
LAWN_Y = 0.55
GROUND_Y = 0.45          # open ground a car can drive on
DECK_Y = ROAD_Y + 9.0    # freeway deck height
RIVER_W = 80.0

AVENUES = ['Maple', 'Oak', 'Elm', 'Cedar', 'Birch', 'Pine', 'Willow', 'Aspen', 'Hazel', 'Cherry', 'Walnut',
           'Poplar', 'Spruce', 'Alder', 'Linden', 'Sycamore', 'Magnolia', 'Juniper', 'Hickory', 'Beech',
           'Cypress', 'Chestnut', 'Redwood', 'Dogwood', 'Laurel', 'Sequoia', 'Mulberry', 'Hawthorn',
           'Cottonwood', 'Ironwood', 'Larch', 'Olive', 'Palm', 'Fir', 'Holly', 'Ash', 'Bay', 'Teak', 'Rowan',
           'Basswood', 'Tamarack', 'Sassafras', 'Buckeye', 'Tupelo', 'Hemlock', 'Locust', 'Persimmon', 'Pecan',
           'Boxwood', 'Cinnamon', 'Elderberry', 'Fig', 'Gum', 'Hornbeam', 'Mahogany', 'Nutmeg', 'Oleander',
           'Plum', 'Quince', 'Sumac', 'Yew']
STREETS = ['Main', 'Church', 'Market', 'Mill', 'Bridge', 'Park', 'Lake', 'River', 'Hill', 'Station', 'School',
           'Garden', 'Spring', 'Meadow', 'Harbor', 'Union', 'Liberty', 'Jackson', 'Franklin', 'Lincoln', 'Kings',
           'Queens', 'Victoria', 'Albert', 'Wellington', 'Nelson', 'Cromwell', 'Windsor', 'Regent', 'Bishop',
           'Abbey', 'Castle', 'Orchard', 'Forest', 'Valley', 'Summit', 'Ridge', 'Canal', 'Dock', 'Quarry',
           'Foundry', 'Albion', 'Bedford', 'Chester', 'Derby', 'Essex', 'Fulton', 'Grafton', 'Hampton', 'Irving',
           'Jefferson', 'Kensington', 'Lexington', 'Madison', 'Norfolk', 'Oxford', 'Preston', 'Quincy',
           'Raleigh', 'Stanton', 'Trenton']
assert len(AVENUES) > NB and len(STREETS) > NB

HIGHWAY_STREETS = {15: 'Route 12'}
HIGHWAY_AVES = {45: 'Route 9'}
ARTERIAL_STREETS = {7: 'Southern Blvd', 25: 'Central Blvd', 45: 'Northern Blvd', 55: 'Ridge Blvd'}
ARTERIAL_AVES = {20: 'Grand Blvd', 33: 'Capitol Blvd', 56: 'Eastern Blvd'}
BRIDGE_AVES = {10: 'Old Mill Bridge', 33: 'Capitol Bridge', 45: 'Route 9 Bridge', 56: 'Eastern Bridge'}
UNDERPASS_EVERY = 4      # every Nth local line passes under a freeway
DRIVE_LEFT = False       # set True for left-hand traffic

# features in coordinates relative to the south-west corner
RIVER = [(-300, 3900), (900, 3750), (2100, 3250), (3300, 3300), (4500, 3650), (5600, 3500), (6300, 3200)]
FREEWAYS = {
    'i5': ('Interstate 5', [(2250, -300), (2250, 1000), (2450, 2200), (2600, 3250), (2650, 4100), (2800, 5100),
                            (2850, 6300)]),
    'i10': ('Interstate 10', [(6300, 5200), (5000, 5000), (3900, 4850), (2800, 5100)]),
}
# (grid column, grid row, freeway, target point on the freeway)  ->  ramp between the road and the deck
INTERCHANGES = [
    (26, 15, 'i5', (2400, 1850)), (21, 15, 'i5', (2300, 1150)),     # Route 12 and Interstate 5
    (29, 45, 'i5', (2700, 4800)), (24, 45, 'i5', (2680, 4200)),     # Northern Blvd and Interstate 5
    (45, 46, 'i10', (4400, 4930)), (45, 52, 'i10', (4300, 4900)),   # Route 9 and Interstate 10
]

RESTAURANTS = [
    dict(name="Tony's Pizza",   target=(900, 900),   color=(214, 60, 52)),
    dict(name='Burger Barn',    target=(4100, 700),  color=(240, 150, 40)),
    dict(name='Sushi Zen',      target=(5300, 1300), color=(40, 160, 160)),
    dict(name='Taco Loco',      target=(1500, 2700), color=(80, 180, 80)),
    dict(name='Noodle House',   target=(1200, 4500), color=(235, 200, 50)),
    dict(name='Curry Corner',   target=(3700, 4200), color=(190, 110, 40)),
    dict(name='Grill & Chill',  target=(5200, 4400), color=(140, 80, 190)),
    dict(name='Sweet Treats',   target=(3200, 5600), color=(235, 120, 170)),
]
DEPOT_TARGET = (3300, 800)
DEPOT_NAME = 'Dash Eats Depot'
DOWNTOWN = (3000, 4300)
DOWNTOWN_R = 330.0

KINDS = {
    'local': dict(width=ASPHALT_W, speed=12.0),
    'arterial': dict(width=ASPHALT_W, speed=20.0),
    'highway': dict(width=26.0, speed=33.0),
    'freeway': dict(width=28.0, speed=50.0),
    'ramp': dict(width=12.0, speed=16.0),
}
ELEVATED_KINDS = ('freeway', 'ramp')


def avenue_name(i):
    return AVENUES[i] + ' Ave'


def street_name(j):
    return STREETS[j] + ' St'


def avenue_x(i):
    return CX0 + i * PITCH


def street_z(j):
    return CZ0 + j * PITCH


# ---- geometry helpers -------------------------------------------------------
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


def in_city(x, z, margin=0.0):
    return CX0 - margin <= x <= CX0 + SIZE + margin and CZ0 - margin <= z <= CZ0 + SIZE + margin


# ---- graph ------------------------------------------------------------------------
class Node:
    __slots__ = ('id', 'x', 'z', 'y', 'edges', 'grid')

    def __init__(self, nid, x, z, y, grid=None):
        self.id, self.x, self.z, self.y, self.edges, self.grid = nid, x, z, y, [], grid


class Edge:
    __slots__ = ('id', 'a', 'b', 'kind', 'name', 'width', 'speed', 'ax', 'az', 'bx', 'bz', 'ya', 'yb', 'hump',
                 'length', 'ux', 'uz', 'bridge', 'under', 'links', 'elevated', 'line')

    def __init__(self, a, b, kind, name, hump=None, bridge=None, under=False, links=None, line=None):
        self.a, self.b, self.kind, self.name = a, b, kind, name
        props = KINDS[kind]
        self.width, self.speed = props['width'], props['speed']
        self.ax, self.az, self.bx, self.bz = a.x, a.z, b.x, b.z
        self.ya, self.yb = a.y, b.y
        self.hump = hump                       # (peak y, ramp fraction) for bridges that rise from ground level
        self.bridge, self.under, self.links, self.line = bridge, under, links, line
        dx, dz = self.bx - self.ax, self.bz - self.az
        self.length = math.hypot(dx, dz)
        self.ux, self.uz = dx / self.length, dz / self.length
        self.elevated = kind in ELEVATED_KINDS or hump is not None
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
    __slots__ = ('id', 'block', 'side', 'k', 'rect', 'body', 'door', 'facing', 'road_kind', 'road_index',
                 'number', 'kind', 'road_pt', 'curb_pt', 'info', 'edge')

    @property
    def address(self):
        name = avenue_name(self.road_index) if self.road_kind == 'ave' else street_name(self.road_index)
        return f'{self.number} {name}'

    @property
    def center(self):
        return ((self.rect[0] + self.rect[2]) / 2, (self.rect[1] + self.rect[3]) / 2)


def block_bounds(bi, bj):
    """Buildable rectangle of a block (inside the sidewalks)."""
    h = ROAD_W / 2
    return (CX0 + bi * PITCH + h, CZ0 + bj * PITCH + h, CX0 + (bi + 1) * PITCH - h, CZ0 + (bj + 1) * PITCH - h)


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
        self.grid = {}
        self.hedge, self.vedge = {}, {}          # adjacent grid edges: (i, j)->edge to (i+1, j) / (i, j+1)
        self.features = FeatureIndex()
        self.freeway_nodes = {}
        self._special = {}
        self.river = [(CX0 + x, CZ0 + z) for x, z in RIVER]
        self._pieces = {}
        self.walls, self.wall_cells, self.edge_cells = [], {}, {}
        self.lots, self.by_address, self.restaurants = [], {}, []
        self.block_lots = {}
        self.depot = None
        self.block_kind = {}
        self.buildable = set()
        self._build_features()
        self._build_grid()
        self._keep_main_component()
        self._index_edges()
        self._find_junctions()
        self._build_lots()
        self._build_walls()

    # ---- nodes / edges --------------------------------------------------------
    def _node(self, x, z, y, grid=None):
        n = Node(len(self.nodes), x, z, y, grid)
        self.nodes.append(n)
        return n

    def _special_node(self, x, z, y):
        key = (round(x), round(z))
        if key not in self._special:
            self._special[key] = self._node(x, z, y)
        return self._special[key]

    def _add_edge(self, a, b, kind, name, **kw):
        e = Edge(a, b, kind, name, **kw)
        e.id = len(self.edges)
        self.edges.append(e)
        a.edges.append(e)
        b.edges.append(e)
        return e

    # ---- features ---------------------------------------------------------------
    def _build_features(self):
        for (ax, az), (bx, bz) in zip(self.river, self.river[1:]):
            self.features.add('water', ax, az, bx, bz, RIVER_W / 2)
        for fid, (name, pts) in FREEWAYS.items():
            world_pts = resample([(CX0 + x, CZ0 + z) for x, z in pts], 110.0)
            nodes = [self._special_node(x, z, DECK_Y) for x, z in world_pts]
            self.freeway_nodes[fid] = nodes
            for a, b in zip(nodes, nodes[1:]):
                if a is not b:
                    self._add_edge(a, b, 'freeway', name)
                    self.features.add('freeway', a.x, a.z, b.x, b.z, KINDS['freeway']['width'] / 2)
        self.ramp_specs = []
        for gi, gj, fid, (tx, tz) in INTERCHANGES:
            gx, gz = avenue_x(gi), street_z(gj)
            target = (CX0 + tx, CZ0 + tz)
            fn = min(self.freeway_nodes[fid], key=lambda n: math.hypot(n.x - target[0], n.z - target[1]))
            self.ramp_specs.append((gi, gj, fid, fn))
            self.features.add('ramp', gx, gz, fn.x, fn.z, KINDS['ramp']['width'] / 2)

    def _line_info(self, axis, idx):
        """kind, name, through-road, bridge name for a grid line."""
        if axis == 'ew':
            if idx in HIGHWAY_STREETS:
                return 'highway', HIGHWAY_STREETS[idx], True, None
            if idx in ARTERIAL_STREETS:
                return 'arterial', ARTERIAL_STREETS[idx], False, None
            return 'local', street_name(idx), False, None
        if idx in HIGHWAY_AVES:
            return 'highway', HIGHWAY_AVES[idx], True, BRIDGE_AVES.get(idx)
        if idx in ARTERIAL_AVES:
            return 'arterial', ARTERIAL_AVES[idx], False, BRIDGE_AVES.get(idx)
        return 'local', avenue_name(idx), False, BRIDGE_AVES.get(idx)

    def _on_highway(self, i, j):
        return j in HIGHWAY_STREETS or i in HIGHWAY_AVES

    def _build_grid(self):
        forced = {(gi, gj) for gi, gj, _, _ in self.ramp_specs}
        for i in range(NB + 1):
            for j in range(NB + 1):
                x, z = avenue_x(i), street_z(j)
                if (i, j) in forced or not self.features.hits(x, z, NODE_MARGIN):
                    self.grid[(i, j)] = self._node(x, z, ROAD_Y, (i, j))
        for axis in ('ew', 'ns'):
            for idx in range(NB + 1):
                kind, name, through, bridge_name = self._line_info(axis, idx)
                prev, prev_k = None, None
                for k in range(NB + 1):
                    key = (k, idx) if axis == 'ew' else (idx, k)
                    n = self.grid.get(key)
                    if n is None:
                        continue
                    if prev is not None:
                        self._try_edge(prev, n, k - prev_k, axis, idx, kind, name, through, bridge_name)
                    prev, prev_k = n, k
        for gi, gj, fid, fn in self.ramp_specs:
            g = self.grid[(gi, gj)]
            low = self._line_info('ew', gj)[1] if gj in HIGHWAY_STREETS or gj in ARTERIAL_STREETS else None
            if low is None:
                low = self._line_info('ns', gi)[1]
            self._add_edge(g, fn, 'ramp', FREEWAYS[fid][0] + ' ramp', links=(low, FREEWAYS[fid][0]))

    def _crossings(self, a, b):
        """Which barriers lie between two nodes (sampled along the segment)."""
        out = set()
        length = math.hypot(b.x - a.x, b.z - a.z)
        n = max(2, int(length // 8))
        for s in range(1, n):
            t = s / n
            if t * length < 22 or (1 - t) * length < 22:
                continue                       # ignore the nodes' own surroundings (ramps start at a node)
            out |= self.features.hits(a.x + (b.x - a.x) * t, a.z + (b.z - a.z) * t, EDGE_MARGIN)
        return out

    def _try_edge(self, a, b, gap, axis, idx, kind, name, through, bridge_name):
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
        elif gap > 1 and not cross:
            return
        if 'freeway' in cross:
            if not (through or kind == 'arterial' or idx % UNDERPASS_EVERY == 0):
                return
            under = True
        if gap > 1 and not cross:
            return
        if not through and (self._on_highway(*a.grid) or self._on_highway(*b.grid)):
            if not (kind == 'arterial' or idx % UNDERPASS_EVERY == 0):
                return                         # side streets meet highways only at every Nth crossing
        e = self._add_edge(a, b, kind, name, hump=hump, bridge=bridge, under=under, line=(axis, idx))
        if gap == 1 and not cross:
            (self.hedge if axis == 'ew' else self.vedge)[a.grid] = e

    def _keep_main_component(self):
        seen, best = set(), []
        for n in self.nodes:
            if n.id in seen:
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
        edge_set = set(self.edges)
        node_set = set(self.nodes)
        for k, e in enumerate(self.edges):
            e.id = k
        for k, n in enumerate(self.nodes):
            n.id = k
        self.hedge = {k: e for k, e in self.hedge.items() if e in edge_set}
        self.vedge = {k: e for k, e in self.vedge.items() if e in edge_set}
        self.grid = {k: n for k, n in self.grid.items() if n in node_set}
        for n in self.nodes:
            n.edges = [e for e in n.edges if e in edge_set]
        for e in self.edges:                                  # the freeway where it crosses the river
            if e.kind == 'freeway' and poly_dist((e.ax + e.bx) / 2, (e.az + e.bz) / 2, self.river) < RIVER_W / 2 + 14:
                e.bridge = 'Harbor Bridge'

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
            if node.id in self.junctions and d < (55 if e.kind == 'freeway' else 26):
                return False
        return True

    def _index_edges(self):
        cell = PITCH
        self.edge_cells = {}
        for e in self.edges:
            pad = e.width / 2 + 4
            for cx in range(int((min(e.ax, e.bx) - pad - CX0) // cell), int((max(e.ax, e.bx) + pad - CX0) // cell) + 1):
                for cz in range(int((min(e.az, e.bz) - pad - CZ0) // cell), int((max(e.az, e.bz) + pad - CZ0) // cell) + 1):
                    self.edge_cells.setdefault((cx, cz), []).append(e)

    # ---- lots ---------------------------------------------------------------------
    def _block_ok(self, bi, bj):
        edges = (self.hedge.get((bi, bj)), self.hedge.get((bi, bj + 1)), self.vedge.get((bi, bj)),
                 self.vedge.get((bi + 1, bj)))
        if any(e is None or e.kind not in ('local', 'arterial') or e.under or e.bridge for e in edges):
            return False
        x0, z0, x1, z1 = block_bounds(bi, bj)
        return self.features.margin((x0 + x1) / 2, (z0 + z1) / 2) > 62

    def _build_lots(self):
        rng = random.Random(SEED + 1)
        for bi in range(NB):
            for bj in range(NB):
                if not self._block_ok(bi, bj):
                    continue
                x0, z0, x1, z1 = block_bounds(bi, bj)
                cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
                if math.hypot(cx - (CX0 + DOWNTOWN[0]), cz - (CZ0 + DOWNTOWN[1])) < DOWNTOWN_R:
                    kind = 'downtown'
                elif rng.random() < .05:
                    kind = 'park'
                else:
                    kind = 'houses'
                self.block_kind[(bi, bj)] = kind
                self.buildable.add((bi, bj))
                if kind != 'park':
                    self._make_lots(bi, bj, kind)
        self._place_specials()

    def _make_lots(self, bi, bj, bkind):
        x0, z0, x1, z1 = block_bounds(bi, bj)
        d = LOT_DEPTH
        w4 = (x1 - x0) / 4
        for k in range(4):
            self._lot(bi, bj, 'S', k, (x0 + k * w4, z0, x0 + (k + 1) * w4, z0 + d), bkind)
            self._lot(bi, bj, 'N', k, (x0 + k * w4, z1 - d, x0 + (k + 1) * w4, z1), bkind)
        h2 = ((z1 - d) - (z0 + d)) / 2
        for k in range(2):
            self._lot(bi, bj, 'W', k, (x0, z0 + d + k * h2, x0 + d, z0 + d + (k + 1) * h2), bkind)
            self._lot(bi, bj, 'E', k, (x1 - d, z0 + d + k * h2, x1, z0 + d + (k + 1) * h2), bkind)

    def _lot(self, bi, bj, side, k, rect, bkind):
        lot = Lot()
        lot.id = len(self.lots)
        lot.block, lot.side, lot.k, lot.rect, lot.info = (bi, bj), side, k, rect, None
        x0, z0, x1, z1 = rect
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        fx, fz = {'S': (0, -1), 'N': (0, 1), 'W': (-1, 0), 'E': (1, 0)}[side]
        lot.facing = (fx, fz)
        if side in 'SN':
            lot.road_kind, lot.road_index = 'st', bj if side == 'S' else bj + 1
            lot.number = 100 * bi + 10 + 20 * k + (1 if side == 'S' else 2)
            lot.road_pt = (cx, street_z(lot.road_index))
            lot.edge = self.hedge[(bi, lot.road_index)]
        else:
            lot.road_kind, lot.road_index = 'ave', bi if side == 'W' else bi + 1
            lot.number = 100 * bj + 30 + 20 * k + (1 if side == 'W' else 2)
            lot.road_pt = (avenue_x(lot.road_index), cz)
            lot.edge = self.vedge[(lot.road_index, bj)]
        lot.curb_pt = (lot.road_pt[0] - fx * 3.5, lot.road_pt[1] - fz * 3.5)
        lot.kind = 'shop' if (bkind == 'downtown' or lot.edge.kind == 'arterial') else 'house'
        setback = 2.0 if lot.kind == 'shop' else SETBACK
        depth = 11.0 if lot.kind == 'house' else LOT_DEPTH - 4
        inset = 2.0 if lot.kind == 'shop' else 2.5
        self._set_body(lot, side, x0, z0, x1, z1, cx, cz, setback, depth, inset)
        self.lots.append(lot)
        self.block_lots.setdefault((bi, bj), []).append(lot)
        self.by_address[(lot.road_kind, lot.road_index, lot.number)] = lot

    @staticmethod
    def _set_body(lot, side, x0, z0, x1, z1, cx, cz, setback, depth, inset):
        if side in 'SN':
            bx0, bx1 = x0 + inset, x1 - inset
            if side == 'S':
                bz0, bz1 = z0 + setback, z0 + setback + depth
                lot.door = (cx, bz0)
            else:
                bz1, bz0 = z1 - setback, z1 - setback - depth
                lot.door = (cx, bz1)
        else:
            bz0, bz1 = z0 + inset, z1 - inset
            if side == 'W':
                bx0, bx1 = x0 + setback, x0 + setback + depth
                lot.door = (bx0, cz)
            else:
                bx1, bx0 = x1 - setback, x1 - setback - depth
                lot.door = (bx1, cz)
        lot.body = (bx0, bz0, bx1, bz1)

    def _place_specials(self):
        used = set()

        def nearest(target):
            tx, tz = CX0 + target[0], CZ0 + target[1]
            best, bd = None, 1e18
            for lot in self.lots:
                if lot.side != 'S' or lot.k != 1 or lot.kind != 'house' or lot.block in used:
                    continue
                d = math.hypot(lot.center[0] - tx, lot.center[1] - tz)
                if d < bd:
                    best, bd = lot, d
            used.add(best.block)
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
        x0, z0, x1, z1 = lot.rect
        cx, cz = lot.center
        self._set_body(lot, lot.side, x0, z0, x1, z1, cx, cz, SETBACK, 14.0, 3.0)
        return lot.body

    # ---- walls / pieces ---------------------------------------------------------------
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
        for e in self.edge_cells.get((int((x - CX0) // PITCH), int((z - CZ0) // PITCH)), ()):
            if e is skip or e.elevated:
                continue
            d, _ = e.project(x, z)
            if d < e.width / 2 + margin:
                return True
        return False

    def _build_walls(self):
        for lot in self.lots:
            x0, z0, x1, z1 = lot.body
            self._add_wall((x0 + x1) / 2, (z0 + z1) / 2, 1.0, 0.0, (x1 - x0) / 2, (z1 - z0) / 2, 0.0, 10.0)
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
            if d < 17 and self._junction(e.a) or e.length - d < 17 and self._junction(e.b):
                continue
            x, z, _ = e.pos(t)
            self._add_wall(x, z, e.ux, e.uz, e.length / n / 2 + .1, .5, 0.0, 1.3)

    @staticmethod
    def _junction(node):
        return len(node.edges) > 2

    # ---- queries -------------------------------------------------------------------------
    def _cell(self, x, z):
        return (int((x - CX0) // PITCH), int((z - CZ0) // PITCH))

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
            if best is not None and bs < r * PITCH * 0.7:
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

    def find_address(self, text):
        """'214 Maple Ave' -> Lot or None."""
        try:
            num, name = text.strip().split(' ', 1)
            num = int(num)
        except ValueError:
            return None
        for i in range(NB + 1):
            if name == avenue_name(i):
                return self.by_address.get(('ave', i, num))
        for j in range(NB + 1):
            if name == street_name(j):
                return self.by_address.get(('st', j, num))
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
