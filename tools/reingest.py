#!/usr/bin/env python3
"""Re-ingest button maps and report the result.

    python3 tools/reingest.py

Idempotent: labels/keys are refreshed, curated roles are preserved.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bindsmith.devices import load_devices
from bindsmith.ingest import ingest_buttonmaps

summary = ingest_buttonmaps(ROOT / "data" / "buttonmaps", ROOT / "data" / "devices")
print(f"created {len(summary['created'])}  updated {len(summary['updated'])}  "
      f"skipped {len(summary['skipped'])}")

devs = load_devices(ROOT / "data" / "devices")
print(f"\ndevices loaded: {len(devs)}")

bad = [d for d in devs.values() if "\n" in (d.name or "") or "\t" in (d.name or "")]
print(f"names containing newline/tab (should be 0): {len(bad)}")
for d in bad[:5]:
    print("   !", repr(d.name[:70]))

print("\nrole coverage on the two VKB units:")
for key in ("231D0200", "231D012C"):
    d = devs.get(key)
    if d:
        roled = [c for c in d.controls if c.role]
        print(f"  {key}  {d.name[:52]:<52} {len(roled)}/{len(d.controls)} roled")
        print(f"      roles: {', '.join(sorted({c.role for c in roled}))}")
    else:
        print(f"  {key}  MISSING")
