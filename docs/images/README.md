# Images and video

Media captured while reverse-engineering, wiring and testing the SH03.

## Home Assistant

| File | Shows |
|---|---|
| `HA_Dash2.png` | The ESPHome device page — both chambers, material selects and drying switches |
| `HA_Dash1.png` | The same device page, scrolled to the diagnostic / manual key buttons |

## Photos

| Folder | Contents |
|---|---|
| `Teardown/` | Opening the case and getting the screen board out |
| `ScreenRemoving/` | The front of the unit and the extracted screen board |
| `InsideTheDyer/` | Internals — heaters, fans, humidity sensor, wiring |
| `Screen_PCB_Side/` | The screen board (`SJ_GZH_PM_V1.2`): overview, the `J1`/`J2`/`J3`/`P1` headers and the silkscreen labels |
| `GigalogicChipCloseup/` | Microscope close-ups of the GD32 (GigaDevice) MCU soldering |
| `PhotosFromMicroscope/` | Microscope shots of solder joints and connection points (see below) |
| `Soldering/` | The wires soldered to U2 pin 9 and to C20 |
| `ConnectingScreenToUSB/` | Bench setup: USB hub with ST-Link + CH340, and the `J3` hookup |
| `ScreenUsage_Original/` | Original panel/display reference (one is a retailer image) |

Key microscope shots:

| File | Shows |
|---|---|
| `PhotosFromMicroscope/IMG1011_001.JPG` | U2 pin 9 solder joint (the PA3 tap) |
| `PhotosFromMicroscope/IMG1011_004.JPG` | 5 V tap at capacitor C20 |
| `PhotosFromMicroscope/IMG1011_008.JPG` | `P1` — the SWD header (ST-Link) |
| `PhotosFromMicroscope/IMG1011_009.JPG` | `J3` — the serial header (CH340) |

## Video

| File | Shows |
|---|---|
| `../video/video_2026-10-19_13-37-28.mp4` | **Working demo** — the dryer running while Home Assistant / ESPHome drives it |
| `../video/VID1011_001.mp4` | Microscope pass over the screen board (e.g. the TM1621B LCD driver, U3) |
| `../video/VID1011_002.mp4` | Microscope close-up of the board's silkscreen labels |
