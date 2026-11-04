"""Builds the 3D open world from citymap.World.

Roads, bridges, freeways and water are built once as chunked meshes. Houses, lawns and trees are streamed in
around the player a few blocks at a time, with a cheap low-detail version of every block visible beyond that.
"""
import math
import random
import time as pytime
from array import array

from ursina import Entity, Mesh, Text, color

import citymap as cm
from citymap import ROAD_Y, WALK_Y, LAWN_Y

CHUNK_BLOCKS = 6                       # detail chunks are 6 x 6 blocks (600 m)
CHUNK = CHUNK_BLOCKS * cm.PITCH

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
    """A flat panel on the road-facing wall (door, window, garage door)."""
    fx, fz = lot.facing
    tx, tz = -fz, fx
    cx, cz = lot.door[0] + fx * out + tx * lat, lot.door[1] + fz * out + tz * lat
    hw = width / 2
    b.quad((cx - tx * hw, base + y0, cz - tz * hw), (cx + tx * hw, base + y0, cz + tz * hw),
           (cx + tx * hw, base + y1, cz + tz * hw), (cx - tx * hw, base + y1, cz - tz * hw), col, .96)


def _tree(b, x, z, rng, base=LAWN_Y, scale=1.0):
    h = rng.uniform(2.2, 3.2) * scale
    b.box(x - .22, base, z - .22, x + .22, base + h, z + .22, (110, 78, 50))
    g = rng.choice(((54, 140, 62), (70, 156, 70), (46, 122, 58), (86, 168, 76)))
    b.octa(x, base + h - .6, z, rng.uniform(1.7, 2.4) * scale, rng.uniform(3.6, 4.8) * scale, g)


def _house(b, lot, rng):
    x0, z0, x1, z1 = lot.body
    fx, fz = lot.facing
    horiz = abs(fz) > 0.5
    wl = (x1 - x0) if horiz else (z1 - z0)
    wall, roof = rng.choice(WALLS), rng.choice(ROOFS)
    storeys = 2 if rng.random() < .4 else 1
    h = 3.1 * storeys + .3
    y0 = LAWN_Y
    b.box(x0, y0, z0, x1, y0 + h, z1, wall)
    b.gable(x0 - .4, y0 + h, z0 - .4, x1 + .4, y0 + h, z1 + .4, rng.uniform(1.8, 2.6), roof, ridge_x=horiz)
    s = rng.choice((-1, 1))
    garage = s * (wl / 2 - 2.3)
    _front_quad(b, lot, garage, 2.8, 0, 2.3, (214, 214, 208))
    _front_quad(b, lot, -s * 1.3, 1.1, 0, 2.2, (92, 60, 44))
    _front_quad(b, lot, -s * (wl / 2 - 2.2), 1.6, 1.0, 2.3, (150, 200, 230))
    if storeys == 2:
        for off in (garage, -s * 1.3, -s * (wl / 2 - 2.2)):
            _front_quad(b, lot, off, 1.6, 3.8, 5.2, (150, 200, 230))
    tx, tz = -fz, fx
    sx, sz = lot.door[0] + tx * garage, lot.door[1] + tz * garage
    ex, ez = sx + fx * cm.SETBACK, sz + fz * cm.SETBACK
    hw = 1.5
    y = LAWN_Y + .03
    b.quad((sx - tx * hw, y, sz - tz * hw), (sx + tx * hw, y, sz + tz * hw),
           (ex + tx * hw, y, ez + tz * hw), (ex - tx * hw, y, ez - tz * hw), (150, 150, 148))
    if rng.random() < .75:
        px = lot.door[0] + fx * 2.6 - tx * s * (wl / 2 - 1.0)
        pz = lot.door[1] + fz * 2.6 - tz * s * (wl / 2 - 1.0)
        _tree(b, px, pz, rng)


