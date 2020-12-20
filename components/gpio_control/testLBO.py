

#!/usr/bin/env python

import time
from PIL import Image, ImageDraw, ImageFont
from ST7789 import ST7789


print("""rainbow.py - Display a rainbow on the Pirate Audio LCD

This example should demonstrate how to:
1. set up the Pirate Audio LCD,
2. create a PIL image to use as a buffer,
3. draw something into that image,
4. and display it on the display

You should see the display change colour.

Press Ctrl+C to exit!

""")

SPI_SPEED_MHZ = 80

img_path="/home/pi/RPi-Jukebox-RFID/shared/low_bat.png"
img= Image.open(img_path,'r')

background = Image.new("RGB", (240, 240), (0, 0, 0))
draw = ImageDraw.Draw(background)
fnt= ImageFont.truetype('/usr/share/fonts/truetype/roboto/slap/RobotoSlab-Bold.ttf',29)
draw.text((10,20),"LOW BATTERY!",font=fnt,fill=(255,0,0))
bg_w, bg_h=background.size
img_w, img_h = img.size
img_w = img_w // 2
img_h = img_h // 2
img.thumbnail([img_w,img_h])
offset = ((bg_w - img_w) // 2,(bg_h - img_h) // 2 + 20)



st7789 = ST7789(
    rotation=90,  # Needed to display the right way up on Pirate Audio
    port=0,       # SPI port
    cs=1,         # SPI port Chip-select channel
    dc=9,         # BCM pin used for data/command
    backlight=13,
    spi_speed_hz=SPI_SPEED_MHZ * 1000 * 1000
)


while(True):
    draw.rectangle(((0,60),(240,240)),(0,0,0))
    st7789.display(background)
    time.sleep(1)
    background.paste(img, offset)
    st7789.display(background)
    time.sleep(1)
