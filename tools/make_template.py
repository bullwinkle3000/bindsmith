#!/usr/bin/env python3
"""Build data/actions/<version>.template.binds — the blank action set.

A .binds is matched to the game by action name, so a usable blank profile
needs the complete action vocabulary for the game version, in order, with
every binding cleared. We derive it from a real config rather than shipping a
hand-typed list, so it stays exactly as complete as the game expects.

    python3 tools/make_template.py [source.binds ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bindsmith.parser import parse_binds
from bindsmith.presets import blank_from
from bindsmith.writer import write

DEFAULT_SOURCES = [
    ROOT / "data/presets/vkb_gladiator_seed.binds",
    Path.home() / ".steam/debian-installation/steamapps/compatdata/359320/pfx/"
                 "drive_c/users/steamuser/AppData/Local/Frontier Developments/"
                 "Elite Dangerous/Options/Bindings/Custom.4.2.binds",
]


def main(argv: list[str]) -> int:
    sources = [Path(a) for a in argv] or DEFAULT_SOURCES
    src = next((s for s in sources if s.exists()), None)
    if src is None:
        print("no usable source .binds found; pass one explicitly")
        return 1

    template = parse_binds(src)
    blank = blank_from(template, name="Blank")
    out = ROOT / "data" / "actions" / f"{template.version}.template.binds"
    out.parent.mkdir(parents=True, exist_ok=True)
    write(blank, out)

    # verify round-trip: same action set, nothing bound
    back = parse_binds(out)
    bound = sum(1 for a in back.actions if a.is_bound)
    print(f"source        : {src.name}")
    print(f"wrote         : {out.relative_to(ROOT)}")
    print(f"actions       : {len(template.actions)} -> {len(back.actions)}")
    print(f"bound actions : {bound} (expected 0)")
    names_a = [a.name for a in template.actions]
    names_b = [a.name for a in back.actions]
    print(f"action order preserved: {names_a == names_b}")
    print(f"settings carried over : {len(back.settings)}")
    return 0 if (bound == 0 and names_a == names_b) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
