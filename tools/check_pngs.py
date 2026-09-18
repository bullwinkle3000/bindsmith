#!/usr/bin/env python3
"""Minimal PNG sanity check: dimensions + rough content density.

A blank or error page compresses to a few KB; a rendered app does not.
"""
import struct
import sys
import zlib
from pathlib import Path

for p in sorted(Path("/tmp").glob("bindsmith-*.png")):
    data = p.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        print(f"{p.name}: NOT A PNG")
        continue
    w, h = struct.unpack(">II", data[16:24])
    # sum of decompressed IDAT bytes ≈ how much real content is in the image
    idat = b""
    i = 8
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        if typ == b"IDAT":
            idat += data[i + 8:i + 8 + ln]
        i += 12 + ln
    try:
        raw = zlib.decompress(idat)
        uniq = len(set(raw[:200000]))
    except zlib.error:
        uniq = -1
    print(f"{p.name}: {w}x{h}  {len(data)//1024} KB  distinct-bytes={uniq}")
