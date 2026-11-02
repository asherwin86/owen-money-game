"""The five mini-games. Each one reports a performance factor (~1.0 = decent run)."""
import random
import time as pytime

from ursina import *

import controls as pad

DIGITS = '0123456789'


def digit_of(key):
    """Map a key name to a digit, including numpad variants."""
    if len(key) == 1 and key in DIGITS:
        return key
    if key[-1:] in DIGITS and ('keypad' in key or 'numpad' in key):
        return key[-1]
    return None


class PadKeys(Entity):
    """On-screen keys you move over with the D-pad / left stick and press with A."""

    def __init__(self, parent, rows, x=0.0, y=-.2, size=.08):
        super().__init__(parent=parent, x=x, y=y)
        self.rows = rows
        self.r = self.c = 0
        self.hint = None
        self.cells = []
        gap = size * 1.08
        for ri, row in enumerate(rows):
            line = []
            for ci, tok in enumerate(row):
                cx, cy = (ci - (len(row) - 1) / 2) * gap, -ri * gap
                bg = Entity(parent=self, model='quad', position=(cx, cy), scale=(size, size))
                label = Text(tok, parent=self, position=(cx, cy), origin=(0, 0), z=-.01,
                             scale=1.0 if len(tok) == 1 else .75)
                line.append((bg, label, tok))
            self.cells.append(line)
        self.paint()

    def token(self):
        return self.rows[self.r][self.c]

    def move(self, d):
        dr = {'up': -1, 'down': 1}.get(d, 0)
        dc = {'left': -1, 'right': 1}.get(d, 0)
        self.r = (self.r + dr) % len(self.rows)
        self.c = min(self.c, len(self.rows[self.r]) - 1)
        self.c = (self.c + dc) % len(self.rows[self.r])
        self.paint()

    def goto(self, tok):
        for ri, row in enumerate(self.rows):
            if tok in row:
                self.r, self.c = ri, row.index(tok)
        self.paint()

    def mark(self, tok):
        self.hint = tok
        self.paint()

    def paint(self):
        for ri, line in enumerate(self.cells):
            for ci, (bg, label, tok) in enumerate(line):
                if (ri, ci) == (self.r, self.c):
                    bg.color = color.gold
                    label.color = color.black
                elif tok == self.hint:
                    bg.color = color.rgba32(40, 120, 70, 255)
                    label.color = color.white
                else:
                    bg.color = color.rgba32(40, 48, 70, 255)
                    label.color = color.white


RESULT_BUTTONS = ('gamepad a', 'gamepad b', 'gamepad x', 'gamepad y', 'gamepad start')


class Mini(Entity):
    title = 'Mini-game'
    instructions = ''
    duration = 30.0
    show_timer = True
    PAD = {}                 # controller button -> the keyboard key it stands for
    pad_hint = ''

    def __init__(self, on_done, on_close, time_bonus=0.0, title=None):
        super().__init__(parent=camera.ui, z=-2)
        self.on_done = on_done
        self.on_close = on_close
        self.time_left = self.duration + time_bonus
        self.done = False
        self.born = pytime.monotonic()
        Entity(parent=self, model='quad', color=color.rgba32(10, 14, 26, 255), scale=(3.2, 1.2), z=1)
        Text(title or self.title, parent=self, y=.44, origin=(0, 0), scale=2, color=color.gold)
        Text(self.instructions, parent=self, y=.37, origin=(0, 0), scale=1, color=color.light_gray)
        Text('ESC / Start to quit (no pay)' if pad.connected() else 'ESC to quit (no pay)', parent=self, y=-.47,
             origin=(0, 0), scale=.8, color=color.gray)
        if pad.connected() and self.pad_hint:
            Text(self.pad_hint, parent=self, y=-.42, origin=(0, 0), scale=.85, color=color.light_gray)
        self.nav = pad.Nav()
        self.kb = None
        self.timer_text = Text('', parent=self, x=.55, y=.44, origin=(0, 0), scale=1.6)
        self.score_text = Text('', parent=self, x=-.55, y=.44, origin=(0, 0), scale=1.6)
        self.setup()

    # -- hooks for subclasses ------------------------------------------------
    def setup(self): pass
    def on_key(self, key): pass
    def on_nav(self, d): pass
    def on_pad(self, key): pass
    def step(self): pass
    def factor(self): return 0.0

    # -- framework -------------------------------------------------------------
    def update(self):
        if self.done:
            return
        self.step()
        if self.done:
            return
        d = self.nav.poll(time.dt)
        if d:
            self.on_nav(d)
        self.time_left -= time.dt
        if self.show_timer:
            self.timer_text.text = f'{max(0, self.time_left):4.1f}s'
        if self.time_left <= 0:
            self.finish()

    def input(self, key):
        if key.endswith(' up') or pytime.monotonic() - self.born < .2:
            return
        if key.startswith('gamepad'):
            self.on_pad_button(key)
            return
        if self.done:
            if key in ('enter', 'space', 'left mouse down'):
                self.close()
            return
        if key == 'escape':
            self.close()
            return
        self.on_key(key)

    def on_pad_button(self, key):
        if self.done:
            if key in RESULT_BUTTONS:
                self.close()
            return
        if key in ('gamepad start', 'gamepad back'):
            self.close()
            return
        mapped = self.PAD.get(key)
        if mapped:
            self.on_key(mapped)
        elif key in pad.DPAD:
            self.on_nav(pad.DPAD[key])
        else:
            self.on_pad(key)

    def finish(self):
        if self.done:
            return
        self.done = True
        lines = self.on_done(max(0.0, self.factor())) or []
        Entity(parent=self, model='quad', color=color.rgba32(10, 14, 26, 255), scale=(3.2, 1.2), z=-.5)
        Text('\n'.join(lines), parent=self, z=-1, origin=(0, 0), y=.05, scale=2, color=color.white)
        Text('Press ENTER or A to continue' if pad.connected() else 'Press ENTER to continue', parent=self, z=-1, origin=(0, 0), y=-.3, scale=1.2, color=color.gray)

    def close(self):
        destroy(self)
        self.on_close()


