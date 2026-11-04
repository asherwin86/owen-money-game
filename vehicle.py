"""The delivery car (arcade driving over roads of different heights) and the AI traffic."""
import math
import random

from ursina import Entity

import citymap as cm
import game_data as gd
from citybuild import MeshBuilder
from citymap import ROAD_Y

WHEELBASE = 2.7
CAR_R = 1.15
CAR_H = 1.8
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
    return b.to_entity(parent)


class Car(Entity):
    """Shared by the player's car and AI cars. Position is x/z/y, heading is rotation_y (0 = north/+z)."""

    def __init__(self, parent, body, sign=None):
        super().__init__(parent=parent)
        car_mesh(self, body, sign)
        self.speed = 0.0

    @property
    def fwd(self):
        h = math.radians(self.rotation_y)
        return math.sin(h), math.cos(h)


def _hits(x, z, heading_deg, walls, y):
    """True if the car (two circles along its length) overlaps a wall at its height."""
    h = math.radians(heading_deg)
    fx, fz = math.sin(h), math.cos(h)
    r2 = CAR_R * CAR_R
    for off in (1.2, -1.2):
        cx, cz = x + fx * off, z + fz * off
        for wx, wz, ux, uz, hl, hw, y0, y1 in walls:
            if y + CAR_H <= y0 or y >= y1 - 0.6:
                continue
            rx, rz = cx - wx, cz - wz
            lx = rx * ux + rz * uz
            lz = -rx * uz + rz * ux
            qx = hl if lx > hl else (-hl if lx < -hl else lx)
            qz = hw if lz > hw else (-hw if lz < -hw else lz)
            if (lx - qx) ** 2 + (lz - qz) ** 2 < r2:
                return True
    return False


