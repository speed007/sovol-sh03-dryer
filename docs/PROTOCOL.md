# SH03 service port — protocol notes

Living document. Update as we learn more.

> **Note.** This is the reverse-engineering log, kept for reference. It refers to
> helper scripts (`capture.py`, `probe.py`, `press.py`, `tapmap.py`, …) and
> intermediate firmware builds that are **not** shipped in this repository —
> they were development tools. For installation, see
> [`FLASHING.md`](FLASHING.md) and [`WIRING.md`](WIRING.md).

## Port characteristics (confirmed)

- UART, **115200 8N1**, ASCII lines terminated with **`\r\n`**.
- The service port emits the **main MCU's debug log**, not (so far) any
  periodic telemetry.
- MCU runs **FreeRTOS** and prints a boot banner.

## Boot banner (power-cycle capture)

```
Frimware Version: V3.5.1        <- note the vendor's typo, "Frimware"
FreeRTOS Version: V11.1.0
Init_Task create successed
```

FreeRTOS **V11.1.0** is a fairly recent kernel. Combined with the log style,
this is a Cortex-M class MCU (not an ESP as far as we can tell).

## Event log lines observed

Format: `<Task/Chamber> <event>\r\n`, plain ASCII, no checksum visible.

| Line | Meaning |
|---|---|
| `Task_Drying1 queue recv. p->cmd:1` + `RUN` | Chamber 1 command `1` received → run |
| `Task_Drying1 queue recv. p->cmd:0` | Chamber 1 command `0` received (pause) |
| `Task_Drying2 queue recv. p->cmd:0` | Chamber 2 command `0` received |
| `Chamber1 EV_WORK_RUN_Bit` | Chamber 1 entered working/running state |
| `Chamber2 EV_WORK_RUN_Bit` | Chamber 2 entered working/running state |
| `EV_WORK_PAUSE_Bit` | Entered paused state (chamber not named) |
| `Chamber1 Fan FG detect error` | Fan tachometer (FG) fault |

### Working hypothesis on the command token

The panel appears to send **`p->cmd:<n>`** to the main MCU over a UART; the MCU
parses it into a FreeRTOS queue and the task logs receipt.

- `p->cmd:0` = pause / stop
- `p->cmd:1` = run / start
- `p->cmd:2`, `p->cmd:3`, ... = unknown (candidates to probe)

The `p` may be a pointer to a per-chamber struct, so chamber 2 might use a
different prefix/token — **TBC**.

## Open questions

1. **Is the port bidirectional?** Does the MCU accept injected commands, or is
   it TX-only? → test with `probe.py`.
2. **Is there periodic telemetry?** We only captured ~7 s of an active run and
   saw no temperature/humidity lines. Need a longer (3–5 min) drying capture.
3. **How are temperature / time / material conveyed?** Changing temp on the
   panel produced no log line. Either the panel buffers them and sends on
   start, or they travel a different path.
4. **Chamber 2 start command** wasn't logged in the `run_ui` capture (only its
   RUN bit and its stop). Re-test cleanly, one action at a time.
5. **Is the service port wired to the same UART as the touch panel** (so we'd
   see panel traffic too), or is it a dedicated debug UART?
6. What MCU is it? (chip marking on the main board.)

## Experiment log

- 2026-10-10: boot + UI capture. Confirmed 115200 8N1 ASCII event log,
  firmware V3.5.1, FreeRTOS V11.1.0. Temp changes produce no output.
- 2026-10-10: first injection attempt — **confounded**. Injected
  `p->cmd:1/1/2/3` while *also* using the touchscreen, so chamber RUN/PAUSE
  events cannot be attributed. Notably `p->cmd:2` and `p->cmd:3` were sent but
  **never appeared in the RX log**; only `p->cmd:1` and `p->cmd:0` did.
  → Clean screen-free test required (`probe.py --one :1 --listen 20`).
- 2026-10-10: **clean screen-free injection test — NEGATIVE.** Sent
  `p->cmd:1`, `p->cmd:0`, `p->cmd:2` as isolated one-shots. No RX echo, no
  `queue recv` log, no physical chamber response. Conclusion: the service
  port's RX is **not read by the running firmware** (TX-only debug console, or
  RX reserved for the bootloader). The MCU's command parser lives on a
  *different* UART.
- 2026-10-10: UI arming sequence observed by hand: tap chamber (1/2) -> that
  side blinks (armed) -> tap run/pause -> runs. This is a two-touch UI safety
  pattern; the panel still sends a single `p->cmd:1` to actually run.
- 2026-10-12: **corrected Key 1 semantics.** Key 1 is a 2-state *armed-chamber*
  toggle (Ch1 ↔ Ch2); an even number of presses returns to the same chamber.
  The earlier "toggle ch1/ch2/both" wording was an inference from firmware
  strings and was later misread as a third focus position. "Both" means both
  chambers running at once, not a third toggle state.

