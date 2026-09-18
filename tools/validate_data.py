#!/usr/bin/env python3
"""Validate every data file in the repository.

    python3 tools/validate_data.py

This is the check CI runs. It is deliberately about *data*, because almost
everything this project ships is data that other people contribute:

  * every ``.binds`` and ``.buttonMap`` is well-formed XML
  * every ``.binds`` parses into actions
  * every device descriptor is valid JSON with an id and controls
  * every role name used anywhere is in the role vocabulary (catches typos)
  * every profile layout loads
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bindsmith.parser import parse_binds          # noqa: E402
from bindsmith.presets import load                # noqa: E402
from bindsmith.roles import all_roles             # noqa: E402

DATA = ROOT / "data"
VOCAB = set(all_roles())
fails: list[str] = []


def ok(label: str, detail: str = "") -> None:
    print(f"[PASS] {label}" + (f"  — {detail}" if detail else ""))


def bad(label: str, detail: str = "") -> None:
    print(f"[FAIL] {label}" + (f"  — {detail}" if detail else ""))
    fails.append(label)


def main() -> int:
    # ---- XML documents ---------------------------------------------------
    xml_files = sorted(list(DATA.rglob("*.buttonMap")) + list(DATA.rglob("*.binds")))
    for f in xml_files:
        try:
            ET.fromstring(f.read_text(encoding="utf-8", errors="replace"))
        except ET.ParseError as e:
            bad(f"well-formed XML: {f.relative_to(ROOT)}", str(e))
    ok("all XML well-formed", f"{len(xml_files)} files")

    # ---- .binds parse into actions ---------------------------------------
    binds = sorted(DATA.rglob("*.binds"))
    for f in binds:
        try:
            p = parse_binds(f)
            if not p.actions:
                bad(f"parses to actions: {f.relative_to(ROOT)}", "0 actions")
        except Exception as e:                     # noqa: BLE001
            bad(f"parses: {f.relative_to(ROOT)}", f"{type(e).__name__}: {e}")
    if binds:
        ok("binds parse into actions", f"{len(binds)} files")

    # ---- device descriptors ---------------------------------------------
    devices = sorted((DATA / "devices").glob("*.json"))
    unknown_roles: set[str] = set()
    for f in devices:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            bad(f"valid JSON: {f.name}", str(e))
            continue
        if isinstance(raw, list):
            # an index of devices rather than a descriptor
            for entry in raw:
                if not isinstance(entry, dict) or "id" not in entry:
                    bad(f"index entries: {f.name}", str(entry)[:60])
            continue
        if "id" not in raw:
            continue          # a metadata file such as _known.json
        for c in raw.get("controls", []):
            if "key" not in c:
                bad(f"control shape: {f.name}", str(c)[:60])
            role = (c.get("role") or "").strip()
            if role and role not in VOCAB:
                unknown_roles.add(f"{f.name}:{role}")
    ok("device descriptors load", f"{len(devices)} files")
    if unknown_roles:
        bad("roles are in the vocabulary", ", ".join(sorted(unknown_roles)[:8]))
    else:
        ok("device roles are in the vocabulary", f"{len(VOCAB)} known roles")

    # ---- profiles --------------------------------------------------------
    presets = sorted((DATA / "presets").glob("*.json"))
    for f in presets:
        try:
            layout = load(f)
        except Exception as e:                     # noqa: BLE001
            bad(f"profile loads: {f.name}", f"{type(e).__name__}: {e}")
            continue
        stray = {a.role for a in layout.assignments
                 if a.role and a.role not in VOCAB}
        if stray:
            bad(f"profile roles: {f.name}", ", ".join(sorted(stray)[:5]))
    ok("profiles load", f"{len(presets)} files")

    print()
    if fails:
        print(f"FAILED ({len(fails)}): " + "; ".join(fails[:6])
              + (" …" if len(fails) > 6 else ""))
        return 1
    print("DATA OK — every file validates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
