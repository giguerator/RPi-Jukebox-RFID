# Low-battery splash (ST7789)

Corrected versions of the two files that live in `~/Documents/throttle-status/`
on the box (a clone of `M4XDMG/throttle-status`, with these added on top).

**Not deployed.** As of 2026-09-11 the splash has never run on the box.

## Why it never worked

Four independent defects, any one of which was fatal:

1. `testLBO.py` loads its font from `.../roboto/slap/RobotoSlab-Bold.ttf`.
   The directory is `slab`. `ImageFont.truetype()` raises before the script
   reaches the display. See `testLBO.py.patch`.
2. `testsplash.service` spells the key `Execstart`. systemd rejects the unit.
3. It also spells `StardardError`, and sets `Restart=1`, which is not a valid
   value for that key.
4. `WorkingDirectory` points at `/home/pi/throttle-status`, which does not
   exist — the clone is under `~/Documents/`.

The unit was also never copied into `/etc/systemd/system/`.

## Hardware, confirmed present

- SPI enabled (`dtparam=spi=on`), `/dev/spidev0.0` and `0.1` exist
- `ST7789` 0.0.4 and `pidi_display_st7789` installed for python3.7
- `shared/low_bat.png` present
- `RobotoSlab-Bold.ttf` present at the corrected path
- `config.txt` already drives `gpio=25=op,dh`, which `testLBO.py` also sets

Nothing else on the box currently drives the display.

## Open design question

`testLBO.py` draws one frame and exits — it does not watch the battery. Nothing
starts it. The `[LowBattery]` section in `../gpio_settings.ini` currently calls
`functionCallShutdown` directly on BCM 12, so the box powers off with no
warning on screen.

Showing the splash during the 30 s hold means replacing that `functionCall`
with something that draws the splash and then shuts down. That is a change to
the GPIO config and probably a small wrapper script — not just installing this
unit.
