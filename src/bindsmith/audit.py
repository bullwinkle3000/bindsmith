"""Audit a .binds preset against a set of device descriptors.

Reports, per device:
  * unknown devices   — bound but no descriptor in the catalog
  * orphan keys       — a key the device descriptor does not define
  * coverage          — which of the device's controls are bound, which are not
  * conflicts         — the same (device, key) driving two actions in a mode
                        (mode-aware when the mode map is available, global
                        otherwise)

This is the "is this preset sound?" answer that ED's UI never gives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict

from .devices import Device
from .parser import Preset


@dataclass
class AuditReport:
    unknown_devices: list[str] = field(default_factory=list)
    orphans: list[dict] = field(default_factory=list)       # {action, device, key}
    coverage: dict[str, dict] = field(default_factory=dict)  # dev -> {bound: [key], free: [key]}
    conflicts: list[dict] = field(default_factory=list)      # {key, device, actions: [...]}
    ok: bool = False

    @property
    def clean(self) -> bool:
        return not (self.unknown_devices or self.orphans or self.conflicts)

    def render(self) -> str:
        lines = []
        if self.clean:
            return "audit: clean — no unknown devices, orphans, or conflicts"
        if self.unknown_devices:
            lines.append("unknown devices (no descriptor in catalog):")
            for d in sorted(set(self.unknown_devices)):
                lines.append(f"  {d}")
        if self.orphans:
            lines.append("orphan keys (device does not define them):")
            for o in self.orphans:
                lines.append(f"  {o['action']:<28} {o['device']} {o['key']}")
        for dev, cov in sorted(self.coverage.items()):
            if not cov["bound"] and not cov["free"]:
                continue
            lines.append(f"coverage {dev}:")
            lines.append(f"  bound: {', '.join(cov['bound']) or '(none)'}")
            lines.append(f"  free : {', '.join(cov['free']) or '(none)'}")
        if self.conflicts:
            lines.append("conflicts (one control, many actions):")
            for c in self.conflicts:
                lines.append(f"  {c['device']} {c['key']} -> {', '.join(c['actions'])}")
        return "\n".join(lines)


def audit(preset: Preset, devices: dict[str, Device]) -> AuditReport:
    rep = AuditReport()
    norm = {d.replace(":", ""): d for d in devices}

    bound_by_key: dict[tuple[str, str], list[str]] = defaultdict(list)

    for action in preset.actions:
        for b in _all_bindings(action):
            if b.is_empty:
                continue
            raw_id = b.device.replace(":", "")
            canon = norm.get(raw_id)
            dev = devices.get(canon) if canon else None
            if dev is None:
                if b.device not in ("Keyboard", "Mouse"):
                    rep.unknown_devices.append(b.device)
                continue
            keys = {c.key for c in dev.controls}
            if b.key not in keys:
                rep.orphans.append({
                    "action": action.name, "device": dev.id, "key": b.key,
                })
            else:
                bound_by_key[(dev.id, b.key)].append(action.name)

    # coverage
    for dev_id, dev in devices.items():
        if not any(k[0] == dev_id for k in bound_by_key):
            continue
        bound = sorted({k for (d, k) in bound_by_key if d == dev_id})
        free = sorted({c.key for c in dev.controls if c.key not in bound})
        rep.coverage[dev_id] = {"bound": bound, "free": free}

    # conflicts (global; mode-awareness lands with the mode map)
    for (dev_id, key), actions in bound_by_key.items():
        unique = sorted(set(actions))
        if len(unique) > 1:
            rep.conflicts.append({
                "device": dev_id, "key": key, "actions": unique,
            })

    rep.ok = rep.clean
    return rep


def _all_bindings(action):
    """Yield every Binding in an action (primary, secondary, extra, holds, modifiers)."""
    from .parser import Binding
    if action.primary:
        yield action.primary
        if action.primary.modifier:
            yield action.primary.modifier
    if action.secondary:
        yield action.secondary
        if action.secondary.modifier:
            yield action.secondary.modifier
    for e in action.extra:
        yield e
        if e.modifier:
            yield e.modifier
    for h in action.holds:
        yield h
