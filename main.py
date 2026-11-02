"""Money Tycoon 3D - run with:  python main.py

Do gigs around town, get a job at Apex Corp, climb the ranks, sell the company,
then build an empire of your own.
"""
import atexit
import math
import random

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

import controls as pad
import delivery as dv
import game_data as gd
import minigames as mg
import updater
import version

S = gd.load_state()
JOBS = gd.load_jobs()
upd = updater.Updater(version.VERSION)
upd.cleanup()                       # remove leftovers of a previous update
if S['updates']['auto']:
    upd.check_async()
MINI_JOBS = [j for j in JOBS if j.get('kind') != 'delivery']      # jobs done as mini-games
drive = None                                                      # the food delivery session, created below

app = Ursina(title='Money Tycoon 3D', borderless=False, vsync=True)
window.exit_button.visible = False
window.fps_counter.enabled = False
window.color = color.rgb32(120, 170, 230)
for _w in ('entity_counter', 'collider_counter', 'cog_button'):
    if hasattr(window, _w):
        getattr(window, _w).enabled = False
Sky()
pad.setup(app)

OFFICE_X = 1000
OWN_X = 2000
SCENES = ['town', 'office', 'own', 'city']
roots = {name: Entity() for name in SCENES}
for _name in ('office', 'own', 'city'):
    roots[_name].enabled = False
current = 'town'


def rgb(r, g, b, a=255):
    return color.rgba32(r, g, b, a)


def block(parent, x, y, z, w, h, d, col, collider=True, model='cube'):
    return Entity(parent=parent, model=model, position=(x, y, z), scale=(w, h, d), color=col,
                  collider='box' if collider else None)


def label(parent, text, x, y, z, scale=24, col=color.white):
    return Text(text, parent=parent, position=(x, y, z), origin=(0, 0), scale=scale * .5,
                billboard=True, color=col)


# ---------------------------------------------------------------- interaction
class Station:
    def __init__(self, scene_name, x, z, text, action, radius=3.5, show=None):
        self.scene, self.x, self.z = scene_name, x, z
        self.text, self.action, self.radius, self.show = text, action, radius, show
        parent = roots[scene_name]
        Entity(parent=parent, model='circle', rotation_x=90, position=(x, .08, z),
               scale=radius * .8, color=rgb(255, 220, 40, 90))
        self.marker = Entity(parent=parent, model='diamond', position=(x, 2.2, z), scale=(.5, .8, .5),
                             color=color.gold)
        MARKERS.append(self.marker)

    def title(self):
        return self.text() if callable(self.text) else self.text


MARKERS = []
STATIONS = {name: [] for name in SCENES}


def station(scene_name, x, z, text, action, radius=3.5, show=None):
    s = Station(scene_name, x, z, text, action, radius, show)
    STATIONS[scene_name].append(s)
    return s


# ---------------------------------------------------------------- HUD / toasts
hud = Text('', parent=camera.ui, position=window.top_left + Vec2(.015, -.015), origin=(-.5, .5), scale=1.4)
help_text = Text('WASD move   SPACE jump   E interact   ESC menu / quit', parent=camera.ui,
                 position=window.top_right + Vec2(-.015, -.015), origin=(.5, .5), scale=.8,
                 color=color.light_gray)
prompt = Text('', parent=camera.ui, y=-.32, origin=(0, 0), scale=1.7, color=color.yellow)
toast_text = Text('', parent=camera.ui, position=window.bottom_left + Vec2(.02, .3), origin=(-.5, -.5), scale=1.1)
update_text = Text('', parent=camera.ui, position=(0, .46), origin=(0, 0), scale=1.2, color=color.gold)
toasts = []


def notify(msg):
    toasts.insert(0, [msg, 5.0])
    del toasts[6:]


