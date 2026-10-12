#!/usr/bin/env python3
"""
patch_sh03.py — apply the "touch over UART" patch to a stock SH03 firmware dump.

The SH03's stock firmware only reads touch codes from the XW05A I2C touch
controller. This patch redirects the touch-read entry point (0x0800b358) to a
small veneer at 0x08012000 that instead consumes a byte from the J3 debug UART
(UART3) when one is waiting, and falls through to the real XW05A I2C read
otherwise. That lets an ESP32 "press" the panel buttons over serial. Physical
touch keeps working exactly as before.

This script contains no vendor code — only the 48 bytes it changes. You supply
your own dump of your own unit:

    python3 -m pyocd cmd -t gd32f303cc -c "savemem 0x08000000 0x40000 sh03_stock.bin"
    python3 patch_sh03.py sh03_stock.bin
    python3 -m pyocd flash -t gd32f303cc sh03_stock_patched.bin

See ../docs/FLASHING.md for the full procedure. A stock SH03 (firmware V3.5.1)
patched with this script yields, over its first 256 KiB:

    sha256 = f116c9a110905f0fdb1735524d5b306b32993ac0f72b5f65060a7d990805369f
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# (offset, expected stock bytes, patched bytes, description)
PATCHES = [
    (
        0x0B358,
        bytes.fromhex("80b584b0"),
        bytes.fromhex("06f052be"),
        "touch-read entry -> 'b.w 0x08012000'",
    ),
    (
        0x12000,
        b"\xff" * 44,
        bytes.fromhex(
            "80b584b000208df80f0044f60043c4f200031888800607d5988840f25a21c2f2000108"
            "70f9f7b4b9f9f79bb9"
        ),
        "veneer: poll UART3 RBNE, else fall through to the XW05A I2C read",
    ),
]

MIN_LEN = max(off + len(patched) for off, _, patched, _ in PATCHES)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("dump", type=Path, help="your stock firmware dump (from pyOCD)")
    ap.add_argument(
        "-o", "--output", type=Path, help="output file (default: <dump>_patched.bin)"
    )
    ap.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="patch even if the stock bytes don't match (only for a known-different "
        "firmware revision)",
    )
    args = ap.parse_args()

    if not args.dump.is_file():
        ap.error(f"no such file: {args.dump}")

    data = bytearray(args.dump.read_bytes())
    if len(data) < MIN_LEN:
        ap.error(
            f"{args.dump} is only {len(data)} bytes; expected at least {MIN_LEN} "
            f"(did the dump succeed?)"
        )

    problems = []
    for off, stock, patched, what in PATCHES:
        current = bytes(data[off : off + len(patched)])
        if current == patched:
            print(f"  [skip]  0x{off:05x}  already patched")
        elif current == stock:
            data[off : off + len(patched)] = patched
            print(f"  [ ok ]  0x{off:05x}  patched  ({what})")
        elif args.force:
            data[off : off + len(patched)] = patched
            print(f"  [force] 0x{off:05x}  stock was {current.hex()} -> patched anyway")
        else:
            problems.append((off, stock, current, what))

    if problems:
        print(
            "\nERROR: this dump doesn't look like the firmware this patch targets.",
            file=sys.stderr,
        )
        for off, stock, current, what in problems:
            print(
                f"  0x{off:05x} ({what})\n"
                f"    expected {stock.hex()}\n"
                f"    found    {current.hex()}",
                file=sys.stderr,
            )
        print(
            "\nMaybe a different firmware revision. Re-check the offsets against "
            "../docs/PROTOCOL.md, or pass --force to patch anyway.",
            file=sys.stderr,
        )
        return 1

    out = args.output or args.dump.with_name(
        args.dump.stem + "_patched" + args.dump.suffix
    )
    out.write_bytes(data)
    print(f"\nwrote {out} ({len(data)} bytes)")
    print(f"sha256 {hashlib.sha256(data).hexdigest()}")
    print(f"\nNow flash it:\n  python3 -m pyocd flash -t gd32f303cc {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
