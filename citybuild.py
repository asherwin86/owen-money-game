"""Builds the 3D open world from citymap.World.

Roads, bridges, freeways and water are built once as chunked meshes. Houses (turned to face their street),
sidewalks, lamps and trees are streamed in around the player one 600 m chunk at a time, with a cheap low-detail
version of every house visible beyond that.
"""
import math
import random
import time as pytime
from array import array

from ursina import Entity, Mesh, Text, color

import citymap as cm
from citymap import ROAD_Y, WALK_Y, LAWN_Y

CHUNK = 600.0                          # detail chunks are 600 m squares
NCH = int(cm.SIZE // CHUNK)

WALLS = [(236, 222, 196), (214, 196, 166), (190, 205, 214), (226, 180, 150), (200, 222, 190), (240, 236, 224),
         (176, 150, 128), (218, 170, 170), (160, 184, 206)]
ROOFS = [(120, 60, 50), (70, 70, 80), (100, 80, 60), (60, 90, 110), (90, 50, 40), (50, 60, 50)]
SHOPS = [(150, 160, 175), (175, 150, 130), (130, 150, 170), (190, 190, 200), (160, 130, 120), (120, 140, 150)]
GRASS = (92, 160, 78)
LAWN = (104, 176, 86)
ASPHALT = (58, 60, 66)
HIGHWAY = (50, 52, 58)
DECK = (54, 56, 62)
CONCRETE = (176, 176, 172)
EMBANK = (146, 146, 142)
RAIL = (205, 205, 200)
WATER = (64, 128, 196)
SIDEWALK = (176, 176, 172)
YELLOW = (232, 200, 70)
WHITE = (228, 228, 228)
SHADE_TOP, SHADE_NS, SHADE_EW, SHADE_BOT = 1.0, .82, .68, .5


class MeshBuilder:
    """Collects quads and triangles with flat vertex colours into arrays Ursina's Mesh can take directly."""

    def __init__(self):
        self.v, self.c, self.t, self.n = array('f'), array('f'), array('I'), 0

    def quad(self, p0, p1, p2, p3, col, shade=1.0):
        r, g, b = col[0] / 255 * shade, col[1] / 255 * shade, col[2] / 255 * shade
        self.v.extend((*p0, *p1, *p2, *p3))
        self.c.extend((r, g, b, 1.0) * 4)
        n = self.n
        self.t.extend((n, n + 1, n + 2, n, n + 2, n + 3))
        self.n += 4

    def tri(self, p0, p1, p2, col, shade=1.0):
        r, g, b = col[0] / 255 * shade, col[1] / 255 * shade, col[2] / 255 * shade
        self.v.extend((*p0, *p1, *p2))
        self.c.extend((r, g, b, 1.0) * 3)
        n = self.n
        self.t.extend((n, n + 1, n + 2))
        self.n += 3

    def flat(self, x0, z0, x1, z1, y, col):
        self.quad((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), col)

    def box(self, x0, y0, z0, x1, y1, z1, col, bottom=False):
        q = self.quad
        q((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), col, SHADE_TOP)
        q((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), col, SHADE_NS)
        q((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), col, SHADE_NS * .92)
        q((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), col, SHADE_EW)
        q((x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0), col, SHADE_EW * .9)
        if bottom:
            q((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), col, SHADE_BOT)

    def obox(self, cx, cz, ux, uz, hl, hw, y0, y1, col):
        """Box rotated to point along (ux, uz)."""
        lx, lz = -uz, ux
        c = [(cx + ux * a + lx * b, cz + uz * a + lz * b) for a, b in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw))]
        self.quad((c[0][0], y1, c[0][1]), (c[1][0], y1, c[1][1]), (c[2][0], y1, c[2][1]), (c[3][0], y1, c[3][1]), col, 1.0)
        for k, sh in zip(range(4), (.8, .68, .75, .62)):
            a, b = c[k], c[(k + 1) % 4]
            self.quad((a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1]), col, sh)

    def gable(self, x0, y0, z0, x1, y1, z1, rise, col, ridge_x):
        """Gabled roof over the rectangle at height y0; ridge runs along x when ridge_x else along z."""
        yr = y0 + rise
        if ridge_x:
            zm = (z0 + z1) / 2
            self.quad((x0, y0, z0), (x1, y0, z0), (x1, yr, zm), (x0, yr, zm), col, .78)
            self.quad((x0, y0, z1), (x1, y0, z1), (x1, yr, zm), (x0, yr, zm), col, .95)
            self.tri((x0, y0, z0), (x0, y0, z1), (x0, yr, zm), col, SHADE_EW)
            self.tri((x1, y0, z0), (x1, y0, z1), (x1, yr, zm), col, SHADE_EW * .9)
        else:
            xm = (x0 + x1) / 2
            self.quad((x0, y0, z0), (x0, y0, z1), (xm, yr, z1), (xm, yr, z0), col, .72)
            self.quad((x1, y0, z0), (x1, y0, z1), (xm, yr, z1), (xm, yr, z0), col, .9)
            self.tri((x0, y0, z0), (x1, y0, z0), (xm, yr, z0), col, SHADE_NS)
            self.tri((x0, y0, z1), (x1, y0, z1), (xm, yr, z1), col, SHADE_NS * .92)

    def gable_o(self, cx, cz, tx, tz, hl, hw, y0, rise, col):
        """Gabled roof over an oriented rectangle; the ridge runs along (tx, tz)."""
        lx, lz = -tz, tx

        def P(a, b, y):
            return (cx + tx * a + lx * b, y, cz + tz * a + lz * b)
        yr = y0 + rise
        self.quad(P(-hl, -hw, y0), P(hl, -hw, y0), P(hl, 0, yr), P(-hl, 0, yr), col, .78)
        self.quad(P(-hl, hw, y0), P(hl, hw, y0), P(hl, 0, yr), P(-hl, 0, yr), col, .95)
        self.tri(P(-hl, -hw, y0), P(-hl, hw, y0), P(-hl, 0, yr), col, .8)
        self.tri(P(hl, -hw, y0), P(hl, hw, y0), P(hl, 0, yr), col, .7)

    def octa(self, cx, y0, cz, r, h, col):
        """Pointed bush/foliage shape."""
        top, bot = (cx, y0 + h, cz), (cx, y0, cz)
        mid = y0 + h * .45
        pts = [(cx - r, mid, cz), (cx, mid, cz - r), (cx + r, mid, cz), (cx, mid, cz + r)]
        for k in range(4):
            a, b = pts[k], pts[(k + 1) % 4]
            self.tri(a, b, top, col, (1.0, .85, .7, .9)[k])
            self.tri(a, b, bot, col, .55)

    def to_entity(self, parent):
        mesh = Mesh(vertices=self.v, triangles=self.t, colors=self.c)
        e = Entity(parent=parent, model=mesh)
        e.double_sided = True
        return e