# ---------------------------------------------------------------- generic panel
class Panel(Entity):
    """A list window. build() returns rows:
       ('info', text[, color]) | ('item', text, button_text, enabled, fn) | ('btn', text, enabled, fn) | ('gap',)"""

    def __init__(self, title, build, width=1.35):
        super().__init__(parent=camera.ui, z=-1)
        self.build, self.width, self.dyn, self.dead = build, width, [], False
        self.btns, self.focus, self.nav = [], 0, pad.Nav()
        self.focus_on = pad.using_pad()          # show the controller highlight once a pad is in use
        Entity(parent=self, model='quad', color=rgb(12, 16, 30, 248), scale=(width, .92), z=.2)
        Entity(parent=self, model='quad', color=color.gold, scale=(width, .004), y=.37, z=.1)
        Text(title, parent=self, y=.42, origin=(0, 0), scale=2, color=color.gold)
        self.hint = Text(pad.hint('panel'), parent=self, y=-.43, origin=(0, 0), scale=.8, color=color.gray)
        self.refresh()

    def refresh(self):
        if self.dead:
            return
        for e in self.dyn:
            destroy(e)
        self.dyn, self.btns = [], []
        self.hint.text = pad.hint('panel')
        y, left = .31, -self.width / 2 + .04
        for row in self.build():
            kind = row[0]
            if kind == 'gap':
                y -= .03
                continue
            if kind == 'info':
                col = row[2] if len(row) > 2 else color.white
                self.dyn.append(Text(row[1], parent=self, x=left, y=y, origin=(-.5, 0), scale=1.1, color=col))
            elif kind == 'item':
                _, text, btn, enabled, fn = row
                self.dyn.append(Text(text, parent=self, x=left, y=y, origin=(-.5, 0), scale=1.0))
                self.add_button(btn, enabled, fn, self.width / 2 - .17, y, (.28, .048))
            elif kind == 'btn':
                _, text, enabled, fn = row
                self.add_button(text, enabled, fn, 0, y, (.6, .05))
            y -= .062
        if self.btns:
            self.focus = max(0, min(self.focus, len(self.btns) - 1))
            if self.focus_on:
                fb = self.btns[self.focus]
                self.dyn.append(Entity(parent=self, model='quad', color=color.gold, position=(fb.x, fb.y),
                                       scale=(fb.scale_x + .014, fb.scale_y + .014), z=.05))
                fb.color = color.azure

    def add_button(self, text, enabled, fn, x, y, scl):
        b = Button(parent=self, text=text, x=x, y=y, scale=scl,
                   color=color.azure.tint(-.2) if enabled else color.dark_gray)
        if enabled:
            b.on_click = lambda: (fn(), invoke(self.refresh, delay=.02))
            self.btns.append(b)
        self.dyn.append(b)

    # -- controller ------------------------------------------------------------
    def move_focus(self, d):
        if d in ('up', 'down') and self.btns:
            self.focus_on = True
            self.focus = (self.focus + (1 if d == 'down' else -1)) % len(self.btns)
            self.refresh()

    def update(self):
        if not self.dead:
            d = self.nav.poll(time.dt)
            if d:
                self.move_focus(d)

    def input(self, key):
        if self.dead:
            return None
        if key in pad.DPAD:
            self.move_focus(pad.DPAD[key])
            return True
        if key == 'gamepad a' and self.btns:
            if not self.focus_on:                  # first press just shows the highlight
                self.focus_on = True
                self.refresh()
            else:
                self.btns[self.focus].on_click()
            return True
        return None


panel = None
mini = None


def open_panel(title, build, **kw):
    global panel
    if panel or mini:
        return
    player.enabled = False
    if drive is not None and drive.active:
        mouse.visible = True
    panel = Panel(title, build, **kw)


def close_panel():
    global panel
    if panel:
        panel.dead = True
        destroy(panel)
        panel = None
        if drive is not None and drive.active:
            mouse.visible = False
        else:
            player.enabled = True


def start_mini(job, mode):
    global mini
    if panel or mini:
        return
    player.enabled = False

    def done(f):
        return finish_job(job, mode, f)

    def closed():
        global mini
        mini = None
        player.enabled = True

    title = job['office_name'] if mode == 'office' else job['name']
    if mode == 'own':
        title = f"{job['office_name']} (your company)"
    mini = mg.GAMES[job['minigame']](done, closed, time_bonus=gd.time_bonus(S), title=title)


# ---------------------------------------------------------------- economy
def earn(amount, company=False):
    S['money'] += amount
    S['total_earned'] += amount
    if company and S['employed']:
        S['company_earned'] += amount


def rating(f):
    return 'Outstanding!' if f >= 1.5 else 'Great' if f >= 1.0 else 'Decent' if f >= .5 else 'Poor'


def finish_job(job, mode, f):
    base = job['base_pay']
    lines = [f'{rating(f)}   ({int(f * 100)}% performance)']
    if mode == 'gig':
        pay = base * f * gd.gig_mult(S)
        earn(pay)
        lines.append(f'Earned {gd.fmt(pay)}')
    elif mode == 'office':
        rank = gd.RANKS[S['rank']]
        pay = base * f * 2 * rank['mult'] * gd.gig_mult(S)
        earn(pay, company=True)
        xp = round(12 * f * (1 + .5 * S['rank']) * gd.xp_mult(S))
        S['xp'] += xp
        lines += [f'Earned {gd.fmt(pay)}  (rank bonus x{rank["mult"]})', f'+{xp} XP']
        nxt = S['rank'] + 1
        if nxt < len(gd.RANKS) and S['xp'] >= gd.RANKS[nxt]['xp']:
            lines.append('You qualify for a promotion! Visit HR.')
    else:
        pay = base * f * 3 * gd.company_manual_mult(S)
        earn(pay)
        lines.append(f'Earned {gd.fmt(pay)}  (company bonus x{gd.company_manual_mult(S):.2f})')
    S['jobs_done'] += 1
    gd.save_state(S)
    return lines


def goto(scene_name, pos, rot=0):
    global current
    roots[current].enabled = False
    roots[scene_name].enabled = True
    current = scene_name
    player.position = Vec3(*pos)
    player.rotation_y = rot
    player.camera_pivot.rotation_x = 0


