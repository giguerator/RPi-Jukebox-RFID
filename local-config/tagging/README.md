# Library tagging and cover art

One-off cleanup of the existing library, 2026-09-12. New downloads should use
the yt-dlp flags at the bottom instead, so this never needs running again.

## The problem

226 files downloaded from YouTube. Most carried an ID3 container but no
artist/title/album, so:

- the ST7789 display fell back to the filename, showing
  `Taylor Swift - Actually Romantic (Visualizer) [ShsfUTynzQU].mp3`
- MusicBrainz cover lookup could not run at all - it searches on artist+album,
  and both were empty

## retag.py

Derives artist/title/album from the filename. **Dry run by default**; `--apply`
writes, `--revert` restores from `shared/tag-backup.json`.

Files that already have both an artist and a title are skipped, so the folders
that were already tagged (21pilots, babyshark) were never touched - 74 of 226
on the first pass.

Handles the four filename shapes present:

| Shape | Example |
|---|---|
| `Artist - Title (junk) [ID]` | `Ed Sheeran - Bad Habits (Comic Book Video) [KXTM0zXqnu4]` |
| `Title-ID` | `Car Radio-Z_Jp2mlzEjw` |
| `Artist - Title-ID` | `Arthur L'aventurier - Costa Rica-y8Xe1uJv9u8` |
| pipe-separated | `Baby Shark Dance _ Most Viewed Video _ PINKFONG Songs-XqZsoesa55w` |

Cleanup applied: trailing YouTube ids in both `-ID` and ` [ID]` forms;
promotional noise (`(Official Video)`, `[Official Studio BTS]`, `(Visualizer)`,
`(Clip officiel)`, `[Live at ...]`); pipe-separated tails (YouTube `|` becomes
`_` on disk, so only the first segment is kept); French descriptive tails
(`- Comptine avec gestes pour enfants`); emoji; smart quotes and stray shell
escaping (`Arthur L\'aventurier`).

`FOLDER_ARTIST` at the top maps card folders to artists where the filename does
not carry one. **That map is the part worth eyeballing** - it is guesswork.

A "Artist - Title" split is only accepted when the folder declares an artist
*and* the left-hand side actually resembles it. Otherwise the filename is
treated as `Title - description`, which is what
`Alouette, gentille alouette - Comptine avec gestes` really is.

Subfolders are walked, so `Schtroumps/Theme-generique/...` is covered. The card
folder - the first path component - supplies the artist and album.

### Result

    226 files tagged, 0 with a blank artist
    46 distinct artists (was 47, with 'Arthur L'aventurier' split three ways
    by straight vs curly apostrophe and a baked-in backslash)

## fetch_covers.py

Saves one `cover.jpg` per card folder. Dry run by default; `--apply` writes.
Never overwrites an existing `cover.jpg`.

The card folders are not albums - they are `Taylor Swift`, `pigloo`, `Noel` -
so searching MusicBrainz by artist+album the way mopidy-pidi does will not
match. This searches by **artist + track title** to find a recording, walks to
its release, and pulls the front image from the Cover Art Archive.

`cover.jpg` specifically, because `htdocs/api/cover.php` hardcodes that name.
It is the only filename the web UI and the display both read.

Expect misses on niche French-Canadian children's content (Passe-Partout,
Les Titounis, comptines) - MusicBrainz simply does not carry it. Those need a
hand-placed `cover.jpg`, now easy over the Samba share.

## For new downloads

This whole exercise is avoidable going forward:

    yt-dlp --embed-metadata --embed-thumbnail \
           -f bestaudio --extract-audio --audio-format mp3 "URL"

That writes proper tags and embeds the artwork, which `pidi-mpd` reads via
mutagen (see `../pidi-mpd/`). The web UI still wants a `cover.jpg` on disk.
