#!/usr/bin/env python3
"""Report controls a profile uses that ED's own button map does not name.

ED ships a control-label map per device. It is not always complete: some
controls are live and bindable but absent from the map, so the game shows them
as a bare key (``Joy_42``) with no name. This prints that gap, plus the
controls the profile never touches (usually free slots worth binding).

    python3 tools/check_coverage.py [profile.binds] [device-id]

Defaults to the profile committed in this repo and the VKB STECS.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bindsmith.parser import parse_binds  # noqa: E402

profile_path = Path(sys.argv[1]) if len(sys.argv) > 1 \
    else ROOT / "data/presets/vkb_gladiator_seed.binds"
device = sys.argv[2] if len(sys.argv) > 2 else "231D012C"
map_path = ROOT / f"data/buttonmaps/{device}.buttonMap"

if not profile_path.exists():
    sys.exit(f"no such profile: {profile_path}")
if not map_path.exists():
    sys.exit(f"no button map for device {device}: {map_path}")

mapped = set(re.findall(r"<(\w+)>", map_path.read_text(encoding="utf-8")))

preset = parse_binds(profile_path)
used: set[str] = set()
for action in preset.actions:
    for b in (action.primary, action.secondary) + tuple(action.extra) + tuple(action.holds):
        if b is not None and b.device == device and b.key:
            used.add(b.key)

print(f"profile        : {profile_path.name}")
print(f"device         : {device}")
print(f"ED map defines : {len(mapped)} controls")
print(f"binds use      : {len(used)} controls")
print(f"\nused but UNMAPPED by ED (no label available):")
for k in sorted(used - mapped):
    print("   ", k)
print(f"\nmapped but unused (device has them, binds don't touch):")
print("   ", ", ".join(sorted(mapped - used)) or "(none)")
