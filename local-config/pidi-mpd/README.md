# Replacing Mopidy with MPD, keeping the display

Done 2026-09-11. Display confirmed working by the user, before and after reboot.

## Why

Mopidy accounted for ~74 s of a ~119 s boot. 58 s of that was Python import
time *before it logged its first line* — Mopidy, GStreamer, pykka and every
extension, on one armv6 core. Disabling Iris and Spotify changed readiness by
0.6 s, so extensions were never the problem.

Plain MPD, already installed and configured on the box, was ready in 6.2 s.

The blocker was the display: `mopidy-pidi` is a Mopidy frontend, and this box
has local modifications to it (battery charge from a DFRobot MAX17043 gauge —
see `../display-stack/`).

## Result

| | Original | After service trims | After MPD swap |
|---|---|---|---|
| Total boot | 2 min 8.4 s | 1 min 59.1 s | **1 min 9.7 s** |
| userspace | 2 min 4.1 s | 1 min 55.6 s | **1 min 6.3 s** |
| `phoniebox-startup-scripts` | 1 min 39.0 s | 1 min 32.3 s | **10.2 s** |

Post-swap boot timeline:

    [33.9s]  Phoniebox RFID-Reader started
    [58.7s]  MPD started
    [58.9s]  pidi-mpd started
    [69.0s]  Phoniebox Startup finished (startup sound played)

Usable — i.e. a card tap actually plays — at ~59 s instead of ~110 s.

## How the display was kept

`pidi-mpd.py` replaces **only** `mopidy_pidi.frontend.PiDiFrontend`, which was a
Mopidy `CoreListener`. Everything below that is reused unchanged:

- `pidi_display_st7789.DisplayST7789` / `pidi_display_pil.DisplayPIL`, including
  the local battery-icon rendering
- `mopidy_pidi.DFRobot_MAX17043`, the fuel gauge driver
- `mopidy_pidi.brainz.Brainz`, album art lookup

It blocks on MPD's `idle` rather than polling, prefers a local `cover.jpg` /
`folder.jpg` next to the track before falling back to MusicBrainz, survives a
dead battery gauge, and reconnects if MPD goes away.

> **Do not `pip uninstall mopidy` or `mopidy-pidi`.** `pidi_display_pil` imports
> its `Display` base class from `mopidy_pidi.plugin`. Both packages must stay
> installed; neither needs to run.

## Config bugs fixed on the way

Both were pre-existing and are why plain MPD had presumably been abandoned.

**`/etc/asound.conf`** (`../alsa/`) pointed its softvol control and default CTL
at card 1. The HifiBerry is card 0 and the only card — onboard audio is off via
`dtparam=audio=off`. Anything opening ALSA `default` got
`Cannot open CTL hw:1`.

**`/etc/mpd.conf`** (`../mpd/`) had the stock `"My ALSA Device"` example
`audio_output` enabled *alongside* the HifiBerry block, so MPD opened the same
device twice. It also had no mixer on the HifiBerry output, so `mpc status`
reported `volume: n/a` and `VOLUMEMANAGER=mpd` could not set volume. Disabled
the example block, added `mixer_type "software"` to match what Mopidy's
SoftwareMixer did.

## Install

    sudo install -m 755 -o root -g root pidi-mpd.py /usr/local/bin/pidi-mpd.py
    sudo install -m 644 -o root -g root pidi-mpd.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl disable mopidy
    sudo systemctl enable --now mpd pidi-mpd

Rollback is one command — Mopidy is still installed and configured:

    sudo systemctl disable --now pidi-mpd mpd && sudo systemctl enable --now mopidy

Backups on the box: `/etc/asound.conf.orig-20260911`,
`/etc/mpd.conf.orig-20260911`.

## Tuning note

`pidi-mpd` uses ~17-23% CPU rendering at 30 fps — the same rate the original
mopidy-pidi ran at, so not a regression. On a single armv6 core that competes
with the RFID reader. Lowering `FPS` in the daemon to 10 would free real
headroom; the only cost is a choppier progress bar.

## What was lost

- **Iris**, Mopidy's web UI. The Phoniebox PHP web UI is unaffected.
- **Spotify**, which was already auto-disabled on this box due to config errors.
- The Info page's "Mopidy Server Status" panel will now show Mopidy down. Cosmetic.
