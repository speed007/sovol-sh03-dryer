# Sovol / Comgrow SH03 filament dryer → Home Assistant

> **Disclaimer:** I am not a programmer but use AI for my benefit! If you are ok
> with it then proceed — or well, not! Also, as I have not yet received any
> permission to upload patched or original firmware from Sovol/Comgrow, you will
> have to obtain it by yourself following this guide! As Sovol is very
> Open-Source friendly they might agree for me to upload it here, so go and
> convince them!

Control a **stock** Comgrow / Sovol SH03 dual-chamber filament dryer from Home
Assistant — and, through HA, from Klipper/Moonraker and Spoolman — **without
replacing the stock firmware and without losing the physical touchscreen.**

A small patch to the dryer's own firmware makes its touch-read routine also
consume a byte from the `J3` debug UART. An ESP32-C3 running ESPHome sends the
touch code for a button, then briefly pulses the touch controller's interrupt
line to make the dryer "press" that button. Real fingers keep working exactly as
before.

![The SH03 screen board](docs/images/Screen_PCB_Side/photo_2026-10-10_20-18-27.jpg)

[![Working demo — the dryer running, driven from Home Assistant](docs/images/HomeAssistant.jpg)](docs/video/video_2026-10-19_13-37-28.mp4)

*The dashboard above is clickable — it opens the working-demo video. More
photos and clips: [`docs/images/`](docs/images/README.md).*

## Status

Working. All five panel buttons are drivable from HA; chamber focus, material
selection and start/stop are exposed as proper entities. Read
[Known issues](#known-issues) before trusting it in an automation.

## Hardware

| Part | Detail |
|---|---|
| Dryer | Comgrow / Sovol SH03 — dual independent chambers, 4 spools, 45–85 °C, 400 W |
| Dryer brain | **GigaDevice GD32F303CC** (Cortex-M4) on the screen board, `SJ_GZH_PM_V1.2` |
| Bridge | **ESP32-C3** (`esp32-c3-devkitm-1`), running ESPHome |

The screen board holds the MCU; the main board is power/driver only.

## Wiring

| ESP32-C3 | Dryer | Notes |
|---|---|---|
| GPIO4 (TX) | `J3` RX | sends the touch-code byte |
| GPIO5 (RX) | `J3` TX | optional — reads the stock debug log |
| GPIO6 | `PA3` / `U2` pin 9 | touch interrupt; open-drain, ~1 kΩ series resistor |
| GND | GND | common ground — mandatory |
| 5V | `J1` pin 2 or USB | power; not both at once |

Full detail, connector pinouts and safety notes: **[docs/WIRING.md](docs/WIRING.md)**.

> ⚠️ The screen board is the brain. With the `J1`/`J2` ribbons unplugged the
> heater driver inputs float and the **heaters can go full on**. Never power the
> dryer with the screen disconnected.

## Flashing

**1 — Dryer firmware.** One-off, via an ST-Link (SWD). This repo ships no vendor
firmware — you dump your own unit and patch it:

```bash
python3 -m pyocd pack install GD32F303CE
python3 -m pyocd cmd -t gd32f303cc -c "savemem 0x08000000 0x40000 sh03_stock.bin"
python3 firmware/patch_sh03.py sh03_stock.bin
python3 -m pyocd flash -t gd32f303cc sh03_stock_patched.bin
```

Keep `sh03_stock.bin` — it's your recovery image. Full step-by-step (SWD wiring,
verification, roll-your-own): **[docs/FLASHING.md](docs/FLASHING.md)**.

**2 — ESP32.** Ordinary ESPHome (a static IP is set in the config — worth
keeping on cloned C3 minis, whose WiFi is often marginal):

```bash
cd esphome
cp secrets.yaml.example secrets.yaml   # then edit it
esphome run sh03-dryer.yaml
```

## Entities and services

Per chamber (`Ch1` / `Ch2`):

- `select` — **ChN Material**: PLA/PET/PC/PP/PA/ASA/PIA/TPU/ABS/PETG
- `switch` — **ChN Drying**: on starts with the selected material, off stops
- `sensor` — **ChN Finishes At**: estimated completion time

HA services:

| Service | Variables | Effect |
|---|---|---|
| `esphome.<node>_sh03_start` | `chamber` (1/2), `material` (0–9) | start, or switch material if already drying |
| `esphome.<node>_sh03_stop` | `chamber` | stop |
| `esphome.<node>_sh03_set_focus` | `chamber` (0 = unknown) | tell the ESP which chamber the panel is on |
| `esphome.<node>_sh03_resync` | `chamber`, `material`, `running` | resync tracked state after manual use |

All key traffic goes through one queued script, so concurrent automations run
one after another instead of fighting over the single UART/touch line.

## How it works

1. The stock firmware maps a raw touch code to a key via a table at
   `0x0800b3a6`. Key codes: `1`=E7 chamber, `2`=F7 settings, `3`=FB up,
   `4`=F9 down, `5`=FC start/stop, `6`=F8 unused.
2. The entry of `XW05A_Get_TouchCode` (`0x0800b358`) is redirected to a veneer
   at `0x08012000`. The veneer checks UART3 (`0x40004C00`) for a waiting byte;
   if there is one it uses it as the touch code, otherwise it falls through to
   the real XW05A I²C read.
3. Touch reads are edge-driven (XW05A INT on `PA3`). The ESP32 sends the key
   byte on `J3` RX, then pulses `PA3` low for ~60 ms to trigger a read.

Full reverse-engineering notes: **[docs/PROTOCOL.md](docs/PROTOCOL.md)**.

## Repository layout

```
esphome/     sh03-dryer.yaml (working config) + secrets example
firmware/    patch_sh03.py — applies the firmware patch to your own dump
docs/        WIRING, FLASHING, PROTOCOL, the SH03 manual, photos + video
```

## Known issues

- **Drying switch fires a stop at boot.** Both `ChN Drying` switches use the
  template-switch default `restore_mode: ALWAYS_OFF`, so `setup()` calls
  `turn_off()`, triggering `turn_off_action` → `run_job(stop)`. On a warm reboot
  (OTA) while drying, the restored `running_*` flag is still true and the boot
  stop sequence is sent — **an OTA update will stop a running cycle.** Fix: add
  `restore_mode: DISABLED` to both switches.
- **Open loop.** The dryer gives no state readback, so anything done on the
  physical panel desyncs the ESP's tracked state. Use `sh03_resync` (or the
  diagnostic buttons) after manual use.
- **`Finishes At` is an estimate**, derived from per-material default times —
  the dryer keeps running regardless.
- **Chamber focus is a 2-state toggle** (Ch1 ↔ Ch2); the stop sequence relies on
  an even number of Key-1 presses returning to the same chamber.
- **No temperature/humidity telemetry yet.** The `J3` console is a printf-only
  debug log with no periodic readings.

## Credits

Reverse-engineered, patched and wired by the repo author. Built with
[ESPHome](https://esphome.io/) and [pyOCD](https://pyocd.io/).

## Disclaimer

Unaffiliated with Comgrow, Sovol or GigaDevice. Ships no vendor firmware — just
a patch script you apply to your own dump; see [`NOTICE`](NOTICE). Modifying and
reflashing a mains-powered appliance is done entirely at your own risk.

## Licence

MIT — see [`LICENSE`](LICENSE). Third-party material (the product manual and one
retailer photo) is covered by [`NOTICE`](NOTICE), not MIT.
