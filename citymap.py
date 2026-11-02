"""City layout for the Food Delivery job: street grid, names, lots, addresses.

Pure logic with no graphics, in world coordinates, so it can be tested without a window.
Avenues run north-south (x is constant), streets run east-west (z is constant).
"""
import math
import random

NB = 22                  # blocks per side
PITCH = 90.0             # road centre to road centre
ROAD_W = 16.0            # asphalt plus both sidewalks
ASPHALT_W = 12.0
LOT_DEPTH = 20.0
SETBACK = 6.0            # front yard depth
CX0, CZ0 = 3000.0, 0.0   # south-west corner of the city (far from the other scenes)
SIZE = NB * PITCH
SEED = 20261102

AVENUES = ['Maple', 'Oak', 'Elm', 'Cedar', 'Birch', 'Pine', 'Willow', 'Aspen', 'Hazel', 'Cherry', 'Walnut',
           'Poplar', 'Spruce', 'Alder', 'Linden', 'Sycamore', 'Magnolia', 'Juniper', 'Hickory', 'Beech',
           'Cypress', 'Chestnut', 'Redwood']
STREETS = ['Main', 'Church', 'Market', 'Mill', 'Bridge', 'Park', 'Lake', 'River', 'Hill', 'Station', 'School',
           'Garden', 'Spring', 'Meadow', 'Harbor', 'Union', 'Liberty', 'Jackson', 'Franklin', 'Lincoln', 'Kings',
           'Queens', 'Victoria']

RESTAURANTS = [
    dict(name="Tony's Pizza",   block=(3, 3),   color=(214, 60, 52)),
    dict(name='Burger Barn',    block=(18, 3),  color=(240, 150, 40)),
    dict(name='Sushi Zen',      block=(3, 18),  color=(40, 160, 160)),
    dict(name='Taco Loco',      block=(18, 18), color=(80, 180, 80)),
    dict(name='Noodle House',   block=(9, 5),   color=(235, 200, 50)),
    dict(name='Curry Corner',   block=(5, 10),  color=(190, 110, 40)),
    dict(name='Grill & Chill',  block=(16, 10), color=(140, 80, 190)),
    dict(name='Sweet Treats',   block=(9, 17),  color=(235, 120, 170)),
]
DEPOT_BLOCK = (11, 3)
DEPOT_NAME = 'Dash Eats Depot'
DOWNTOWN_R = 2           # blocks around the centre that are downtown


def avenue_name(i):
    return f'{AVENUES[i]} Ave'


def street_name(j):
    return f'{STREETS[j]} St'


def avenue_x(i):
    return CX0 + i * PITCH


def street_z(j):
    return CZ0 + j * PITCH


class Lot:
    __slots__ = ('id', 'block', 'side', 'k', 'rect', 'body', 'door', 'facing', 'road_kind', 'road_index',
                 'number', 'kind', 'road_pt', 'curb_pt', 'info')

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


def _block_kind(bi, bj, restaurant_blocks, rng):
    c = NB // 2
    if (bi, bj) == DEPOT_BLOCK:
        return 'depot'
    if (bi, bj) in restaurant_blocks:
        return 'restaurant'
    if abs(bi - c) <= DOWNTOWN_R and abs(bj - c) <= DOWNTOWN_R:
        return 'downtown'
    if rng.random() < .06:
        return 'park'
    return 'houses'