class TypingMini(Mini):
    title = 'Data Entry'
    instructions = 'Type each word exactly. Wrong letters are ignored.'
    duration = 30.0
    TARGET = 9
    PAD_TARGET = 6          # fewer words needed when typing with the on-screen keys
    pad_hint = 'Controller: D-pad or left stick to pick a letter, A to press it (the next letter is shaded green)'
    WORDS = ['invoice', 'ledger', 'profit', 'budget', 'revenue', 'margin', 'balance', 'payroll',
             'shipment', 'contract', 'forecast', 'quarterly', 'dividend', 'treasury', 'merger',
             'auditor', 'capital', 'asset', 'income', 'equity', 'receipt', 'invest', 'stocks']

    def setup(self):
        self.count = 0
        self.typed = ''
        self.word = ''
        self.word_text = Text('', parent=self, y=.1, origin=(0, 0), scale=5)
        self.target = self.PAD_TARGET if pad.using_pad() else self.TARGET
        if pad.connected():
            self.kb = PadKeys(self, [list('qwertyuiop'), list('asdfghjkl'), list('zxcvbnm')], y=-.12, size=.085)
            self.kb.enabled = pad.using_pad()
        self.next_word()

    def next_word(self):
        self.word = random.choice(self.WORDS)
        self.typed = ''
        self.refresh()

    def refresh(self):
        rest = self.word[len(self.typed):]
        self.word_text.text = f'<lime>{self.typed}<white>{rest}'
        self.score_text.text = f'Words: {self.count}'
        if self.kb and rest:
            self.kb.mark(rest[0])

    def on_nav(self, d):
        if self.kb:
            self.kb.enabled = True
            self.kb.move(d)

    def on_pad(self, key):
        if self.kb and key == 'gamepad a':
            self.kb.enabled = True
            self.on_key(self.kb.token())

    def on_key(self, key):
        if len(key) == 1 and key.isalpha() and key.lower() == self.word[len(self.typed)]:
            self.typed += key.lower()
            if self.typed == self.word:
                self.count += 1
                self.next_word()
            else:
                self.refresh()

    def factor(self):
        return min(2.5, self.count / self.target)


