"""Food Delivery job: the driving session (car, traffic, GPS, orders, pay) for the city scene."""
import math
import random

from ursina import Entity, Text, Vec2, Vec3, camera, color, held_keys, scene, window

import citymap as cm
import controls as pad
import citybuild
import gps
import minimap as mm
import vehicle as vh
import game_data as gd

OFFER_SECONDS = 20.0
ARRIVE_R = 10.0
ARRIVE_SPEED = 7.0


def lane_heading(lot):
    """Heading (degrees) that puts the lot's curb on the right-hand side of the car."""
    road_dx, road_dz = lot.tx, lot.tz
    cx = lot.curb_pt[0] - lot.road_pt[0]
    cz = lot.curb_pt[1] - lot.road_pt[1]
    for sgn in (1, -1):
        dx, dz = road_dx * sgn, road_dz * sgn
        rx, rz = dz, -dx
        if cm.DRIVE_LEFT:
            rx, rz = -rx, -rz
        if rx * cx + rz * cz > 0:
            return math.degrees(math.atan2(dx, dz))
    return 0.0


class Order:
    def __init__(self, restaurant, rlot, clot, dist, route_time):
        self.restaurant, self.rlot, self.clot = restaurant, rlot, clot
        self.state = 'offer'                      # offer -> pickup -> dropoff
        self.dist = dist                          # length of the fastest route from restaurant to customer
        self.fare = 25 + dist * 0.075
        self.allowed = route_time * 1.5 + 50      # seconds from pickup
        self.elapsed = 0.0
        self.quality = 100.0
        self.age = 0.0

    @property
    def target(self):
        return self.rlot if self.state == 'pickup' else self.clot

    def pay(self, rating_mult):
        late = self.elapsed - self.allowed
        on_time = late <= 0
        bonus = 0.0
        if on_time:
            bonus = self.fare * .35 * max(0.0, min(1.0, (self.allowed - self.elapsed) / self.allowed))
        tip = self.fare * (.30 if on_time else .08)
        q = max(.25, self.quality / 100.0)
        base = self.fare + bonus + tip
        return base * q * rating_mult, on_time, bonus, tip


