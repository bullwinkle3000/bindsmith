"""Device descriptors: what a controller's controls ARE, independent of any preset.

A descriptor is a JSON file under data/devices/ keyed by VID:PID (or a
name for ED's named devices such as "SaitekX52Pro"). It carries the control
inventory with *roles* — the semantic meaning of each axis/button — which is
what lets a preset written in roles be instantiated onto different hardware.

Two sources of truth:
  * ED ships per-device control labels in
    Options/DeviceButtonMaps/<DEVICEID>.buttonMap  (a <Key>label</Key> list).
    That is the authoritative control inventory + friendly names for a device,
    and `generate` builds a descriptor skeleton from it.
  * A human then assigns roles to the controls (or the CLI walks them in
    order). ED's own button map only tells us the *names*; the *roles* are
    the value this project adds.

Descriptor schema (v1):
{
  "id": "231D:012C",
  "name": "VKB STECS Modern Throttle Mini Plus",
  "vendor": "VKB Sim",
  "kind": "throttle",                 # joystick | throttle | rudder | hat | pedal | trackpad | unknown
  "controls": [
    {
      "key": "Joy_8",                 # ED's key value
      "label": "PUSH CCW",            # from ED's button map, or chosen
      "type": "button",               # axis | button | pov
      "axis": "Z",                    # for type=axis: X|Y|Z|RX|RY|RZ|U|V
      "role": "thrust_up",            # a role from roles.py, or "" if unassigned
      "group": 0                      # 0 = nongrouped; hats/pads get 1..n
    },
    ...
  ]
}

A "role" is a logical control meaning:
  axes : yaw, pitch, roll, thrust_fwd, thrust_aft, thrust_left, thrust_right,
         rudder, throttle, tune, invertible variants implied by direction
  buttons: gear, lights, night_vision, cargo, menu_up/down/left/right,
           wingman_1..n, power_*, toggle_*, ...
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path


DEVICE_ID_RE = re.compile(r"^[0-9A-Fa-f]{8}$")


@dataclass
class Control:
    key: str
    label: str = ""
    type: str = "button"          # axis | button | pov
    axis: str = ""                # X|Y|Z|RX|RY|RZ|U|V for axes
    role: str = ""                # logical role
    group: int = 0                # hat/pad group id, 0 = none
    # Per-control tuning that travels WITH the control (it is hardware
    # character, not author preference) — carried into instantiated presets.
    deadzone: float = 0.0
    inverted: bool = False

    @property
    def is_axis(self) -> bool:
        return self.type == "axis"

    @property
    def is_pov(self) -> bool:
        return self.type == "pov"


@dataclass
class Device:
    id: str                       # "231D:012C" or "SaitekX52Pro"
    name: str = ""
    vendor: str = ""
    kind: str = "unknown"
    controls: list[Control] = field(default_factory=list)

    # -- lookup -----------------------------------------------------------
    def by_key(self, key: str) -> Control | None:
        for c in self.controls:
            if c.key == key:
                return c
        return None

    def axes(self, axis: str | None = None) -> list[Control]:
        return [c for c in self.controls
                if c.type == "axis" and (axis is None or c.axis == axis)]

    def buttons(self) -> list[Control]:
        return [c for c in self.controls if c.type == "button"]

    def povs(self) -> list[Control]:
        return [c for c in self.controls if c.type == "pov"]

    def groups(self) -> list[int]:
        return sorted({c.group for c in self.controls if c.group})


def _control_from_key(key: str, label: str) -> Control:
    m = re.fullmatch(r"Joy_([XYZRXU V])Axis|Joy_([XYZRXU V])Axis", key)
    if key.startswith("Joy_") and key.endswith("Axis"):
        return Control(key=key, label=label, type="axis", axis=key[4:-4])
    if key.startswith("Joy_") and key.endswith("POV"):
        # Joy_POV1Up / Joy_POV1Right / ...
        m2 = re.fullmatch(r"Joy_POV(\d+)(Up|Right|Down|Left|UpRight|UpLeft|DownRight|DownLeft)", key)
        if m2:
            return Control(key=key, label=label, type="pov", group=int(m2.group(1)))
        return Control(key=key, label=label, type="pov")
    return Control(key=key, label=label, type="button")


def device_id_from_filename(filename: str) -> str | None:
    """'231D012C.buttonMap' -> '231D:012C'; named devices return None."""
    stem = Path(filename).stem
    if DEVICE_ID_RE.match(stem):
        return f"{stem[:4]}:{stem[4:]}"
    return None


def generate_from_button_map(button_map_path: str | Path) -> Device | None:
    """Build a Device skeleton from an ED DeviceButtonMaps file.

    ED's button map is a flat <Root><Key>label</Key>... list keyed by
    the same <Key> values .binds files use. We get the inventory + names
    for free; roles start empty for a human (or the CLI wizard) to assign.
    """
    import xml.etree.ElementTree as ET
    p = Path(button_map_path)
    dev_id = device_id_from_filename(p.name)
    if dev_id is None:
        dev_id = p.stem  # named device, e.g. T16000MTHROTTLE
    text = p.read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(text)
    dev = Device(id=dev_id, name=p.stem)
    for child in root:
        key = child.tag
        label = (child.text or "").strip()
        if key and label:
            dev.controls.append(_control_from_key(key, label))
    return dev


def load_devices(data_dir: str | Path) -> dict[str, Device]:
    out: dict[str, Device] = {}
    for f in sorted(Path(data_dir).glob("*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "id" not in raw:
            continue  # skip generated.json (a list) and any non-device files
        dev = Device(
            id=raw["id"].replace(":", ""),
            name=raw.get("name", ""),
            vendor=raw.get("vendor", ""),
            kind=raw.get("kind", "unknown"),
            controls=[Control(**c) for c in raw.get("controls", [])],
        )
        out[dev.id] = dev
    return out


def save_device(dev: Device, data_dir: str | Path) -> Path:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{dev.id.replace(':', '')}.json"
    payload = {**asdict(dev), "controls": [asdict(c) for c in dev.controls]}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    import sys
    from .paths import buttonmaps_dir
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else buttonmaps_dir()
    if src is None:
        print("No Elite Dangerous button maps found. Pass a directory of "
              "*.buttonMap files (or set $BINDSMITH_ED_BINDS).")
        raise SystemExit(2)
    n = 0
    for f in sorted(Path(src).glob("*.buttonMap")):
        dev = generate_from_button_map(f)
        if dev is None:
            continue
        n += 1
        a = len(dev.axes())
        b = len(dev.buttons())
        print(f"  {dev.id:<16} {dev.name:<28} axes={a:<3} buttons={b:<3}")
    print(f"{n} devices generated from ED button maps")
