#!/usr/bin/env python3
"""Deliver the Lumaris poster to the grading output directory.

The poster image is bundled next to this script as ``entry.png``.  This
program copies those bytes out unchanged after checking that they satisfy
the competition gates: a non-empty file, at most one mebibyte, a recognised
JPEG or PNG header, dimensions no larger than 1024 by 1024 pixels, and a
proper JPEG trailer when the image is a JPEG.

Nothing here touches the network, the clock, or any random source, so two
runs over the same bundle always produce the same output file.

Usage: set MAKEFUN_OUTPUT_DIR to the directory that should receive the
poster (it defaults to ``/output``) and run ``python3 main.py``.
"""

from __future__ import annotations

import os
import sys

MAX_BYTES = 1_048_576
MAX_WIDTH = 1024
MAX_HEIGHT = 1024

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_TRAILER = b"\xff\xd9"


def poster_path() -> str:
    """Absolute path of the bundled poster sitting beside this script."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "entry.png")


def read_jpeg_size(data: bytes) -> tuple[int, int]:
    """Pull (width, height) out of the first baseline/progressive SOF marker.

    Walks the JPEG segment table from the start-of-image marker, skipping
    segments by their declared length, until it reaches a start-of-frame
    marker (SOF0, SOF1 or SOF2).  The height and width live there as
    big-endian 16-bit values, height first.
    """
    pos = 2  # past the FF D8 start-of-image marker
    while pos + 9 <= len(data):
        if data[pos] != 0xFF:
            raise ValueError("malformed JPEG segment table")
        marker = data[pos + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height = int.from_bytes(data[pos + 5:pos + 7], "big")
            width = int.from_bytes(data[pos + 7:pos + 9], "big")
            return width, height
        if marker == 0xD9:  # end of image before any frame: no size found
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            pos += 2  # standalone markers carry no length field
            continue
        segment_len = int.from_bytes(data[pos + 2:pos + 4], "big")
        if segment_len < 2:
            raise ValueError("malformed JPEG segment length")
        pos += 2 + segment_len
    raise ValueError("no start-of-frame marker found in JPEG")


def read_png_size(data: bytes) -> tuple[int, int]:
    """Pull (width, height) out of the PNG IHDR chunk (bytes 16-24)."""
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ValueError("PNG is missing its IHDR chunk")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def check_poster(data: bytes) -> tuple[int, int, str]:
    """Run every competition gate and return (width, height, format)."""
    if not data:
        raise ValueError("poster file is empty")
    if len(data) > MAX_BYTES:
        raise ValueError(
            f"poster is {len(data)} bytes, over the {MAX_BYTES} byte limit"
        )
    if data.startswith(JPEG_MAGIC):
        if not data.endswith(JPEG_TRAILER):
            raise ValueError("JPEG does not end with the FF D9 trailer")
        width, height = read_jpeg_size(data)
        kind = "JPEG"
    elif data.startswith(PNG_MAGIC):
        width, height = read_png_size(data)
        kind = "PNG"
    else:
        raise ValueError("poster is neither JPEG nor PNG (bad magic bytes)")
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        raise ValueError(
            f"poster is {width}x{height}, over the "
            f"{MAX_WIDTH}x{MAX_HEIGHT} limit"
        )
    return width, height, kind


def main() -> int:
    source = poster_path()
    try:
        with open(source, "rb") as handle:
            payload = handle.read()
    except OSError as exc:
        print(f"error: cannot read bundled poster {source}: {exc}",
              file=sys.stderr)
        return 1

    try:
        width, height, kind = check_poster(payload)
    except ValueError as exc:
        print(f"error: poster failed validation: {exc}", file=sys.stderr)
        return 1

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    try:
        os.makedirs(out_dir, exist_ok=True)
        destination = os.path.join(out_dir, "entry.png")
        with open(destination, "wb") as handle:
            handle.write(payload)
        written = os.path.getsize(destination)
    except OSError as exc:
        print(f"error: cannot write poster to {out_dir}: {exc}",
              file=sys.stderr)
        return 1

    if written != len(payload):
        print(
            f"error: wrote {written} bytes but the poster has "
            f"{len(payload)} bytes",
            file=sys.stderr,
        )
        return 1

    print(
        f"poster delivered: {kind} {width}x{height}, {len(payload)} bytes "
        f"-> {destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