# ---------------------------------------------------------------- panels: shop / bank
def shop_rows():
    rows = [('info', f'Your cash: {gd.fmt(S["money"])}', color.lime), ('gap',)]
    for key, item in gd.SHOP.items():
        lvl = S['shop'][key]
        text = f'{item["name"]}  Lv {lvl}/{item["max"]}  -  {item["desc"]}'
        if lvl >= item['max']:
            rows.append(('item', text, 'MAX', False, None))
        else:
            cost = gd.shop_cost(key, lvl)

            def buy(key=key, cost=cost):
                if S['money'] >= cost:
                    S['money'] -= cost
                    S['shop'][key] += 1
                    player.speed = gd.walk_speed(S)
                    if drive is not None:
                        drive.apply_upgrades()
                    notify(f'Bought {gd.SHOP[key]["name"]}!')

            rows.append(('item', text, gd.fmt(cost), S['money'] >= cost, buy))
    return rows


def bank_rows():
    def deposit(amount):
        amt = min(amount, S['money'])
        S['money'] -= amt
        S['bank'] += amt

    def withdraw():
        S['money'] += S['bank']
        S['bank'] = 0

    return [
        ('info', f'Wallet: {gd.fmt(S["money"])}', color.lime),
        ('info', f'Savings: {gd.fmt(S["bank"])}   (earns 1% every 30 seconds, up to $250,000)', color.gold),
        ('gap',),
        ('btn', 'Deposit $100', S['money'] >= 100, lambda: deposit(100)),
        ('btn', 'Deposit $1,000', S['money'] >= 1000, lambda: deposit(1000)),
        ('btn', 'Deposit everything', S['money'] >= 1, lambda: deposit(S['money'])),
        ('btn', 'Withdraw everything', S['bank'] >= 1, withdraw),
    ]


def pause_rows():
    def quit_game():
        gd.save_state(S)
        application.quit()

    def stop_shift():
        close_panel()
        if drive.orders:
            S['delivery']['rating'] = round(max(1.0, S['delivery']['rating'] - .3 * len(drive.orders)), 3)
            drive.orders = []
        leave_city()

    def check_now():
        close_panel()
        if upd.state not in ('checking', 'downloading'):
            upd.check_async(manual=True)
            notify('Checking for updates...')

    def toggle_auto():
        S['updates']['auto'] = not S['updates']['auto']

    rows = [
        ('info', f'Money Tycoon 3D v{version.VERSION}. Your progress is saved automatically.', color.light_gray),
        ('gap',),
        ('btn', 'Resume', True, close_panel),
    ]
    if drive is not None and drive.active:
        rows.append(('btn', 'End shift and return to town', True, stop_shift))
    rows.append(('btn', 'Check for updates', True, check_now))
    rows.append(('btn', f'Automatic update checks: {"ON" if S["updates"]["auto"] else "OFF"}', True, toggle_auto))
    rows.append(('btn', 'Save and quit', True, quit_game))
    return rows


# ---------------------------------------------------------------- updates
def update_rows():
    info = upd.info
    if upd.state == 'ready':
        return [
            ('info', f'Version {info["version"]} is downloaded and checked.', color.lime),
            ('info', 'Restart to finish updating. Your progress is saved first.', color.light_gray),
            ('gap',),
            ('btn', 'Restart and finish updating', True, restart_for_update),
            ('btn', 'Later', True, close_panel),
        ]

    def start_download():
        close_panel()
        upd.download_async()
        notify('Downloading the update...')

    def skip():
        S['updates']['skip'] = info['version']
        close_panel()

    rows = [('info', f'Version {info["version"]} is available (you have {version.VERSION}).', color.lime)]
    for line in [ln.strip() for ln in info.get('notes', '').splitlines() if ln.strip()][:5]:
        rows.append(('info', line[:100], color.light_gray))
    rows.append(('gap',))
    if upd.can_self_update:
        rows.append(('btn', 'Update now', True, start_download))
    else:
        rows.append(('btn', 'Open the download page', True, upd.open_download_page))
    rows.append(('btn', 'Remind me later', True, close_panel))
    rows.append(('btn', f'Skip version {info["version"]}', True, skip))
    return rows


def restart_for_update():
    gd.save_state(S)
    try:
        upd.install(launch=True)
    except Exception as e:
        close_panel()
        notify(f'Update failed: {e}')
        return
    application.quit()


# ---------------------------------------------------------------- food delivery
def start_delivery():
    if panel or mini or drive is None:
        return

    def go():
        drive.build()
        goto('city', (0, 2, 0))
        player.enabled = False
        mouse.visible = False
        drive.enter()

    if drive.built:
        go()
        return
    player.enabled = False
    cover = Entity(parent=camera.ui, model='quad', color=rgb(10, 14, 26), scale=(3.2, 1.2), z=-5)
    note = Text('Building the city...', parent=camera.ui, origin=(0, 0), scale=3, color=color.gold, z=-6)

    def build_then_go():
        go()
        destroy(cover)
        destroy(note)

    invoke(build_then_go, delay=.25)          # let the loading screen draw first


def leave_city():
    drive.leave()
    goto('town', (30, 2, -3), 0)
    player.enabled = True
    mouse.visible = True