class City:
    def __init__(self, seed=SEED):
        rng = random.Random(seed)
        restaurant_blocks = {r['block']: r for r in RESTAURANTS}
        self.block_kind = {}
        self.lots = []
        self.by_address = {}
        self.solids = {}                      # (bi, bj) -> [rect, ...]
        self.restaurants = []                 # (info, lot)
        self.depot = None
        for bi in range(NB):
            for bj in range(NB):
                kind = _block_kind(bi, bj, restaurant_blocks, rng)
                self.block_kind[(bi, bj)] = kind
                self.solids[(bi, bj)] = []
                if kind != 'park':
                    self._make_lots(bi, bj, kind, restaurant_blocks.get((bi, bj)))
        self.deliverable = [l for l in self.lots if l.kind in ('house', 'shop')]

    # ---- lots ------------------------------------------------------------
    def _make_lots(self, bi, bj, kind, restaurant):
        x0, z0, x1, z1 = block_bounds(bi, bj)
        d = LOT_DEPTH
        w4 = (x1 - x0) / 4
        for k in range(4):
            self._lot(bi, bj, 'S', k, (x0 + k * w4, z0, x0 + (k + 1) * w4, z0 + d), kind, restaurant)
            self._lot(bi, bj, 'N', k, (x0 + k * w4, z1 - d, x0 + (k + 1) * w4, z1), kind, restaurant)
        h2 = ((z1 - d) - (z0 + d)) / 2
        for k in range(2):
            self._lot(bi, bj, 'W', k, (x0, z0 + d + k * h2, x0 + d, z0 + d + (k + 1) * h2), kind, restaurant)
            self._lot(bi, bj, 'E', k, (x1 - d, z0 + d + k * h2, x1, z0 + d + (k + 1) * h2), kind, restaurant)

    def _lot(self, bi, bj, side, k, rect, bkind, restaurant):
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
            rz = street_z(lot.road_index)
            lot.road_pt = (cx, rz)
        else:
            lot.road_kind, lot.road_index = 'ave', bi if side == 'W' else bi + 1
            lot.number = 100 * bj + 30 + 20 * k + (1 if side == 'W' else 2)
            lot.road_pt = (avenue_x(lot.road_index), cz)
        lot.curb_pt = (lot.road_pt[0] - fx * 3.5, lot.road_pt[1] - fz * 3.5)

        special = None
        if bkind == 'restaurant' and side == 'S' and k == 1:
            special = 'restaurant'
        elif bkind == 'depot' and side == 'S' and k == 1:
            special = 'depot'
        lot.kind = special or ('shop' if bkind == 'downtown' else 'house')

        setback = 2.0 if lot.kind == 'shop' else SETBACK
        depth = {'house': 11.0, 'shop': LOT_DEPTH - 4, 'restaurant': 14.0, 'depot': 14.0}[lot.kind]
        inset = 2.0 if lot.kind in ('shop',) else (3.0 if lot.kind in ('restaurant', 'depot') else 2.5)
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
        self.lots.append(lot)
        self.solids[(bi, bj)].append(lot.body)
        self.by_address[(lot.road_kind, lot.road_index, lot.number)] = lot
        if special == 'restaurant':
            lot.info = restaurant
            self.restaurants.append((restaurant, lot))
        elif special == 'depot':
            self.depot = lot

    # ---- lookups ---------------------------------------------------------
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
        """A random deliverable lot, optionally at a distance range from a point."""
        for _ in range(200):
            lot = rng.choice(self.deliverable)
            if near is None:
                return lot
            d = math.hypot(lot.curb_pt[0] - near[0], lot.curb_pt[1] - near[1])
            if min_dist <= d <= max_dist:
                return lot
        return rng.choice(self.deliverable)

    def solids_near(self, x, z):
        bi = int(math.floor((x - CX0) / PITCH))
        bj = int(math.floor((z - CZ0) / PITCH))
        out = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                out += self.solids.get((bi + di, bj + dj), ())
        return out


# ---- road helpers (module level: they only depend on the constants) --------
def in_city(x, z, margin=0.0):
    return CX0 - margin <= x <= CX0 + SIZE + margin and CZ0 - margin <= z <= CZ0 + SIZE + margin


def _band_dist(v, origin):
    d = (v - origin) % PITCH
    return min(d, PITCH - d)


def on_road(x, z):
    if not in_city(x, z, ROAD_W / 2):
        return False
    half = ASPHALT_W / 2 + 1.5
    return _band_dist(x, CX0) <= half or _band_dist(z, CZ0) <= half


def snap(x, z):
    """Nearest road line: ('ns', avenue_index, z) or ('ew', street_index, x)."""
    dx, dz = _band_dist(x, CX0), _band_dist(z, CZ0)
    if dx <= dz:
        i = min(NB, max(0, round((x - CX0) / PITCH)))
        return ('ns', i, min(CZ0 + SIZE, max(CZ0, z)))
    j = min(NB, max(0, round((z - CZ0) / PITCH)))
    return ('ew', j, min(CX0 + SIZE, max(CX0, x)))


def road_name_at(x, z):
    axis, idx, _ = snap(x, z)
    return avenue_name(idx) if axis == 'ns' else street_name(idx)


def cross_street_at(x, z):
    """The nearest perpendicular road, for 'Maple Ave & Main St' style readouts."""
    axis, idx, t = snap(x, z)
    if axis == 'ns':
        j = min(NB, max(0, round((t - CZ0) / PITCH)))
        return street_name(j)
    i = min(NB, max(0, round((t - CX0) / PITCH)))
    return avenue_name(i)
