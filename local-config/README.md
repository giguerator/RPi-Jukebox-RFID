# Local hardware configuration

Configuration for this fork's physical Phoniebox. Nothing upstream reads this
directory — it exists so the box's setup is version-controlled instead of
living only on the SD card. Files here are copies; the running system reads
them from the paths noted below.

## Deployed box

| | |
|---|---|
| Host | `192.168.86.52` (`raspberrypi`), user `pi` |
| Board | armv6 (Pi Zero / Pi 1), kernel 5.10.63 |
| OS | Raspbian 10 (buster) |
| Phoniebox | v2.3, commit `2425890`, branch `master` |
| Edition | Plus (+Spotify), Mopidy |
| RFID reader | PN532 (`scripts/deviceName.txt`), via stock `Reader.py.experimental` |

Audited 2026-09-11.

## gpio_settings.ini

Live path on the box: `~/RPi-Jukebox-RFID/settings/gpio_settings.ini`.

Read by `components/gpio_control/gpio_control.py`, which hardcodes that absolute
path. Current upstream (`gpio_control.py:132`) still uses the same hardcoded
path, so there is no config-path migration to worry about on an upgrade. The
installer's `EXISTINGuseGpio` prompt copies this file out of `~/BACKUP` into the
new install for you.

(`~/.config/phoniebox/gpio_settings.ini` appears nowhere in upstream — that path
was introduced by the obsolete 2020 `stop_on_removal_PN532` branch.)

Two buttons, both using the stock `ShutdownButton` type and the stock
`functionCallShutdown`. No custom Python is involved.

| Section | BCM pin | Trigger | Hold | Purpose |
|---|---|---|---|---|
| `Shutdown` | 17 | falling, pull-up | 5 s | Power button — press and hold to shut down |
| `LowBattery` | 12 | rising, pull-down | 30 s | Battery LBO line — sustained low battery shuts the box down |

`LowBattery` is wired to the battery module's low-battery-output pin rather than
to a button. The 30 s hold plus 2 s poll interval debounces it, so a momentary
sag under load does not trigger a shutdown.

## Not configured here

- **Stop-on-removal** is upstream's `Swipe_or_Place = PLACENOTSWIPE` setting,
  toggled in the web UI. It is not a local patch.
- **Low-battery splash screen** (ST7789) lives in a separate clone at
  `~/Documents/throttle-status/` on the box and is currently not installed.