# ---------------------------------------------------------------- panels: career
def hr_rows():
    r = gd.RANKS[S['rank']]
    rows = [('info', f'Rank: {r["name"]}   (task pay x{r["mult"]},  salary {gd.fmt(r["salary"])} every '
                     f'{int(gd.SALARY_INTERVAL)}s)', color.lime)]
    if S['rank'] + 1 < len(gd.RANKS):
        nxt = gd.RANKS[S['rank'] + 1]
        rows.append(('info', f'XP: {S["xp"]} / {nxt["xp"]}   (do tasks at the desks to earn XP)'))
        rows.append(('gap',))

        def promote():
            S['rank'] += 1
            notify(f'Promoted to {gd.RANKS[S["rank"]]["name"]}!')

        rows.append(('btn', f'Promote to {nxt["name"]}  (x{nxt["mult"]} pay)', S['xp'] >= nxt['xp'], promote))
    else:
        rows.append(('info', 'You are the CEO. Visit the boardroom to sell the company.', color.gold))
    return rows


confirm = {}


def board_rows():
    if S['rank'] + 1 < len(gd.RANKS):
        return [('info', 'Only the CEO can sell the company.'),
                ('info', f'Current rank: {gd.RANKS[S["rank"]]["name"]}  -  keep climbing!')]
    price = gd.company_sale_price(S)

    def sell():
        if not confirm.get('sell'):
            confirm['sell'] = True
            notify('Click again to confirm the sale.')
            return
        confirm['sell'] = False
        S['money'] += price
        S['employed'] = False
        S['rank'], S['xp'], S['company_earned'] = 0, 0, 0
        S['founder'] = True
        gd.save_state(S)
        close_panel()
        refresh_lot()
        goto('town', (0, 2, 40), 180)
        notify(f'Company sold for {gd.fmt(price)}! Claim the vacant lot to start your own.')

    return [
        ('info', 'The board has an offer for Apex Corp.', color.gold),
        ('info', f'Offer: {gd.fmt(price)}   (based on your XP and the profit you made)'),
        ('info', 'Selling ends your job. You can start your own company afterwards.'),
        ('gap',),
        ('btn', 'CLICK AGAIN TO CONFIRM' if confirm.get('sell') else f'Sell for {gd.fmt(price)}', True, sell),
    ]


# ---------------------------------------------------------------- panels: own company
ADJ = ['Golden', 'Rapid', 'Bright', 'Iron', 'Silver', 'Neon', 'Royal', 'Giga', 'Prime', 'Apex']
NOUN = ['Dynamics', 'Industries', 'Ventures', 'Labs', 'Holdings', 'Works', 'Systems', 'Enterprises']
pending_name = {'v': f'{random.choice(ADJ)} {random.choice(NOUN)}'}


def lot_rows():
    def reroll():
        pending_name['v'] = f'{random.choice(ADJ)} {random.choice(NOUN)}'

    def found():
        if S['money'] >= gd.FOUNDING_COST:
            S['money'] -= gd.FOUNDING_COST
            S['own'] = gd.new_company(pending_name['v'])
            close_panel()
            refresh_lot()
            refresh_staff()
            notify(f'{pending_name["v"]} is born! Walk in and start working.')

    return [
        ('info', 'Found your own company', color.gold),
        ('info', f'Name: {pending_name["v"]}'),
        ('info', f'Founding fee: {gd.fmt(gd.FOUNDING_COST)}'),
        ('gap',),
        ('btn', 'Pick another name', True, reroll),
        ('btn', f'Found company ({gd.fmt(gd.FOUNDING_COST)})', S['money'] >= gd.FOUNDING_COST, found),
    ]


def manage_rows():
    c = S['own']
    inc = gd.passive_income(S)
    rows = [('info', f'{c["name"]}  -  {gd.TIERS[c["tier"]]["name"]}   |   Income {gd.fmt(inc)}/s   |   '
                     f'Cash {gd.fmt(S["money"])}', color.lime)]
    if c['tier'] + 1 < len(gd.TIERS):
        t = gd.TIERS[c['tier'] + 1]

        def expand():
            if S['money'] >= t['cost']:
                S['money'] -= t['cost']
                c['tier'] += 1
                refresh_lot()
                notify(f'Expanded to {t["name"]}!')

        rows.append(('item', f'Expand to {t["name"]}  (x{t["mult"]} everything)', gd.fmt(t['cost']),
                     S['money'] >= t['cost'], expand))
    for s in gd.STAFF:
        owned = c['staff'].get(s['id'], 0)
        if c['tier'] < s['tier']:
            rows.append(('info', f'{s["name"]}: requires {gd.TIERS[s["tier"]]["name"]}', color.gray))
            continue
        cost = gd.staff_cost(s, owned)

        def hire(s=s, cost=cost):
            if S['money'] >= cost:
                S['money'] -= cost
                c['staff'][s['id']] = c['staff'].get(s['id'], 0) + 1
                refresh_staff()

        rows.append(('item', f'Hire {s["name"]}  (own {owned})  +{gd.fmt(s["rate"])}/s each',
                     gd.fmt(cost), S['money'] >= cost, hire))
    for key, u in gd.UPGRADES.items():
        lvl = c['up'][key]
        text = f'{u["name"]} Lv {lvl}/{u["max"]}  -  {u["desc"]}'
        if lvl >= u['max']:
            rows.append(('item', text, 'MAX', False, None))
            continue
        cost = gd.upgrade_cost(key, lvl)

        def up(key=key, cost=cost):
            if S['money'] >= cost:
                S['money'] -= cost
                c['up'][key] += 1

        rows.append(('item', text, gd.fmt(cost), S['money'] >= cost, up))
    if c['tier'] >= gd.IPO_MIN_TIER:
        payout = gd.ipo_payout(S)

        def ipo():
            if not confirm.get('ipo'):
                confirm['ipo'] = True
                notify('Click again to confirm the IPO (your company resets).')
                return
            confirm['ipo'] = False
            S['money'] += payout
            S['prestige'] += 1
            S['own'] = gd.new_company(c['name'])
            refresh_lot()
            refresh_staff()
            notify(f'IPO complete! +{gd.fmt(payout)} and a permanent +50% bonus.')

        rows.append(('gap',))
        rows.append(('item', f'Take company public: {gd.fmt(payout)} + permanent +50% bonus',
                     'CONFIRM' if confirm.get('ipo') else 'IPO', True, ipo))
    return rows