# ---- houses, shops, trees -------------------------------------------------------------
def _front_quad(b, lot, lat, width, y0, y1, col, out=.06, base=LAWN_Y):
    """A flat panel on the road-facing wall (door, window, garage door); lat is the offset along the street."""
    fx, fz = lot.facing
    tx, tz = lot.tx, lot.tz
    cx, cz = lot.door[0] + fx * out + tx * lat, lot.door[1] + fz * out + tz * lat
    hw = width / 2
    b.quad((cx - tx * hw, base + y0, cz - tz * hw), (cx + tx * hw, base + y0, cz + tz * hw),
           (cx + tx * hw, base + y1, cz + tz * hw), (cx - tx * hw, base + y1, cz - tz * hw), col, .96)


def _tree(b, x, z, rng, base=LAWN_Y, scale=1.0):
    h = rng.uniform(2.2, 3.2) * scale
    b.box(x - .22, base, z - .22, x + .22, base + h, z + .22, (110, 78, 50))
    g = rng.choice(((54, 140, 62), (70, 156, 70), (46, 122, 58), (86, 168, 76)))
    b.octa(x, base + h - .6, z, rng.uniform(1.7, 2.4) * scale, rng.uniform(3.6, 4.8) * scale, g)


def _pine(b, x, z, rng):
    h = rng.uniform(5.5, 9.5)
    b.box(x - .25, 0.0, z - .25, x + .25, 1.6, z + .25, (96, 70, 46))
    g = rng.choice(((34, 104, 58), (40, 118, 62), (30, 92, 54)))
    b.octa(x, 1.2, z, rng.uniform(1.8, 2.8), h, g)


