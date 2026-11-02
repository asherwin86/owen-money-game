"""The delivery car (arcade driving) and the AI traffic."""
import math
import random

from ursina import Entity, Vec3, time

import citymap as cm
from citybuild import MeshBuilder, ROAD_Y, LAWN_Y
from gps import DIRS, node_pos

DRIVE_LEFT = False                 # set True for left-hand traffic
LANE = 3.0                         # lane centre offset from the road centre line
WHEELBASE = 2.7
CAR_R = 1.15
BODY_COLORS = [(214, 60, 52), (60, 110, 200), (240, 240, 236), (40, 44, 50), (240, 190, 50), (70, 160, 100),
               (150, 150, 156), (150, 70, 170), (230, 120, 40)]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def car_mesh(parent, body, sign=None):
    b = MeshBuilder()
    glass, dark = (46, 66, 86), (28, 28, 32)
    b.box(-.95, .35, -2.1, .95, 1.0, 2.1, body)
    b.box(-.8, 1.0, -1.15, .8, 1.5, .95, glass)
    b.box(-.82, 1.5, -1.2, .82, 1.58, 1.0, body)
    for sx in (-1, 1):
        for z in (-1.3, 1.3):
            xa, xb = sx * .8, sx * 1.1
            b.box(min(xa, xb), 0, z - .38, max(xa, xb), .72, z + .38, dark)
    for sx in (-.65, .65):
        b.quad((sx - .22, .55, 2.11), (sx + .22, .55, 2.11), (sx + .22, .75, 2.11), (sx - .22, .75, 2.11), (255, 240, 170))
        b.quad((sx - .22, .55, -2.11), (sx + .22, .55, -2.11), (sx + .22, .75, -2.11), (sx - .22, .75, -2.11), (220, 40, 40))
    if sign:
        b.box(-.4, 1.58, -.3, .4, 1.95, .3, sign)
    e = b.to_entity(parent)
    return e


class Car(Entity):
    """Shared by the player's car and AI cars. Position is x/z, heading is rotation_y (0 = north/+z)."""

    def __init__(self, parent, body, sign=None):
        super().__init__(parent=parent)
        car_mesh(self, body, sign)
        self.speed = 0.0

    @property
    def fwd(self):
        h = math.radians(self.rotation_y)
        return math.sin(h), math.cos(h)


def _hits(x, z, heading_deg, rects):
    h = math.radians(heading_deg)
    fx, fz = math.sin(h), math.cos(h)
    for off in (1.2, -1.2):
        cx, cz = x + fx * off, z + fz * off
        for x0, z0, x1, z1 in rects:
            px = min(max(cx, x0), x1)
            pz = min(max(cz, z0), z1)
            if (cx - px) ** 2 + (cz - pz) ** 2 < CAR_R * CAR_R:
                return True
    return False


class PlayerCar(Car):
    def __init__(self, parent, level=0):
        super().__init__(parent, (230, 90, 50), sign=(250, 250, 250))
        self.steer = 0.0
        self.level = level
        self.on_crash = lambda impact, kind: None
        self._crash_cd = 0.0
        self.apply_level(level)

    def apply_level(self, level):
        self.level = level
        self.top = 21.0 + 2.6 * level
        self.acc = 8.5 + 1.4 * level

    def place(self, x, z, heading):
        self.x, self.z, self.rotation_y = x, z, heading
        self.y = ROAD_Y
        self.speed = 0.0
        self.steer = 0.0

    def step(self, dt, throttle, steer_in, handbrake, city, traffic=()):
        dt = min(dt, 1 / 20)
        v = self.speed
        top = self.top
        road = cm.on_road(self.x, self.z)
        cap = top if road else top * .45
        if throttle > 0:
            v += (28 * dt) if v < 0 else self.acc * max(0.05, 1 - v / top) * dt
        elif throttle < 0:
            v -= (26 * dt) if v > .3 else self.acc * .55 * dt
        else:
            v -= math.copysign(min(abs(v), 3.2 * dt), v)
        if handbrake:
            v -= math.copysign(min(abs(v), 30 * dt), v)
        if v > cap:
            v -= min(v - cap, 25 * dt)
        v = clamp(v, -8.0, top * 1.02)
        self.steer += (steer_in - self.steer) * min(1.0, 7 * dt)
        lock = 34 - 26 * min(1.0, abs(v) / (top * .9))
        yaw = v / WHEELBASE * math.tan(math.radians(self.steer * lock))
        if handbrake and abs(v) > 6:
            yaw *= 1.5
        h = self.rotation_y + math.degrees(yaw * dt)
        hr = math.radians(h)
        nx, nz = self.x + math.sin(hr) * v * dt, self.z + math.cos(hr) * v * dt

        solids = city.solids_near(nx, nz)
        self._crash_cd = max(0.0, self._crash_cd - dt)
        crashed = None
        if _hits(nx, nz, h, solids):
            impact = abs(v)
            if not _hits(nx, self.z, h, solids):
                nz, v = self.z, v * .7
            elif not _hits(self.x, nz, h, solids):
                nx, v = self.x, v * .7
            else:
                nx, nz, h, v = self.x, self.z, self.rotation_y, -v * .25
            crashed = ('building', impact)
        # city edge
        lim = cm.ROAD_W / 2 + 2
        cxl, cxh, czl, czh = cm.CX0 - lim, cm.CX0 + cm.SIZE + lim, cm.CZ0 - lim, cm.CZ0 + cm.SIZE + lim
        if not (cxl <= nx <= cxh and czl <= nz <= czh):
            nx, nz = clamp(nx, cxl, cxh), clamp(nz, czl, czh)
            crashed = crashed or ('edge', abs(v))
            v *= -.2
        # other cars
        for c in traffic:
            dx, dz = nx - c.x, nz - c.z
            d2 = dx * dx + dz * dz
            if d2 < 3.6 * 3.6:
                d = math.sqrt(d2) or .01
                nx += dx / d * (3.6 - d) * .6
                nz += dz / d * (3.6 - d) * .6
                crashed = crashed or ('car', abs(v - c.speed) + 2)
                v *= .5
                c.speed *= .4
        if crashed and crashed[1] > 4 and self._crash_cd <= 0:
            self._crash_cd = .6
            self.on_crash(crashed[1], crashed[0])
        self.speed = v
        self.x, self.z, self.rotation_y = nx, nz, h
        target_y = ROAD_Y if cm.on_road(nx, nz) else LAWN_Y
        self.y += (target_y - self.y) * min(1.0, 12 * dt)