## Confirmed conclusion (2026-10-10)

The service port is a **read-only debug console**:
- We see the MCU *logging* commands it received (`Task_Drying1 queue recv.
  p->cmd:1`), i.e. we're seeing the MCU's own printf output.
- Injecting the exact same bytes the panel sends produces nothing, so the port
  is **not** the UART the command parser reads.

=> For full control we must reach the **panel <-> MCU UART** inside the case
   (the bus `p->cmd:1` actually travels on).

## Architecture (corrected 2026-10-10)

- The **touchscreen board contains the main MCU** — it runs the FreeRTOS
  V3.5.1 firmware, reads the temperature sensors and fan tachometers, and
  drives the heaters/fans. The `5V GND TX RX` debug header is **on the screen
  board**, not the main PCB.
- The **main board is a power/driver board**: mains input, relays/MOSFETs,
  transformers, `POWER / HOT1 / HOT2 / MOT` terminals, fan connectors.
- `p->cmd:N` is an **internal FreeRTOS queue message** (UI task -> drying task),
  not an external command. The debug UART is a `printf` console; nothing reads
  commands there, which is why injection did nothing.
- **Safety:** with the screen (J1/J2) disconnected, the main board's driver
  inputs float and the **heaters go full on**. Never power it with the screen
  unplugged.

## Firmware (dumped via SWD, 2026-10-10)

`sh03.bin` — 512 KB, GD32F303, no readout protection. Key strings recovered:

- `Frimware Version: %s` / `FreeRTOS Version: %s` (V3.5.1 / V11.1.0)
- **Humidity sensor = `GXHT30`** (I2C, SHT30-compatible — measures **temp AND
  humidity**). String: `Chamber%d GXHT30 I2C reset successed.` Two channels,
  so likely addresses **0x44 (ch1) and 0x45 (ch2)**.
- **Touch controller = `XW05A`** (I2C): `XW05A_Get_TouchCode: i2c read failed`.
- Display = segment LCD via **TM1621B**.
- FreeRTOS tasks: `Init_Task, Task_SensorDataUpdate, Task_KeyScan,
  Task_SystemMonitor, Task_InteractiveProcess, Task_Drying,
  Task_CountDownTimer, Task_SystemErrAlarm`.
- `Task_Drying%d queue recv. p->cmd:%d` confirms `p->cmd:N` is **internal IPC**
  (UI task -> drying task), not a UART protocol.
- Material presets in strings: `pPETG pABS pPVA pASA` (PLA etc.).
- Peripheral literals found: **I2C1 (0x40005400) and I2C2 (0x40005800)** — two
  I2C buses, likely one for sensors, one for touch.

**No UART command parser exists** — the `J3` console is printf-only. That's why
injection did nothing. So there is no ready-made command channel.

### Routes to control
- **A. ESP32 takeover** — rejected by owner (wants to keep stock firmware).
- **B. Patch the stock firmware** to source the touch code from the `J3` UART.
- **C. Virtual XW05A** — ESP32 acts as I2C slave at `0x41` on bus `0x40005800`.

## Touch path (decoded from disassembly, 2026-10-10)

- `XW05A_Get_TouchCode` @ `0x0800b356` reads the touch chip into RAM
  `0x20000258`; the **code byte is at `0x2000025a`**.
- I2C read helper @ `0x0800b930`; bus handle @ `0x20000000` whose `+4` field
  is **`0x40005800`** (second I2C). Uses DMA.
- Transmit helper @ `0x08004d98` sets/clears **bit0 = R/W** before writing the
  data register -> the byte `0x82` is an **address byte** => **XW05A = 0x41**.
- Raw code -> internal key 1..6 via TBB @ `0x0800b3a6`:

  | raw | key | | raw | key |
  |---|---|---|---|---|
  | `0xE7`,`0xEF` | 1 | | `0xFB` | 3 |
  | `0xF7` | 2 | | `0xF9`,`0xFD` | 4 |
  | `0xF8`,`0xFA` | 6 | | `0xFC`,`0xFE` | 5 |
  | `0xFF` + others | none | | | |

- RAM snapshot (app running): `0x20000258 = 82 00 FF 00` (addr byte 0x82,
  last code 0xFF = no touch). I2C2 + DMA + GPIOA/C + TIMER0 handles visible.

## Firmware patch (flashed 2026-10-10)

Goal: let the ESP32 "press keys" over UART while keeping the stock UI + touch.

- **J3 debug UART = UART3 @ `0x40004C00`**, 115200, **TX+RX enabled** (mode 0xC),
  pins on GPIOC.
- Patch `XW05A_Get_TouchCode` (`0x0800b358`): entry rewritten to `b.w 0x08012000`.
- Veneer @ `0x08012000`: replicates the prologue, then checks UART3 `STAT0`
  (`0x40004C00`) bit 5 (RBNE). If a byte is waiting, it stores it to the touch
  buffer `0x2000025a` and jumps to the stock mapping (`0x0800b390`); otherwise
  it falls through to the stock XW05A I2C read (`0x0800b362`) so physical touch
  still works.
