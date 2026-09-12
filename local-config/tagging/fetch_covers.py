#!/usr/bin/env python3
"""Fetch one cover.jpg per card folder from MusicBrainz / Cover Art Archive.

Dry run by default; pass --apply to write files.

The card folders are not albums (they are "Taylor Swift", "pigloo", "Noel"),
so searching MusicBrainz by artist+album the way mopidy-pidi does will not
match. This searches by artist + track title to find a *recording*, walks to
its release, and pulls the front cover from the Cover Art Archive.

Saved as cover.jpg because htdocs/api/cover.php hardcodes that name - it is the
only filename the web UI and the ST7789 display both read.
"""

import argparse
import os
import sys
import time
import urllib.error
import urllib.request

import musicbrainzngs as mus
from mutagen.easyid3 import EasyID3

MUSIC_DIR = "/home/pi/RPi-Jukebox-RFID/shared/audiofolders"
CAA = "https://coverartarchive.org/release/%s/front-500"
TRIES_PER_FOLDER = 4          # distinct track titles to attempt
RELEASES_PER_TITLE = 5        # candidate releases per title
MIN_SCORE = 90                # reject weak MusicBrainz matches

mus.set_useragent("phoniebox-cover-fetch", "1.0", "https://github.com/giguerator/RPi-Jukebox-RFID")


def folder_tracks(folder):
    """(artist, [titles]) for a card folder, from the tags we just wrote."""
    artists, titles = {}, []
    root = os.path.join(MUSIC_DIR, folder)
    for dirpath, _d, files in os.walk(root):
        for fn in sorted(files):
            if not fn.lower().endswith(".mp3"):
                continue
            try:
                t = EasyID3(os.path.join(dirpath, fn))
            except Exception:
                continue
            a = (t.get("artist", [""]) or [""])[0].strip()
            ti = (t.get("title", [""]) or [""])[0].strip()
            if a:
                artists[a] = artists.get(a, 0) + 1
            if ti:
                titles.append(ti)
    if not artists:
        return None, []
    artist = max(artists.items(), key=lambda kv: kv[1])[0]
    return artist, titles


def caa_front(mbid):
    try:
        req = urllib.request.Request(CAA % mbid, headers={"User-Agent": "phoniebox-cover-fetch/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            if r.status == 200:
                data = r.read()
                if data[:2] == b"\xff\xd8" or data[:8].startswith(b"\x89PNG"):
                    return data
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        pass
    return None


def _key(v):
    return "".join(c for c in (v or "").lower() if c.isalnum())


def artist_matches(want, credit):
    """Loose but not permissive: one name must contain the other."""
    a, b = _key(want), _key(credit)
    if not a or not b:
        return False
    return a in b or b in a


def find_cover(artist, titles):
    seen = set()
    tried = 0
    for title in titles:
        if tried >= TRIES_PER_FOLDER:
            break
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        tried += 1
        try:
            res = mus.search_recordings(artist=artist, recording=title, limit=RELEASES_PER_TITLE)
        except Exception as e:
            print("      musicbrainz error: %s" % e)
            continue
        for rec in res.get("recording-list", []):
            # MusicBrainz returns loose matches. Without checking the credited
            # artist and the match score, "Paw Patrol" happily resolves to an
            # unrelated French release that merely shares a track title.
            try:
                score = int(rec.get("ext:score", "0"))
            except (TypeError, ValueError):
                score = 0
            if score < MIN_SCORE:
                continue
            credits = [c.get("artist", {}).get("name", "")
                       for c in rec.get("artist-credit", [])
                       if isinstance(c, dict)]
            if not any(artist_matches(artist, c) for c in credits):
                continue
            for rel in rec.get("release-list", []):
                mbid = rel.get("id")
                if not mbid:
                    continue
                data = caa_front(mbid)
                if data:
                    return data, "%s / %s" % (rel.get("title", "?"), title)
        time.sleep(1.0)   # MusicBrainz asks for <=1 req/sec
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--folder")
    args = ap.parse_args()

    got, missing, already = [], [], []
    for folder in sorted(os.listdir(MUSIC_DIR)):
        fdir = os.path.join(MUSIC_DIR, folder)
        if not os.path.isdir(fdir):
            continue
        if args.folder and folder != args.folder:
            continue
        target = os.path.join(fdir, "cover.jpg")
        if os.path.isfile(target):
            already.append(folder)
            continue
        artist, titles = folder_tracks(folder)
        if not artist:
            missing.append((folder, "no tags"))
            continue
        print("  %-24s artist=%s" % (folder, artist))
        data, why = find_cover(artist, titles)
        if not data:
            missing.append((folder, "no match"))
            continue
        got.append((folder, why, len(data)))
        if args.apply:
            with open(target, "wb") as fh:
                fh.write(data)
            os.chmod(target, 0o777)

    print("\n=== FOUND ===")
    for f, why, n in got:
        print("  %-24s %-45s %d bytes" % (f, why[:45], n))
    print("\n=== NO COVER ===")
    for f, why in missing:
        print("  %-24s %s" % (f, why))
    print("\n=== ALREADY HAS cover.jpg ===")
    for f in already:
        print("  %s" % f)
    if not args.apply:
        print("\n(dry run - nothing written; pass --apply)")


if __name__ == "__main__":
    main()
