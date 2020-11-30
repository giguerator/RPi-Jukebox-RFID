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

#printf "Installing Python requirements for USB encoder...\n"
#todo sudo python3 -m pip install --upgrade --force-reinstall -q -r "${JUKEBOX_HOME_DIR}"/components/control/buttons-USB-Encoder/requirements.txt

#TODO configure input

printf "Start phoniebox-usb-encoder service...\n"
sudo cp -v "${JUKEBOX_HOME_DIR}"/components/control/buttons-USB-Encoder/phoniebox-usb-encoder.service.sample /etc/systemd/system/phoniebox-usb-eoncoder.service
sudo systemctl start phoniebox-usb-encoder.service
sudo systemctl enable phoniebox-usb-encoder.service

printf "Disabling phoniebox-gpio-control service as its not needed...\n"
sudo systemctl stop phoniebox-gpio-control.service
sudo systemctl disable phoniebox-gpio-control.service

printf "Done.\n"
