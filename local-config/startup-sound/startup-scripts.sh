#!/bin/bash

# The absolute path to the folder whjch contains all the scripts.
# Unless you are working with symlinks, leave the following line untouched.
PATHDATA="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

###########################################################
# Read global configuration file (and create is not exists) 
# create the global configuration file from single files - if it does not exist
if [ ! -f $PATHDATA/../settings/global.conf ]; then
    . /home/pi/RPi-Jukebox-RFID/scripts/inc.writeGlobalConfig.sh
fi
. $PATHDATA/../settings/global.conf
###########################################################
echo "Phoniebox is starting..."

cat $PATHDATA/../settings/version-number

cat $PATHDATA/../settings/global.conf

echo "${AUDIOVOLSTARTUP} is the mpd startup volume"

####################################
# make playists, files and folders 
# and shortcuts 
# readable and writable to all
sudo chmod -R 777 ${AUDIOFOLDERSPATH}
sudo chmod -R 777 ${PLAYLISTSFOLDERPATH}
sudo chmod -R 777 $PATHDATA/../shared/shortcuts

#########################################
# wait until mopidy/MPD server is running
STATUS=0
while [ "$STATUS" != "ACTIVE" ]; do STATUS=$(echo -e status\\nclose | nc -w 1 localhost 6600 | grep 'OK MPD'| sed 's/^.*$/ACTIVE/'); done

####################################
# Set volume levels on boot
# Both can be set in the Web UI under settings
# Confusion explained:
# 1. Set the volume to the global boot level.
#    Sometimes the Pi sets volume to 0.
#    The first command makes sure there is *some* level, not 0.
# 2. Then set the volume to the startup volume.
#    If the kids crank up the volume at night,
#    after a reboot, the box will be back to this level.
/home/pi/RPi-Jukebox-RFID/scripts/playout_controls.sh -c=setvolumetobootvolume
/home/pi/RPi-Jukebox-RFID/scripts/playout_controls.sh -c=setvolumetostartup

####################
# play startup sound
mpgvolume=$((32768*${AUDIOVOLBOOT}/100))
echo "${mpgvolume} is the mpg123 startup volume"
# Local fix: under systemd's minimal environment mpg123 probes JACK, fails to
# connect, and segfaults (SIGSEGV, exit 139) before reaching ALSA. Forcing the
# alsa module avoids the probe. The explicit device bypasses pcm.!default,
# whose softvol control in /etc/asound.conf points at card 1 while the
# HifiBerry is card 0 - see README.md.
/usr/bin/mpg123 -o alsa -a plughw:CARD=sndrpihifiberry,DEV=0 -f -${mpgvolume} /home/pi/RPi-Jukebox-RFID/shared/startupsound.mp3

#######################
# re-scan music library
mpc rescan 

#######################
# read out wifi config?
if [ "${READWLANIPYN}" == "ON" ]; then
    /home/pi/RPi-Jukebox-RFID/scripts/playout_controls.sh -c=readwifiipoverspeaker
fi

#######################
# Default audio output to speakers (instead of bluetooth device) irrespective of setting at shutdown
if [ -f $PATHDATA/../settings/bluetooth-sink-switch ]; then
    BTSINKSWITCH=`cat $PATHDATA/../settings/bluetooth-sink-switch`
    if [ "${BTSINKSWITCH}" == "enabled" ]; then
	$PATHDATA/../components/bluetooth-sink-switch/bt-sink-switch.py speakers
    fi
fi



