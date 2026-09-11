# Fixing `RuntimeError: Failed to add edge detection`

`phoniebox-gpio-control` failed on its first start after every boot — 144
occurrences in the journal before this fix. systemd's `Restart=always` /
`RestartSec=3` retried and the second attempt succeeded, so the symptom was
subtle: **the buttons were dead for roughly the first 45 seconds after boot.**

## Cause

`SimpleButton.__init__` calls `GPIO.add_event_detect()`
(`GPIODevices/simple_button.py:87`). RPi.GPIO implements edge detection through
sysfs: it exports the pin, then immediately writes the pin's `edge` file.

The kernel creates `edge` as `root:root 0644`. The rule that relaxes it is
asynchronous — `/etc/udev/rules.d/99-com.rules:59`:

    SUBSYSTEM=="gpio", KERNEL=="gpio*", ACTION=="add", PROGRAM="/bin/sh -c
      'chown root:gpio /sys%p/active_low /sys%p/direction /sys%p/edge /sys%p/value ;
       chmod 660 ...'"

The service runs as `User=pi`. On a busy boot it writes `edge` before udev has
caught up, gets `EACCES`, and the process exits 1.

Reproduced directly on an unused pin (26):

    # immediately after export
    -rw-r--r-- 1 root root /sys/class/gpio/gpio26/edge
    $ echo falling > /sys/class/gpio/gpio26/edge
    bash: Permission denied

    # one second later, after udev
    -rw-rw---- 1 root gpio /sys/class/gpio/gpio26/edge

The retry succeeds because by then the pin is already exported and udev has
fixed the permissions.

## Fix

`phoniebox-gpio-prepare.sh` runs before the service, as root, and does the
export plus the chown/chmod synchronously — the same thing udev would do, just
not racily. Wired in through a drop-in so a Phoniebox reinstall that rewrites
the unit file cannot silently drop it.

Install:

    sudo install -m 755 -o root -g root phoniebox-gpio-prepare.sh \
      /usr/local/sbin/phoniebox-gpio-prepare.sh
    sudo mkdir -p /etc/systemd/system/phoniebox-gpio-control.service.d
    sudo install -m 644 -o root -g root 10-gpio-edge-race.conf \
      /etc/systemd/system/phoniebox-gpio-control.service.d/
    sudo systemctl daemon-reload

The `+` prefix on `ExecStartPre` runs the helper as root despite `User=pi`.
Needs systemd >= 231; the box has 241.

The helper reads the pin list out of `settings/gpio_settings.ini` rather than
hardcoding it, so it keeps working if the mapping changes. Verified against both
the live config (finds `12 17`) and the stock example in `gpio_settings.ini.bak`
(finds `3 5 6 16 17 19 20 21 22 23 26 27`, covering `PinUp`, `PinDown`, `Pin1`,
`Pin2`).

It always exits 0: if it ever fails, the old retry path still works, so it must
never be the thing that keeps the service down.

## Verified

- Pins torn down and service restarted: comes up with `NRestarts=0`, logs
  `Ready for taking actions`, no traceback
- Running the helper alone, then testing as `pi` with no delay: `edge` is
  `root:gpio 0660` and writable — the exact operation that failed before

## Not verified

Behaviour across an actual reboot. The teardown test reproduces the state but
not the boot-time load that makes udev lose the race in the first place.
