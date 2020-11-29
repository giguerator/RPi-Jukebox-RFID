# USB Encoder Buttons

Taken from [issue 1156](https://github.com/MiczFlor/RPi-Jukebox-RFID/issues/1156).

Supports the button functionality that are connected via [USB Encoder]( https://www.amazon.de/gp/product/B01N0GZQZI/).

The USB Encoder is the easy solution for anyone who doesn't want to solder, but also wants arcade buttons.

## Usage

1. The USB Encoder only needs to be plugged in. You dont need to install any drivers. After plugging in, it acts like an input device.
2. Run the script `setup_USB_Encoder.sh`
3. The script has to be variable because the input device number depends on the devices that are attached.

The other variable stuff is how you map the GPIO on the keyboard. There are many possibilities to map the buttons:

![USB Encoder schematics](usb-encoder.jpg)
