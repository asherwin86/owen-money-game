"""Builds the 3D city from citymap.City as a few big combined meshes (one per chunk)."""
import math
import random
from array import array

from ursina import Entity, Mesh, Text, color

import citymap as cm

ROAD_Y = 0.30
WALK_Y = 0.45
LAWN_Y = 0.55
CHUNK = 4                       # blocks per chunk side

WALLS = [(236, 222, 196), (214, 196, 166), (190, 205, 214), (226, 180, 150), (200, 222, 190), (240, 236, 224),
         (176, 150, 128), (218, 170, 170), (160, 184, 206)]
ROOFS = [(120, 60, 50), (70, 70, 80), (100, 80, 60), (60, 90, 110), (90, 50, 40), (50, 60, 50)]
SHOPS = [(150, 160, 175), (175, 150, 130), (130, 150, 170), (190, 190, 200), (160, 130, 120), (120, 140, 150)]
GRASS = (92, 160, 78)
LAWN = (104, 176, 86)
ASPHALT = (58, 60, 66)
SIDEWALK = (176, 176, 172)
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
    horiz = abs(fz) > 0.5                      # front wall runs along x
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
    # driveway from the garage to the sidewalk
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


def _shop(b, lot, rng):
    x0, z0, x1, z1 = lot.body
    bx, bz = (x0 + x1) / 2, (z0 + z1) / 2
    centre = max(abs(bx - (cm.CX0 + cm.SIZE / 2)), abs(bz - (cm.CZ0 + cm.SIZE / 2)))
    h = rng.uniform(10, 26) + max(0.0, 150 - centre) * rng.uniform(.08, .28)
    col = rng.choice(SHOPS)
    b.box(x0, LAWN_Y, z0, x1, LAWN_Y + h, z1, col)
    b.box(x0 - .2, LAWN_Y + h, z0 - .2, x1 + .2, LAWN_Y + h + .6, z1 + .2, (90, 94, 100))
    wl = (x1 - x0) if abs(lot.facing[1]) > .5 else (z1 - z0)
    for f in range(int(h // 3.6)):
        _front_quad(b, lot, 0, wl * .86, 1.1 + f * 3.6, 2.7 + f * 3.6, (140, 186, 214), out=.08)
    _front_quad(b, lot, 0, 2.4, 0, 2.5, (40, 44, 56), out=.1)


def _venue(b, lot, col, labels):
    """Restaurant or depot: a coloured low building with a roadside sign panel."""
    x0, z0, x1, z1 = lot.body
    b.box(x0, LAWN_Y, z0, x1, LAWN_Y + 4.2, z1, col)
    b.box(x0 - .5, LAWN_Y + 4.2, z0 - .5, x1 + .5, LAWN_Y + 4.8, z1 + .5, (50, 52, 60))
    wl = (x1 - x0) if abs(lot.facing[1]) > .5 else (z1 - z0)
    _front_quad(b, lot, 0, wl * .7, 1.0, 3.0, (150, 200, 230), out=.08)
    _front_quad(b, lot, wl * .3, 1.6, 0, 2.3, (40, 44, 56), out=.1)
    fx, fz = lot.facing
    px, pz = lot.door[0] + fx * 4.0, lot.door[1] + fz * 4.0
    b.box(px - .15, LAWN_Y, pz - .15, px + .15, LAWN_Y + 7.5, pz + .15, (70, 70, 76))
    tx, tz = -fz, fx
    b.quad((px - tx * 3, LAWN_Y + 5.5, pz - tz * 3), (px + tx * 3, LAWN_Y + 5.5, pz + tz * 3),
           (px + tx * 3, LAWN_Y + 8.2, pz + tz * 3), (px - tx * 3, LAWN_Y + 8.2, pz - tz * 3), col, 1.0)
    labels.append((lot, px, LAWN_Y + 9.4, pz))
    # parking area
    b.flat(lot.rect[0], lot.rect[1], lot.rect[2], lot.rect[3], LAWN_Y + .02, (92, 94, 98))


def build_city(root, city):
    """Create all meshes under root. Returns a dict with labels and chunk entities."""
    rng = random.Random(cm.SEED + 5)
    nchunks = (cm.NB + CHUNK - 1) // CHUNK
    chunks = {}

    def chunk(bi, bj):
        key = (bi // CHUNK, bj // CHUNK)
        if key not in chunks:
            chunks[key] = MeshBuilder()
        return chunks[key]

    # distant grass under everything
    ground = MeshBuilder()
    pad = 1500
    ground.flat(cm.CX0 - pad, cm.CZ0 - pad, cm.CX0 + cm.SIZE + pad, cm.CZ0 + cm.SIZE + pad, 0, GRASS)
    ground.to_entity(root)

    half_a, half_r = cm.ASPHALT_W / 2, cm.ROAD_W / 2
    labels = []
    for bi in range(cm.NB + 1):
        for bj in range(cm.NB + 1):
            b = chunk(min(bi, cm.NB - 1), min(bj, cm.NB - 1))
            x, z = cm.avenue_x(bi), cm.street_z(bj)
            # intersection and the road segments leading north/east from it
            b.flat(x - half_a, z - half_a, x + half_a, z + half_a, ROAD_Y, ASPHALT)
            if bj < cm.NB:
                b.flat(x - half_a, z + half_a, x + half_a, z + cm.PITCH - half_a, ROAD_Y, ASPHALT)
                for k in range(0, 8):
                    zz = z + half_a + 2 + k * 10
                    if zz + 4 < z + cm.PITCH - half_a - 2:
                        b.flat(x - .15, zz, x + .15, zz + 4, ROAD_Y + .03, (232, 200, 70))
            if bi < cm.NB:
                b.flat(x + half_a, z - half_a, x + cm.PITCH - half_a, z + half_a, ROAD_Y, ASPHALT)
                for k in range(0, 8):
                    xx = x + half_a + 2 + k * 10
                    if xx + 4 < x + cm.PITCH - half_a - 2:
                        b.flat(xx, z - .15, xx + 4, z + .15, ROAD_Y + .03, (232, 200, 70))
            # crosswalk stripes on the four approaches
            for k in range(-4, 5):
                o = k * 1.2
                b.flat(x + o - .35, z + half_a + .5, x + o + .35, z + half_a + 3, ROAD_Y + .03, (225, 225, 225))
                b.flat(x + o - .35, z - half_a - 3, x + o + .35, z - half_a - .5, ROAD_Y + .03, (225, 225, 225))
                b.flat(x + half_a + .5, z + o - .35, x + half_a + 3, z + o + .35, ROAD_Y + .03, (225, 225, 225))
                b.flat(x - half_a - 3, z + o - .35, x - half_a - .5, z + o + .35, ROAD_Y + .03, (225, 225, 225))

    for bi in range(cm.NB):
        for bj in range(cm.NB):
            b = chunk(bi, bj)
            x0, z0, x1, z1 = cm.block_bounds(bi, bj)
            ax0, az0 = cm.avenue_x(bi) + half_a, cm.street_z(bj) + half_a
            ax1, az1 = cm.avenue_x(bi + 1) - half_a, cm.street_z(bj + 1) - half_a
            # raised block: kerb walls, sidewalk ring, lawn
            for p, q in (((ax0, az0), (ax1, az0)), ((ax0, az1), (ax1, az1))):
                b.quad((p[0], ROAD_Y, p[1]), (q[0], ROAD_Y, q[1]), (q[0], WALK_Y, q[1]), (p[0], WALK_Y, p[1]), (140, 140, 138), .85)
            for p, q in (((ax0, az0), (ax0, az1)), ((ax1, az0), (ax1, az1))):
                b.quad((p[0], ROAD_Y, p[1]), (q[0], ROAD_Y, q[1]), (q[0], WALK_Y, q[1]), (p[0], WALK_Y, p[1]), (140, 140, 138), .7)
            b.flat(ax0, az0, ax1, az1, WALK_Y, SIDEWALK)
            kind = city.block_kind[(bi, bj)]
            lawn = (118, 170, 100) if kind == 'park' else LAWN
            b.flat(x0, z0, x1, z1, LAWN_Y, lawn)
            # street lamps on two corners
            for lx, lz in ((x0 + .8, z0 + .8), (x1 - .8, z1 - .8)):
                b.box(lx - .1, WALK_Y, lz - .1, lx + .1, WALK_Y + 5.2, lz + .1, (64, 66, 72))
                b.box(lx - .45, WALK_Y + 5.2, lz - .45, lx + .45, WALK_Y + 5.5, lz + .45, (250, 235, 160))
            if kind == 'park':
                b.flat(x0 + 28, z0 + 28, x1 - 28, z1 - 28, LAWN_Y + .03, (86, 150, 200))
                for _ in range(46):
                    tx, tz = rng.uniform(x0 + 3, x1 - 3), rng.uniform(z0 + 3, z1 - 3)
                    if not (x0 + 24 < tx < x1 - 24 and z0 + 24 < tz < z1 - 24):
                        _tree(b, tx, tz, rng)
                continue
            # backyard trees in the middle of the block
            for _ in range(rng.randint(4, 9)):
                _tree(b, rng.uniform(x0 + 21, x1 - 21), rng.uniform(z0 + 21, z1 - 21), rng)

    for lot in city.lots:
        b = chunk(*lot.block)
        lrng = random.Random(lot.id * 7919 + 13)
        if lot.kind == 'house':
            _house(b, lot, lrng)
        elif lot.kind == 'shop':
            _shop(b, lot, lrng)
        elif lot.kind == 'restaurant':
            _venue(b, lot, lot.info['color'], labels)
        elif lot.kind == 'depot':
            _venue(b, lot, (60, 120, 220), labels)

    entities = [mb.to_entity(root) for mb in chunks.values()]

    texts = []
    for lot, px, py, pz in labels:
        name = lot.info['name'] if lot.kind == 'restaurant' else cm.DEPOT_NAME
        col = color.white
        t = Text(name, parent=root, position=(px, py, pz), origin=(0, 0), scale=11, billboard=True, color=col)
        texts.append(t)
    return dict(entities=entities, labels=texts, chunks=len(chunks), verts=sum(mb.n for mb in chunks.values()))
