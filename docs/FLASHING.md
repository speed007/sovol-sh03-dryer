# Flashing the dryer firmware

The SH03's own firmware has to be patched before it will accept touch codes over
the `J3` UART. This is a **one-off** step. Use the ready-made image in
`firmware/patched/` — you do **not** need a CH340 or any reverse-engineering
tools for this.

> ⚠️ **Mains appliance.** Work on it unplugged from mains where you can, and
> never power it with the screen ribbons (`J1`/`J2`) disconnected — the heater
> driver inputs float and the heaters can go full on.

## What you need

- An **ST-Link V2** (or clone) — the SWD programmer.
- `pyocd` on your PC:

  ```bash
  pip install pyocd
  python3 -m pyocd pack install GD32F303CE   # GigaDevice flash algorithm
  ```

  OpenOCD's generic `stm32f1x` driver does **not** work on this part.

## Connect the ST-Link

The SWD pads are on the screen board at **`P1`**, labelled `3V3 IO CK GND`.

| ST-Link | P1  | Notes |
|---------|-----|-------|
| GND     | GND | connect first |
| SWDIO   | IO  | |
| SWCLK   | CK  | |
| 3.3V    | 3V3 | powers the board during flashing |

**You do not need to power the dryer from mains to flash it.** The ST-Link's
3.3 V (from its own USB) is enough to run the MCU for SWD. That's the easy and
safe route — nothing is plugged into mains, so the heaters can't fire.

The screen board on its own may hard-fault (the touch task waits on hardware
that isn't attached). That is irrelevant to flashing — SWD works no matter what
the firmware is doing. It only matters later, when you *test* injection: that
needs the dryer fully assembled. If your ST-Link's 3.3 V browns out on the
board, power the dryer normally instead (screen attached).

![SWD header on the screen board](images/pinout/photo_2026-10-11_01-11-17.jpg)

## Flash the patch

```bash
python3 -m pyocd flash -t gd32f303cc firmware/patched/sh03_patched_256k.bin
```

- The target is **`gd32f303cc`** — the CC part (256 KB flash). The `CE` target
  faults, because its flash algorithm expects 64 KB of RAM.
- A harmless SVD parse warning from pyOCD can be ignored.

## Verify

Power-cycle the dryer. With a CH340 or any 3.3 V USB-serial adapter on `J3`
(115200 8N1) you can watch the boot banner:

```
Frimware Version: V3.5.1
FreeRTOS Version: V11.1.0
Init_Task create successed
```

(The vendor's "Frimware" typo is real.) Once patched, sending the key byte `E7`
on `J3` RX and pulsing `PA3` low switches the chamber — that's exactly what the
ESP32 does.

## Recovery — put the original back

If anything goes wrong, restore the untouched dump:

```bash
python3 -m pyocd flash -t gd32f303cc firmware/original/sh03_original_256k.bin
```

That file is the first 256 KB of a raw SWD dump (the upper half of the 512 KB
read is blank `0xFF`). It differs from the patched image only at `0x0b358`
(the entry stub) and `0x12000`–`0x1202b` (the veneer).

## Side note — rolling your own patch

If you want to dump *your* unit and patch it yourself (say, a different firmware
revision), you'll additionally want:

- a **CH340** (or any 3.3 V USB-serial adapter) on `J3` for the serial console
  and for injecting test bytes, and
- the reverse-engineering notes in [`PROTOCOL.md`](PROTOCOL.md), which document
  the touch path, the veneer, the key map and the patch addresses.

The CH340 is a development tool only. End users flashing the ready-made image
never need one.

## ESP32 side

Flashing the ESP32-C3 is a separate, ordinary ESPHome job — see the main
[README](../README.md#esphome) and [`WIRING.md`](WIRING.md).
