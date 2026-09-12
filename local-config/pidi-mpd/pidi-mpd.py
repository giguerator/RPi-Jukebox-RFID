#!/usr/bin/env python3
"""Drive the Pirate Audio ST7789 from MPD instead of Mopidy.

Replaces mopidy-pidi's PiDiFrontend, which is a Mopidy CoreListener. Everything
below the event source is reused unchanged: the DisplayST7789 / DisplayPIL
render layer including the local battery-icon rendering, the DFRobot MAX17043
fuel gauge driver, and Brainz for album art lookup.

mopidy_pidi and mopidy must remain installed (pidi_display_pil imports its
Display base class from mopidy_pidi.plugin), but neither needs to be running.
"""

import hashlib
import logging
import os
import threading
import time

from mpd import MPDClient, ConnectionError as MPDConnectionError
from mutagen import File as MutagenFile

from pidi_display_st7789 import DisplayST7789
from mopidy_pidi import DFRobot_MAX17043
from mopidy_pidi.brainz import Brainz

MPD_HOST = os.environ.get("MPD_HOST", "localhost")
MPD_PORT = int(os.environ.get("MPD_PORT", 6600))
MUSIC_DIR = "/home/pi/RPi-Jukebox-RFID/shared/audiofolders"
CACHE_DIR = "/home/pi/.cache/pidi-mpd"
EMBED_CACHE_DIR = os.path.join(CACHE_DIR, "embedded")

FPS = 30.0
BATTERY_INTERVAL_SEC = 5.0
# Matches idle_timeout in the old [pidi] section of mopidy.conf. After this long
# with no player event, blank the panel and drop the backlight - otherwise GPIO
# 13 is held high forever, which is a constant drain on a battery-powered box.
# 0 disables sleeping.
IDLE_TIMEOUT_SEC = 900
COVER_NAMES = ("cover.jpg", "cover.png", "folder.jpg", "folder.png", "front.jpg")

logger = logging.getLogger("pidi-mpd")


class DisplayConfig:
    """Matches mopidy_pidi.frontend.PiDiConfig, which the display class expects."""

    rotation = 90
    spi_port = 0
    spi_chip_select_pin = 1
    spi_data_command_pin = 9
    spi_speed_mhz = 80
    backlight_pin = 13
    size = 240
    blur_album_art = True


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.shuffle = False
        self.repeat = False
        self.state = "stop"
        self.volume = 100
        self.progress = 0.0
        self.elapsed = 0.0
        self.length = 0.0
        self.title = ""
        self.album = ""
        self.artist = ""
        self.charge = 50.0
        # wall-clock anchor so the progress bar advances between MPD updates
        self.elapsed_anchor = time.time()
        # last player event, for the idle blank
        self.last_change = time.time()


def find_local_cover(song_file):
    """Look for cover art next to the track before falling back to MusicBrainz."""
    if not song_file:
        return None
    folder = os.path.dirname(os.path.join(MUSIC_DIR, song_file))
    for name in COVER_NAMES:
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def extract_embedded_cover(song_file):
    """Pull artwork embedded in the file itself and cache it as a file on disk.

    MPD 0.21 has no `readpicture` command (that arrived in 0.22), and its
    `albumart` only serves cover files from the song's directory - neither can
    reach embedded art. Read the tag directly instead; mutagen handles ID3,
    FLAC/Vorbis and MP4 alike, so this keeps working regardless of MPD version.

    The display API takes a path, so the image is written to a cache keyed by
    the song's URI.
    """
    if not song_file:
        return None
    path = os.path.join(MUSIC_DIR, song_file)
    if not os.path.isfile(path):
        return None

    key = hashlib.sha1(song_file.encode("utf-8")).hexdigest()
    cached = os.path.join(EMBED_CACHE_DIR, key + ".jpg")
    if os.path.isfile(cached):
        return cached if os.path.getsize(cached) else None

    data = None
    try:
        tags = MutagenFile(path)
        if tags is not None:
            # ID3 (mp3): any APIC frame
            if getattr(tags, "tags", None) is not None:
                for k in tags.tags.keys():
                    if k.startswith("APIC"):
                        data = tags.tags[k].data
                        break
            # FLAC / Ogg
            if data is None and getattr(tags, "pictures", None):
                data = tags.pictures[0].data
            # MP4 / M4A
            if data is None:
                try:
                    covr = tags.get("covr")
                except Exception:
                    covr = None
                if covr:
                    data = bytes(covr[0])
    except Exception:
        logger.exception("embedded art extraction failed for %s", song_file)
        return None

    try:
        # Write even when empty: a zero-byte marker means "checked, none here",
        # so untagged tracks are not re-parsed on every track change.
        with open(cached, "wb") as fh:
            fh.write(data or b"")
    except Exception:
        logger.exception("could not cache embedded art for %s", song_file)
        return cached if data else None

    return cached if data else None


