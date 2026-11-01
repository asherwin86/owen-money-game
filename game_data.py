"""Static game data, formulas and save/load for Money Tycoon 3D."""
import json
import os
import sys

FROZEN = getattr(sys, 'frozen', False)
# Bundled read-only data (inside the exe when frozen) vs. writable files next to the game.
BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
USER_DIR = os.path.dirname(sys.executable) if FROZEN else BASE
SAVE_PATH = os.path.join(USER_DIR, 'save.json')
JOBS_PATH = os.path.join(BASE, 'data', 'jobs.json')
OVERRIDE_JOBS_PATH = os.path.join(USER_DIR, 'data', 'jobs.json')

DEFAULT_JOBS = [
    {"id": "data_entry", "name": "Data Entry", "office_name": "Filing Desk", "desc": "Type the words.",
     "minigame": "typing", "base_pay": 45, "color": [80, 160, 255]},
]


def load_jobs():
    # a data/jobs.json next to the exe overrides the bundled one, so jobs stay moddable
    for path in (OVERRIDE_JOBS_PATH, JOBS_PATH):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return DEFAULT_JOBS


# ---- corporate career -------------------------------------------------------
RANKS = [
    dict(name='Intern',            xp=0,     mult=1.0,  salary=20),
    dict(name='Junior Associate',  xp=100,   mult=1.6,  salary=45),
    dict(name='Associate',         xp=300,   mult=2.4,  salary=90),
    dict(name='Senior Associate',  xp=700,   mult=3.5,  salary=170),
    dict(name='Team Lead',         xp=1500,  mult=5.0,  salary=320),
    dict(name='Manager',           xp=3000,  mult=7.5,  salary=600),
    dict(name='Director',          xp=6000,  mult=11.0, salary=1100),
    dict(name='Vice President',    xp=12000, mult=16.0, salary=2000),
    dict(name='CEO',               xp=25000, mult=24.0, salary=3800),
]
SALARY_INTERVAL = 15.0
FOUNDING_COST = 20000

# ---- shop -------------------------------------------------------------------
SHOP = {
    'tools':  dict(name='Better Tools',    desc='+15% pay on every task',      base=120, growth=1.7, max=10),
    'shoes':  dict(name='Running Shoes',   desc='Walk faster around the city', base=150, growth=1.8, max=5),
    'coffee': dict(name='Coffee Machine',  desc='+3s on every mini-game',      base=250, growth=1.9, max=5),
    'suit':   dict(name='Power Suit',      desc='+10% rank XP',                base=400, growth=1.8, max=10),
}


def shop_cost(key, level):
    s = SHOP[key]
    return int(s['base'] * s['growth'] ** level)


# ---- your own company -----------------------------------------------------
TIERS = [
    dict(name='Garage Startup',    cost=0,          mult=1.0),
    dict(name='Small Office',      cost=15000,      mult=1.5),
    dict(name='Floor Suite',       cost=150000,     mult=2.5),
    dict(name='Headquarters',      cost=1500000,    mult=4.0),
    dict(name='Corporate Campus',  cost=15000000,   mult=7.0),
]
STAFF = [
    dict(id='intern',    name='Intern',    base=400,      rate=2,     tier=0),
    dict(id='clerk',     name='Clerk',     base=3000,     rate=15,    tier=0),
    dict(id='engineer',  name='Engineer',  base=25000,    rate=130,   tier=1),
    dict(id='manager',   name='Manager',   base=200000,   rate=1100,  tier=2),
    dict(id='executive', name='Executive', base=1800000,  rate=10000, tier=3),
]
UPGRADES = {
    'machines':  dict(name='Better Machines', desc='+25% pay from hands-on work', base=2000, growth=2.0, max=15),
    'marketing': dict(name='Marketing',       desc='+20% staff income',           base=5000, growth=1.9, max=15),
}
IPO_MIN_TIER = 3


def staff_cost(s, owned):
    return int(s['base'] * 1.15 ** owned)


def upgrade_cost(key, level):
    u = UPGRADES[key]
    return int(u['base'] * u['growth'] ** level)


def new_company(name='My Company'):
    return dict(name=name, tier=0, staff={s['id']: 0 for s in STAFF},
                up={k: 0 for k in UPGRADES}, earned=0)


# ---- state ------------------------------------------------------------------
def new_state():
    return dict(
        money=50.0, bank=0.0, xp=0, rank=0, employed=False, company_earned=0.0,
        total_earned=0.0, jobs_done=0, founder=False, prestige=0, own=None,
        shop={k: 0 for k in SHOP},
    )


def load_state():
    state = new_state()
    try:
        with open(SAVE_PATH, encoding='utf-8') as f:
            saved = json.load(f)
        for k, v in saved.items():
            if isinstance(v, dict) and isinstance(state.get(k), dict):
                state[k].update(v)
            else:
                state[k] = v
    except (OSError, ValueError):
        pass
    return state


def save_state(state):
    try:
        tmp = SAVE_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=1)
        os.replace(tmp, SAVE_PATH)
    except OSError:
        pass


# ---- formulas ---------------------------------------------------------------
def gig_mult(S):
    return 1 + 0.15 * S['shop']['tools']


def xp_mult(S):
    return 1 + 0.10 * S['shop']['suit']


def prestige_mult(S):
    return 1 + 0.5 * S['prestige']


def walk_speed(S):
    return 7 + 1.2 * S['shop']['shoes']


def time_bonus(S):
    return 3.0 * S['shop']['coffee']


def company_manual_mult(S):
    c = S['own']
    return TIERS[c['tier']]['mult'] * (1 + 0.25 * c['up']['machines']) * prestige_mult(S) * gig_mult(S)


def passive_income(S):
    """Money per second produced by staff of your own company."""
    c = S['own']
    if not c:
        return 0.0
    base = sum(s['rate'] * c['staff'].get(s['id'], 0) for s in STAFF)
    return base * TIERS[c['tier']]['mult'] * (1 + 0.2 * c['up']['marketing']) * prestige_mult(S)


def ipo_payout(S):
    return passive_income(S) * 1200 + 1_000_000


def company_sale_price(S):
    return int(50000 + S['xp'] * 5 + S['company_earned'] * 0.3)


def fmt(n):
    n = float(n)
    if abs(n) >= 1e9:
        return f'${n / 1e9:.2f}B'
    if abs(n) >= 1e6:
        return f'${n / 1e6:.2f}M'
    return f'${n:,.0f}'
