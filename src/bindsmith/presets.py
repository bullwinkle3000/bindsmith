"""Presets: a control LAYOUT expressed in roles, independent of hardware.

A preset is the semantic heart of the tool. It says *what each ED action
means* ("PitchAxisRaw is the pitch role", "ForwardThrustButton is thrust_fwd")
without saying *which physical control* carries it. That last step is resolved
at instantiation time against a device descriptor.

The result:
  * one preset serves every device that has the required roles;
  * a layout can be compared across machines ("is my new setup the same as
    the one I like?") by diffing role assignments;
  * sharing is trivial — a preset file is portable data.

A preset can be *seeded* from an existing .binds + a device descriptor: the
device tells us the role of each bound control, so the preset becomes
"{action: role}" for everything that is bound. That is how the shipped VKB
preset is generated, and it is the path a user follows to export *their*
layout.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

from .devices import Device
from .parser import Preset, Action, Binding, _derive_action


@dataclass
class Assignment:
    action: str
    role: str                 # "" = intentionally unbound
    inverted: bool = False
    deadzone: float = 0.0
    note: str = ""            # author's rationale, shown in the UI


@dataclass
class PresetLayout:
    id: str
    name: str
    description: str = ""
    ed_version: str = "4.2"
    assignments: list[Assignment] = field(default_factory=list)
    # Actions the preset intentionally leaves to the keyboard (so an
    # instantiation does not report them as missing).
    keyboard_defaults: list[str] = field(default_factory=list)

    def role_for(self, action: str) -> Assignment | None:
        for a in self.assignments:
            if a.action == action:
                return a
        return None

    def roles(self) -> list[str]:
        return sorted({a.role for a in self.assignments if a.role})


def seed_from_binds(preset: Preset, device: Device) -> PresetLayout:
    """Extract a role-based layout from a real .binds + its device descriptor.

    For every bound control, look up its role on the device. The output is the
    semantic layout, ready to be instantiated onto other hardware.
    """
    key_role = {c.key: c.role for c in device.controls if c.role}
    out: list[Assignment] = []
    for action in preset.actions:
        for b in _iter_bindings(action):
            if b.is_empty:
                continue
            role = key_role.get(b.key, "")
            if not role:
                continue
            out.append(Assignment(
                action=action.name, role=role,
                inverted=b.inverted, deadzone=b.deadzone,
            ))
            break  # one assignment per action (the primary binding)
    # De-duplicate: keep the first (primary) assignment per action.
    seen: set[str] = set()
    deduped: list[Assignment] = []
    for a in out:
        if a.action in seen:
            continue
        seen.add(a.action)
        deduped.append(a)
    return PresetLayout(
        id=device.id.replace(":", "").lower(),
        name=f"{device.name} layout",
        assignments=deduped,
    )


def instantiate(layout: PresetLayout, device: Device,
                skeleton: Preset) -> Preset:
    """Turn a role-based layout into a concrete .binds for `device`.

    `skeleton` supplies the full ordered action set (every action ED expects);
    we only fill in the bindings the layout specifies. Unspecified actions are
    left empty. The returned Preset is directly writable.
    """
    role_key = {c.role: c for c in device.controls if c.role}
    result = copy.deepcopy(skeleton)
    for action in result.actions:
        asg = layout.role_for(action.name)
        if asg is None:
            continue
        ctl = role_key.get(asg.role)
        if ctl is None:
            continue  # device lacks the role; leave unbound (audit will flag)
        _set_binding(action, device.id, ctl.key, asg.inverted, asg.deadzone)
    # re-derive convenience fields
    for i, action in enumerate(result.actions):
        result.actions[i] = _derive_action(action.name, action.children)
    return result


def _set_binding(action: Action, device_id: str, key: str,
                 inverted: bool, deadzone: float) -> None:
    """Rewrite the action's primary (or first) binding to (device, key)."""
    from .parser import RawChild
    # Prefer an existing Primary/Secondary/Binding child so we preserve
    # element ordering; if the action is empty, add a Primary.
    target = None
    for rc in action.children:
        if rc.tag in ("Primary", "Secondary", "Binding"):
            target = rc
            break
    if target is None:
        target = RawChild(tag="Primary")
        action.children.insert(0, target)
    target.attrs = {"Device": device_id, "Key": key}
    # carry per-control tuning as value siblings (Inverted/Deadzone)
    _set_value_child(action, "Inverted", "1" if inverted else "0")
    _set_value_child(action, "Deadzone", f"{deadzone:.8f}")


def _set_value_child(action: Action, tag: str, value: str) -> None:
    from .parser import RawChild
    for rc in action.children:
        if rc.tag == tag:
            rc.attrs = {"Value": value}
            return
    action.children.append(RawChild(tag=tag, attrs={"Value": value}))


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------

def save(layout: PresetLayout, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": layout.id, "name": layout.name,
        "description": layout.description, "ed_version": layout.ed_version,
        "keyboard_defaults": layout.keyboard_defaults,
        "assignments": [
            {"action": a.action, "role": a.role, "inverted": a.inverted,
             "deadzone": a.deadzone, "note": a.note}
            for a in layout.assignments
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load(path: str | Path) -> PresetLayout:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return PresetLayout(
        id=raw["id"], name=raw.get("name", ""),
        description=raw.get("description", ""),
        ed_version=raw.get("ed_version", "4.2"),
        keyboard_defaults=raw.get("keyboard_defaults", []),
        assignments=[Assignment(**a) for a in raw.get("assignments", [])],
    )


def load_all(data_dir: str | Path) -> dict[str, PresetLayout]:
    out: dict[str, PresetLayout] = {}
    for f in sorted(Path(data_dir).glob("*.json")):
        try:
            pl = load(f)
        except (KeyError, json.JSONDecodeError):
            continue
        out[pl.id] = pl
    return out


def _iter_bindings(action: Action):
    if action.primary:
        yield action.primary
    if action.secondary:
        yield action.secondary
    for e in action.extra:
        yield e
    for h in action.holds:
        yield h
