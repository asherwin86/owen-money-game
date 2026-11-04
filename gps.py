"""GPS: fastest-route planning over the road graph, turn-by-turn directions and a route follower.

Costs are travel times (length / speed limit) plus small penalties for turns, so routes use freeways and
highways when they save time. Pure logic (no graphics) so it can be tested without a window.
"""
import heapq
import math

import citymap as cm

TURN_COST = 4.0          # seconds
UTURN_COST = 35.0
BEHIND_COST = 25.0       # starting off against the way the car is facing
MAX_SPEED = 50.0
SAMPLE = 25.0            # metres between route points


class Route:
    def __init__(self, pts, steps, time, end_xz):
        self.pts = pts                      # (x, z, y) every ~25 m
        self.steps = steps                  # (distance along route, kind, text)
        self.time = time                    # seconds at the speed limits
        self.end_xz = end_xz
        self.cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.length = self.cum[-1]
        self._seg = 0

    def project(self, x, z, y):
        """(distance along the route, how far off it) - 'off' includes a penalty for being on another level."""
        n = len(self.pts) - 1
        if n < 1:
            return 0.0, 0.0
        best = None
        for window in ((max(0, self._seg - 12), min(n, self._seg + 40)), (0, n)):
            best = None
            for k in range(window[0], window[1]):
                ax, az, ay = self.pts[k]
                bx, bz, by = self.pts[k + 1]
                dx, dz = bx - ax, bz - az
                l2 = dx * dx + dz * dz or 1e-9
                u = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / l2))
                d = math.hypot(x - (ax + dx * u), z - (az + dz * u)) + 0.9 * abs(ay + (by - ay) * u - y)
                if best is None or d < best[0]:
                    best = (d, k, self.cum[k] + math.sqrt(l2) * u)
            if best[0] < 30:
                break
        self._seg = best[1]
        return best[2], best[0]

    def next_step(self, s):
        for st in self.steps:
            if st[0] > s + 1.0:
                return st
        return self.steps[-1]

    def remaining(self, s):
        return max(0.0, self.length - s)


def _turn_angle(tin, tout):
    return math.atan2(tin[0] * tout[1] - tin[1] * tout[0], tin[0] * tout[0] + tin[1] * tout[1])


def _turn_cost(angle):
    a = abs(angle)
    if a < 0.6:
        return 0.0
    return TURN_COST if a < 2.6 else UTURN_COST


def _maneuver(prev, nxt, angle):
    """(kind, text) for the transition from edge prev to edge nxt, or None if nothing to say."""
    if nxt.kind == 'ramp' and prev.kind != 'ramp':
        if prev.kind == 'freeway':
            return 'exit', f'Take the exit toward {nxt.links[0]}'
        return 'ramp', f'Take the ramp to {nxt.links[1]}'
    if prev.kind == 'ramp' and nxt.kind == 'freeway':
        return 'merge', f'Merge onto {nxt.name}'
    if nxt.bridge and nxt.bridge != prev.bridge:
        return 'bridge', f'Cross {nxt.bridge}'
    a = abs(angle)
    if a < 0.5:
        if nxt.name != prev.name and not (prev.bridge and nxt.name == prev.name):
            return 'straight', f'Continue onto {nxt.name}'
        return None
    if a > 2.6:
        return 'uturn', 'Make a U-turn'
    side = 'left' if angle > 0 else 'right'
    return side, f'Turn {side} onto {nxt.name}'


def plan(world, start, end, heading=None):
    """Fastest route from start (x, z, y) to end (x, z) as a Route, or None."""
    sy = start[2] if len(start) > 2 else cm.ROAD_Y
    s_hit = world.nearest_edge_point(start[0], start[1], sy, reach=3)
    d_hit = world.nearest_edge_point(end[0], end[1], cm.ROAD_Y, reach=3)
    if not s_hit or not d_hit:
        return None
    se, st, _ = s_hit
    de, du, _ = d_hit
    end_xz = (end[0], end[1])

    if se is de:
        return _build(world, [(se, st, du)], end_xz)

    def behind(sgn):
        if heading is None:
            return 0.0
        return BEHIND_COST if (se.ux * sgn * heading[0] + se.uz * sgn * heading[1]) < -.3 else 0.0

    heap, g, prev = [], {}, {}
    tx, tz = end_xz

    def h(node):
        return math.hypot(node.x - tx, node.z - tz) / MAX_SPEED

    for sgn in (1, -1):
        node = se.b if sgn == 1 else se.a
        t_to = 1.0 if sgn == 1 else 0.0
        cost = abs(t_to - st) * se.length / se.speed + behind(sgn)
        state = (se.id, sgn)
        g[state] = cost
        prev[state] = None
        heapq.heappush(heap, (cost + h(node), cost, state))
    best_total, best_state, best_final = 1e18, None, None
    edges = world.edges
    while heap:
        f, cost, state = heapq.heappop(heap)
        if f >= best_total:
            break
        if cost > g.get(state, 1e18):
            continue
        eid, sgn = state
        e = edges[eid]
        node = e.b if sgn == 1 else e.a
        if node is de.a or node is de.b:
            if node is de.a:
                final = du * de.length / de.speed
                seg = (de, 0.0, du)
            else:
                final = (1 - du) * de.length / de.speed
                seg = (de, 1.0, du)
            if cost + final < best_total:
                best_total, best_state, best_final = cost + final, state, seg
        tin = (e.ux * sgn, e.uz * sgn)
        for f_edge in node.edges:
            sgn2 = 1 if f_edge.a is node else -1
            if f_edge is e and len(node.edges) > 1:
                continue
            tout = (f_edge.ux * sgn2, f_edge.uz * sgn2)
            nxt_node = f_edge.b if sgn2 == 1 else f_edge.a
            nc = cost + f_edge.length / f_edge.speed + _turn_cost(_turn_angle(tin, tout))
            ns = (f_edge.id, sgn2)
            if nc < g.get(ns, 1e18):
                g[ns] = nc
                prev[ns] = state
                heapq.heappush(heap, (nc + h(nxt_node), nc, ns))
    if best_state is None:
        return None
    chain = []
    s = best_state
    while s is not None:
        chain.append(s)
        s = prev[s]
    chain.reverse()
    segs = []
    for k, (eid, sgn) in enumerate(chain):
        e = edges[eid]
        if k == 0:
            segs.append((e, st, 1.0 if sgn == 1 else 0.0))
        else:
            segs.append((e, 0.0, 1.0) if sgn == 1 else (e, 1.0, 0.0))
    segs.append(best_final)
    return _build(world, segs, end_xz)