class SortMini(Mini):
    title = 'Package Sorting'
    instructions = 'Press 1 / 2 / 3 (or click) to send the package to the matching bin.'
    duration = 25.0
    TARGET = 16
    PAD = {'gamepad b': '1', 'gamepad a': '2', 'gamepad x': '3', 'gamepad dpad left': '1',
           'gamepad dpad down': '2', 'gamepad dpad right': '3'}
    pad_hint = 'Controller: B = red bin, A = green bin, X = blue bin (or D-pad left / down / right)'
    BINS = [('Red', color.red), ('Green', color.lime), ('Blue', color.azure)]

    def setup(self):
        self.count = 0
        self.wrong = 0
        self.current = 0
        self.package = Entity(parent=self, model='quad', scale=(.22, .22), y=.1, color=color.red)
        self.buttons = []
        for i, (name, col) in enumerate(self.BINS):
            b = Button(parent=self, text=f'{name}  [{i + 1}]', x=(i - 1) * .45, y=-.22,
                       scale=(.38, .14), color=col.tint(-.25))
            b.highlight_color = col
            b.on_click = lambda i=i: self.choose(i)
            self.buttons.append(b)
        self.new_package()

    def new_package(self):
        self.current = random.randrange(3)
        self.package.color = self.BINS[self.current][1]
        self.score_text.text = f'Sorted: {self.count}'

    def choose(self, i):
        if self.done:
            return
        if i == self.current:
            self.count += 1
        else:
            self.wrong += 1
            self.package.shake(duration=.15)
        self.new_package()

    def on_key(self, key):
        if key in ('1', '2', '3'):
            self.choose(int(key) - 1)
        elif key in ('a', 's', 'd'):
            self.choose('asd'.index(key))

    def factor(self):
        return min(2.5, max(0, self.count - 0.5 * self.wrong) / self.TARGET)


class ReactionMini(Mini):
    title = 'Courier Dash'
    instructions = 'Wait for GREEN, then press SPACE (or click). Too early scores zero for that round.'
    duration = 90.0
    show_timer = False
    ROUNDS = 5
    PAD = {'gamepad a': 'space', 'gamepad b': 'space', 'gamepad x': 'space', 'gamepad y': 'space'}
    pad_hint = 'Controller: press A (or any face button) when the light turns green'

    def setup(self):
        self.clock = 0.0
        self.round = 0
        self.points = []
        self.state = 'wait'
        self.wait = random.uniform(1.2, 3.0)
        self.light = Entity(parent=self, model='quad', scale=(1.0, .45), y=.05, color=color.red)
        self.msg = Text('Wait for green...', parent=self, y=-.25, origin=(0, 0), scale=2)
        self.score_text.text = f'Round 1/{self.ROUNDS}'

    def step(self):
        self.clock += time.dt
        if self.state == 'wait':
            self.wait -= time.dt
            if self.wait <= 0:
                self.state = 'go'
                self.go_time = self.clock
                self.light.color = color.lime
                self.msg.text = 'NOW!'
        elif self.state == 'between':
            self.wait -= time.dt
            if self.wait <= 0:
                if self.round >= self.ROUNDS:
                    self.finish()
                    return
                self.state = 'wait'
                self.wait = random.uniform(1.2, 3.0)
                self.light.color = color.red
                self.msg.text = 'Wait for green...'
                self.score_text.text = f'Round {self.round + 1}/{self.ROUNDS}'

    def on_key(self, key):
        if key not in ('space', 'left mouse down'):
            return
        if self.state == 'wait':
            self.points.append(0.0)
            self.msg.text = 'Too early!'
        elif self.state == 'go':
            r = self.clock - self.go_time
            self.points.append(max(0.0, min(1.6, 1.6 - r * 2)))
            self.msg.text = f'{int(r * 1000)} ms'
        else:
            return
        self.round += 1
        self.state = 'between'
        self.wait = 1.1

    def factor(self):
        return sum(self.points) / self.ROUNDS