def _right(d):
    dx, dz = DIRS[d]
    s = -1 if DRIVE_LEFT else 1
    return (dz * s, -dx * s)


class TrafficCar(Car):
    def __init__(self, parent, rng):
        super().__init__(parent, rng.choice(BODY_COLORS))
        self.rng = rng
        self.cruise = rng.uniform(8.5, 13.0)
        self.node, self.dir = (0, 0), 0
        self.wp = []
        self.steer_deg = 0.0

    def spawn(self, node, d):
        self.node, self.dir = node, d
        nx, nz = node_pos(*node)
        rx, rz = _right(d)
        dx, dz = DIRS[d]
        self.x, self.z = nx - dx * 45 + rx * LANE, nz - dz * 45 + rz * LANE
        self.y = ROAD_Y
        self.rotation_y = math.degrees(math.atan2(dx, dz))
        self.speed = self.cruise * .5
        self.wp = []
        self.extend()

    def extend(self):
        while len(self.wp) < 3:
            i, j = self.node
            d = self.dir
            options = []
            for d2, w in ((d, 6), ((d + 1) % 4, 2), ((d - 1) % 4, 2)):
                ni, nj = i + DIRS[d2][0], j + DIRS[d2][1]
                if 0 <= ni <= cm.NB and 0 <= nj <= cm.NB:
                    options.append((d2, w))
            d2 = self.rng.choices([o[0] for o in options], [o[1] for o in options])[0]
            nx, nz = node_pos(i, j)
            rin, rout = _right(d), _right(d2)
            self.wp.append((nx - DIRS[d][0] * 14 + rin[0] * LANE, nz - DIRS[d][1] * 14 + rin[1] * LANE))
            self.wp.append((nx + DIRS[d2][0] * 14 + rout[0] * LANE, nz + DIRS[d2][1] * 14 + rout[1] * LANE))
            self.node, self.dir = (i + DIRS[d2][0], j + DIRS[d2][1]), d2

    def drive(self, dt, others):
        tx, tz = self.wp[0]
        dx, dz = tx - self.x, tz - self.z
        dist = math.hypot(dx, dz)
        if dist < 5 or (dist < 16 and len(self.wp) > 1 and dx * self.fwd[0] + dz * self.fwd[1] < 0):
            self.wp.pop(0)
            self.extend()
            tx, tz = self.wp[0]
            dx, dz = tx - self.x, tz - self.z
        want = math.degrees(math.atan2(dx, dz))
        err = (want - self.rotation_y + 180) % 360 - 180
        steer = clamp(err * 1.0, -32, 32)
        self.rotation_y += math.degrees(self.speed / WHEELBASE * math.tan(math.radians(steer)) * dt)
        target = self.cruise if abs(err) < 25 else 5.0
        fx, fz = self.fwd
        for o in others:
            if o is self:
                continue
            rx, rz = o.x - self.x, o.z - self.z
            if rx > 18 or rx < -18 or rz > 18 or rz < -18:
                continue
            ahead = rx * fx + rz * fz
            if 0 < ahead < 16 and abs(rx * fz - rz * fx) < 3.0:
                target = min(target, 0.0 if ahead < 8 else self.cruise * (ahead - 8) / 8)
        self.speed += clamp(target - self.speed, -14 * dt, 6 * dt)
        h = math.radians(self.rotation_y)
        self.x += math.sin(h) * self.speed * dt
        self.z += math.cos(h) * self.speed * dt


class Traffic:
    def __init__(self, parent, count=40, seed=77):
        self.rng = random.Random(seed)
        self.cars = [TrafficCar(parent, self.rng) for _ in range(count)]
        self._t = 0.0

    def scatter(self, around):
        for c in self.cars:
            self._respawn(c, around, 0, 500)

    def _respawn(self, car, around, rmin, rmax):
        for _ in range(30):
            i = self.rng.randint(0, cm.NB)
            j = self.rng.randint(0, cm.NB)
            nx, nz = node_pos(i, j)
            if rmin <= math.hypot(nx - around[0], nz - around[1]) <= rmax:
                break
        car.spawn((i, j), self.rng.randrange(4))
        # start it a little way along so it doesn't spawn on top of the player
        if math.hypot(car.x - around[0], car.z - around[1]) < 40:
            car.x += DIRS[car.dir][0] * 120
            car.z += DIRS[car.dir][1] * 120

    def update(self, dt, player):
        dt = min(dt, 1 / 20)
        others = list(self.cars) + [player]
        for c in self.cars:
            if (c.x - player.x) ** 2 + (c.z - player.z) ** 2 > 750 ** 2:
                self._respawn(c, (player.x, player.z), 250, 550)
            c.drive(dt, others)