class DriveSession:
    def __init__(self, app, S, root, notify, earn, open_panel, close_panel, leave_cb):
        self.app, self.S, self.root = app, S, root
        self.notify, self.earn, self.open_panel, self.close_panel, self.leave_cb = notify, earn, open_panel, close_panel, leave_cb
        self.active = False
        self.built = False
        self.rng = random.Random()
        self._hud_made = False

    # ---- one-time build --------------------------------------------------
    def build(self):
        if self.built:
            return
        self.city = cm.World()
        self.scene = citybuild.CityScene(self.root, self.city)
        self.car = vh.PlayerCar(self.root, gd.car_level(self.S))
        self.car.on_crash = self.on_crash
        self.traffic = vh.Traffic(self.root, self.city, 40)
        self.nav = gps.Navigator(self.city)
        self.minimap = mm.Minimap(self.app, self.root)
        self.minimap.add_map_layer(self.city)
        dep = self.city.depot
        self.scene.prime(dep.curb_pt[0], dep.curb_pt[1], 650)
        for r, lot in self.city.restaurants:
            self.minimap.add_icon(lot.curb_pt[0], lot.curb_pt[1], color.rgb32(*r['color']))
        self.minimap.add_icon(self.city.depot.curb_pt[0], self.city.depot.curb_pt[1], color.rgb32(60, 120, 220), 1.3)
        self.pin_target = self.minimap.add_pin(color.rgb32(255, 255, 255))
        self.route_line = mm.RouteLine(self.root)
        self.beacon = Entity(parent=self.root, model='cube', scale=(1.5, 70, 1.5), color=color.rgba32(255, 160, 40, 110),
                             enabled=False)
        self.beacon.double_sided = True
        self.beacon_label = Text('', parent=self.root, origin=(0, 0), scale=13, billboard=True, enabled=False)
        self._make_hud()
        self.orders, self.offer = [], None
        self.manual = None
        self.shift = dict(deliveries=0, earned=0.0, start_rating=self.S['delivery']['rating'])
        self.cooldown = 3.0
        self.banner_t = 0.0
        self.abandon_t = 0.0
        self.built = True

    def _make_hud(self):
        ui = camera.ui
        self.h_speed = Text('', parent=ui, position=window.bottom_right + Vec2(-.03, .09), origin=(.5, -.5), scale=2.6, color=color.white)
        self.h_street = Text('', parent=ui, position=(0, -.44), origin=(0, 0), scale=1.4, color=color.light_gray)
        self.h_turn = Text('', parent=ui, position=(0, .415), origin=(0, 0), scale=2.1, color=color.white)
        self.h_turn2 = Text('', parent=ui, position=(0, .355), origin=(0, 0), scale=1.05, color=color.light_gray)
        self.h_orders = Text('', parent=ui, position=window.left + Vec2(.02, .1), origin=(-.5, .5), scale=1.05, color=color.white)
        self.h_offer = Text('', parent=ui, position=(0, .235), origin=(0, 0), scale=1.3, color=color.yellow)
        self.h_prompt = Text('', parent=ui, position=(0, -.32), origin=(0, 0), scale=1.5, color=color.yellow)
        self.h_banner = Text('', parent=ui, position=(0, .12), origin=(0, 0), scale=3, color=color.lime)
        self.h_help = Text(pad.hint('drive'), parent=ui,
                           position=window.bottom_left + Vec2(.02, .025), origin=(-.5, -.5), scale=.75, color=color.light_gray)
        def backing(x, y, w, h):
            return Entity(parent=ui, model='quad', color=color.rgba32(8, 12, 24, 150), position=(x, y), scale=(w, h), z=1)

        self.bk_turn = backing(0, .385, 1.1, .14)
        self.bk_offer = backing(0, .235, 1.1, .1)
        self.bk_speed = backing(window.right.x - .17, -.41, .3, .1)
        self.bk_street = backing(0, -.44, .85, .05)
        self.huds = [self.bk_turn, self.bk_offer, self.bk_speed, self.bk_street, self.h_speed, self.h_street, self.h_turn, self.h_turn2, self.h_orders, self.h_offer,
                     self.h_prompt, self.h_banner, self.h_help]

    def _show_hud(self, on):
        for h in self.huds:
            h.enabled = on

    # ---- enter / leave -----------------------------------------------------
    def apply_upgrades(self):
        if self.built:
            self.car.apply_level(gd.car_level(self.S))

    def enter(self):
        self.build()
        self.apply_upgrades()
        self._saved_cam = (camera.parent, Vec3(*camera.position), Vec3(*camera.rotation), camera.fov,
                           camera.clip_plane_near)
        camera.parent = scene
        camera.clip_plane_near = 2.5
        camera.fov = 82
        lot = self.city.depot
        self.car.place(lot.curb_pt[0], lot.curb_pt[1], lane_heading(lot))
        self.traffic.scatter((self.car.x, self.car.z))
        self.orders, self.offer, self.manual = [], None, None
        self.shift = dict(deliveries=0, earned=0.0, start_rating=self.S['delivery']['rating'])
        self.cooldown = 3.0
        self.nav.clear()
        self._snap_camera()
        self.minimap.set_mode('mini')
        self._show_hud(True)
        self.active = True
        self.notify('Shift started. Orders will pop up: press Y to accept.')

    def leave(self):
        self.active = False
        self.minimap.set_mode('off')
        self.route_line.clear()
        self.beacon.enabled = self.beacon_label.enabled = self.pin_target.enabled = False
        self._show_hud(False)
        par, pos, rot, fov, near = self._saved_cam
        camera.parent = par
        camera.position, camera.rotation = pos, rot
        camera.fov, camera.clip_plane_near = fov, near
        sh = self.shift
        if sh['deliveries']:
            self.notify(f'Shift over: {sh["deliveries"]} deliveries, {gd.fmt(sh["earned"])} earned.')

    # ---- camera ----------------------------------------------------------
    def _cam_target(self):
        c = self.car
        fx, fz = c.fwd
        back = 10.5 + abs(c.speed) * .09
        up = 4.6 + abs(c.speed) * .03
        return Vec3(c.x - fx * back, c.y + up, c.z - fz * back), Vec3(c.x + fx * 6, c.y + 1.3, c.z + fz * 6)

    @staticmethod
    def _aim(pos, look):
        """Point the camera at look without roll (Ursina's look_at tilts the horizon at some headings)."""
        dx, dy, dz = look[0] - pos[0], look[1] - pos[1], look[2] - pos[2]
        camera.rotation = Vec3(math.degrees(math.atan2(-dy, math.hypot(dx, dz))), math.degrees(math.atan2(dx, dz)), 0)

    def _snap_camera(self):
        pos, look = self._cam_target()
        camera.position = pos
        self._aim(pos, look)

    def _follow_camera(self, dt):
        pos, look = self._cam_target()
        k = 1 - math.exp(-9 * dt)
        camera.position = camera.position + (pos - camera.position) * k
        self._aim(camera.position, look)
        camera.fov = 82 + min(abs(self.car.speed), 56) * .3

    # ---- crashes -----------------------------------------------------------
    def on_crash(self, impact, kind):
        carried = [o for o in self.orders if o.state == 'dropoff']
        if not carried:
            return
        loss = min(22.0, impact * 1.1)
        for o in carried:
            o.quality = max(0.0, o.quality - loss)
        self.notify(f'Crash! The food got shaken up (-{int(loss)}% quality).')

    # ---- orders ------------------------------------------------------------
    def _new_offer(self):
        """A restaurant and a customer far enough apart that the trip needs real navigation."""
        r, rlot = self.rng.choice(self.city.restaurants)
        best = None
        for _ in range(14):
            clot = self.city.random_house(self.rng, rlot.curb_pt, 700, 4200)
            route = gps.plan(self.city, (rlot.curb_pt[0], rlot.curb_pt[1], cm.ROAD_Y), clot.curb_pt)
            if route and 900 <= route.length <= 7000:
                best = (clot, route)
                break
            if route and best is None:
                best = (clot, route)
        clot, route = best
        order = Order(r, rlot, clot, route.length, route.time)
        order.state = 'offer'
        self.offer = order

    def _accept(self):
        o, self.offer = self.offer, None
        o.state = 'pickup'
        self.orders.append(o)
        self.notify(f'Accepted: {o.restaurant["name"]} to {o.clot.address}')
        self._retarget()

    def _decline(self, expired=False):
        self.offer = None
        self.cooldown = 5.0
        if expired:
            self.notify('Order offer expired.')

    def _retarget(self):
        """Point the GPS at the nearest pending stop (a manual destination wins)."""
        if self.manual is not None:
            self.nav.set_target(self.manual[0], self.manual[1])
            col = color.rgba32(80, 200, 255, 110)
            self.beacon.color = col
            self.beacon.position = (self.manual[0][0], 35, self.manual[0][1])
            self.beacon_label.text = self.manual[1]
            self.beacon_label.position = (self.manual[0][0], 40, self.manual[0][1])
            self.pin_target.color = col
            self.pin_target.position = (self.manual[0][0], 68, self.manual[0][1])
            self.beacon.enabled = self.beacon_label.enabled = self.pin_target.enabled = True
            return
        if not self.orders:
            self.nav.clear()
            self.beacon.enabled = self.beacon_label.enabled = self.pin_target.enabled = False
            return
        best, bd = None, 1e18
        for o in self.orders:
            t = o.target
            d = math.hypot(t.curb_pt[0] - self.car.x, t.curb_pt[1] - self.car.z)
            if d < bd:
                best, bd = o, d
        t = best.target
        label = (f'Pick up: {best.restaurant["name"]}' if best.state == 'pickup'
                 else f'Deliver: {t.address}')
        self.nav.set_target(t.curb_pt, label)
        self._beacon_for(best)

    def _beacon_for(self, o):
        t = o.target
        pick = o.state == 'pickup'
        col = color.rgba32(255, 160, 40, 110) if pick else color.rgba32(60, 230, 120, 110)
        self.beacon.color = col
        self.beacon.position = (t.curb_pt[0], 35, t.curb_pt[1])
        self.beacon.enabled = True
        self.beacon_label.text = f'PICK UP\n{o.restaurant["name"]}' if pick else f'DELIVER\n{t.address}'
        self.beacon_label.position = (t.curb_pt[0], 40, t.curb_pt[1])
        self.beacon_label.enabled = True
        self.pin_target.color = col
        self.pin_target.position = (t.curb_pt[0], 68, t.curb_pt[1])
        self.pin_target.enabled = True

    def _arrivals(self):
        c = self.car
        if abs(c.speed) > ARRIVE_SPEED or abs(c.y - cm.ROAD_Y) > 3:
            return
        for o in list(self.orders):
            t = o.target
            if math.hypot(t.curb_pt[0] - c.x, t.curb_pt[1] - c.z) > ARRIVE_R:
                continue
            if o.state == 'pickup':
                o.state = 'dropoff'
                o.elapsed = 0.0
                self.notify(f'Picked up from {o.restaurant["name"]}. Deliver to {o.clot.address}.')
                self._retarget()
            else:
                self._deliver(o)
                self.orders.remove(o)
                self._retarget()

    def _deliver(self, o):
        S = self.S
        d = S['delivery']
        total, on_time, bonus, tip = o.pay(gd.delivery_pay_mult(S))
        total *= gd.gig_mult(S)
        self.earn(total)
        d['deliveries'] += 1
        d['earned'] += total
        d['best'] = max(d['best'], total)
        if not on_time:
            d['late'] += 1
        q = o.quality
        score = 5.0 - (0 if on_time else 1.5) - (0 if q >= 85 else .7 if q >= 65 else 1.5 if q >= 40 else 2.5)
        score = max(1.0, min(5.0, score))
        d['rating'] = round(d['rating'] * .8 + score * .2, 3)
        self.shift['deliveries'] += 1
        self.shift['earned'] += total
        self.banner_t = 3.0
        self.h_banner.text = f'DELIVERED!  +{gd.fmt(total)}'
        self.h_banner.color = color.lime if on_time else color.orange
        extra = f'tip {gd.fmt(tip)}' + (f', speed bonus {gd.fmt(bonus)}' if bonus > 0 else ', late')
        self.notify(f'{o.clot.address}: {gd.fmt(total)} ({extra}, food {int(q)}%). Rating {d["rating"]:.1f}')
        self.cooldown = 3.0

    # ---- destination picker --------------------------------------------------
    def open_destinations(self):
        def go(xz, name):
            def f():
                self.manual = (xz, name)
                self._retarget()
                self.notify(f'GPS: navigating to {name}')
                self.close_panel()
            return f

        def clear():
            self.manual = None
            self._retarget()
            if not self.orders:
                self.route_line.clear()
            self.close_panel()

        def rows():
            out = [('info', 'Where to? (or pick up an order and the GPS guides you automatically)', color.light_gray)]
            for r, lot in self.city.restaurants:
                out.append(('item', f'{r["name"]}  -  {lot.address}', 'GO', True, go(lot.curb_pt, r['name'])))
            d = self.city.depot
            out.append(('item', f'{cm.DEPOT_NAME}  -  {d.address}', 'GO', True, go(d.curb_pt, cm.DEPOT_NAME)))
            out.append(('btn', 'Clear route', self.manual is not None or self.nav.target is not None, clear))
            return out

        self.open_panel('GPS Destination', rows)

    # ---- per-frame ---------------------------------------------------------
    def update(self, dt):
        if not self.active:
            return
        throttle = (held_keys['w'] or held_keys['up arrow']) - (held_keys['s'] or held_keys['down arrow'])
        steer = (held_keys['d'] or held_keys['right arrow']) - (held_keys['a'] or held_keys['left arrow'])
        throttle = max(-1.0, min(1.0, throttle + pad.trigger('right') - pad.trigger('left')))
        steer = max(-1.0, min(1.0, steer + pad.axis('left stick x')
                              + held_keys['gamepad dpad right'] - held_keys['gamepad dpad left']))
        handbrake = bool(held_keys['space'] or pad.held('left shoulder'))
        c = self.car
        c.step(dt, throttle, steer, handbrake, self.city, self.traffic.cars)
        self.traffic.update(dt, c)
        self.scene.update(c.x, c.z)
        self._follow_camera(dt)

        # orders
        for o in self.orders:
            if o.state == 'dropoff':
                o.elapsed += dt
                o.quality = max(0.0, o.quality - dt * .09 * (1 - .14 * gd.bag_level(self.S)))
        if self.offer:
            self.offer.age += dt
            if self.offer.age > OFFER_SECONDS:
                self._decline(expired=True)
        else:
            self.cooldown -= dt
            if self.cooldown <= 0 and len(self.orders) < gd.order_capacity(self.S) and self.manual is None:
                self._new_offer()
        self._arrivals()
        if self.manual is not None and math.hypot(self.manual[0][0] - c.x, self.manual[0][1] - c.z) < 14:
            self.notify('You have arrived.')
            self.manual = None
            self._retarget()
            if not self.orders:
                self.route_line.clear()

        # navigation
        self.nav.update(dt, c.x, c.z, c.y, c.fwd)
        self.route_line.update(self.nav.route, self.nav.version, self.nav.s)
        self.minimap.update(c)
        self._refresh_hud(dt)

    def _refresh_hud(self, dt):
        c = self.car
        S = self.S
        hint = pad.hint('drive')
        if hint != getattr(self, '_hint', None):
            self._hint = hint
            self.h_help.text = hint
        self.h_speed.text = f'{int(abs(c.speed) * 3.6)} km/h'
        self.h_street.text = self.city.road_label(c.x, c.z, c.y)
        ins = self.nav.instruction()
        if ins:
            text, dist, kind = ins
            self.h_turn.text = text
            self.h_turn2.text = (f'in {gps.fmt_dist(dist)}     {gps.fmt_dist(self.nav.remaining())} to go  '
                                 f'({gps.fmt_time(self.nav.remaining_time())})  -  {self.nav.label}')
        else:
            self.h_turn.text = ''
            self.h_turn2.text = 'No route. Accept an order or press G to pick a destination.' if not self.orders else ''
        lines = []
        cap = gd.order_capacity(S)
        for k, o in enumerate(self.orders, 1):
            if o.state == 'pickup':
                lines.append(f'{k}. PICK UP  {o.restaurant["name"]}  ->  {o.clot.address}')
            else:
                left = o.allowed - o.elapsed
                clock = f'{int(left // 60)}:{int(abs(left) % 60):02d}' if left >= 0 else f'LATE {int(-left)}s'
                lines.append(f'{k}. DELIVER  {o.clot.address}   time {clock}   food {int(o.quality)}%')
        head = f'DELIVERY  {len(self.orders)}/{cap} orders   rating {S["delivery"]["rating"]:.1f}/5   this shift {gd.fmt(self.shift["earned"])}'
        self.h_orders.text = head + ('\n' + '\n'.join(lines) if lines else '')
        if self.offer:
            o = self.offer
            self.h_offer.text = (f'NEW ORDER   {o.restaurant["name"]}  ->  {o.clot.address}\n'
                                 f'about {gd.fmt(o.fare * 1.5)}   {gps.fmt_dist(o.dist)} trip   '
                                 f'[{"X" if pad.using_pad() else "Y"}] accept    [{"B" if pad.using_pad() else "N"}] skip    ({int(OFFER_SECONDS - o.age)}s)')
        else:
            self.h_offer.text = ''
        self.bk_offer.enabled = self.offer is not None
        dep = self.city.depot
        near_depot = (math.hypot(dep.curb_pt[0] - c.x, dep.curb_pt[1] - c.z) < 16 and abs(c.speed) < 6)
        key_name = 'A' if pad.using_pad() else 'E'
        self.h_prompt.text = f'[{key_name}] End shift and return to town' if near_depot else ''
        if self.banner_t > 0:
            self.banner_t -= dt
            if self.banner_t <= 0:
                self.h_banner.text = ''
        if self.abandon_t > 0:
            self.abandon_t = max(0.0, self.abandon_t - dt)

    # ---- keys --------------------------------------------------------------
    def on_key(self, key):
        if not self.active:
            return
        if key == 'm':
            self.minimap.set_mode('full' if self.minimap.mode == 'mini' else 'mini')
            self._show_hud(self.minimap.mode != 'full')
            self.route_line.set_full(self.minimap.mode == 'full')
        elif key == 'g':
            self.open_destinations()
        elif key == 'y' and self.offer:
            self._accept()
        elif key == 'n' and self.offer:
            self._decline()
        elif key == 'r':
            self._reset_car()
        elif key == 'e':
            dep = self.city.depot
            c = self.car
            if math.hypot(dep.curb_pt[0] - c.x, dep.curb_pt[1] - c.z) < 16 and abs(c.speed) < 6:
                if self.orders and self.abandon_t <= 0:
                    self.abandon_t = 4.0
                    self.notify('You still have orders! Press E again within 4 seconds to abandon them (rating drops).')
                    return
                if self.orders:
                    d = self.S['delivery']
                    d['rating'] = round(max(1.0, d['rating'] - .3 * len(self.orders)), 3)
                    self.orders = []
                self.leave_cb()

    def _reset_car(self):
        c = self.car
        hit = self.city.nearest_edge_point(c.x, c.z, c.y, reach=3)
        if not hit:
            return
        e, t, _ = hit
        fx, fz = c.fwd
        sgn = 1 if (e.ux * fx + e.uz * fz) >= 0 else -1
        x, z, y = e.pos(t)
        dx, dz = e.ux * sgn, e.uz * sgn
        side = -1 if cm.DRIVE_LEFT else 1
        lane = cm.lane_offset(e)
        c.place(x + dz * side * lane, z - dx * side * lane, math.degrees(math.atan2(dx, dz)), y=y)
        self.notify('Car reset to the road.')