# ---------------------------------------------------------------- build: town
def build_town():
    r = roots['town']
    block(r, 0, -.5, 0, 220, 1, 220, rgb(70, 140, 70))
    block(r, 0, .03, 0, 70, .06, 46, rgb(170, 170, 175), collider=False)          # plaza
    block(r, 0, .04, 32, 220, .06, 9, rgb(55, 55, 60), collider=False)             # road
    for x in range(-100, 101, 10):
        block(r, x, .08, 32, 4, .02, .5, rgb(230, 220, 120), collider=False)
    block(r, 0, .04, -30, 4, .06, 60, rgb(150, 150, 150), collider=False)          # path to lot
    for sx, sz, w, d in ((0, 110, 224, 2), (0, -110, 224, 2), (110, 0, 2, 224), (-110, 0, 2, 224)):
        wall = block(r, sx, 10, sz, w, 20, d, color.clear)
        wall.visible = False

    # gig plaza kiosks
    label(r, 'GIG PLAZA  -  jobs open any time', 0, 9, 8, scale=30, col=color.gold)
    for i, job in enumerate(JOBS):
        x = (i - (len(JOBS) - 1) / 2) * 12
        col = rgb(*job['color'])
        block(r, x, 1.6, 6, 5, 3.2, 3, col)
        block(r, x, 3.5, 5.2, 6.4, .3, 4.4, col.tint(-.3), collider=False)
        label(r, job['name'], x, 5.6, 6, scale=18)
        label(r, f'${job["base_pay"]}+ per run', x, 4.8, 6, scale=12, col=color.light_gray)

        if job.get('kind') == 'delivery':
            station('town', x, 2, f'[E] Start a shift: {job["name"]}  -  {job["desc"]}', start_delivery)
            continue

        def act(job=job):
            start_mini(job, 'gig')
        station('town', x, 2, f'[E] Work gig: {job["name"]}  -  {job["desc"]}', act)

    # Apex Corp headquarters
    block(r, 0, 24, 62, 32, 48, 22, rgb(70, 110, 170))
    for yy in range(4, 46, 6):
        block(r, 0, yy, 50.6, 30, 2.2, .3, rgb(150, 210, 250), collider=False)
    block(r, 0, 3, 50.7, 7, 6, .5, rgb(25, 30, 45), collider=False)
    label(r, 'APEX CORP', 0, 53, 49, scale=46, col=color.white)
    label(r, 'Now hiring!', 0, 8.5, 49, scale=16, col=color.gold)

    def hq():
        if not S['employed']:
            S['employed'] = True
            S['rank'], S['xp'], S['company_earned'] = 0, 0, 0
            notify('You are hired as an Intern at Apex Corp!')
        goto('office', (OFFICE_X, 2, -16), 0)

    station('town', 0, 46, lambda: '[E] Enter Apex Corp' if S['employed'] else '[E] Apply for a job at Apex Corp',
            hq, radius=4.5)

    # shop and bank
    block(r, -50, 5, 22, 18, 10, 14, rgb(230, 140, 50))
    block(r, -50, 2.5, 14.8, 5, 5, .4, rgb(40, 30, 20), collider=False)
    label(r, 'SHOP', -50, 12.5, 15, scale=36)
    station('town', -50, 11, '[E] Browse the shop', lambda: open_panel('The Shop', shop_rows), radius=4.5)
    block(r, 50, 6, 22, 18, 12, 14, rgb(235, 235, 225))
    block(r, 50, 2.5, 14.8, 5, 5, .4, rgb(40, 60, 40), collider=False)
    label(r, 'BANK', 50, 14.5, 15, scale=36, col=color.lime)
    station('town', 50, 11, '[E] Open the bank', lambda: open_panel('City Bank', bank_rows), radius=4.5)

    # decoration
    rng = random.Random(7)
    for _ in range(90):
        x, z = rng.uniform(-105, 105), rng.uniform(-105, 105)
        if abs(z - 32) < 8 or (abs(x) < 38 and -85 < z < 70) or abs(x) < 30 and z < -40:
            continue
        h = rng.uniform(3, 5)
        block(r, x, h / 2, z, .8, h, .8, rgb(100, 70, 40), collider=False)
        block(r, x, h + 1.2, z, 3.5, 3.2, 3.5, rgb(40, rng.randint(110, 160), 50), collider=False, model='sphere')
    for x in range(-100, 101, 20):
        block(r, x, 2.5, 27, .3, 5, .3, rgb(60, 60, 70), collider=False)
        block(r, x, 5, 27, 1, .4, 1, color.yellow, collider=False)
    for i in range(7):
        Car(r, 30 + (2 if i % 2 else -2), 1 if i % 2 else -1, rng.uniform(8, 16), rng.uniform(-100, 100))
    lot_root.parent = r


