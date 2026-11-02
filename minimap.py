"""GPS minimap and full map: a top-down orthographic camera drawn into its own corner of the window,
plus the glowing route line painted on the road.
"""
import math

from panda3d.core import BitMask32, Camera, OrthographicLens, Vec4
from ursina import Entity, Mesh, Text, camera, color, scene, window

import citymap as cm
from citybuild import MeshBuilder, ROAD_Y

MASK = BitMask32.bit(5)           # cameras with this bit see "minimap only" objects
ALL = BitMask32(0x7FFFFFFF)       # every ordinary bit (Panda reserves the top one)
ROUTE_COL = (40, 205, 255)


def minimap_only(e):
    e.hide(ALL)
    e.show(MASK)


def remaining_points(route, s):
    """The part of the route polyline ahead of distance s."""
    out = []
    for k in range(len(route.pts) - 1):
        if route.cum[k + 1] <= s:
            continue
        if not out:
            a, b = route.pts[k], route.pts[k + 1]
            u = max(0.0, (s - route.cum[k]) / ((route.cum[k + 1] - route.cum[k]) or 1))
            out.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
        out.append(route.pts[k + 1])
    return out


def ribbon(pts, width, y, col):
    b = MeshBuilder()
    h = width / 2
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        dx, dz = bx - ax, bz - az
        n = math.hypot(dx, dz) or 1
        px, pz = -dz / n * h, dx / n * h
        ex, ez = dx / n * h, dz / n * h
        b.quad((ax - ex + px, y, az - ez + pz), (ax - ex - px, y, az - ez - pz),
               (bx + ex - px, y, bz + ez - pz), (bx + ex + px, y, bz + ez + pz), col)
    return b


