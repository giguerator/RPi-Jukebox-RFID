#!/usr/bin/env bash

HOME_DIR="/home/pi"
JUKEBOX_HOME_DIR="${HOME_DIR}/RPi-Jukebox-RFID"

question() {
    local question=$1
    read -p "${question} (y/n)? " choice
    case "$choice" in
      y|Y ) ;;
      n|N ) exit 0;;
      * ) echo "Error: invalid" ; question ${question};;
    esac
}

printf "Please make sure that the USB Encoder and the buttons are connected before continuing...\n"
question "Continue"

printf "Installing Python requirements for USB encoder...\n"
todo sudo python3 -m pip install --upgrade --force-reinstall -q -r "${JUKEBOX_HOME_DIR}"/components/rfid-reader/RC522/requirements.txt

TODO configure input


printf "Configure RFID reader in Phoniebox...\n"
cp "${JUKEBOX_HOME_DIR}"/scripts/Reader.py.experimental "${JUKEBOX_HOME_DIR}"/scripts/Reader.py
printf "MFRC522" > "${JUKEBOX_HOME_DIR}"/scripts/deviceName.txt
sudo chown pi:www-data "${JUKEBOX_HOME_DIR}"/scripts/deviceName.txt
sudo chmod 644 "${JUKEBOX_HOME_DIR}"/scripts/deviceName.txt

printf "Start phoniebox-usb-encoder service...\n"
sudo cp -v "${JUKEBOX_HOME_DIR}"/components/control/buttons-USB-Encoder/phoniebox-usb-encoder.service.sample /etc/systemd/system/phoniebox-usb-eoncoder.service
sudo systemctl start phoniebox-usb-encoder.service
sudo systemctl enable phoniebox-usb-encoder.service

TODO remove gpio control


printf "Done.\n"