class Car(Entity):
    def __init__(self, parent, z, direction, speed, x):
        col = random.choice([color.red, color.azure, color.orange, color.white, color.violet])
        super().__init__(parent=parent, model='cube', position=(x, 1, z), scale=(5, 1.4, 2.4), color=col)
        Entity(parent=self, model='cube', position=(0, .9, 0), scale=(.5, .7, .9), color=rgb(30, 40, 60))
        self.dir, self.speed = direction, speed

    def update(self):
        self.x += self.dir * self.speed * time.dt
        if abs(self.x) > 105:
            self.x = -self.dir * 105


lot_root = Entity()


def refresh_lot():
    for c in list(lot_root.children):
        destroy(c)
    r = lot_root
    block(r, 0, .05, -68, 34, .1, 26, rgb(140, 115, 80), collider=False)
    if not S['founder']:
        label(r, 'VACANT LOT', 0, 7, -66, scale=34, col=color.light_gray)
        label(r, 'Sell a company first to claim it', 0, 4.5, -66, scale=15, col=color.gray)
    elif not S['own']:
        label(r, 'YOUR LOT', 0, 7, -66, scale=34, col=color.gold)
        label(r, 'Walk up and found your company', 0, 4.5, -66, scale=15, col=color.white)
    else:
        t = S['own']['tier']
        h = 9 + t * 8
        w = 24 + t * 3
        block(r, 0, h / 2, -72, w, h, 14, rgb(60 + t * 25, 90 + t * 20, 70 + t * 10))
        for yy in range(3, int(h), 5):
            block(r, 0, yy, -64.9, w - 2, 1.6, .3, rgb(250, 235, 160), collider=False)
        block(r, 0, 3, -64.8, 6, 6, .5, rgb(25, 30, 45), collider=False)
        label(r, S['own']['name'], 0, h + 4, -64, scale=32, col=color.gold)


def lot_action():
    if not S['founder']:
        notify('You need to sell a company before you can claim this lot.')
    elif not S['own']:
        open_panel('Found Your Company', lot_rows)
    else:
        goto('own', (OWN_X, 2, -20), 0)


# ---------------------------------------------------------------- build: office
def build_interior(name, ox, width, depth, floor_col, wall_col):
    r = roots[name]
    block(r, ox, -.5, 0, width, 1, depth, floor_col)
    block(r, ox, 6, depth / 2, width, 12, 1, wall_col)
    block(r, ox, 6, -depth / 2, width, 12, 1, wall_col)
    block(r, ox - width / 2, 6, 0, 1, 12, depth, wall_col)
    block(r, ox + width / 2, 6, 0, 1, 12, depth, wall_col)
    block(r, ox, 12.5, 0, width + 2, 1, depth + 2, rgb(235, 235, 240), collider=False)
    return r


def desk(r, x, z, col, text, w=5):
    block(r, x, .6, z, w, 1.2, 2.2, rgb(110, 80, 50))
    block(r, x, 1.8, z + .3, 2, 1.2, .2, rgb(25, 25, 35), collider=False)
    block(r, x, 1.8, z + .18, 1.8, 1, .1, col, collider=False)
    label(r, text, x, 4.2, z, scale=14)


def build_office():
    r = build_interior('office', OFFICE_X, 50, 44, rgb(90, 100, 120), rgb(215, 220, 230))
    for i, job in enumerate(MINI_JOBS):
        x = OFFICE_X + (i - (len(MINI_JOBS) - 1) / 2) * 9
        desk(r, x, 17, rgb(*job['color']), job['office_name'])

        def act(job=job):
            start_mini(job, 'office')
        station('office', x, 13, f'[E] Work at the {job["office_name"]}  -  {job["desc"]}', act)
    block(r, OFFICE_X - 17, .7, -4, 7, 1.4, 2.5, rgb(60, 130, 90))
    label(r, 'HR  -  Promotions', OFFICE_X - 17, 4, -4, scale=16, col=color.lime)
    station('office', OFFICE_X - 17, -7, '[E] Talk to HR about a promotion',
            lambda: open_panel('Human Resources', hr_rows), radius=4)
    block(r, OFFICE_X + 17, .7, -4, 9, 1.4, 4, rgb(70, 50, 40))
    label(r, 'BOARDROOM', OFFICE_X + 17, 4, -4, scale=16, col=color.gold)
    station('office', OFFICE_X + 17, -8, '[E] Enter the boardroom',
            lambda: open_panel('Boardroom', board_rows), radius=4)
    block(r, OFFICE_X, 3, -21.4, 6, 6, .4, rgb(30, 30, 40), collider=False)
    station('office', OFFICE_X, -18, '[E] Leave to the street',
            lambda: goto('town', (0, 2, 42), 180), radius=3)
    label(r, 'EXIT', OFFICE_X, 7, -21, scale=16)
    global office_board
    office_board = Text('', parent=r, position=(OFFICE_X, 8, 21.4), origin=(0, 0), scale=22, color=color.white)


