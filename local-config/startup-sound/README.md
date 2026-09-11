# Startup sound: fixing the mpg123 segfault

The startup sound had never played. Fixed and verified 2026-09-11.

## Symptom

Every boot, in `phoniebox-startup-scripts.service`:

    Cannot connect to server socket err = No such file or directory
    jack server is not running or cannot be started
    JackShmReadWritePtr::~JackShmReadWritePtr - Init not done for -1, skipping unlock
    startup-scripts.sh: line 53: 3171 Segmentation fault  /usr/bin/mpg123 -f -9830 ...

## Why it was hard to see

The command runs fine from an interactive shell — exit 0, audio plays. It only
fails under systemd. Reproduced deliberately with a stripped environment:

    $ env -i /usr/bin/mpg123 -f -9830 shared/startupsound.mp3
    ... jack server is not running or cannot be started
    exit=139          # 128 + SIGSEGV

With no session environment, mpg123 probes its output modules, reaches JACK,
fails to connect, and segfaults in that failure path before ever trying ALSA.
Interactively the richer environment selects a working module first.

## Fix

`scripts/startup-scripts.sh` line 53 (backup on box: `.orig-20260911`):

    -/usr/bin/mpg123 -f -${mpgvolume} .../startupsound.mp3
    +/usr/bin/mpg123 -o alsa -a plughw:CARD=sndrpihifiberry,DEV=0 -f -${mpgvolume} .../startupsound.mp3

`-o alsa` skips the module probe entirely. The explicit device is needed because
of a second, independent bug — see below.

Verified on a real boot: `Decoding of startupsound.mp3 finished.`,
`ExecMainStatus=0`, no segfault, and audible confirmation from the user.

Cost: boot went 1 min 59.1 s → 2 min 3.6 s. The ~4.5 s is the sound actually
playing rather than crashing instantly. That is the point of the change.

## Second bug, worked around not fixed

`/etc/asound.conf` points at a card that does not exist:

    pcm.hifiberry {
        type            softvol
        slave.pcm       "plughw:CARD=sndrpihifiberry,DEV=0"
        control.name    "Master"
        control.card    1      <-- card 1
    }
    ctl.!default {
        type            hw
        card            1      <-- card 1
    }

But `/proc/asound/cards` lists exactly one card:

     0 [sndrpihifiberry]: RPi-simple - snd_rpi_hifiberry_dac

Almost certainly stale from before `dtparam=audio=off` disabled onboard audio,
which promoted the HifiBerry from card 1 to card 0. Anything opening ALSA
`default` hits `Cannot open CTL hw:1`.

The mpg123 fix sidesteps `pcm.!default` with an explicit device rather than
editing this file, because Mopidy currently works and changing global audio
config to fix a startup sound is the wrong risk trade. Correcting both `1`s to
`0` is probably right, but should be done deliberately and tested against
Mopidy playback and the web UI volume control.
