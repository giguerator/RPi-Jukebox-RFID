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

## Two regressions the swap caused, and their fixes

Both surfaced only after a reboot in normal use. Neither was visible in the
service states — everything reported `active` while nothing worked.

### 1. Nothing played, from RFID or the web UI

`settings/edition` was `plusSpotify`. `playlist_recursive_by_folder.php` branches
on it: `plusSpotify` emits Mopidy URIs, `classic` emits plain paths.

    local:track:pigloo/Beijos%20de%20Esquim%C3%B3%20%28Bizoo%20D%27Eskimo%29-...mp3

Plain MPD has no idea what `local:track:` is, so `mpc load pigloo` silently
loaded **0 tracks**. MPD itself was healthy the whole time — `mpc add` + `mpc play`
on a raw file worked fine, which is what made this confusing.

Fix: `settings/edition` → `classic`, and `EDITION` in `settings/global.conf` to
match. Playlists regenerate on each swipe, so stale ones heal themselves.

Verified end to end: `./rfid_trigger_play.sh --cardid=1195791950544896` loads
5 tracks and plays.

### 2. All the music buttons stopped

`mopidy-raspberry-gpio` was handling them, so they died with Mopidy. The
mapping was in `/etc/mopidy/mopidy.conf`:

    bcm5  = play_pause      bcm20 = play_pause
    bcm6  = volume_down     bcm24 = volume_up
    bcm16 = next            bcm22 = next
    bcm27 = prev            bcm15 = do_nothing

Only `Shutdown` (17) and `LowBattery` (12) were in `gpio_settings.ini`, which is
why `gpio_control` looked healthy — it was loading everything it was asked to.

Fix: those seven pins moved into `../gpio_settings.ini` as `Button` sections
(`active_low` → `pull_up: True`), mapped to the stock `functionCallPlayerPause`,
`functionCallVolU`/`VolD`, `functionCallPlayerNext`/`Prev`. `bcm15` was
`do_nothing` and is omitted.

**Known trade-off:** these route through `playout_controls.sh`, which costs
~0.95 s per press (see `../rfid-latency/`). Mopidy handled them in-process. If
the buttons feel sluggish, the same fix used for the RFID removal path applies —
call `mpc` directly for next/prev/pause. Volume is worth leaving alone, since
`playout_controls.sh` enforces the max-volume limit.

### 3. Display never slept, so the charge LED stayed lit

`mopidy-pidi` was configured with `idle_timeout = 900` in the `[pidi]` section
of `mopidy.conf`. After 15 minutes with no player event it called
`display.stop()`, which drops the backlight and issues `ST7789_DISPOFF`.

The first version of `pidi-mpd.py` did not implement that at all, so GPIO 13
was held high permanently — a constant extra load on a battery-powered box,
which showed up as the charging light never going out.

Fix: `IDLE_TIMEOUT_SEC = 900` in the daemon, matching the original. The render
thread blanks the panel once idle and drops to a 0.5 s poll instead of spinning
at 30 fps, then wakes on the next MPD event.

Verified with a temporary 20 s timeout:

    INFO idle for 20s, blanking display     -> GPIO 13: level=0
    INFO waking display                     -> GPIO 13: level=1

## Album art

Three sources, tried in this order:

1. **A cover file beside the track** — `cover.jpg`, `cover.png`, `folder.jpg`,
   `folder.png`, `front.jpg`. Fastest, works offline.
2. **Art embedded in the file itself** — read with mutagen and cached under
   `~/.cache/pidi-mpd/embedded/`, keyed by a hash of the song URI.
3. **MusicBrainz**, via the reused `mopidy_pidi.brainz`. Needs artist + album
   tags and the network.

Embedded art is read directly rather than through MPD: `readpicture` arrived in
MPD 0.22 and the box runs 0.21.4, and `albumart` only serves cover files from
the song's directory. Reading the tag with mutagen sidesteps the version issue
and handles ID3, FLAC/Vorbis and MP4 alike.

Files with no embedded art get a zero-byte cache marker so they are not
re-parsed on every track change.

**Note the web UI wants something different.** `htdocs/api/cover.php` hardcodes
`cover.jpg` in the folder — it reads neither `.png` nor embedded art. So
`cover.jpg` is the only filename that satisfies both the display and the web UI.

As of 2026-09-12 exactly 1 of 226 files in the library has embedded art, so
source 2 is effectively forward-looking — for downloads made with
`yt-dlp --embed-thumbnail --embed-metadata`.

## What was lost

- **Iris**, Mopidy's web UI. The Phoniebox PHP web UI is unaffected.
- **Spotify**, which was already auto-disabled on this box due to config errors.
- The Info page's "Mopidy Server Status" panel will now show Mopidy down. Cosmetic.
