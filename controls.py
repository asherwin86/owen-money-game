"""Controller (gamepad) support.

Ursina reports gamepad buttons as key events ('gamepad a', 'gamepad dpad up', ...) and sticks/triggers as
held_keys values. This module wraps those, keeps track of whether the player last used a pad or the keyboard
(so on-screen hints can match), and maps pad buttons onto the keyboard actions the game already understands.
"""
import math

from ursina import Entity, held_keys, input_handler

DEADZONE = 0.2
NAV_FIRST_DELAY = 0.38
NAV_REPEAT = 0.13

_state = {'last': 'keys'}

# pad button -> the keyboard key it stands for, per situation
MAPS = {
    'world': {'gamepad x': 'e', 'gamepad start': 'escape', 'gamepad back': 'escape'},
    'panel': {'gamepad b': 'escape', 'gamepad start': 'escape'},
    'drive': {'gamepad x': 'y', 'gamepad b': 'n', 'gamepad y': 'g', 'gamepad back': 'm',
              'gamepad right shoulder': 'r', 'gamepad a': 'e', 'gamepad start': 'escape'},
}

HINTS = {
    ('world', 'keys'): 'WASD move   SPACE jump   E interact   ESC menu / quit',
    ('world', 'pad'): 'Left stick move   Right stick look   A jump   X interact   Start menu',
    ('drive', 'keys'): 'WASD drive   SPACE handbrake   M map   G destination   R reset car   ESC menu',
    ('drive', 'pad'): 'Left stick steer   RT gas   LT brake   LB handbrake   X accept   B skip   Y GPS   Back map   RB reset   Start menu',
    ('panel', 'keys'): 'E / ESC to close',
    ('panel', 'pad'): 'D-pad / stick: choose    A: select    B: close',
}


def connected():
    return bool(getattr(input_handler, 'gamepads', None))


def last_input():
    return _state['last']


def using_pad():
    return _state['last'] == 'pad'


def hint(context):
    return HINTS[(context, 'pad' if using_pad() else 'keys')]


def is_release(key):
    """True for key-release events. Careful: a D-pad-up *press* is named 'gamepad dpad up', which also ends in ' up'."""
    return key.endswith(' up') and key != 'gamepad dpad up'


def note_input(key):
    """Remember whether the latest input came from a pad or the keyboard."""
    if key.startswith('gamepad'):
        if not is_release(key):
            _state['last'] = 'pad'
    elif 'mouse' not in key and not key.endswith(' up') and not key.endswith(' hold'):
        _state['last'] = 'keys'


def translate(context, key):
    return MAPS.get(context, {}).get(key, key)


def axis(name):
    """A stick axis in -1..1 with the dead zone removed, e.g. axis('left stick x')."""
    v = float(held_keys[f'gamepad {name}'])
    if abs(v) <= DEADZONE:
        return 0.0
    return math.copysign((abs(v) - DEADZONE) / (1 - DEADZONE), v)


def trigger(side):
    """0..1 for 'left' or 'right'."""
    return max(0.0, min(1.0, float(held_keys[f'gamepad {side} trigger'])))


def held(button):
    return bool(held_keys[f'gamepad {button}'])


DPAD = {'gamepad dpad up': 'up', 'gamepad dpad down': 'down', 'gamepad dpad left': 'left', 'gamepad dpad right': 'right'}


class Nav:
    """Menu navigation from the left stick (with key-repeat while held). D-pad presses arrive as events."""

    def __init__(self):
        self.dir = None
        self.t = 0.0

    def poll(self, dt):
        x, y = axis('left stick x'), axis('left stick y')
        d = None
        if abs(x) > .45 or abs(y) > .45:
            d = ('right' if x > 0 else 'left') if abs(x) > abs(y) else ('up' if y > 0 else 'down')
        if d is None:
            self.dir = None
            return None
        if d != self.dir:
            self.dir, self.t = d, NAV_FIRST_DELAY
            return d
        self.t -= dt
        if self.t <= 0:
            self.t = NAV_REPEAT
            return d
        return None


class _Bridge(Entity):
    """Watches every input event so last_input() stays current."""

    def input(self, key):
        note_input(key)


def setup(app):
    """Call once after the Ursina app exists: tracks input and supports plugging a pad in while playing."""
    _Bridge(eternal=True)

    def refresh_devices(*_):
        try:
            from panda3d.core import InputDevice
            from ursina import gamepad
            input_handler.gamepads = app.devices.getDevices(InputDevice.DeviceClass.gamepad)
            gamepad.connect_all()
        except Exception:
            pass

    app.accept('connect-device', refresh_devices)
    app.accept('disconnect-device', refresh_devices)
    if connected():
        _state['last'] = 'keys'
