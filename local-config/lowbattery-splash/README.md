# Low-battery splash (ST7789)

Corrected versions of the two files that live in `~/Documents/throttle-status/`
on the box (a clone of `M4XDMG/throttle-status`, with these added on top).

**Deployed 2026-09-11.** Before that date the splash had never run.

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

## How it is wired

`ShutdownButton.callbackFunctionHandler` polls the pin every `iteration_time`
for `hold_time` and only then calls the configured `functionCall`. It exposes no
per-iteration hook other than an LED pin, so the splash cannot be shown *during*
the 30 s hold — only once the hold completes, immediately before shutdown.

`gpio_control.py` resolves `functionCall` with
`getattr(self.function_calls, name)`, so the hook has to be a method on
`phoniebox_function_calls`. Hence `function_calls.py.patch`, which adds
`functionCallLowBatteryShutdown`: it runs `testLBO.py` with a 15 s timeout,
swallows any exception so a display fault can never block the shutdown, then
delegates to the stock `functionCallShutdown`.

`../gpio_settings.ini` `[LowBattery]` now points at that method.

`testsplash.service` is therefore **not needed** for the low-battery path and is
not installed. Keep it only if you want to trigger the splash by hand.

## Verified

- `testLBO.py` exits 0 as both `pi` and `root` after the font fix
- `getattr` resolves `functionCallLowBatteryShutdown` on the instance
- `phoniebox-gpio-control` restarts clean: "adding GPIO-Device, LowBattery",
  "Ready for taking actions", no traceback

## Not verified

The end-to-end path has **not** been triggered. Doing so requires either a real
low-battery event or a deliberate shutdown of the box, since the final step is a
genuine power-off. The splash step and the config wiring were verified
separately, but the two have never run in sequence.

## Pre-existing, unrelated

- `RuntimeError: Failed to add edge detection` on first start after boot,
  144 occurrences in the journal going back months. systemd's `RestartSec=3`
  retries and the second attempt succeeds, so buttons are dead for roughly the
  first 45 s after boot.
- The box powers itself off on the 60 min idle timer
  (`settings/Idle_Time_Before_Shutdown`), via `sudo poweroff` from `atd`. That
  path does not go through `functionCall`, so it will not show the splash —
  which is correct.