def _shop(b, lot, rng, world):
    x0, z0, x1, z1 = lot.body
    bx, bz = (x0 + x1) / 2, (z0 + z1) / 2
    centre = math.hypot(bx - (cm.CX0 + cm.DOWNTOWN[0]), bz - (cm.CZ0 + cm.DOWNTOWN[1]))
    if lot.edge.kind == 'arterial' and centre > cm.DOWNTOWN_R:
        h = rng.uniform(6, 14)
    else:
        h = rng.uniform(10, 26) + max(0.0, 330 - centre) * rng.uniform(.06, .17)
    col = rng.choice(SHOPS)
    b.box(x0, LAWN_Y, z0, x1, LAWN_Y + h, z1, col)
    b.box(x0 - .2, LAWN_Y + h, z0 - .2, x1 + .2, LAWN_Y + h + .6, z1 + .2, (90, 94, 100))
    wl = (x1 - x0) if abs(lot.facing[1]) > .5 else (z1 - z0)
    for f in range(int(h // 3.6)):
        _front_quad(b, lot, 0, wl * .86, 1.1 + f * 3.6, 2.7 + f * 3.6, (140, 186, 214), out=.08)
    _front_quad(b, lot, 0, 2.4, 0, 2.5, (40, 44, 56), out=.1)


def _venue(b, lot, col):
    """Restaurant or depot: a coloured low building with a roadside sign panel and a parking area."""
    x0, z0, x1, z1 = lot.body
    b.box(x0, LAWN_Y, z0, x1, LAWN_Y + 4.2, z1, col)
    b.box(x0 - .5, LAWN_Y + 4.2, z0 - .5, x1 + .5, LAWN_Y + 4.8, z1 + .5, (50, 52, 60))
    wl = (x1 - x0) if abs(lot.facing[1]) > .5 else (z1 - z0)
    _front_quad(b, lot, 0, wl * .7, 1.0, 3.0, (150, 200, 230), out=.08)
    _front_quad(b, lot, wl * .3, 1.6, 0, 2.3, (40, 44, 56), out=.1)
    px, pz = sign_pos(lot)
    fx, fz = lot.facing
    b.box(px - .15, LAWN_Y, pz - .15, px + .15, LAWN_Y + 7.5, pz + .15, (70, 70, 76))
    tx, tz = -fz, fx
    b.quad((px - tx * 3, LAWN_Y + 5.5, pz - tz * 3), (px + tx * 3, LAWN_Y + 5.5, pz + tz * 3),
           (px + tx * 3, LAWN_Y + 8.2, pz + tz * 3), (px - tx * 3, LAWN_Y + 8.2, pz - tz * 3), col, 1.0)
    b.flat(lot.rect[0], lot.rect[1], lot.rect[2], lot.rect[3], LAWN_Y + .02, (92, 94, 98))


def sign_pos(lot):
    return lot.door[0] + lot.facing[0] * 4.0, lot.door[1] + lot.facing[1] * 4.0


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
    def _builder(self, x, z):
        key = (int((x - cm.CX0) // CHUNK), int((z - cm.CZ0) // CHUNK))
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
        s = 14.0
        while s + 4 < e.length - 12:
            for off, c in (((0.0,), YELLOW),) if e.kind != 'highway' else (((6.0,), WHITE), ((-6.0,), WHITE)):
                o = off[0]
                x0, z0 = e.ax + e.ux * s + lx * o, e.az + e.uz * s + lz * o
                x1, z1 = x0 + e.ux * 4, z0 + e.uz * 4
                b.quad((x0 - lx * .15, y, z0 - lz * .15), (x0 + lx * .15, y, z0 + lz * .15),
                       (x1 + lx * .15, y, z1 + lz * .15), (x1 - lx * .15, y, z1 - lz * .15), c)
            s += 10.0
        if e.kind == 'highway':
            n = max(1, int(math.ceil(e.length / 10.0)))
            for k in range(n):
                d = e.length * (k + .5) / n
                if (d < 17 and len(e.a.edges) > 2) or (e.length - d < 17 and len(e.b.edges) > 2):
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
        b.flat(n.x - half, n.z - half, n.x + half, n.z + half, ROAD_Y, col)
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

    # ---- low detail layer (every block, visible beyond the streamed area) ------------------
    def _build_lod(self):
        rng = random.Random(11)
        builders = {}
        for (bi, bj), kind in self.world.block_kind.items():
            if kind == 'park':
                continue
            key = (bi // CHUNK_BLOCKS, bj // CHUNK_BLOCKS)
            b = builders.setdefault(key, MeshBuilder())
            x0, z0, x1, z1 = cm.block_bounds(bi, bj)
            col = rng.choice(ROOFS) if kind == 'houses' else rng.choice(SHOPS)
            h = rng.choice((4.5, 4.5, 7.5)) if kind == 'houses' else rng.uniform(14, 40)
            d = 11.0
            b.flat(x0, z0, x1, z1, LAWN_Y, LAWN)
            b.box(x0 + 3, LAWN_Y, z0 + 6, x1 - 3, LAWN_Y + h, z0 + 6 + d, col)
            b.box(x0 + 3, LAWN_Y, z1 - 6 - d, x1 - 3, LAWN_Y + h, z1 - 6, col)
            b.box(x0 + 6, LAWN_Y, z0 + 26, x0 + 6 + d, LAWN_Y + h, z1 - 26, col)
            b.box(x1 - 6 - d, LAWN_Y, z0 + 26, x1 - 6, LAWN_Y + h, z1 - 26, col)
        for key, b in builders.items():
            self.lod[key] = b.to_entity(self.root)

    # ---- labels -----------------------------------------------------------------------
    def _build_labels(self):
        world = self.world
        for lot in [l for _, l in world.restaurants] + [world.depot]:
            name = lot.info['name'] if lot.kind == 'restaurant' else cm.DEPOT_NAME
            px, pz = sign_pos(lot)
            self.labels.append(Text(name, parent=self.root, position=(px, LAWN_Y + 9.4, pz), origin=(0, 0),
                                    scale=11, billboard=True, color=color.white))
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
        """Generator that builds one chunk's blocks, yielding between blocks."""
        world = self.world
        b = MeshBuilder()
        bx0, bz0 = key[0] * CHUNK_BLOCKS, key[1] * CHUNK_BLOCKS
        for bi in range(bx0, min(bx0 + CHUNK_BLOCKS, cm.NB)):
            for bj in range(bz0, min(bz0 + CHUNK_BLOCKS, cm.NB)):
                if (bi, bj) in world.buildable:
                    self._block(b, bi, bj)
                    yield
        self.loaded[key] = b.to_entity(self.root) if b.n else None
        if key in self.lod:
            self.lod[key].enabled = False
        yield

    def _block(self, b, bi, bj):
        world = self.world
        rng = random.Random(bi * 1009 + bj * 9176 + 5)
        half_a = cm.ASPHALT_W / 2
        x0, z0, x1, z1 = cm.block_bounds(bi, bj)
        ax0, az0 = cm.avenue_x(bi) + half_a, cm.street_z(bj) + half_a
        ax1, az1 = cm.avenue_x(bi + 1) - half_a, cm.street_z(bj + 1) - half_a
        for p, q in (((ax0, az0), (ax1, az0)), ((ax0, az1), (ax1, az1))):
            b.quad((p[0], ROAD_Y, p[1]), (q[0], ROAD_Y, q[1]), (q[0], WALK_Y, q[1]), (p[0], WALK_Y, p[1]), (140, 140, 138), .85)
        for p, q in (((ax0, az0), (ax0, az1)), ((ax1, az0), (ax1, az1))):
            b.quad((p[0], ROAD_Y, p[1]), (q[0], ROAD_Y, q[1]), (q[0], WALK_Y, q[1]), (p[0], WALK_Y, p[1]), (140, 140, 138), .7)
        b.flat(ax0, az0, ax1, az1, WALK_Y, SIDEWALK)
        kind = world.block_kind[(bi, bj)]
        b.flat(x0, z0, x1, z1, LAWN_Y, (118, 170, 100) if kind == 'park' else LAWN)
        for lx, lz in ((x0 + .8, z0 + .8), (x1 - .8, z1 - .8)):
            b.box(lx - .1, WALK_Y, lz - .1, lx + .1, WALK_Y + 5.2, lz + .1, (64, 66, 72))
            b.box(lx - .45, WALK_Y + 5.2, lz - .45, lx + .45, WALK_Y + 5.5, lz + .45, (250, 235, 160))
        if kind == 'park':
            b.flat(x0 + 28, z0 + 28, x1 - 28, z1 - 28, LAWN_Y + .03, (86, 150, 200))
            for _ in range(46):
                tx, tz = rng.uniform(x0 + 3, x1 - 3), rng.uniform(z0 + 3, z1 - 3)
                if not (x0 + 24 < tx < x1 - 24 and z0 + 24 < tz < z1 - 24):
                    _tree(b, tx, tz, rng)
            return
        for _ in range(rng.randint(4, 9)):
            _tree(b, rng.uniform(x0 + 21, x1 - 21), rng.uniform(z0 + 21, z1 - 21), rng)
        for lot in world.block_lots.get((bi, bj), ()):
            lrng = random.Random(lot.id * 7919 + 13)
            if lot.kind == 'house':
                _house(b, lot, lrng)
            elif lot.kind == 'shop':
                _shop(b, lot, lrng, world)
            elif lot.kind == 'restaurant':
                _venue(b, lot, lot.info['color'])
            elif lot.kind == 'depot':
                _venue(b, lot, (60, 120, 220))

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
                if 0 <= kx < cm.NB // CHUNK_BLOCKS and 0 <= kz < cm.NB // CHUNK_BLOCKS:
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
