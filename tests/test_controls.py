"""Run with:  python -m unittest discover -s tests   (no window or controller needed)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ursina import held_keys

import controls as pad


class ControlsTests(unittest.TestCase):
    def tearDown(self):
        for k in list(held_keys):
            if k.startswith('gamepad'):
                held_keys[k] = 0

    def test_dead_zone_and_scaling(self):
        held_keys['gamepad left stick x'] = 0.1
        self.assertEqual(pad.axis('left stick x'), 0.0)
        held_keys['gamepad left stick x'] = 1.0
        self.assertAlmostEqual(pad.axis('left stick x'), 1.0)
        held_keys['gamepad left stick x'] = -0.6
        self.assertLess(pad.axis('left stick x'), 0)

    def test_triggers_are_clamped(self):
        held_keys['gamepad right trigger'] = 1.7
        self.assertEqual(pad.trigger('right'), 1.0)
        held_keys['gamepad right trigger'] = -0.2
        self.assertEqual(pad.trigger('right'), 0.0)

    def test_button_translation_per_context(self):
        self.assertEqual(pad.translate('world', 'gamepad x'), 'e')
        self.assertEqual(pad.translate('world', 'gamepad start'), 'escape')
        self.assertEqual(pad.translate('panel', 'gamepad b'), 'escape')
        self.assertEqual(pad.translate('drive', 'gamepad x'), 'y')       # accept order
        self.assertEqual(pad.translate('drive', 'gamepad b'), 'n')       # skip order
        self.assertEqual(pad.translate('drive', 'gamepad back'), 'm')    # map
        self.assertEqual(pad.translate('world', 'w'), 'w')               # keyboard keys pass through

    def test_last_input_tracking(self):
        pad.note_input('gamepad a')
        self.assertTrue(pad.using_pad())
        pad.note_input('gamepad a up')                                   # releases do not count
        self.assertTrue(pad.using_pad())
        pad.note_input('left mouse down')                                # nor does the mouse
        self.assertTrue(pad.using_pad())
        pad.note_input('w')
        self.assertFalse(pad.using_pad())

    def test_dpad_up_press_is_not_mistaken_for_a_release(self):
        self.assertFalse(pad.is_release('gamepad dpad up'))            # the press itself ends in ' up'
        self.assertTrue(pad.is_release('gamepad dpad up up'))          # its release
        self.assertTrue(pad.is_release('gamepad a up'))
        self.assertFalse(pad.is_release('gamepad a'))
        pad.note_input('w')
        pad.note_input('gamepad dpad up')
        self.assertTrue(pad.using_pad())

    def test_menu_navigation_repeats_while_held(self):
        nav = pad.Nav()
        held_keys['gamepad left stick y'] = -1.0
        self.assertEqual(nav.poll(.016), 'down')                         # immediate
        self.assertIsNone(nav.poll(.1))                                  # waits before repeating
        self.assertIsNone(nav.poll(.1))
        self.assertEqual(nav.poll(.3), 'down')                           # then repeats
        held_keys['gamepad left stick y'] = 0.0
        self.assertIsNone(nav.poll(.016))
        held_keys['gamepad left stick x'] = 1.0
        self.assertEqual(nav.poll(.016), 'right')


if __name__ == '__main__':
    unittest.main()
