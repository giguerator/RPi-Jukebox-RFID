#!/bin/sh
# Pre-export the GPIO pins gpio_control uses, and apply the ownership and mode
# that udev would, before the service starts.
#
# Why: RPi.GPIO's add_event_detect() exports a pin and then immediately writes
# its sysfs "edge" file. The kernel creates that file root:root 0644; the rule
# in /etc/udev/rules.d/99-com.rules that relaxes it to root:gpio 0660 runs
# asynchronously. phoniebox-gpio-control runs as User=pi, so on a busy boot it
# writes "edge" before udev has caught up, gets EACCES, and dies with
#   RuntimeError: Failed to add edge detection
# systemd restarts it 3s later and the second attempt wins, because the pin is
# already exported and udev has since fixed the permissions. Net effect without
# this script: the buttons are dead for roughly the first 45 seconds of a boot.
#
# Doing the export and chmod synchronously here removes the race entirely.
# Exporting early is harmless: RPi.GPIO drives direction and pull-ups through
# /dev/gpiomem, not sysfs, and add_event_detect() copes with an already-exported
# pin.
#
# Runs as root via the "+" prefix on ExecStartPre. Always exits 0 — a failure
# here must never keep the service down, since the retry path still works.

INI=/home/pi/RPi-Jukebox-RFID/settings/gpio_settings.ini
[ -r "$INI" ] || exit 0

# Any key containing "pin" (case-insensitive): Pin, Pin1, Pin2, PinUp, PinDown,
# led_pin. Takes the first run of digits in the value, so trailing ";comments"
# are ignored. Skips commented-out lines.
PINS=$(awk -F'[:=]' '
    /^[[:space:]]*[#;]/ { next }
    tolower($1) ~ /pin/ && match($2, /[0-9]+/) { print substr($2, RSTART, RLENGTH) }
' "$INI" | sort -u)
[ -n "$PINS" ] || exit 0

for p in $PINS; do
    [ -d "/sys/class/gpio/gpio$p" ] || echo "$p" > /sys/class/gpio/export 2>/dev/null
done

# Give sysfs a moment to materialise the attribute files.
sleep 0.3

for p in $PINS; do
    d="/sys/class/gpio/gpio$p"
    [ -d "$d" ] || continue
    chown root:gpio "$d/active_low" "$d/direction" "$d/edge" "$d/value" 2>/dev/null
    chmod 660 "$d/active_low" "$d/direction" "$d/edge" "$d/value" 2>/dev/null
done

exit 0
