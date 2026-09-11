# Hardware reference

`phoniebox-schematic-rev2.pdf` — EasyEDA, drawn by benjamin.giguere.
Sheet 1 rev 2.0 (2020-11-28) PSU board; sheets 2-3 rev 1.0 (2021-01-31) Pi
interface and button/LED board.

## GPIO map, from the schematic

| GPIO | Net | Direction | Purpose |
|---|---|---|---|
| 12 | `LOW_BAT_LVTTL` | **in** | Low-battery, via Q3 2N3906 + R4/R5/R6 from PowerBoost `LBO_N` |
| 14 | `SOFT_PWR_ON` | out | **Power latch.** Held high by `gpio=14=op,dh` in config.txt |
| 15 | `CHG_LVTTL` | **in** | USB-power-present, via 74HC125D buffer from PowerBoost `USB` |
| 17 | `INIT_SHT_DN` | in | Shutdown button |
| 20 | `BTN_PLAY` | in | Play/pause |
| 22 | `BTN_NEXT` | in | Next |
| 27 | `BTN_PREV` | in | Previous |
| 2/3 | `BATT_I2C_SDA/SCL` | — | LC709203F gauge (reads as MAX17043-compatible at 0x36) |

Pins 5, 6, 16, 24 are the Pirate Audio HAT's own buttons, not this board.

This confirms the `[PlayPause2]`, `[NextSong2]` and `[PrevSong]` pins in
`../gpio_settings.ini`, which were derived independently from the old
`[raspberry-gpio]` section of mopidy.conf.

## The LEDs are not software-controlled

Sheet 3 is a separate board: four LEDs (2x red, 1x blue, 1x green), each driven
by a 2N3904 with a 100R series resistor and a 10k base resistor. The bases come
from `LED1`-`LED4` on J2, which lines up pin-for-pin with the `BUTTONS` header
on sheet 2 carrying `SOFT_PWR_ON`, `CHARGE_EN`, `LOW_BAT_LVTTL` and `PB`.

`CHARGE_EN` traces to J13 pin 11, the PowerBoost's raw `USB` signal.

**LED colours in the drawing are wrong.** As built (confirmed by the owner
2026-09-12): LED_1 and LED_2 are **green**, LED_4 is **red**. The schematic
shows LED_1/LED_2 as red and LED_4 as green. Identify LEDs by net, not colour.

The green "charging" light on the box is **LED_2 = `CHARGE_EN`**. It is lit
by hardware whenever USB power is present. It does not indicate that charging
is succeeding, and no software can turn it off.

**So the charging LED is lit by hardware when USB power is present.** No GPIO
output drives it. Nothing in the Mopidy-to-MPD migration could have changed it —
`mopidy-raspberry-gpio` only ever did `GPIO.setup(pin, GPIO.IN, ...)` with a
`handle_do_noting` that is literally `pass`.

## Open discrepancy, 2026-09-12

With the charging LED lit:

- `GPIO15` read `level=0` continuously over 40 s — per the schematic, no USB
  power detected
- the LC709203F showed a steady ~30 %/hour discharge (67.6 % -> 61.8 % over
  21 minutes), unchanged whether the display backlight was lit or blanked

Two of the three indicators say the pack is not charging. Next test is to
unplug USB and see whether the LED goes out: if it does, the USB-sense path
(the 74HC125D buffer, or the `CHARGE_GPIO` 0R link) is not reaching the Pi; if
it stays lit, the LED is wired to something other than `CHARGE_EN`.

**Do not toggle GPIO14 to identify an LED.** It is `SOFT_PWR_ON`, the power
latch — driving it the wrong way cuts power to the box.
