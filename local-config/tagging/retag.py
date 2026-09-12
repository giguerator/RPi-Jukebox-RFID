#!/usr/bin/env python3
"""Derive artist/title/album tags from YouTube-style filenames.

Dry run by default. Pass --apply to write tags.

Files that already carry both an artist and a title are left alone, so the
folders that were tagged properly (21pilots, babyshark) are never touched.

Original tags are dumped to a JSON sidecar before the first write, so a bad
run can be reversed with --revert.
"""

import argparse
import json
import os
import re
import sys

from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError

MUSIC_DIR = "/home/pi/RPi-Jukebox-RFID/shared/audiofolders"
BACKUP = "/home/pi/RPi-Jukebox-RFID/shared/tag-backup.json"

# Folders where the filename carries no artist. Album defaults to the folder
# name unless overridden here. Edit freely - this is the part worth eyeballing.
FOLDER_ARTIST = {
    "21pilots": "twenty one pilots",
    "Alouette": "Comptines",
    "Arthur-L-Aventurier": "Arthur L'aventurier",
    "babyshark": "Pinkfong",
    "Bateau-sur-l-eau": "Comptines",
    "Éléphant": "Comptines",
    "ferme_mathurin": "Comptines",
    "F-Zero": "F-Zero",
    "I-like-to-move-it": "Reel 2 Real",
    "Monde des titounis": "Les Titounis",
    "Passe-Partout": "Passe-Partout",
    "patpatrouille": "Paw Patrol",
    "pigloo": "Pigloo",
    "Pomme-de-reinette": "Comptines",
    "Reine des Neiges": "La Reine des Neiges",
    "Schtroumps": "Les Schtroumpfs",
}

# Trailing YouTube id: "-dQw4w9WgXcQ" or " [dQw4w9WgXcQ]"
RE_ID_BRACKET = re.compile(r"\s*\[[A-Za-z0-9_-]{11}\]$")
RE_ID_DASH = re.compile(r"-[A-Za-z0-9_-]{11}$")

# Promotional noise, in several languages
NOISE = re.compile(
    r"""\s*[\(\[]\s*(?:
        official(?:\s+(?:music\s+)?(?:video|audio|lyric\s+video|visualiser|visualizer))?
      | official\s+[\w'\s]{0,40}
      | visualizer | visualiser | lyric[s]?(?:\s+video)? | audio | hd | hq | 4k
      | live\s+at\s+[\w'\s]{0,40}
      | clip\s+officiel | video\s+officielle? | paroles | avec\s+les\s+paroles
      | original\s+video | comic\s+book\s+video | cover\s+version
      | sing-?along | from\s+["“＂].*?["”＂]
      | de\s+["“＂].*?["”＂]
    )\s*[\)\]]""",
    re.IGNORECASE | re.VERBOSE,
)

# YouTube pipes become underscores on disk: "A _ B _ C" -> keep A
def strip_pipes(name):
    parts = [p.strip() for p in name.split(" _ ")]
    return parts[0] if parts and parts[0] else name


# Descriptive tails common on French children's uploads:
#   "Bateau sur l'eau - Comptine avec gestes pour enfants"
RE_TAIL = re.compile(
    r"\s*[-–—]\s*(?:comptines?|chansons?|berceuses?|"
    r"chanson\s+pour\s+enfants?)\b.*$",
    re.IGNORECASE,
)

# Emoji and other pictographs sprinkled through YouTube titles
RE_EMOJI = re.compile(
    "[🀀-🫿☀-➿🇦-🇿️⬀-⯿]+"
)


def clean(name):
    name = RE_ID_BRACKET.sub("", name)
    name = RE_ID_DASH.sub("", name)
    name = strip_pipes(name)
    prev = None
    while prev != name:
        prev = name
        name = NOISE.sub("", name)
    name = unsmart(name)
    name = RE_TAIL.sub("", name)
    name = RE_EMOJI.sub("", name)
    name = re.sub(r"\s{2,}", " ", name)
    return name.strip(" -–—")


# YouTube titles mix straight and curly apostrophes, which splits one artist
# into several in MPD's list and defeats MusicBrainz lookups.
SMART = {
    "’": "'", "‘": "'", "ʼ": "'",
    "“": '"', "”": '"', "＂": '"',
    "–": "-", "—": "-",
}


def unsmart(v):
    for bad, good in SMART.items():
        v = v.replace(bad, good)
    # Earlier tooling baked shell escaping into some tags: Arthur L'aventurier
    for ch in (chr(39), chr(34)):
        v = v.replace(chr(92) + ch, ch)
    return v


def _norm(v):
    return re.sub(r"[^a-z0-9]", "", (v or "").lower())


