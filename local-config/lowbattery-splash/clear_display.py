#!/usr/bin/env python3
# Blank the ST7789 and switch its backlight off.
# testLBO.py leaves its last frame on the panel; in normal operation that is
# fine because a shutdown follows immediately. Use this after testing it by hand.

from PIL import Image
from ST7789 import ST7789

st7789 = ST7789(
    rotation=90,
    port=0,
    cs=1,
    dc=9,
    backlight=13,
    spi_speed_hz=80 * 1000 * 1000
)

st7789.display(Image.new('RGB', (240, 240), (0, 0, 0)))
st7789.set_backlight(0)