- Send raw codes over J3 RX: 1→`E7` 2→`F7` 3→`FB` 4→`F9` 5→`FC` 6→`F8`,
  release `FF`. Helper: `press.py`.

### Flashing recipe (worked)

- Chip: **GD32F303CC** (256 KB code flash / 48 KB SRAM). OpenOCD's stm32f1x
  driver times out; the GigaDevice FMC needs its own algorithm.
- Use **pyOCD** with GigaDevice's DFP:
  ```
  python3 -m pyocd pack install GD32F303CE
  python3 -m pyocd flash -t gd32f303cc sh03_patched_256k.bin
  ```
  (CE target faults: its flash algo uses 64 KB RAM. CC works.)
- Images: `sh03_patched.bin` (512K), `sh03_patched_256k.bin` (use this),
  `sh03_patched_128k.bin` (fallback). Original dump = `sh03.bin` (recovery).
- Debug builds: `sh03_debug2_256k.bin` (echoes injected byte on J3 TX),
  `sh03_keyprint_256k.bin` (prints `*<key>` on J3 TX for **every** touch read).

## UI key map (confirmed by tapping the physical screen, 2026-10-11)

The touch read is **edge-driven** (XW05A INT on `PA3`/`U2 pin 9`, EXTI3/IRQ9).
Pulling that line low = a "touch". The read only runs on that event.

| key | code | physical button |
|---|---|---|
| 1 | `E7` | **Chamber Switch / Copy** (`1/2`): short = toggle the **armed** chamber between 1 and 2; long-press 2s = copy params. It is a **2-state** toggle (an even number of presses returns to the same chamber). "Both" is a *run* state (both chambers drying at once), **not** a third toggle position. |
| 2 | `F7` | **Setting Selection / Auto Mode** (gear): short = cycle params; long-press 2s = auto mode |
| 3 | `FB` | Increase (up) |
| 4 | `F9` | Decrease (down) |
| 5 | `FC` | Start / End |
| 6 | `F8` | unused (panel has only 5 buttons) |

**Flow:** select chamber (`1`) -> tap `2` to make the active chamber's filament
blink, then `3`/`4` to cycle material, then `2` again to move to time, `3`/`4`
for hours/minutes -> `5` to start. **Stop:** `1`, `1`, `5` — Key 1 is a 2-state
toggle, so the two presses land back on the target chamber before `5` stops it.

**Injection recipe:** send the key byte on `J3` RX, then pulse `PA3`/U2 pin 9
**low briefly** (~50-100 ms), then release. A long hold desyncs the stock touch
state machine (physical touch then only clicks). Physical touch and injection
coexist when the pulse is short.

**Beware:** the screen standalone (J1/J2 unplugged from the main board) hard-
faults, so the touch task never runs — injection only works with the dryer
assembled.




## Screen board (SJ_GZH_PM_V1.2, 20250826) — the brain

- **U1 = GigaDevice GD32F303** (Cortex-M4) — the MCU.
- **U3, U4** = `TM1621B` (Titan Micro) — LCD **segment** drivers. The "screen"
  is a custom segment LCD (hence the blinking chamber indicators), not a TFT.
- **J1, J2** = 16-pin ribbons to the power board — signals silkscreened.
- **J3** = `3V3 RX TX GND` = the debug UART (3.3V logic).
- **P1** = `3V3 IO CK GND` = **SWD header**. Owner has an **ST-Link** ->
  firmware dump/flash is possible (pending RDP status).

### J1/J2 signal names (confirmed from closeup)

**J1** (power / analog / heater / fan / humidity), pins bottom→top:
`GND, 5V, MC_HUM_SCL, MC_HUM_SDA, MC_K_FAN1, MC_K_FAN1_FG, MC_K_FAN2,
MC_K_FAN2_FG, MC_K_FAN3, MC_K_FAN3_FG, MC_HOT1, MC_HOT2, TH1, TH2`

**J2** (spool-rotation motors + hall), pins bottom→top:
`GND, GND, 3V3, MC_HALLA, MC_XQA1, MC_XQA2, MC_HALLB, MC_XQB1, MC_XQB2,
MC_HALLC, MC_XQC1, MC_XQC2, MC_HALLD, MC_XQD1, MC_XQD2`

Meaning: the MCU reads thermistors (`TH1/TH2`), an I2C humidity sensor
(`MC_HUM_SCL/SDA`), fan tach (`MC_K_FANx_FG`) and hall sensors (`MC_HALLx`),
and drives 3 fans (`MC_K_FANx`), 2 heaters (`MC_HOT1/2`) and 4 spool motors
(`MC_XQx1/2`). All low-voltage logic — the mains switching is on the power
board. **J1/J2 is safe to probe.**