class MemoryMini(Mini):
    title = 'Security Console'
    instructions = 'Watch the pattern, then repeat it with keys 1-4 (or click the pads).'
    duration = 60.0
    TARGET = 5
    PAD = {'gamepad b': '1', 'gamepad a': '2', 'gamepad x': '3', 'gamepad y': '4'}
    pad_hint = 'Controller: B = red, A = green, X = blue, Y = yellow'
    PADS = [color.red, color.lime, color.azure, color.yellow]

    def setup(self):
        self.rounds = 0
        self.seq = [random.randrange(4) for _ in range(3)]
        self.pads = []
        for i, col in enumerate(self.PADS):
            b = Button(parent=self, text=str(i + 1), x=(i - 1.5) * .3, y=-.05, scale=(.26, .26),
                       color=col.tint(-.5))
            b.on_click = lambda i=i: self.press(i)
            self.pads.append(b)
        self.msg = Text('', parent=self, y=-.3, origin=(0, 0), scale=2)
        self.begin_show(1.0)

    def begin_show(self, delay):
        self.state = 'show'
        self.idx = 0
        self.t = delay
        self.lit = False
        self.msg.text = 'Watch...'
        self.score_text.text = f'Patterns: {self.rounds}'

    def light(self, i, on):
        self.pads[i].color = self.PADS[i] if on else self.PADS[i].tint(-.5)

    def step(self):
        if self.state == 'show':
            self.t -= time.dt
            if self.t > 0:
                return
            if not self.lit:
                if self.idx >= len(self.seq):
                    self.state = 'input'
                    self.idx = 0
                    self.msg.text = 'Your turn!'
                    return
                self.light(self.seq[self.idx], True)
                self.lit = True
                self.t = .5
            else:
                self.light(self.seq[self.idx], False)
                self.lit = False
                self.idx += 1
                self.t = .2
        elif self.state == 'pause':
            self.t -= time.dt
            if self.t <= 0:
                self.begin_show(.2)

    def press(self, i):
        if self.state != 'input' or self.done:
            return
        self.light(i, True)
        invoke(self.light, i, False, delay=.15)
        if i != self.seq[self.idx]:
            self.finish()
            return
        self.idx += 1
        if self.idx >= len(self.seq):
            self.rounds += 1
            self.seq.append(random.randrange(4))
            self.state = 'pause'
            self.t = .7
            self.msg.text = 'Correct!'
            self.score_text.text = f'Patterns: {self.rounds}'

    def on_key(self, key):
        if key in ('1', '2', '3', '4'):
            self.press(int(key) - 1)

    def factor(self):
        return min(2.5, self.rounds / self.TARGET)


class MathMini(Mini):
    title = 'Quick Accounting'
    instructions = 'Type the answer and press ENTER.'
    duration = 30.0
    TARGET = 8
    pad_hint = 'Controller: D-pad or left stick to move on the keypad, A press, X delete, Y submit'

    def setup(self):
        self.count = 0
        self.wrong = 0
        self.entry = ''
        if pad.connected():
            self.kb = PadKeys(self, [['7', '8', '9'], ['4', '5', '6'], ['1', '2', '3'], ['Del', '0', 'OK']],
                              x=.5, y=.18, size=.09)
            self.kb.enabled = pad.using_pad()
        self.q_text = Text('', parent=self, y=.12, origin=(0, 0), scale=5)
        self.a_text = Text('', parent=self, y=-.1, origin=(0, 0), scale=4, color=color.lime)
        self.new_question()

    def new_question(self):
        hi = 9 + self.count * 3
        a, b = random.randint(2, hi), random.randint(2, hi)
        op = random.choice('+-x')
        if op == '-' and b > a:
            a, b = b, a
        if op == 'x':
            a, b = random.randint(2, 6 + self.count // 2), random.randint(2, 9)
        self.answer = a + b if op == '+' else a - b if op == '-' else a * b
        self.q_text.text = f'{a} {op} {b} = ?'
        self.entry = ''
        self.a_text.text = '_'
        self.score_text.text = f'Solved: {self.count}'

    def on_nav(self, d):
        if self.kb:
            self.kb.enabled = True
            self.kb.move(d)

    def on_pad(self, key):
        if not self.kb:
            return
        self.kb.enabled = True
        if key == 'gamepad a':
            tok = self.kb.token()
            self.on_key({'Del': 'backspace', 'OK': 'enter'}.get(tok, tok))
        elif key == 'gamepad x':
            self.on_key('backspace')
        elif key == 'gamepad y':
            self.on_key('enter')

    def on_key(self, key):
        d = digit_of(key)
        if d is not None and len(self.entry) < 6:
            self.entry += d
        elif key == 'backspace':
            self.entry = self.entry[:-1]
        elif key in ('enter', 'return', 'keypad enter', 'numpad enter') and self.entry:
            if int(self.entry) == self.answer:
                self.count += 1
            else:
                self.wrong += 1
            self.new_question()
            return
        self.a_text.text = self.entry or '_'

    def factor(self):
        return min(2.5, max(0, self.count - 0.5 * self.wrong) / self.TARGET)


GAMES = {
    'typing': TypingMini,
    'sort': SortMini,
    'reaction': ReactionMini,
    'memory': MemoryMini,
    'math': MathMini,
}
