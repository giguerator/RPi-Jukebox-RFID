# RFID latency and boot time

Measured and changed 2026-09-11 on the live box (Pi Zero 1, armv6, v2.3).

## Upstream does not fix this

`scripts/daemon_rfid_reader.py` is byte-identical between v2.3 and current
develop for everything timing-related. `time.sleep(0.2)` and `signal.alarm(1)`
are unchanged. The only diffs in four years are `time.time()` →
`time.monotonic()` and comment cleanup. **Upgrading V2 buys nothing here.**

## Where the time went

Measured on the box, not estimated:

| Operation | Cost |
|---|---|
| `playout_controls.sh` (any command) | **~0.95 s** |
| `playlist_recursive_by_folder.php` | 0.26 s |
| bare `php -r 'exit(0);'` | 0.25 s |
| `mpc status` round-trip to Mopidy | 0.12 s |
| bare `bash -c true` | 0.03 s |

The dominant cost is `playout_controls.sh`: 1137 lines of bash sourcing 15
config files, re-parsed on every invocation. PHP was a red herring — its 0.26 s
is almost entirely interpreter startup, and it runs once per tap.

`playerpauseforce`, the command the removal path calls, is in full:

    sleep $VALUE
    mpc pause

So ~0.95 s of shell startup to run a 0.12 s command.

## Changes applied

`daemon_rfid_reader.py.patch` (backup on box: `.orig-20260911`):

1. **Removal handler calls `/usr/bin/mpc pause` directly** instead of
   `playout_controls.sh -c=playerpauseforce -v=0.1`. Verified equivalent by
   reading the implementation. Saves ~0.85 s, and drops the deliberate 0.1 s
   sleep that command adds.
2. **`signal.alarm(1)` → `signal.setitimer(signal.ITIMER_REAL, 0.5)`.**
   `alarm()` only accepts whole seconds, so 1 s was a hard floor on removal
   detection. `setitimer` takes a float.
3. **`time.sleep(0.2)` → `time.sleep(0.05)`** at the top of the read loop.

Expected removal latency: **~1.95 s → ~0.6 s**.

0.5 s is deliberately conservative. 0.3 s is available if it proves stable —
the risk is a spurious pause if the PN532 ever takes longer than the timer to
confirm a card that is still present.

### Debug logging

`settings/debugLogging.conf` had `DEBUG_rfid_trigger_play_sh="TRUE"` — the one
script that runs on every card tap. Each debug line is a separate
`echo >> debug.log`, so every tap did dozens of open/write/close cycles to SD.
Set to FALSE; the 727 KB log was archived.

## Boot

Baseline: **2 min 8 s** (kernel 4.4 s + userspace 2 min 4 s).

    1min 38.990s  phoniebox-startup-scripts.service
         21.768s  exim4.service
         16.285s  lighttpd.service
         13.667s  nmbd.service
         13.535s  smbd.service

`phoniebox-startup-scripts.service` is not itself slow — it blocks on one line
waiting for port 6600:

    while [ "$STATUS" != "ACTIVE" ]; do STATUS=$(... nc -w 1 localhost 6600 ...); done

The RFID daemon does **not** wait for it — it is live at boot+35 s. But a tap
before Mopidy is up produces `mpd error: Connection refused`, so the real
usable-boot-time is Mopidy readiness: **~95 s** under boot contention, against
**26 s** measured idle. The remaining ~70 s is contention for one armv6 core.

Disabling Iris *and* Spotify changed Mopidy readiness from 25.9 s to 26.5 s —
i.e. nothing. The cost is Mopidy's Python/GStreamer core, not its extensions.
Trimming extensions is not a lever.

### Services disabled

- `exim4` — a mail transfer agent on a jukebox; `MailWlanIpYN=OFF`, so unused
- `colord` — masked; colour management on a headless box
- `phpsessionclean.timer` — disabled

Bluetooth (`hciuart`, ~7 s) was left alone: it is active, and disabling it would
rule out a BT speaker later.

Re-enable with `systemctl enable exim4`, `systemctl unmask colord`,
`systemctl enable phpsessionclean.timer`.

### Result after the service trims

Rebooted 2026-09-11 21:36.

| | Before | After |
|---|---|---|
| Total boot | 2 min 8.4 s | **1 min 59.1 s** |
| `phoniebox-startup-scripts` | 1 min 39.0 s | 1 min 32.3 s |

Only ~9 s. The service trims were not the lever, because the bottleneck is not
contention — it is Mopidy itself. Monotonic timeline of the boot after the fix:

    [ 33.9s]  Phoniebox RFID-Reader started
    [ 35.2s]  systemd starts Mopidy
    [ 93.4s]  Mopidy's FIRST log line: "Starting Mopidy 3.2.0"
    [109.1s]  Mopidy backends up
    [118.6s]  startup script unblocks

**Mopidy spends 58 s between launch and printing anything** — pure Python import
time for Mopidy, GStreamer, pykka and every extension on one armv6 core. Plus
~15 s of init. Mopidy is ~74 s of a ~119 s boot.

### Plain MPD, measured

MPD 0.21.5 is already installed and fully configured on the box (music dir,
playlist dir, hifiberry output) — just disabled.

    MPD READY IN: 6.23 s

Against Mopidy's 26 s idle / ~74 s at boot. That figure includes MPD's database
scan, which had not run in years, so steady-state is likely lower.

Projected boot if Mopidy were replaced: **~119 s → ~50 s.**

Caveat observed during the test: `mpc status` under plain MPD reported
`volume: n/a`. Mopidy provides SoftwareMixer; mpd.conf would need its mixer
configured before `VOLUMEMANAGER=mpd` behaves.

### Known bug, not fixed

`mpg123` **segfaults** on the startup sound every boot, after JACK connection
errors:

    startup-scripts.sh: line 53: 3171 Segmentation fault  /usr/bin/mpg123 ...

The startup sound has never played. Removing that line would save a little boot
time and lose nothing.