class PlayerCar(Car):
    def __init__(self, parent, level=0):
        super().__init__(parent, (230, 90, 50), sign=(250, 250, 250))
        self.steer = 0.0
        self.vy = 0.0
        self.level = level
        self.on_crash = lambda impact, kind: None
        self._crash_cd = 0.0
        self.safe = None
        self._safe_t = 0.0
        self.apply_level(level)

    def apply_level(self, level):
        self.level = level
        self.top = gd.car_top_speed(level)
        self.acc = gd.car_acceleration(level)

    def place(self, x, z, heading, y=ROAD_Y):
        self.x, self.z, self.y, self.rotation_y, self.rotation_x = x, z, y, heading, 0
        self.speed = self.vy = self.steer = 0.0
        self.safe = (x, z, heading, y)

    def step(self, dt, throttle, steer_in, handbrake, world, traffic=()):
        """Advance the car; fast cars are stepped in small pieces so they cannot jump through a thin rail."""
        dt = min(dt, 1 / 20)
        n = max(1, int(abs(self.speed) * dt / .8) + 1)
        for _ in range(n):
            self._step(dt / n, throttle, steer_in, handbrake, world, traffic)

    def _step(self, dt, throttle, steer_in, handbrake, world, traffic=()):
        v = self.speed
        top = self.top
        hgt, edge = world.surface(self.x, self.z, self.y)
        cap = top if edge is not None else top * .45
        if throttle > 0:
            v += (28 * dt) if v < 0 else self.acc * max(0.05, 1 - v / top) * dt * min(1.0, throttle)
        elif throttle < 0:
            v -= (26 * dt) if v > .3 else self.acc * .55 * dt
        else:
            v -= math.copysign(min(abs(v), 3.2 * dt), v)
        if handbrake:
            v -= math.copysign(min(abs(v), 30 * dt), v)
        if v > cap:
            v -= min(v - cap, 25 * dt)
        v = clamp(v, -8.0, top * 1.02)
        self.steer += (steer_in - self.steer) * min(1.0, 7 / (1 + abs(v) / 25) * dt)
        lock = 34 / (1 + (abs(v) / 18) ** 1.6)                    # less steering lock the faster you go
        yaw = v / WHEELBASE * math.tan(math.radians(self.steer * lock))
        yaw_cap = 32.0 / max(abs(v), 1.0)                         # at most about 3 g sideways
        yaw = max(-yaw_cap, min(yaw_cap, yaw))
        if handbrake and abs(v) > 6:
            yaw *= 1.5
        h = self.rotation_y + math.degrees(yaw * dt)
        hr = math.radians(h)
        nx, nz = self.x + math.sin(hr) * v * dt, self.z + math.cos(hr) * v * dt

        walls = world.walls_near(nx, nz)
        self._crash_cd = max(0.0, self._crash_cd - dt)
        crashed = None
        if _hits(nx, nz, h, walls, self.y):
            impact = abs(v)
            if not _hits(nx, self.z, h, walls, self.y):
                nz, v = self.z, v * .7
            elif not _hits(self.x, nz, h, walls, self.y):
                nx, v = self.x, v * .7
            else:
                nx, nz, h, v = self.x, self.z, self.rotation_y, -v * .25
            crashed = ('wall', impact)
        lim = cm.ROAD_W / 2 + 2
        cxl, cxh, czl, czh = cm.CX0 - lim, cm.CX0 + cm.SIZE + lim, cm.CZ0 - lim, cm.CZ0 + cm.SIZE + lim
        if not (cxl <= nx <= cxh and czl <= nz <= czh):
            nx, nz = clamp(nx, cxl, cxh), clamp(nz, czl, czh)
            crashed = crashed or ('edge', abs(v))
            v *= -.2
        for c in traffic:
            dx, dz = nx - c.x, nz - c.z
            if abs(dx) > 4 or abs(dz) > 4 or abs(c.y - self.y) > 2.5:
                continue
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

        # height: follow the road surface at our level, otherwise fall to the ground
        hgt, edge = world.surface(nx, nz, self.y)
        gy = cm.GROUND_Y
        if edge is not None:
            self.vy = 0.0
            self.y += (hgt - self.y) * min(1.0, 14 * dt)
            self._safe_t -= dt
            if self._safe_t <= 0 and abs(v) > 2 and abs(hgt - self.y) < .5 and not world.in_water(nx, nz):
                self.safe = (nx, nz, h, self.y)
                self._safe_t = .6
        elif self.y > gy + .15:
            self.vy -= 28 * dt
            self.y += self.vy * dt
            if self.y <= gy:
                impact = -self.vy
                self.y, self.vy = gy, 0.0
                if impact > 8:
                    self.on_crash(impact, 'fall')
        else:
            self.y = gy
            if world.in_water(nx, nz):
                self.splash()
        # tilt with the slope ahead
        ahead, _ = world.surface(nx + math.sin(hr) * 4, nz + math.cos(hr) * 4, self.y)
        slope = math.atan2((ahead - self.y) if ahead is not None else 0.0, 4.0)
        self.rotation_x += (-math.degrees(slope) - self.rotation_x) * min(1.0, 8 * dt)

    def splash(self):
        """Drove into the river: back to the last safe road point."""
        self.on_crash(18, 'water')
        if self.safe:
            self.place(*self.safe[:3], y=self.safe[3])


def _right(ux, uz):
    s = -1 if cm.DRIVE_LEFT else 1
    return (uz * s, -ux * s)