def _house(b, lot, rng):
    cx, cz, tx, tz, hl, hw = lot.body
    fx, fz = lot.facing
    wall, roof = rng.choice(WALLS), rng.choice(ROOFS)
    storeys = 2 if rng.random() < .4 else 1
    h = 3.1 * storeys + .3
    y0 = LAWN_Y
    b.obox(cx, cz, tx, tz, hl, hw, y0, y0 + h, wall)
    b.gable_o(cx, cz, tx, tz, hl + .4, hw + .4, y0 + h, rng.uniform(1.8, 2.6), roof)
    wl = hl * 2
    s = rng.choice((-1, 1))
    garage = s * (wl / 2 - 2.3)
    _front_quad(b, lot, garage, 2.8, 0, 2.3, (214, 214, 208))
    _front_quad(b, lot, -s * 1.3, 1.1, 0, 2.2, (92, 60, 44))
    _front_quad(b, lot, -s * (wl / 2 - 2.2), 1.6, 1.0, 2.3, (150, 200, 230))
    if storeys == 2:
        for off in (garage, -s * 1.3, -s * (wl / 2 - 2.2)):
            _front_quad(b, lot, off, 1.6, 3.8, 5.2, (150, 200, 230))
    # driveway from the garage to the road edge
    dist = math.hypot(lot.door[0] - lot.road_pt[0], lot.door[1] - lot.road_pt[1]) - lot.edge.width / 2
    sx, sz = lot.door[0] + tx * garage, lot.door[1] + tz * garage
    ex, ez = sx + fx * dist, sz + fz * dist
    hwd = 1.5
    y = LAWN_Y + .05
    b.quad((sx - tx * hwd, y, sz - tz * hwd), (sx + tx * hwd, y, sz + tz * hwd),
           (ex + tx * hwd, y, ez + tz * hwd), (ex - tx * hwd, y, ez - tz * hwd), (150, 150, 148))
    if rng.random() < .8:
        px = lot.door[0] + fx * 3.0 - tx * s * (wl / 2 - 1.0)
        pz = lot.door[1] + fz * 3.0 - tz * s * (wl / 2 - 1.0)
        _tree(b, px, pz, rng)
    if rng.random() < .6:                                       # a tree in the back garden
        bx, bz = cx - fx * (hw + 4.0) + tx * rng.uniform(-hl, hl), cz - fz * (hw + 4.0) + tz * rng.uniform(-hl, hl)
        _tree(b, bx, bz, rng)