def _build(world, segs, end_xz):
    pts, steps, total_time = [], [], 0.0
    dist = 0.0
    prev_dir = None
    for k, (e, t0, t1) in enumerate(segs):
        first_pt = len(pts) if k == 0 else len(pts)
        length = abs(t1 - t0) * e.length
        total_time += length / e.speed
        n = max(1, int(math.ceil(length / SAMPLE)))
        if e.hump is not None:
            n = max(n, int(math.ceil(length / 12.0)))
        for i in range(n + 1):
            if i == 0 and pts and k > 0:
                continue
            x, z, y = e.pos(t0 + (t1 - t0) * i / n)
            pts.append((x, z, y))
        sgn = 1 if t1 >= t0 else -1
        tdir = (e.ux * sgn, e.uz * sgn)
        side = -1 if cm.DRIVE_LEFT else 1
        lane = e.width / 4
        ox, oz = tdir[1] * side * lane, -tdir[0] * side * lane       # route runs in the right-hand lane
        for j in range(first_pt, len(pts)):
            pts[j] = (pts[j][0] + ox, pts[j][1] + oz, pts[j][2])
        if k == 0:
            steps.append((0.0, 'depart', f'Head along {e.name}'))
        else:
            pe = segs[k - 1][0]
            man = _maneuver(pe, e, _turn_angle(prev_dir, tdir))
            if man:
                steps.append((dist, man[0], man[1]))
        dist += length
        prev_dir = tdir
    steps.append((dist, 'arrive', 'Arrive at your destination'))
    # steps carry distances along the sampled polyline, which equals the summed segment lengths
    return Route(pts, steps, total_time, end_xz)


def describe(route, s):
    """(text, metres to it, kind) for the next maneuver."""
    when, kind, text = route.next_step(s)
    return (text, max(0.0, when - s), kind)


def fmt_dist(m):
    if m >= 1000:
        return f'{m / 1000:.1f} km'
    return f'{int(round(m / 10.0) * 10)} m' if m >= 100 else f'{int(m)} m'


def fmt_time(seconds):
    seconds = int(max(0, seconds))
    return f'{seconds // 60}:{seconds % 60:02d}'


class Navigator:
    """Holds the current destination and keeps a route to it, rerouting when you leave it."""

    def __init__(self, world):
        self.world = world
        self.target = None          # (x, z)
        self.label = ''
        self.route = None
        self.s = 0.0
        self.off = 0.0
        self.version = 0            # increments whenever the route changes (to redraw the line)
        self._cool = 0.0
        self.heading = (0.0, 1.0)

    def set_target(self, xz, label=''):
        self.target, self.label, self.route, self._cool = xz, label, None, 0.0

    def clear(self):
        self.target, self.label, self.route = None, '', None
        self.version += 1

    def update(self, dt, x, z, y, heading):
        self._cool = max(0.0, self._cool - dt)
        self.heading = heading
        if self.target is None:
            return
        need = self.route is None
        if self.route is not None:
            self.s, self.off = self.route.project(x, z, y)
            need = self.off > 40.0 and self._cool <= 0
        if need and self._cool <= 0:
            self.route = plan(self.world, (x, z, y), self.target, heading)
            self.s = 0.0
            self._cool = 1.5
            self.version += 1
            if self.route is not None:
                self.s, self.off = self.route.project(x, z, y)

    def instruction(self):
        if self.route is None:
            return None
        text, dist, kind = describe(self.route, self.s)
        r = self.route
        if kind == 'depart' and len(r.pts) > 1 and self.s < 15:
            dx, dz = r.pts[1][0] - r.pts[0][0], r.pts[1][1] - r.pts[0][1]
            n = math.hypot(dx, dz) or 1
            if (dx * self.heading[0] + dz * self.heading[1]) / n < -.3:
                return ('Make a U-turn when it is safe', 0.0, 'uturn')
        return (text, dist, kind)

    def remaining(self):
        return self.route.remaining(self.s) if self.route else 0.0

    def remaining_time(self):
        if not self.route or self.route.length <= 0:
            return 0.0
        return self.route.time * self.remaining() / self.route.length