def parse(filename, folder):
    stem = os.path.splitext(filename)[0]
    cleaned = clean(stem)
    artist = None
    title = cleaned
    known = FOLDER_ARTIST.get(folder)

    # "Artist - Title", splitting on the FIRST separator only.
    for sep in (" - ", " – ", " — "):
        if sep in cleaned:
            left, right = cleaned.split(sep, 1)
            left, right = left.strip(), right.strip()
            if not (left and right):
                break
            # Where the folder declares an artist, only treat the left side as
            # one if it actually looks like that artist. Otherwise this is a
            # "Title - description" filename ("Alouette... - Comptine avec
            # gestes") and splitting would put the description in the title.
            if known and _norm(left) not in _norm(known) and _norm(known) not in _norm(left):
                break
            artist, title = left, clean(right)
            break

    if not artist:
        artist = known or folder
    return artist, title


def load_tags(path):
    try:
        return EasyID3(path)
    except ID3NoHeaderError:
        return None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write tags")
    ap.add_argument("--revert", action="store_true", help="restore from backup")
    ap.add_argument("--folder", help="limit to one folder")
    ap.add_argument("--normalize", action="store_true",
                    help="rewrite smart quotes in existing tags")
    args = ap.parse_args()

    if args.revert:
        with open(BACKUP) as fh:
            saved = json.load(fh)
        for rel, tags in saved.items():
            path = os.path.join(MUSIC_DIR, rel)
            if not os.path.isfile(path):
                continue
            try:
                a = EasyID3(path)
                for k in ("artist", "title", "album"):
                    a.pop(k, None)
                    if tags.get(k):
                        a[k] = tags[k]
                a.save()
            except Exception as e:
                print("  revert failed %s: %s" % (rel, e))
        print("reverted %d files" % len(saved))
        return

    if args.normalize:
        fixed = 0
        for folder in sorted(os.listdir(MUSIC_DIR)):
            fdir = os.path.join(MUSIC_DIR, folder)
            if not os.path.isdir(fdir):
                continue
            for root, _dirs, files in os.walk(fdir):
              for fn in sorted(files):
                if not fn.lower().endswith(".mp3"):
                    continue
                path = os.path.join(root, fn)
                tags = load_tags(path)
                if tags is None:
                    continue
                changed = False
                for key in ("artist", "title", "album"):
                    cur = (tags.get(key, [""]) or [""])[0]
                    new = unsmart(cur)
                    if new != cur:
                        tags[key] = new
                        changed = True
                if changed:
                    try:
                        tags.save()
                        fixed += 1
                    except Exception as e:
                        print("  FAILED %s: %s" % (fn, e))
        print("normalized %d files" % fixed)
        return

    backup = {}
    if os.path.isfile(BACKUP):
        with open(BACKUP) as fh:
            backup = json.load(fh)

    changes, skipped = [], 0
    for folder in sorted(os.listdir(MUSIC_DIR)):
        fdir = os.path.join(MUSIC_DIR, folder)
        if not os.path.isdir(fdir):
            continue
        if args.folder and folder != args.folder:
            continue
        for root, _dirs, files in os.walk(fdir):
          for fn in sorted(files):
            if not fn.lower().endswith(".mp3"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, MUSIC_DIR)
            tags = load_tags(path)
            cur_artist = (tags.get("artist", [""])[0] if tags else "") or ""
            cur_title = (tags.get("title", [""])[0] if tags else "") or ""
            if cur_artist.strip() and cur_title.strip():
                skipped += 1
                continue
            artist, title = parse(fn, folder)
            album = folder
            changes.append((rel, artist, title, album))
            if args.apply:
                backup.setdefault(rel, {
                    "artist": cur_artist,
                    "title": cur_title,
                    "album": (tags.get("album", [""])[0] if tags else "") or "",
                })

    if args.apply:
        with open(BACKUP, "w") as fh:
            json.dump(backup, fh, indent=1, ensure_ascii=False)
        for rel, artist, title, album in changes:
            path = os.path.join(MUSIC_DIR, rel)
            try:
                try:
                    a = EasyID3(path)
                except ID3NoHeaderError:
                    a = MutagenFile(path, easy=True)
                    a.add_tags()
                a["artist"] = artist
                a["title"] = title
                a["album"] = album
                a.save()
            except Exception as e:
                print("  FAILED %s: %s" % (rel, e))
        print("wrote tags to %d files (backup: %s)" % (len(changes), BACKUP))
    else:
        cur = None
        for rel, artist, title, album in changes:
            folder = os.path.dirname(rel)
            if folder != cur:
                print("\n### %s" % folder)
                cur = folder
            print("  %-34s | %-24s | %s" % (title[:34], artist[:24], album[:18]))
        print("\n%d files would change, %d already tagged and left alone"
              % (len(changes), skipped))


if __name__ == "__main__":
    main()
