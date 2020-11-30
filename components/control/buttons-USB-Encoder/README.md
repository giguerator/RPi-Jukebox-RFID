# USB Encoder Buttons

Taken from [issue 1156](https://github.com/MiczFlor/RPi-Jukebox-RFID/issues/1156).

Supports the button functionality that are connected via [USB Encoder]( https://www.amazon.de/gp/product/B01N0GZQZI/).

The USB Encoder is the easy solution for anyone who doesn't want to solder, but also wants arcade buttons.

## Usage

1. The USB Encoder only needs to be plugged in. You dont need to install any drivers. After plugging in, it acts like an input device.
2. Find the input device with `cat /proc/bus/input/devices` and look for the **Handlers=** entry
3. Add that to `buttons-USB-Encoder.py` in line 9
4. Run the script `setup_USB_Encoder.sh`
5. Update the **BTN_BASE** values in `buttons-USB-Encoder.py` depending on where you connected which button. See schematics:

![USB Encoder schematics](usb-encoder.jpg)