def _shop(b, lot, rng, world, towns):
    cx, cz, tx, tz, hl, hw = lot.body
    t = towns.get(lot.town)
    centre = math.hypot(cx - t['center'][0], cz - t['center'][1]) if t else 999.0
    downtown = bool(t and t['kind'] == 'downtown')
    if downtown:
        h = rng.uniform(10, 26) + max(0.0, 360 - centre) * rng.uniform(.05, .14)
    else:
        h = rng.uniform(6, 13)
    col = rng.choice(SHOPS)
    b.obox(cx, cz, tx, tz, hl, hw, LAWN_Y, LAWN_Y + h, col)
    b.obox(cx, cz, tx, tz, hl + .2, hw + .2, LAWN_Y + h, LAWN_Y + h + .6, (90, 94, 100))
    wl = hl * 2
    for f in range(int(h // 3.6)):
        _front_quad(b, lot, 0, wl * .86, 1.1 + f * 3.6, 2.7 + f * 3.6, (140, 186, 214), out=.08)
    _front_quad(b, lot, 0, 2.4, 0, 2.5, (40, 44, 56), out=.1)


def sign_pos(lot):
    return lot.door[0] + lot.facing[0] * 4.0, lot.door[1] + lot.facing[1] * 4.0


def _venue(b, lot, col):
    """Restaurant or depot: a coloured low building with a roadside sign panel and a parking area."""
    cx, cz, tx, tz, hl, hw = lot.body
    b.obox(cx, cz, tx, tz, hl, hw, LAWN_Y, LAWN_Y + 4.2, col)
    b.obox(cx, cz, tx, tz, hl + .5, hw + .5, LAWN_Y + 4.2, LAWN_Y + 4.8, (50, 52, 60))
    wl = hl * 2
    _front_quad(b, lot, 0, wl * .7, 1.0, 3.0, (150, 200, 230), out=.08)
    _front_quad(b, lot, wl * .3, 1.6, 0, 2.3, (40, 44, 56), out=.1)
    px, pz = sign_pos(lot)
    b.box(px - .15, LAWN_Y, pz - .15, px + .15, LAWN_Y + 7.5, pz + .15, (70, 70, 76))
    b.quad((px - tx * 3, LAWN_Y + 5.5, pz - tz * 3), (px + tx * 3, LAWN_Y + 5.5, pz + tz * 3),
           (px + tx * 3, LAWN_Y + 8.2, pz + tz * 3), (px - tx * 3, LAWN_Y + 8.2, pz - tz * 3), col, 1.0)
    # parking apron between the building and the road
    fx, fz = lot.facing
    d0 = math.hypot(lot.door[0] - lot.road_pt[0], lot.door[1] - lot.road_pt[1]) - lot.edge.width / 2
    ax, az = lot.door[0], lot.door[1]
    bx, bz = ax + fx * d0, az + fz * d0
    hwp = lot.w / 2 - 1.0
    b.quad((ax - tx * hwp, LAWN_Y + .05, az - tz * hwp), (ax + tx * hwp, LAWN_Y + .05, az + tz * hwp),
           (bx + tx * hwp, LAWN_Y + .05, bz + tz * hwp), (bx - tx * hwp, LAWN_Y + .05, bz - tz * hwp), (92, 94, 98))


def _sidewalk(b, lot, rng):
    """Sidewalk strip with a curb along the front of a lot, plus a street lamp on every other lot."""
    px, pz = lot.road_pt
    nx, nz = -lot.facing[0], -lot.facing[1]
    tx, tz = lot.tx, lot.tz
    half = lot.edge.width / 2
    d0, d1 = half + .02, half + 2.4
    hw = lot.w / 2 + .15

    def P(s, d, y):
        return (px + tx * s + nx * d, y, pz + tz * s + nz * d)
    b.quad(P(-hw, d0, WALK_Y), P(hw, d0, WALK_Y), P(hw, d1, WALK_Y), P(-hw, d1, WALK_Y), SIDEWALK)
    b.quad(P(-hw, d0, ROAD_Y), P(hw, d0, ROAD_Y), P(hw, d0, WALK_Y), P(-hw, d0, WALK_Y), (150, 150, 146), .85)
    b.quad(P(-hw, d1, 0.0), P(hw, d1, 0.0), P(hw, d1, WALK_Y), P(-hw, d1, WALK_Y), (140, 140, 138), .8)
    if lot.id % 2 == 0:
        lx, _, lz = P(-hw + 1.0, d0 + .6, 0)
        b.box(lx - .1, WALK_Y, lz - .1, lx + .1, WALK_Y + 5.2, lz + .1, (64, 66, 72))
        b.box(lx - .45, WALK_Y + 5.2, lz - .45, lx + .45, WALK_Y + 5.5, lz + .45, (250, 235, 160))


class CityScene:
    """All the 3D geometry of the world, with houses streamed in around the player."""
    LOAD_R = 1100.0
    UNLOAD_R = 1700.0

    def __init__(self, root, world):
        self.root, self.world = root, world
        self._sb = {}
        self.static_entities, self.labels = [], []
        self.loaded, self.jobs, self.lod = {}, {}, {}
        self._last_chunk, self._wanted = None, []
        self.stats = {}
        self.towns = {t['name']: t for t in world.towns}
        self.chunk_lots, self.chunk_trees = {}, {}
        for lot in world.lots:
            self.chunk_lots.setdefault(self._key(*lot.center), []).append(lot)
        for x, z in world.forest:
            self.chunk_trees.setdefault(self._key(x, z), []).append((x, z))
        t0 = pytime.perf_counter()
        self._build_ground_and_water()
        self._build_roads()
        for key, b in self._sb.items():
            if b.n:
                self.static_entities.append(b.to_entity(root))
        self._sb = {}
        t1 = pytime.perf_counter()
        self._build_lod()
        self._build_labels()
        self.stats = dict(roads=t1 - t0, lod=pytime.perf_counter() - t1)

    # ---- helpers ------------------------------------------------------------------
    @staticmethod
    def _key(x, z):
        return (max(0, min(NCH - 1, int((x - cm.CX0) // CHUNK))), max(0, min(NCH - 1, int((z - cm.CZ0) // CHUNK))))

    def _builder(self, x, z):
        key = self._key(x, z)
        b = self._sb.get(key)
        if b is None:
            b = self._sb[key] = MeshBuilder()
        return b

    @staticmethod
    def _chunk_center(key):
        return (cm.CX0 + (key[0] + .5) * CHUNK, cm.CZ0 + (key[1] + .5) * CHUNK)

    # ---- ground and water -----------------------------------------------------------
    def _build_ground_and_water(self):
        g = MeshBuilder()
        pad = 2500
        g.flat(cm.CX0 - pad, cm.CZ0 - pad, cm.CX0 + cm.SIZE + pad, cm.CZ0 + cm.SIZE + pad, 0, GRASS)
        pts = self.world.river
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            dx, dz = bx - ax, bz - az
            n = math.hypot(dx, dz)
            ux, uz = dx / n, dz / n
            hw = cm.RIVER_W / 2 + 4
            a0 = (ax - ux * 30, az - uz * 30)
            b0 = (bx + ux * 30, bz + uz * 30)
            lx, lz = -uz * hw, ux * hw
            g.quad((a0[0] - lx, .28, a0[1] - lz), (a0[0] + lx, .28, a0[1] + lz),
                   (b0[0] + lx, .28, b0[1] + lz), (b0[0] - lx, .28, b0[1] - lz), WATER)
            # round the corner where the river bends
            g.tri((bx, .28, bz), (bx - uz * hw, .28, bz + ux * hw), (bx + uz * hw, .28, bz - ux * hw), WATER)
        self.static_entities.append(g.to_entity(self.root))

    # ---- roads ----------------------------------------------------------------------
    def _build_roads(self):
        world = self.world
        for e in world.edges:
            if e.elevated:
                self._elevated(e)
            else:
                self._ground_road(e)
        for n in world.nodes:
            self._junction(n)

    def _ground_road(self, e):
        b = self._builder((e.ax + e.bx) / 2, (e.az + e.bz) / 2)
        half = e.width / 2
        lx, lz = -e.uz, e.ux
        col = HIGHWAY if e.kind == 'highway' else ASPHALT
        b.quad((e.ax - lx * half, ROAD_Y, e.az - lz * half), (e.ax + lx * half, ROAD_Y, e.az + lz * half),
               (e.bx + lx * half, ROAD_Y, e.bz + lz * half), (e.bx - lx * half, ROAD_Y, e.bz - lz * half), col)
        y = ROAD_Y + .03
        s = 9.0
        while s + 3 < e.length - 8:
            for o, c in ((0.0, YELLOW),) if e.kind != 'highway' else ((6.0, WHITE), (-6.0, WHITE)):
                x0, z0 = e.ax + e.ux * s + lx * o, e.az + e.uz * s + lz * o
                x1, z1 = x0 + e.ux * 3, z0 + e.uz * 3
                b.quad((x0 - lx * .15, y, z0 - lz * .15), (x0 + lx * .15, y, z0 + lz * .15),
                       (x1 + lx * .15, y, z1 + lz * .15), (x1 - lx * .15, y, z1 - lz * .15), c)
            s += 8.0
        if e.kind == 'highway':
            n = max(1, int(math.ceil(e.length / 10.0)))
            for k in range(n):
                d = e.length * (k + .5) / n
                if (d < 26 and len(e.a.edges) > 2) or (e.length - d < 26 and len(e.b.edges) > 2):
                    continue
                x, z, _ = e.pos((k + .5) / n)
                b.obox(x, z, e.ux, e.uz, e.length / n / 2 + .1, .5, ROAD_Y, 1.3, CONCRETE)

    def _junction(self, n):
        ground = [e for e in n.edges if not e.elevated]
        if not ground:
            return
        b = self._builder(n.x, n.z)
        half = max(e.width for e in ground) / 2
        col = HIGHWAY if any(e.kind == 'highway' for e in ground) else ASPHALT
        pts = [(n.x + math.cos(a * math.tau / 12) * half, n.z + math.sin(a * math.tau / 12) * half) for a in range(12)]
        for k in range(12):
            p, q = pts[k], pts[(k + 1) % 12]
            b.tri((n.x, ROAD_Y, n.z), (p[0], ROAD_Y, p[1]), (q[0], ROAD_Y, q[1]), col)
        if len(ground) < 3:
            return
        y = ROAD_Y + .03
        for e in ground:
            if e.kind == 'highway':
                continue
            sgn = 1 if e.a is n else -1
            dx, dz = e.ux * sgn, e.uz * sgn
            lx, lz = -dz, dx
            d0, d1 = e.width / 2 + .8, e.width / 2 + 3.2
            for k in range(-3, 4):
                o = k * 1.5
                b.quad((n.x + dx * d0 + lx * (o - .35), y, n.z + dz * d0 + lz * (o - .35)),
                       (n.x + dx * d0 + lx * (o + .35), y, n.z + dz * d0 + lz * (o + .35)),
                       (n.x + dx * d1 + lx * (o + .35), y, n.z + dz * d1 + lz * (o + .35)),
                       (n.x + dx * d1 + lx * (o - .35), y, n.z + dz * d1 + lz * (o - .35)), WHITE)

    def _elevated(self, e):
        b = self._builder((e.ax + e.bx) / 2, (e.az + e.bz) / 2)
        half = e.width / 2
        lx, lz = -e.uz, e.ux
        thick = 1.3

        def P(t, off, dy=0.0, y=None):
            x, z, h = e.pos(t)
            return (x + lx * off, (h if y is None else y) + dy, z + lz * off)

        for k, (t0, t1, viaduct) in enumerate(self.world.pieces(e)):
            tm = (t0 + t1) / 2
            _, _, hm = e.pos(tm)
            rise = hm - ROAD_Y
            Al0, Ar0, Al1, Ar1 = P(t0, -half), P(t0, half), P(t1, -half), P(t1, half)
            b.quad(Al0, Ar0, Ar1, Al1, DECK, 1.0)
            low = lambda p: (p[0], p[1] - thick, p[2])
            b.quad(Al0, Al1, low(Al1), low(Al0), CONCRETE, .8)
            b.quad(Ar0, Ar1, low(Ar1), low(Ar0), CONCRETE, .65)
            if viaduct:
                b.quad(low(Al0), low(Ar0), low(Ar1), low(Al1), CONCRETE, .45)
            if rise > 1.2:
                rails = rise >= self.world.rail_min_rise(e) and self.world.rail_ok(e, tm)
                for sgn in (-1, 1):
                    o_out, o_in = sgn * half, sgn * (half - .7)
                    if rails:
                        b.quad(P(t0, o_out, 1.0), P(t0, o_in, 1.0), P(t1, o_in, 1.0), P(t1, o_out, 1.0), RAIL, 1.0)
                        b.quad(P(t0, o_in), P(t1, o_in), P(t1, o_in, 1.0), P(t0, o_in, 1.0), RAIL, .8)
                        b.quad(P(t0, o_out), P(t1, o_out), P(t1, o_out, 1.0), P(t0, o_out, 1.0), RAIL, .7)
                    if not viaduct:
                        b.quad(P(t0, o_out, -thick), P(t1, o_out, -thick), P(t1, o_out, y=0.0), P(t0, o_out, y=0.0),
                               EMBANK, .8 if sgn < 0 else .65)
            if k == 0:
                for px, pz, ph in self.world.pillars(e):
                    b.box(px - .9, 0.0, pz - .9, px + .9, ph, pz + .9, CONCRETE)
            if k % 2 == 0:
                x, z, h = e.pos(t0 + (t1 - t0) * .1)
                x2, z2, h2 = e.pos(t0 + (t1 - t0) * .7)
                if e.kind in ('freeway', 'highway'):
                    offs = ((0.0, YELLOW), (half / 2, WHITE), (-half / 2, WHITE))
                else:
                    offs = ((0.0, YELLOW),)
                for off, c in offs:
                    b.quad((x + lx * (off - .15), h + .03, z + lz * (off - .15)),
                           (x + lx * (off + .15), h + .03, z + lz * (off + .15)),
                           (x2 + lx * (off + .15), h2 + .03, z2 + lz * (off + .15)),
                           (x2 + lx * (off - .15), h2 + .03, z2 + lz * (off - .15)), c)

    # ---- low detail layer (every house, visible beyond the streamed area) ------------------
    def _build_lod(self):
        rng = random.Random(11)
        for key, lots in self.chunk_lots.items():
            b = MeshBuilder()
            for lot in lots:
                cx, cz, tx, tz, hl, hw = lot.body
                if lot.kind == 'shop':
                    t = self.towns.get(lot.town)
                    downtown = bool(t and t['kind'] == 'downtown')
                    h = rng.uniform(12, 34) if downtown else rng.uniform(6, 12)
                    col = rng.choice(SHOPS)
                else:
                    h = 4.8
                    col = rng.choice(ROOFS)
                b.obox(cx, cz, tx, tz, hl, hw, LAWN_Y, LAWN_Y + h, col)
            if b.n:
                self.lod[key] = b.to_entity(self.root)

    # ---- labels -----------------------------------------------------------------------
    def _build_labels(self):
        world = self.world
        for lot in [l for _, l in world.restaurants] + [world.depot]:
            name = lot.info['name'] if lot.kind == 'restaurant' else cm.DEPOT_NAME
            px, pz = sign_pos(lot)
            self.labels.append(Text(name, parent=self.root, position=(px, LAWN_Y + 9.4, pz), origin=(0, 0),
                                    scale=11, billboard=True, color=color.white))
        for t in world.towns:
            if not t['ends']:
                continue
            cx, cz = t['center']
            self.labels.append(Text(t['name'].upper(), parent=self.root, position=(cx, 60, cz), origin=(0, 0),
                                    scale=34, billboard=True, color=color.rgba32(255, 255, 255, 200)))
        seen = set()
        for e in world.edges:
            if e.bridge and e.bridge not in seen and (e.hump is not None or e.kind == 'freeway'):
                seen.add(e.bridge)
                x, z, h = e.pos(.5)
                self.labels.append(Text(e.bridge.upper(), parent=self.root, position=(x, h + 9, z), origin=(0, 0),
                                        scale=16, billboard=True, color=color.yellow))
        for e in world.edges:
            if e.kind == 'ramp':
                x, z, h = e.pos(.12)
                self.labels.append(Text(f'RAMP\n{e.links[1]}', parent=self.root, position=(x, h + 7, z), origin=(0, 0),
                                        scale=10, billboard=True, color=color.orange))

    # ---- streamed detail ----------------------------------------------------------------
    def _detail_job(self, key):
        """Generator that builds one chunk's houses, sidewalks and trees, yielding every few lots."""
        world = self.world
        b = MeshBuilder()
        for n, lot in enumerate(self.chunk_lots.get(key, ())):
            lrng = random.Random(lot.id * 7919 + 13)
            _sidewalk(b, lot, lrng)
            if lot.kind == 'house':
                _house(b, lot, lrng)
            elif lot.kind == 'shop':
                _shop(b, lot, lrng, world, self.towns)
            elif lot.kind == 'restaurant':
                _venue(b, lot, lot.info['color'])
            elif lot.kind == 'depot':
                _venue(b, lot, (60, 120, 220))
            if n % 8 == 7:
                yield
        trng = random.Random(key[0] * 7001 + key[1] * 131 + 3)
        for k, (x, z) in enumerate(self.chunk_trees.get(key, ())):
            if trng.random() < .35:
                _pine(b, x, z, trng)
            else:
                _tree(b, x, z, trng, scale=1.5)
            if k % 60 == 59:
                yield
        self.loaded[key] = b.to_entity(self.root) if b.n else None
        if key in self.lod:
            self.lod[key].enabled = False
        yield

    def prime(self, x, z, radius=650.0):
        """Build the chunks around a point right now (used while a loading screen is up)."""
        for key in self._chunks_near(x, z, radius):
            if key not in self.loaded:
                for _ in self._detail_job(key):
                    pass
                self.jobs.pop(key, None)

    def _chunks_near(self, x, z, radius):
        out = []
        n = int(radius // CHUNK) + 2
        cx, cz = int((x - cm.CX0) // CHUNK), int((z - cm.CZ0) // CHUNK)
        for kx in range(cx - n, cx + n + 1):
            for kz in range(cz - n, cz + n + 1):
                if 0 <= kx < NCH and 0 <= kz < NCH:
                    mx, mz = self._chunk_center((kx, kz))
                    d = math.hypot(mx - x, mz - z)
                    if d < radius + CHUNK * .5:
                        out.append(((kx, kz), d))
        out.sort(key=lambda p: p[1])
        return [k for k, _ in out]

    def update(self, x, z, budget=0.004):
        """Stream chunks around (x, z); call every frame. Uses at most `budget` seconds."""
        t0 = pytime.perf_counter()
        here = (int((x - cm.CX0) // CHUNK), int((z - cm.CZ0) // CHUNK))
        if here != self._last_chunk:
            self._last_chunk = here
            self._wanted = [k for k in self._chunks_near(x, z, self.LOAD_R) if k not in self.loaded]
            for key in list(self.loaded):
                mx, mz = self._chunk_center(key)
                if math.hypot(mx - x, mz - z) > self.UNLOAD_R + CHUNK * .5:
                    ent = self.loaded.pop(key)
                    if ent is not None:
                        from ursina import destroy
                        destroy(ent)
                    if key in self.lod:
                        self.lod[key].enabled = True
        while pytime.perf_counter() - t0 < budget:
            if not self.jobs:
                while self._wanted and (self._wanted[0] in self.loaded or self._wanted[0] in self.jobs):
                    self._wanted.pop(0)
                if not self._wanted:
                    return
                key = self._wanted.pop(0)
                self.jobs[key] = self._detail_job(key)
            key = next(iter(self.jobs))
            try:
                next(self.jobs[key])
            except StopIteration:
                self.jobs.pop(key, None)
