#!/usr/bin/env python3
"""Ingest .buttonMap files into device descriptors.

Two data sources, deliberately separated:

  * INVENTORY  — every control a device has, with its human label. Comes from
    the .buttonMap files in data/buttonmaps/ (ED's own auto-generated maps,
    plus the community-curated MIT set from EDCD/EliteCustomButtonNames).
    Nobody should have to type these by hand, and we should not guess them.

  * MEANING    — which role a control plays (pitch, throttle, gear...). This is
    human judgement and lives in data/roles/<ID>.json, hand-authored and small.

This tool joins them: full inventory from the map, roles overlaid from the
curated file. Hand-written role files stay tiny and reviewable; descriptors
stay complete, so the audit can honestly report coverage instead of drowning
in false "orphan" warnings.

Usage:
    python3 tools/ingest_buttonmaps.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUTTONMAPS = ROOT / "data" / "buttonmaps"
ROLES = ROOT / "data" / "roles"
DEVICES = ROOT / "data" / "devices"

AXIS_KEYS = {"X", "Y", "Z", "RX", "RY", "RZ", "U", "V", "SL0", "SL1"}
POV_RE = re.compile(r"^Joy_POV(\d+)(Up|Down|Left|Right)$")
AXIS_RE = re.compile(r"^Joy_([A-Z]{1,3}\d?|SL\d)Axis$")
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)


def parse_buttonmap(path: Path) -> tuple[str, list[tuple[str, str]]]:
    """Return (device name, [(control key, label)])."""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = COMMENT_RE.search(text)
    name = m.group(1).strip() if m else path.stem
    entries: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("<") or line.startswith("<?") or line.startswith("<Root"):
            continue
        em = re.match(r"^<(\w+)>(.*?)</\1>$", line)
        if em:
            entries.append((em.group(1), em.group(2).strip()))
    return name, entries


def classify(key: str) -> dict:
    """Infer control type/axis/group from ED's key naming."""
    am = AXIS_RE.match(key)
    if am and am.group(1) in AXIS_KEYS:
        return {"type": "axis", "axis": am.group(1)}
    pm = POV_RE.match(key)
    if pm:
        return {"type": "pov", "group": int(pm.group(1))}
    return {"type": "button"}


def load_role_file(dev_id: str) -> dict:
    """Hand-authored role overrides, keyed by control key."""
    for cand in (ROLES / f"{dev_id}.json", ROLES / f"{dev_id.lower()}.json"):
        if cand.exists():
            return json.loads(cand.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    ROLES.mkdir(parents=True, exist_ok=True)
    DEVICES.mkdir(parents=True, exist_ok=True)
    known = []
    built = 0
    for bm in sorted(BUTTONMAPS.glob("*.buttonMap")):
        dev_id = bm.stem
        name, entries = parse_buttonmap(bm)
        roles = load_role_file(dev_id)
        controls = []
        for key, label in entries:
            meta = classify(key)
            role = (roles.get("roles", {}) or {}).get(key, "")
            ctl = {"key": key, "label": label, **meta}
            if role:
                ctl["role"] = role
            controls.append(ctl)
        known.append({
            "id": dev_id, "name": name, "file": bm.name,
            "controls": len(controls),
            "has_roles": bool(roles.get("roles")),
        })
        # Only emit a descriptor for devices we have curated roles for;
        # everyone else stays in the known-devices index (name + inventory).
        if roles.get("roles"):
            payload = {
                "id": dev_id,
                "name": roles.get("name", name),
                "vendor": roles.get("vendor", ""),
                "kind": roles.get("kind", "unknown"),
                "source": "buttonmap+roles",
                "controls": controls,
            }
            (DEVICES / f"{dev_id}.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            built += 1

    (DEVICES / "_known.json").write_text(
        json.dumps({"devices": known}, indent=2) + "\n", encoding="utf-8")
    print(f"button maps read : {len(known)}")
    print(f"descriptors built: {built}")
    print(f"known-device index: {DEVICES / '_known.json'}")
    for k in known[:6]:
        print(f"  {k['id']:>12}  {k['controls']:>3} controls  {k['name'][:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