class RouteLine:
    """Route drawn on the road in the 3D view (thin) and on the map (thick)."""

    def __init__(self, parent):
        self.world = Entity(parent=parent)
        self.world.double_sided = True
        self.thick = Entity(parent=parent)
        self.thick.double_sided = True
        minimap_only(self.thick)
        self._key = None

    def clear(self):
        self.world.model = None
        self.thick.model = None
        self._key = None

    def update(self, route, version, s):
        if route is None:
            if self._key is not None:
                self.clear()
            return
        key = (version, int(s // 12))
        if key == self._key:
            return
        self._key = key
        pts = remaining_points(route, s)
        if len(pts) < 2:
            self.clear()
            return
        self.world.model = Mesh(vertices=(m := ribbon(pts, 2.0, ROAD_Y + .14, ROUTE_COL)).v, triangles=m.t, colors=m.c)
        self.thick.model = Mesh(vertices=(m2 := ribbon(pts, 14.0, ROAD_Y + 2.0, ROUTE_COL)).v, triangles=m2.t, colors=m2.c)


class Minimap:
    def __init__(self, app, parent):
        self.app = app
        self.mode = 'off'
        self.holder = Entity(parent=scene)
        lens = OrthographicLens()
        lens.setNearFar(1, 3000)
        lens.setFilmSize(400, 400)
        self.lens = lens
        node = Camera('minimap')
        node.setLens(lens)
        node.setCameraMask(MASK)
        self.cam_np = self.holder.attachNewNode(node)
        self.dr = app.win.makeDisplayRegion(.7, .98, .55, .98)
        self.dr.setCamera(self.cam_np)
        self.dr.setSort(5)
        self.dr.setClearColorActive(True)
        self.dr.setClearColor(Vec4(.06, .08, .12, 1))
        self.dr.setClearDepthActive(True)
        self.dr.setActive(False)
        # the normal camera must not see minimap-only objects
        app.cam.node().setCameraMask(BitMask32(0x7FFFFFFF & ~(1 << 5)))

        self.frame = Entity(parent=camera.ui, enabled=False)
        self.edges = [Entity(parent=self.frame, model='quad', color=color.gold) for _ in range(4)]
        self.title = Text('', parent=self.frame, origin=(0, 0), scale=.9, color=color.gold)
        self.hint = Text('', parent=self.frame, origin=(0, 0), scale=.75, color=color.light_gray)

        # minimap-only icons
        b = MeshBuilder()
        b.tri((-1, 0, -1), (1, 0, -1), (0, 0, 1.5), (255, 220, 40))
        self.arrow = Entity(parent=parent, model=Mesh(vertices=b.v, triangles=b.t, colors=b.c))
        self.arrow.double_sided = True
        minimap_only(self.arrow)
        self.icons = []
        self.pins = []

    def add_icon(self, x, z, col, size=1.0):
        e = Entity(parent=self.arrow.parent, model='circle', rotation_x=90, position=(x, ROAD_Y + 3, z), color=col)
        e.double_sided = True
        minimap_only(e)
        self.icons.append((e, size))
        return e

    def add_pin(self, col):
        e = Entity(parent=self.arrow.parent, model='circle', rotation_x=90, color=col, enabled=False)
        e.double_sided = True
        minimap_only(e)
        self.pins.append(e)
        return e

    # ---- layout ------------------------------------------------------------
    def set_mode(self, mode):
        self.mode = mode
        self.dr.setActive(mode != 'off')
        self.frame.enabled = mode != 'off'
        self.arrow.enabled = mode != 'off'
        for e, _ in self.icons:
            e.enabled = mode != 'off'
        self.layout()

    def layout(self):
        aspect = window.aspect_ratio
        if self.mode == 'mini':
            side = .30
            w = side / aspect
            l, r = .985 - w, .985
            b, t = .985 - side - .0, .985
            b = 1 - .015 - side
            t = 1 - .015
            l = 1 - .012 - side / aspect
            r = 1 - .012
            self.title.text = ''
            self.hint.text = 'M: big map'
        elif self.mode == 'full':
            h = .84
            w = min(.92, h / aspect)
            l, r = .5 - w / 2, .5 + w / 2
            b, t = .5 - h / 2, .5 + h / 2
            self.title.text = 'CITY MAP'
            self.hint.text = 'M: close'
        else:
            return
        self.dr.setDimensions(l, r, b, t)
        self.region_aspect = ((r - l) * aspect) / (t - b)
        ux0, ux1 = (l - .5) * aspect, (r - .5) * aspect
        uy0, uy1 = b - .5, t - .5
        th = .004
        cx, cy, w_, h_ = (ux0 + ux1) / 2, (uy0 + uy1) / 2, ux1 - ux0, uy1 - uy0
        spec = [(cx, uy1, w_ + th, th), (cx, uy0, w_ + th, th), (ux0, cy, th, h_), (ux1, cy, th, h_)]
        for e, (x, y, sx, sy) in zip(self.edges, spec):
            e.position, e.scale = (x, y), (sx, sy)
        self.title.position = (cx, uy1 + .025)
        self.hint.position = (cx, uy0 - .02)

    # ---- per-frame ---------------------------------------------------------
    def update(self, car):
        if self.mode == 'off':
            return
        if getattr(self, '_aspect', None) != window.aspect_ratio:
            self._aspect = window.aspect_ratio
            self.layout()
        fx, fz = car.fwd
        if self.mode == 'mini':
            film = 330 + min(abs(car.speed), 30) * 5
            self.holder.position = (car.x + fx * film * .18, 900, car.z + fz * film * .18)
            self.holder.rotation = (90, car.rotation_y, 0)
            fw = film
        else:
            fw = cm.SIZE * 1.12
            self.holder.position = (cm.CX0 + cm.SIZE / 2, 900, cm.CZ0 + cm.SIZE / 2)
            self.holder.rotation = (90, 0, 0)
        self.lens.setFilmSize(fw, fw / self.region_aspect)
        k = fw / 330.0
        self.arrow.position = (car.x, 600, car.z)
        self.arrow.rotation_y = car.rotation_y
        self.arrow.scale = 7 * k
        for e, size in self.icons:
            e.scale = 11 * k * size
        for e in self.pins:
            e.scale = 15 * k