class TrafficCar(Car):
    """Follows the road graph: a position along an edge, a lane offset and smoothed turns."""

    def __init__(self, parent, rng):
        super().__init__(parent, rng.choice(BODY_COLORS))
        self.rng = rng
        self.edge, self.sgn, self.s = None, 1, 0.0
        self.nxt = None
        self.cruise_factor = rng.uniform(.55, .78)
        self.ox = self.oz = 0.0

    def spawn(self, edge, sgn, s):
        self.edge, self.sgn, self.s = edge, sgn, s
        self.nxt = self._choose_next()
        self.ox = self.oz = 0.0
        x, z, y, hd = self._target()
        self.x, self.z, self.y, self.rotation_y = x, z, y, hd
        self.rotation_x = 0
        self.speed = min(self.edge.speed * self.cruise_factor, 8.0)

    def _target(self):
        e, sgn = self.edge, self.sgn
        t = self.s / e.length if sgn == 1 else 1 - self.s / e.length
        x, z, y = e.pos(clamp(t, 0.0, 1.0))
        dx, dz = e.ux * sgn, e.uz * sgn
        rx, rz = _right(dx, dz)
        lane = e.width / 4
        return x + rx * lane, z + rz * lane, y, math.degrees(math.atan2(dx, dz))

    def _choose_next(self):
        e, sgn = self.edge, self.sgn
        node = e.b if sgn == 1 else e.a
        options, weights = [], []
        for f in node.edges:
            if f is e and len(node.edges) > 1:
                continue
            sgn2 = 1 if f.a is node else -1
            ang = math.atan2((e.ux * sgn) * (f.uz * sgn2) - (e.uz * sgn) * (f.ux * sgn2),
                             (e.ux * sgn) * (f.ux * sgn2) + (e.uz * sgn) * (f.uz * sgn2))
            w = 8.0 if abs(ang) < .6 else (1.5 if abs(ang) < 2.5 else 0.3)
            options.append((f, sgn2, ang))
            weights.append(w)
        pick = self.rng.choices(options, weights)[0]
        return pick

    def drive(self, dt, others):
        e = self.edge
        target = e.speed * self.cruise_factor
        if self.nxt and abs(self.nxt[2]) > .6 and e.length - self.s < 28:
            target = min(target, 6.0)
        fx, fz = self.fwd
        for o in others:
            if o is self:
                continue
            rx, rz = o.x - self.x, o.z - self.z
            if rx > 22 or rx < -22 or rz > 22 or rz < -22 or abs(o.y - self.y) > 3:
                continue
            ahead = rx * fx + rz * fz
            if 0 < ahead < 20 and abs(rx * fz - rz * fx) < 3.0:
                target = min(target, 0.0 if ahead < 8 else self.speed * (ahead - 8) / 12)
        self.speed += clamp(target - self.speed, -14 * dt, 4 * dt)
        old = (self.x, self.z)
        self.s += self.speed * dt
        if self.s >= e.length:
            self.s -= e.length
            f, sgn2, _ = self.nxt
            self.edge, self.sgn = f, sgn2
            self.nxt = self._choose_next()
            if self.s > f.length:
                self.s = 0.0
        tx, tz, ty, thd = self._target()
        # a decaying offset smooths the jump between lanes when changing road
        if self.ox == 0 and self.oz == 0 and (abs(old[0] - tx) > 2 or abs(old[1] - tz) > 2) and self.s < 3:
            self.ox, self.oz = old[0] - tx, old[1] - tz
        k = math.exp(-6 * dt)
        self.ox *= k
        self.oz *= k
        if abs(self.ox) < .02 and abs(self.oz) < .02:
            self.ox = self.oz = 0.0
        self.x, self.z, self.y = tx + self.ox, tz + self.oz, ty
        diff = (thd - self.rotation_y + 180) % 360 - 180
        self.rotation_y += diff * min(1.0, 7 * dt)


class Traffic:
    def __init__(self, parent, world, count=40, seed=77):
        self.world = world
        self.rng = random.Random(seed)
        self.cars = [TrafficCar(parent, self.rng) for _ in range(count)]
        self.fast_edges = [e for e in world.edges if e.kind in ('freeway', 'highway')]

    def scatter(self, around):
        for c in self.cars:
            self._respawn(c, around, 60, 600)

    def _respawn(self, car, around, rmin, rmax):
        edges = self.fast_edges if self.rng.random() < .3 else self.world.edges
        for _ in range(120):
            e = self.rng.choice(edges)
            mx, mz = (e.ax + e.bx) / 2, (e.az + e.bz) / 2
            if rmin <= math.hypot(mx - around[0], mz - around[1]) <= rmax:
                break
        else:
            e = self.rng.choice(self.world.edges)
        car.spawn(e, self.rng.choice((1, -1)), self.rng.uniform(0, e.length))

    def update(self, dt, player):
        dt = min(dt, 1 / 20)
        others = list(self.cars) + [player]
        for c in self.cars:
            if (c.x - player.x) ** 2 + (c.z - player.z) ** 2 > 900 ** 2:
                self._respawn(c, (player.x, player.z), 350, 750)
            c.drive(dt, others)