class Renderer(threading.Thread):
    """Redraws at FPS from whatever State currently holds."""

    def __init__(self, state, display, brainz):
        super().__init__(daemon=True)
        self.state = state
        self.display = display
        self.brainz = brainz
        self.running = threading.Event()
        self.running.set()
        self._last_art = None
        self._last_battery_read = 0.0
        self._display_on = True
        self._gauge = None
        try:
            self._gauge = DFRobot_MAX17043.DFRobot_MAX17043()
            self._gauge.begin()
            # The first read after begin() comes back 0.0% / 0.000V before the
            # gauge has settled. Throw it away so the display never shows a
            # spurious empty battery on startup.
            self._gauge.readPercentage()
            time.sleep(0.3)
        except Exception:
            # A dead gauge must not take the display down; charge just stays put.
            logger.exception("MAX17043 init failed, battery readings disabled")

    def set_album_art(self, path):
        if path and path != self._last_art and os.path.isfile(path):
            self.display.update_album_art(path)
            self._last_art = path

    def _read_battery(self, st):
        now = time.time()
        if self._gauge is None or now - self._last_battery_read < BATTERY_INTERVAL_SEC:
            return
        self._last_battery_read = now
        try:
            pct = self._gauge.readPercentage()
            # A 0.0 reading means the gauge hiccuped, not a flat pack - a truly
            # empty cell would have cut power long before this.
            if pct > 0:
                st.charge = round(pct, 2)
        except Exception:
            logger.exception("battery read failed")

    def run(self):
        delay = 1.0 / FPS
        while self.running.is_set():
            with self.state.lock:
                idle_for = time.time() - self.state.last_change

            if IDLE_TIMEOUT_SEC and idle_for >= IDLE_TIMEOUT_SEC:
                if self._display_on:
                    logger.info("idle for %.0fs, blanking display", idle_for)
                    try:
                        self.display.stop()
                    except Exception:
                        logger.exception("display stop failed")
                    self._display_on = False
                # nothing to draw while asleep; stop burning CPU at 30fps
                time.sleep(0.5)
                continue

            if not self._display_on:
                logger.info("waking display")
                try:
                    self.display.start()
                except Exception:
                    logger.exception("display start failed")
                self._display_on = True

            with self.state.lock:
                st = self.state
                self._read_battery(st)
                elapsed = st.elapsed
                if st.state == "play":
                    elapsed += time.time() - st.elapsed_anchor
                progress = (elapsed / st.length) if st.length else 0.0
                args = (st.shuffle, st.repeat, st.state, st.volume,
                        progress, elapsed * 1000.0, st.title, st.album,
                        st.artist, st.charge)
            try:
                self.display.update_overlay(*args)
                self.display.redraw()
            except Exception:
                logger.exception("redraw failed")
            time.sleep(delay)


def apply_status(state, renderer, status, song):
    with state.lock:
        state.state = status.get("state", "stop")
        state.repeat = status.get("repeat") == "1"
        state.shuffle = status.get("random") == "1"
        try:
            state.volume = float(status.get("volume", 0))
        except (TypeError, ValueError):
            state.volume = 0.0
        try:
            state.elapsed = float(status.get("elapsed", 0))
        except (TypeError, ValueError):
            state.elapsed = 0.0
        try:
            state.length = float(status.get("duration", status.get("time", 0)) or 0)
        except (TypeError, ValueError):
            state.length = 0.0
        state.elapsed_anchor = time.time()
        state.last_change = time.time()
        state.title = song.get("title") or os.path.basename(song.get("file", "")) or ""
        state.album = song.get("album") or ""
        state.artist = song.get("artist") or ""
        artist, album, title = state.artist, state.album, state.title

    # A cover file beside the track wins; then art embedded in the file itself;
    # MusicBrainz only as a last resort, since it needs the network and tags.
    art = find_local_cover(song.get("file", "")) or extract_embedded_cover(song.get("file", ""))
    if art:
        renderer.set_album_art(art)
    elif artist or album or title:
        try:
            renderer.brainz.get_album_art(artist, album or title, renderer.set_album_art)
        except Exception:
            logger.exception("album art lookup failed")


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(EMBED_CACHE_DIR, exist_ok=True)

    display = DisplayST7789(DisplayConfig())
    display.start()

    renderer = Renderer(State(), display, Brainz(cache_dir=CACHE_DIR))
    state = renderer.state
    renderer.start()

    client = MPDClient()
    client.timeout = 10
    client.idletimeout = None

    while True:
        try:
            client.connect(MPD_HOST, MPD_PORT)
            logger.info("connected to MPD at %s:%s", MPD_HOST, MPD_PORT)
            apply_status(state, renderer, client.status(), client.currentsong())
            while True:
                # Block until MPD says something changed, then re-read.
                client.idle("player", "mixer", "options")
                apply_status(state, renderer, client.status(), client.currentsong())
        except (MPDConnectionError, OSError) as e:
            logger.warning("MPD connection lost (%s), retrying in 2s", e)
            try:
                client.disconnect()
            except Exception:
                pass
            time.sleep(2)


if __name__ == "__main__":
    main()
