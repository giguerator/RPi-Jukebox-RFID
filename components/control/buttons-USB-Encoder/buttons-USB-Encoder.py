#!/usr/bin/env python3

import logging
from subprocess import subprocess
from evdev import InputDevice, categorize, ecodes, KeyEvent
from components.gpio_control.function_calls import functionCallPlayerNext, functionCallPlayerPause, functionCallPlayerPrev, functionCallShutdown, functionCallVolD, functionCallVolU

logger = logging.getLogger()
logger.setLevel('INFO')

# update correct input device here; find the correct one with 'cat /proc/bus/input/devices'
gamepad = InputDevice('/dev/input/event1')

logger.info('USB encoder uses device: {}'.format(gamepad))

for event in gamepad.read_loop():
    if event.type == ecodes.EV_KEY:
        keyevent = categorize(event)
        if keyevent.keystate == KeyEvent.key_down:
            try:
                print(keyevent.keycode)
                if keyevent.keycode == 'BTN_BASE':
                    functionCallShutdown
                elif keyevent.keycode == 'BTN_BASE2':
                    functionCallPlayerPrev
                elif keyevent.keycode == 'BTN_BASE3':
                    functionCallPlayerPause
                elif keyevent.keycode == 'BTN_BASE4':
                    functionCallPlayerNext
                elif keyevent.keycode == 'BTN_BASE5':
                    functionCallVolD
                elif keyevent.keycode == 'BTN_BASE6':
                    functionCallVolU
            except subprocess.CalledProcessError as e:
                logger.warn('USB Encoder: error: {}', e.output)
