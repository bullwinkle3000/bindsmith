#!/usr/bin/env python3
"""End-to-end test against the real VKB binds from the Weatherwax ED prefix.

Run:  PYTHONPATH=src python3 test_smoke.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from bindsmith.parser import load_all_binds
from bindsmith.devices import load_devices
from bindsmith.presets import seed_from_binds, instantiate, save
from bindsmith.audit import audit
from bindsmith.writer import render

BINDS = "/home/andy/.steam/debian-installation/steamapps/compatdata/359320/pfx/" \
        "drive_c/users/steamuser/AppData/Local/Frontier Developments/" \
        "Elite Dangerous/Options/Bindings"
DATA = Path(__file__).parent / "data"

def main() -> int:
    presets = load_all_binds(BINDS)
    print("presets:", sorted(presets))
    p = presets["VKB"]
    devs = load_devices(DATA / "devices")
    gl = devs["231D0200"]
    st = devs["231D012C"]

    # 1. seed a role-based layout from the real binds + descriptors
    layout = seed_from_binds(p, gl)
    print(f"1. seeded layout: {len(layout.assignments)} role assignments")
    print("   roles:", layout.roles()[:14])
    save(layout, DATA / "presets" / "vkb_gladiator_seed.json")

    # 2. instantiate back onto the same device -> should preserve the layout
    inst = instantiate(layout, gl, p)
    orig_bound = sum(1 for a in p.actions if a.is_bound)
    inst_bound = sum(1 for a in inst.actions if a.is_bound)
    print(f"2. roundtrip: original bound={orig_bound} instantiated bound={inst_bound}")

    # 3. audit the original
    rep = audit(p, devs)
    print(f"3. audit clean={rep.clean}")
    print(rep.render()[:800])

    # 4. write the instantiated preset and confirm it parses back
    out = DATA / "presets" / "vkb_gladiator_seed.binds"
    from bindsmith.writer import write
    write(inst, out)
    reparsed = load_all_binds(out)
    print(f"4. wrote {out}; reparsed preset '{reparsed and list(reparsed)}' "
          f"actions={len(list(reparsed.values())[0].actions) if reparsed else 0}")

    ok = (len(layout.assignments) > 20 and inst_bound >= orig_bound * 0.9)
    print("\nRESULT:", "PASS" if ok else "NEEDS REVIEW")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
