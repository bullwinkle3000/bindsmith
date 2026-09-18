#!/usr/bin/env python3
"""Do the binds reference controls ED's own button map doesn't define?"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from bindsmith.parser import load_all_binds

ROOT = Path(__file__).resolve().parent.parent
BINDS = "/home/andy/.steam/debian-installation/steamapps/compatdata/359320/pfx/" \
        "drive_c/users/steamuser/AppData/Local/Frontier Developments/" \
        "Elite Dangerous/Options/Bindings"

# controls ED's button map defines for the STECS
text = (ROOT / "data/buttonmaps/231D012C.buttonMap").read_text()
mapped = set(re.findall(r"<(\w+)>", text))

# controls the user's binds actually use on that device
p = load_all_binds(BINDS)["VKB"]
used = set()
for a in p.actions:
    for b in (a.primary, a.secondary) + tuple(a.extra) + tuple(a.holds):
        if b is not None and b.device == "231D012C" and b.key:
            used.add(b.key)

print(f"ED map defines : {len(mapped)} controls")
print(f"binds use      : {len(used)} controls on 231D012C")
print(f"used but UNMAPPED by ED (no label available):")
for k in sorted(used - mapped):
    print("   ", k)
print(f"\nmapped but unused (device has them, binds don't touch):")
print("   ", ", ".join(sorted(mapped - used)))
