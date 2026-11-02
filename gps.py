"""GPS: shortest-route planning over the street grid, turn-by-turn directions, and the minimap.

Routing is pure logic (no graphics) so it can be tested headless; the Minimap class needs a window.
"""
import heapq
import math

import citymap as cm

DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]       # east, north, west, south
TURN_COST = 18.0
UTURN_COST = 120.0
BEHIND_COST = 150.0                              # starting off against the direction you are facing


def node_pos(i, j):
    return (cm.avenue_x(i), cm.street_z(j))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _ends(pos):
    """Both road-junction ends of the segment a snapped position lies on.
    Returns [(node, distance, direction_of_travel_to_reach_it)]."""
    axis, idx, t = pos
    if axis == 'ns':
        j0 = _clamp(int((t - cm.CZ0) // cm.PITCH), 0, cm.NB - 1)
        return [((idx, j0), t - cm.street_z(j0), 3), ((idx, j0 + 1), cm.street_z(j0 + 1) - t, 1)]
    i0 = _clamp(int((t - cm.CX0) // cm.PITCH), 0, cm.NB - 1)
    return [((i0, idx), t - cm.avenue_x(i0), 2), ((i0 + 1, idx), cm.avenue_x(i0 + 1) - t, 0)]


def _xz(pos):
    axis, idx, t = pos
    return (cm.avenue_x(idx), t) if axis == 'ns' else (t, cm.street_z(idx))


def _segment_id(pos):
    axis, idx, t = pos
    if axis == 'ns':
        return (axis, idx, _clamp(int((t - cm.CZ0) // cm.PITCH), 0, cm.NB - 1))
    return (axis, idx, _clamp(int((t - cm.CX0) // cm.PITCH), 0, cm.NB - 1))


def _turn_penalty(d_in, d_out):
    if d_in is None or d_in == d_out:
        return 0.0
    return UTURN_COST if (d_in - d_out) % 4 == 2 else TURN_COST


class Route:
    def __init__(self, pts):
        self.pts = pts
        self.cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.length = self.cum[-1]
        self.steps = self._steps()
        self._seg = 0

    @staticmethod
    def _name(a, b):
        if abs(b[0] - a[0]) > abs(b[1] - a[1]):
            return cm.street_name(_clamp(round((a[1] - cm.CZ0) / cm.PITCH), 0, cm.NB))
        return cm.avenue_name(_clamp(round((a[0] - cm.CX0) / cm.PITCH), 0, cm.NB))

    def _steps(self):
        """Maneuvers: (distance along route, kind, road name after the maneuver)."""
        steps = []
        if len(self.pts) < 2:
            return [(0.0, 'arrive', '')]
        steps.append((0.0, 'depart', self._name(self.pts[0], self.pts[1])))
        for k in range(1, len(self.pts) - 1):
            a, b, c = self.pts[k - 1], self.pts[k], self.pts[k + 1]
            d1 = (b[0] - a[0], b[1] - a[1])
            d2 = (c[0] - b[0], c[1] - b[1])
            n1, n2 = math.hypot(*d1) or 1, math.hypot(*d2) or 1
            dot = (d1[0] * d2[0] + d1[1] * d2[1]) / (n1 * n2)
            cross = (d1[0] * d2[1] - d1[1] * d2[0]) / (n1 * n2)
            if dot > .9:
                continue
            kind = 'uturn' if dot < -.9 else ('left' if cross > 0 else 'right')
            steps.append((self.cum[k], kind, self._name(b, c)))
        steps.append((self.length, 'arrive', ''))
        return steps

    def project(self, x, z):
        """Distance travelled along the route and how far the point is from it."""
        best, best_s, best_off = None, 0.0, 1e9
        n = len(self.pts) - 1
        order = list(range(self._seg, n)) + list(range(0, self._seg))
        for k in order:
            ax, az = self.pts[k]
            bx, bz = self.pts[k + 1]
            dx, dz = bx - ax, bz - az
            l2 = dx * dx + dz * dz or 1e-9
            u = _clamp(((x - ax) * dx + (z - az) * dz) / l2, 0.0, 1.0)
            px, pz = ax + dx * u, az + dz * u
            off = math.hypot(x - px, z - pz)
            if off < best_off:
                best, best_off, best_s = k, off, self.cum[k] + math.sqrt(l2) * u
        self._seg = best if best is not None else 0
        return best_s, best_off

    def next_step(self, s):
        for st in self.steps:
            if st[0] > s + 1.0:
                return st
        return self.steps[-1]

    def remaining(self, s):
        return max(0.0, self.length - s)


def plan(start_xz, end_xz, heading=None):
    """Shortest route (with a small penalty per turn) between two world positions, or None."""
    S = cm.snap(*start_xz)
    E = cm.snap(*end_xz)
    sxz, exz = _xz(S), _xz(E)
    if _segment_id(S) == _segment_id(E):
        return Route([sxz, exz])
    starts = _ends(S)
    ends = {node: (dist, dr) for node, dist, dr in _ends(E)}   # node -> (distance to E, direction from E to node)

    def behind(d):
        if heading is None:
            return 0.0
        return BEHIND_COST if (DIRS[d][0] * heading[0] + DIRS[d][1] * heading[1]) < -.3 else 0.0

    heap, dist, prev = [], {}, {}
    for node, d0, dr in starts:
        st = (node[0], node[1], dr)
        c = d0 + behind(dr)
        if c < dist.get(st, 1e18):
            dist[st], prev[st] = c, None
            heapq.heappush(heap, (c, st))
    best_total, best_state = 1e18, None
    while heap:
        c, st = heapq.heappop(heap)
        if c > dist.get(st, 1e18) or c >= best_total:
            continue
        i, j, d = st
        if (i, j) in ends:
            dend, dr_from_e = ends[(i, j)]
            out_dir = (dr_from_e + 2) % 4                # direction travelled from the node toward E
            total = c + dend + _turn_penalty(d, out_dir)
            if total < best_total:
                best_total, best_state = total, st
        for d2, (dx, dz) in enumerate(DIRS):
            ni, nj = i + dx, j + dz
            if not (0 <= ni <= cm.NB and 0 <= nj <= cm.NB):
                continue
            nst = (ni, nj, d2)
            nc = c + cm.PITCH + _turn_penalty(d, d2)
            if nc < dist.get(nst, 1e18):
                dist[nst], prev[nst] = nc, st
                heapq.heappush(heap, (nc, nst))
    if best_state is None:
        return None
    nodes = []
    st = best_state
    while st is not None:
        nodes.append((st[0], st[1]))
        st = prev[st]
    nodes.reverse()
    pts = [sxz] + [node_pos(i, j) for i, j in nodes] + [exz]
    # drop zero-length / duplicate points
    clean = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > .5:
            clean.append(p)
    if len(clean) < 2:
        clean = [sxz, exz]
    return Route(clean)


KIND_TEXT = {'left': 'Turn left', 'right': 'Turn right', 'uturn': 'Make a U-turn'}


def describe(route, s):
    """('Turn left onto Oak Ave', metres to it, kind) for the next maneuver."""
    when, kind, name = route.next_step(s)
    dist = max(0.0, when - s)
    if kind == 'arrive':
        return ('Arrive at your destination', dist, kind)
    if kind == 'depart':
        return (f'Head along {name}', dist, kind)
    return (f'{KIND_TEXT[kind]} onto {name}', dist, kind)


def fmt_dist(m):
    if m >= 1000:
        return f'{m / 1000:.1f} km'
    return f'{int(round(m / 10.0) * 10)} m' if m >= 100 else f'{int(m)} m'


class Navigator:
    """Holds the current destination and keeps a route to it, rerouting when you leave it."""

    def __init__(self):
        self.target = None          # (x, z)
        self.label = ''
        self.route = None
        self.s = 0.0
        self.version = 0            # increments whenever the route changes (to redraw the line)
        self._cool = 0.0
        self.heading = (0.0, 1.0)

    def set_target(self, xz, label=''):
        self.target, self.label, self.route, self._cool = xz, label, None, 0.0

    def clear(self):
        self.target, self.label, self.route = None, '', None
        self.version += 1

    def update(self, dt, x, z, heading):
        self._cool = max(0.0, self._cool - dt)
        self.heading = heading
        if self.target is None:
            return
        need = self.route is None
        if self.route is not None:
            self.s, off = self.route.project(x, z)
            need = off > 35.0 and self._cool <= 0
        if need and self._cool <= 0:
            self.route = plan((x, z), self.target, heading)
            self.s = 0.0
            self._cool = 1.5
            self.version += 1
            if self.route is not None:
                self.s, _ = self.route.project(x, z)

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