office_board = None


# ---------------------------------------------------------------- build: own company
staff_root = Entity()
STAFF_COLORS = {'intern': color.light_gray, 'clerk': color.azure, 'engineer': color.orange,
                'manager': color.violet, 'executive': color.gold}


def refresh_staff():
    for c in list(staff_root.children):
        destroy(c)
    if not S['own']:
        return
    slots = [(OWN_X + gx * 5.5, -4 + gz * 4.5) for gz in range(6) for gx in range(-5, 6) if abs(gx) > 1 or gz > 1]
    random.Random(3).shuffle(slots)
    people = []
    for s in gd.STAFF:
        people += [s['id']] * min(S['own']['staff'].get(s['id'], 0), 12)
    for pid, (x, z) in zip(people, slots):
        col = STAFF_COLORS[pid]
        block(staff_root, x, .8, z, .8, 1.6, .6, col, collider=False)
        block(staff_root, x, 1.9, z, .7, .7, .7, rgb(240, 200, 160), collider=False, model='sphere')
        block(staff_root, x, .5, z - .7, 1.6, .8, .8, rgb(90, 70, 50), collider=False)


def build_own():
    r = build_interior('own', OWN_X, 70, 50, rgb(70, 90, 80), rgb(235, 225, 200))
    staff_root.parent = r
    for i, job in enumerate(MINI_JOBS):
        x = OWN_X + (i - (len(MINI_JOBS) - 1) / 2) * 11
        desk(r, x, 21, rgb(*job['color']), job['office_name'], w=6)

        def act(job=job):
            if S['own']:
                start_mini(job, 'own')
        station('own', x, 17, f'[E] Hands-on work: {job["office_name"]}  (boosted by your company)', act)
    block(r, OWN_X, .7, -10, 8, 1.4, 3, rgb(40, 40, 55))
    block(r, OWN_X, 2.1, -9.5, 5, 2.4, .3, rgb(20, 25, 35), collider=False)
    block(r, OWN_X, 2.1, -9.3, 4.6, 2, .1, rgb(80, 220, 140), collider=False)
    label(r, 'MANAGEMENT', OWN_X, 5, -10, scale=18, col=color.lime)
    station('own', OWN_X, -13, '[E] Open the management computer',
            lambda: open_panel('Company Management', manage_rows, width=1.55), radius=4)
    block(r, OWN_X, 3, -25.4, 6, 6, .4, rgb(30, 30, 40), collider=False)
    station('own', OWN_X, -22, '[E] Leave to the street', lambda: goto('town', (0, 2, -52), 0), radius=3)
    label(r, 'EXIT', OWN_X, 7, -25, scale=16)


# ---------------------------------------------------------------- build world
atexit.register(lambda: gd.save_state(S))
build_town()
build_office()
build_own()
refresh_lot()
refresh_staff()
station('town', 0, -54, lambda: '[E] Enter your company' if S['own'] else '[E] Claim the lot', lot_action,
        radius=5)

class PadPlayer(FirstPersonController):
    """First-person walker that also takes the left stick (move), right stick (look) and A (jump)."""

    def input(self, key):
        if key == 'gamepad a':
            self.jump()
        else:
            super().input(key)

    def update(self):
        sx, sy = pad.axis('left stick x'), pad.axis('left stick y')
        mag = min(1.0, math.hypot(sx, sy))
        saved = {k: held_keys[k] for k in 'wasd'}
        base = self.speed
        if mag:
            held_keys['w'] = saved['w'] or max(0.0, sy)
            held_keys['s'] = saved['s'] or max(0.0, -sy)
            held_keys['d'] = saved['d'] or max(0.0, sx)
            held_keys['a'] = saved['a'] or max(0.0, -sx)
            if not any(saved.values()):
                self.speed = base * max(.35, mag)
        super().update()
        self.speed = base
        for k, v in saved.items():
            held_keys[k] = v
        rx, ry = pad.axis('right stick x'), pad.axis('right stick y')
        if rx or ry:
            self.rotation_y += rx * time.dt * 150
            self.camera_pivot.rotation_x = clamp(self.camera_pivot.rotation_x - ry * time.dt * 110, -90, 90)


player = PadPlayer(position=(0, 2, -10), speed=gd.walk_speed(S), jump_height=1.6)
player.cursor.scale = .004
drive = dv.DriveSession(app, S, roots['city'], notify, earn, open_panel, close_panel, leave_city)


