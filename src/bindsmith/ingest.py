"""Ingest device descriptors from a directory of ED ``.buttonMap`` files.

The button-map format is ED's own (``<Root><Joy_8>label</Joy_8>...</Root>``):
the same ``<Key>`` values ``.binds`` files use, plus a friendly label per
control. The community project EliteCustomButtonNames (Richard Buckle, MIT)
curates far better labels than ED ships and covers the whole device roster —
see NOTICE.md for attribution.

Ingest is idempotent and *merging*:

* A descriptor file that already exists is updated in place:
  labels and any newly-seen keys are added; keys and roles that already
  exist are left untouched (a curated role is never clobbered by a label).
* A descriptor that does not exist yet is created with a name taken from the
  buttonMap's ``<!-- name -->`` header, vendor sniffed from the name, and
  ``kind`` inferred from the control mix.
* The ``Generic`` template becomes the generic fallback descriptor that the
  audit uses to classify keys on unknown devices (and to report them instead
  of leaving them as orphans).

Usage (library):  ``ingest_buttonmaps(buttonmaps_dir, data_dir)``
Usage (CLI):      ``bindsmith ingest BUTTONMAPS_DIR [--data DIR]``
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .devices import (
    DEVICE_ID_RE,
    Control,
    Device,
    device_id_from_filename,
    load_devices,
    save_device,
)

GENERIC_ID = "GENERIC"  # sentinel id for the fallback descriptor

VENDOR_HINTS: list[tuple[str, str]] = [
    ("VKB", "VKB Sim"),
    ("T16000", "ThrustMaster"),
    ("Saitek", "Saitek"),
    ("SaitekX5", "Saitek"),
    ("CHPro", "CH Products"),
    ("VPC", "VPC / VKB"),
    ("DualSense", "Sony"),
    ("Logitech", "Logitech"),
]


def _vendor_from_name(name: str) -> str:
    for hint, vendor in VENDOR_HINTS:
        if hint.lower() in name.lower():
            return vendor
    return ""


def _kind_for(dev: Device) -> str:
    """Infer the device kind from its control mix (best effort)."""
    if not dev.controls:
        return "unknown"
    n_axes = len(dev.axes())
    n_buttons = len(dev.buttons())
    n_povs = len(dev.povs())
    # Throttle-like: a Z throttle axis with relatively few free buttons.
    if dev.axes("Z") and n_axes >= 3:
        return "throttle"
    # Rudder-like: U/V pedal axes.
    if dev.axes("U") and dev.axes("V"):
        return "rudder"
    # A hat/pad is a cluster of POVs with little else.
    if n_povs >= 4 and n_buttons == 0 and n_axes == 0:
        return "hat"
    if n_axes >= 3 or (n_axes >= 2 and n_buttons >= 4):
        return "joystick"
    if n_povs >= 4:
        return "hat"
    return "unknown"


def _header_name(text: str) -> str:
    """'<!-- VKB Gladiator NXT EVO ... -->' -> the name inside the comment."""
    m = re.search(r"<!--\s*(.+?)\s*-->", text, re.S)
    if m:
        return m.group(1).strip()
    return ""


def _parse_button_map(path: Path) -> Device | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    dev_id = device_id_from_filename(path.name) or path.stem
    dev = Device(
        id=dev_id,
        name=_header_name(text) or path.stem,
        vendor=_vendor_from_name(_header_name(text) or path.stem),
    )
    for child in root:
        key = child.tag
        label = (child.text or "").strip()
        if not key or not label:
            continue
        dev.controls.append(_control_from_key_public(key, label))
    return dev


# Re-export the label->control mapping from devices.py under a public name.
from .devices import _control_from_key as _control_from_key_public  # noqa: E402


def _merge_controls(existing: Device, fresh: Device) -> Device:
    """Fresh keys/labels in, curated keys/roles preserved."""
    by_key = {c.key: c for c in existing.controls}
    for fc in fresh.controls:
        if fc.key in by_key:
            ec = by_key[fc.key]
            # label: only fill in when missing
            if not ec.label:
                ec.label = fc.label
            # axis letter for axes: fill in when missing
            if ec.type == "axis" and not ec.axis:
                ec.axis = fc.axis
        else:
            existing.controls.append(fc)
    return existing


def ingest_buttonmaps(
    buttonmaps_dir: str | Path,
    data_dir: str | Path,
    *,
    update: bool = True,
) -> dict:
    """Ingest every ``*.buttonMap`` under *buttonmaps_dir* into *data_dir*.

    Returns a summary: ``{"created": [...], "updated": [...], "skipped": [...]}``.
    """
    buttonmaps_dir = Path(buttonmaps_dir)
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    existing = load_devices(data_dir) if update else {}
    summary = {"created": [], "updated": [], "skipped": []}

    for f in sorted(buttonmaps_dir.glob("*.buttonMap")):
        fresh = _parse_button_map(f)
        if fresh is None or not fresh.controls:
            summary["skipped"].append(f.name)
            continue

        is_generic = f.stem.lower() == "generic"
        target_id = GENERIC_ID if is_generic else fresh.id
        # filenames carry no colon (save_device strips it)
        path = data_dir / f"{target_id.replace(':', '')}.json"

        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            merged = Device(
                id=raw["id"],
                name=raw.get("name") or fresh.name,
                vendor=raw.get("vendor") or fresh.vendor,
                kind=raw.get("kind") or _kind_for(fresh),
                controls=[Control(**c) for c in raw.get("controls", [])],
            )
            merged = _merge_controls(merged, fresh)
            if not merged.kind or merged.kind == "unknown":
                merged.kind = _kind_for(merged)
            save_device(merged, data_dir)
            summary["updated"].append(f"{f.name} -> {path.name}")
        else:
            fresh.id = target_id
            if not fresh.name:
                fresh.name = f.stem
            if not fresh.kind:
                fresh.kind = "unknown" if is_generic else _kind_for(fresh)
            save_device(fresh, data_dir)
            summary["created"].append(f"{f.name} -> {path.name}")

    return summary
