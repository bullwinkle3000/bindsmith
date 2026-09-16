"""Port a .binds preset from one device onto another.

The core value of the tool. Two mapping strategies, tried in order per key:

  1. role_map  — the source key has a role on the source device (from its
                 descriptor); find the target control with the same role and
                 use its key. This is the correct path when the devices have
                 different layouts (same kind of hardware, different grip).
  2. index_map — fall back to the same ED key (Joy_8 -> Joy_8). Correct when
                 the target has the same control inventory in the same order
                 (identical hardware, different machine).

A key that matches neither is reported as `unmapped` and left as-is (the
game will simply not bind it), so a port never silently corrupts a layout.
Keyboard, Mouse and {NoDevice} references are always left untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .devices import Device
from .parser import Preset, RawChild


@dataclass
class PortResult:
    preset: Preset
    remapped: list[dict] = field(default_factory=list)    # {action, old, new, strategy}
    unmapped: list[dict] = field(default_factory=list)    # {action, key, device}
    unchanged: int = 0


def _role_index(dev: Device) -> dict[str, str]:
    """role -> ED key (first control that has the role wins)."""
    out: dict[str, str] = {}
    for c in dev.controls:
        if c.role and c.role not in out:
            out[c.role] = c.key
    return out


def _key_role(dev: Device) -> dict[str, str]:
    """ED key -> role."""
    return {c.key: c.role for c in dev.controls if c.role}


def port(
    preset: Preset,
    src: Device,
    dst: Device,
    *,
    strategies: tuple[str, ...] = ("role", "index"),
) -> PortResult:
    """Return a new Preset with every binding on `src` re-targeted to `dst`."""
    result = PortResult(preset=_clone(preset))
    role_map = _role_index(dst)
    key_role_src = _key_role(src)

    def remap(action_name: str, rc: RawChild) -> bool:
        if rc.device != src.id and rc.device.replace(":", "") != src.id.replace(":", ""):
            return False
        if not rc.key:
            return True
        # role strategy
        if "role" in strategies:
            role = key_role_src.get(rc.key)
            if role and role in role_map:
                new_key = role_map[role]
                if new_key != rc.key:
                    result.remapped.append({
                        "action": action_name,
                        "from": rc.key, "to": new_key, "strategy": "role",
                        "role": role,
                    })
                rc.attrs["Key"] = new_key
                rc.attrs["Device"] = dst.id
                return True
        # index strategy
        if "index" in strategies and rc.key in {c.key for c in dst.controls}:
            if rc.key != rc.attrs["Key"] or rc.attrs["Device"] != dst.id:
                result.remapped.append({
                    "action": action_name,
                    "from": rc.key, "to": rc.key, "strategy": "index",
                })
            rc.attrs["Device"] = dst.id
            return True
        result.unmapped.append({
            "action": action_name, "key": rc.key, "device": src.id,
        })
        return False

    def walk(action_name: str, rc: RawChild) -> None:
        if rc.tag in ("Primary", "Secondary", "Binding", "Modifier", "Hold") \
                and "Device" in rc.attrs:
            remap(action_name, rc)
        for ch in rc.children:
            walk(action_name, ch)

    for action in result.preset.actions:
        for rc in action.children:
            walk(action.name, rc)
        # refresh derived convenience fields after mutation
        from .parser import _derive_action
        result.preset.actions[result.preset.actions.index(action)] = \
            _derive_action(action.name, action.children)

    result.unchanged = sum(
        1 for a in result.preset.actions if a.is_bound
    ) - len(result.remapped) - len(result.unmapped)
    return result


def _clone(preset: Preset) -> Preset:
    import copy
    return copy.deepcopy(preset)