# ---------------------------------------------------------------- main loop
class Game(Entity):
    def __init__(self):
        super().__init__()
        self.t_hud = self.t_save = self.t_bank = self.t_pay = 0.0
        self.clock = 0.0
        self.frac_paid = 0.0
        self.upd_seen = None
        self.hint_shown = None

    def nearest(self):
        best, bd = None, 1e9
        px, pz = player.x, player.z
        for s in STATIONS[current]:
            d = math.hypot(s.x - px, s.z - pz)
            if d < s.radius and d < bd and (s.show is None or s.show()):
                best, bd = s, d
        return best

    def update(self):
        dt = time.dt
        self.clock += dt
        for i, m in enumerate(MARKERS):
            m.rotation_y += 90 * dt
            m.y = 2.2 + math.sin(self.clock * 2.5 + i) * .25
        if player.y < -20:
            player.position = Vec3(player.x, 3, player.z)
        # passive income from your own company
        if S['own']:
            earn(gd.passive_income(S) * dt)
        # salary
        if current == 'office' and S['employed']:
            self.t_pay += dt
            if self.t_pay >= gd.SALARY_INTERVAL:
                self.t_pay = 0
                pay = gd.RANKS[S['rank']]['salary']
                earn(pay, company=True)
                notify(f'Paycheck: +{gd.fmt(pay)}')
        # bank interest
        self.t_bank += dt
        if self.t_bank >= 30:
            self.t_bank = 0
            interest = min(S['bank'], 250000) * .01
            if interest >= 1:
                S['bank'] += interest
                notify(f'Bank interest: +{gd.fmt(interest)}')
        self.t_save += dt
        if self.t_save >= 20:
            self.t_save = 0
            gd.save_state(S)
        if drive.active and not (panel or mini):
            drive.update(dt)
        # updates
        update_text.text = f'Downloading update... {int(upd.progress * 100)}%' if upd.state == 'downloading' else ''
        if upd.state != self.upd_seen and not (panel or mini or drive.active):
            self.upd_seen = upd.state
            if upd.state == 'available':
                upd.prompted = True
                if upd.manual or upd.info['version'] != S['updates']['skip']:
                    open_panel('Update Available', update_rows)
            elif upd.state == 'ready':
                open_panel('Update Ready', update_rows)
            elif upd.state == 'none' and upd.manual:
                notify(f"You're up to date (v{version.VERSION}).")
            elif upd.state == 'error' and upd.manual:
                notify(f'Could not check for updates: {upd.error}')
            elif upd.state == 'failed':
                notify(f'Update failed: {upd.error}')
        # toasts
        for t in toasts:
            t[1] -= dt
        toasts[:] = [t for t in toasts if t[1] > 0]
        toast_text.text = '\n'.join(t[0] for t in toasts)
        # prompt
        st = self.nearest() if not (panel or mini) else None
        prompt.text = st.title() if st else ''
        overlay = bool(panel or mini)
        for w in (hud, toast_text, prompt, update_text):
            w.enabled = not overlay
        help_text.enabled = not overlay and not drive.active
        hint = pad.hint('world')
        if hint != self.hint_shown:
            self.hint_shown = hint
            help_text.text = hint
        # hud
        self.t_hud -= dt
        if self.t_hud <= 0:
            self.t_hud = .1
            self.refresh_hud()
        if office_board and current == 'office':
            r = gd.RANKS[S['rank']]
            office_board.text = f'Your rank: {r["name"]}\nXP {S["xp"]}'

    def refresh_hud(self):
        lines = [f'<lime>{gd.fmt(S["money"])}<default>   savings {gd.fmt(S["bank"])}']
        if S['employed']:
            r = gd.RANKS[S['rank']]
            lines.append(f'Apex Corp - {r["name"]}   XP {S["xp"]}')
        if S['own']:
            lines.append(f'<gold>{S["own"]["name"]}<default>  +{gd.fmt(gd.passive_income(S))}/s'
                         + (f'   prestige {S["prestige"]}' if S['prestige'] else ''))
        if S['delivery']['deliveries'] and current != 'city':
            lines.append(f'Delivery rating {S["delivery"]["rating"]:.1f}/5   {S["delivery"]["deliveries"]} deliveries')
        hud.text = '\n'.join(lines)

    def input(self, key):
        if mini:
            return
        if panel:
            if key in ('escape', 'e') or pad.translate('panel', key) == 'escape':
                close_panel()
            return
        key = pad.translate('drive' if drive.active else 'world', key)
        if key == 'escape':
            open_panel('Paused', pause_rows, width=.9)
        elif drive.active:
            drive.on_key(key)
        elif key == 'e':
            st = self.nearest()
            if st:
                st.action()


Game()
if S['jobs_done'] == 0:
    notify('Welcome! Walk to a kiosk in the Gig Plaza and press E to earn your first cash.')
    notify('Apex Corp (the tall blue tower) is hiring - climb the ranks, sell up, then found your own company.')

if __name__ == '__main__':
    app.run()
