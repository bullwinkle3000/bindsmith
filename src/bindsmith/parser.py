"""Parser for Elite Dangerous .binds files.

ED writes its bindings as well-formed XML (tab-indented, CRLF). The
indentation is cosmetic; the *tree* is authoritative:
  Root
    <Setting>value</Setting>              # leaf settings (MouseXMode, ...)
    <ActionName>                          # one action, e.g. PitchAxisRaw
      <Primary Device=.. Key=../>          # or <Secondary>, <Binding>, <Hold>
      <Inverted Value="1"/>                # value leaves, siblings of the bindings
      <Deadzone Value="0.15"/>
      <Secondary ...><Modifier .../></Secondary>
    </ActionName>

The parser preserves the *raw* per-action structure (ordered child elements,
each with attributes and optional nested children) so a writer can reproduce
ED's exact layout while swapping in different binding values. Convenience
fields (primary/secondary/extra) are derived from that raw structure.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# Elements that carry a (device, key) control reference.
BINDING_TAGS = {"Primary", "Secondary", "Binding", "Modifier", "Hold"}
# Elements that carry a scalar Value attribute.
VALUE_TAGS = {"Inverted", "Deadzone", "ToggleOn", "Value", "Sensitivity"}


@dataclass
class RawChild:
    """One child element of an action, structure preserved."""
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["RawChild"] = field(default_factory=list)
    text: str = ""

    @property
    def device(self) -> str:
        return self.attrs.get("Device", "")

    @property
    def key(self) -> str:
        return self.attrs.get("Key", "")

    @property
    def value(self) -> str:
        return self.attrs.get("Value", self.text or "")

    def binding(self) -> "Binding":
        return Binding(device=self.device, key=self.key)


@dataclass
class Binding:
    """A concrete (device, control) reference with per-control tuning."""
    device: str
    key: str
    inverted: bool = False
    deadzone: float = 0.0
    modifier: "Binding | None" = None

    @property
    def is_empty(self) -> bool:
        return self.device in ("{NoDevice}", "") or not self.key

    @property
    def device_id(self) -> str:
        d = self.device
        if len(d) == 8 and re.fullmatch(r"[0-9A-Fa-f]{8}", d):
            return f"{d[:4]}:{d[4:]}"
        return ""


@dataclass
class Action:
    name: str
    children: list[RawChild] = field(default_factory=list)   # raw structure
    # derived, for convenience:
    primary: Binding | None = None
    secondary: Binding | None = None
    extra: list[Binding] = field(default_factory=list)
    holds: list[Binding] = field(default_factory=list)
    toggles_on: bool | None = None
    inverted: bool = False
    deadzone: float = 0.0

    @property
    def is_bound(self) -> bool:
        return (
            (self.primary and not self.primary.is_empty)
            or (self.secondary and not self.secondary.is_empty)
            or any(not e.is_empty for e in self.extra)
            or any(not h.is_empty for h in self.holds)
        )


@dataclass
class Preset:
    name: str
    major: int
    minor: int
    keyboard_layout: str = "en-US"
    settings: dict[str, str] = field(default_factory=dict)  # root-level leaf settings
    actions: list[Action] = field(default_factory=list)

    def action(self, name: str) -> Action | None:
        for a in self.actions:
            if a.name == name:
                return a
        return None

    @property
    def version(self) -> str:
        return f"{self.major}.{self.minor}"


def _build_raw(tag: ET.Element) -> RawChild:
    rc = RawChild(tag=tag.tag, attrs=dict(tag.attrib),
                  text=(tag.text or "").strip())
    for child in tag:
        rc.children.append(_build_raw(child))
    return rc


def _derive_action(name: str, children: list[RawChild]) -> Action:
    a = Action(name=name, children=children)
    for rc in children:
        if rc.tag == "Primary":
            a.primary = _binding_with_children(rc)
        elif rc.tag == "Secondary":
            a.secondary = _binding_with_children(rc)
        elif rc.tag == "Binding":
            a.extra.append(_binding_with_children(rc))
        elif rc.tag == "Hold":
            for h in rc.children:
                if h.tag in ("Primary", "Secondary", "Binding"):
                    a.holds.append(_binding_with_children(h))
        elif rc.tag == "Inverted":
            a.inverted = rc.value == "1"
        elif rc.tag == "Deadzone":
            try:
                a.deadzone = float(rc.value)
            except ValueError:
                pass
        elif rc.tag == "ToggleOn":
            a.toggles_on = rc.value == "1"
    return a


def _binding_with_children(rc: RawChild) -> Binding:
    b = Binding(device=rc.device, key=rc.key)
    for ch in rc.children:
        if ch.tag == "Inverted":
            b.inverted = ch.value == "1"
        elif ch.tag == "Deadzone":
            try:
                b.deadzone = float(ch.value)
            except ValueError:
                pass
        elif ch.tag == "Modifier":
            b.modifier = Binding(device=ch.device, key=ch.key)
    return b


def parse_binds(path: str | Path) -> Preset:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    # Normalise line endings; ED's XML is well-formed once CRLF is sane.
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    root = ET.fromstring(body)

    preset = Preset(
        name=root.get("PresetName", ""),
        major=int(root.get("MajorVersion", "0") or 0),
        minor=int(root.get("MinorVersion", "0") or 0),
    )

    for child in root:
        if child.tag == "KeyboardLayout":
            preset.keyboard_layout = child.text or "en-US"
            continue
        # A root-level leaf (no children) is a setting.
        if len(child) == 0:
            preset.settings[child.tag] = child.get("Value", child.text or "")
            continue
        # Otherwise it is an action element.
        raw = [_build_raw(c) for c in child]
        action = _derive_action(child.tag, raw)
        preset.actions.append(action)

    return preset


def load_all_binds(bindings_dir: str | Path) -> dict[str, Preset]:
    out: dict[str, Preset] = {}
    for f in sorted(Path(bindings_dir).glob("*.binds")):
        try:
            p = parse_binds(f)
        except ET.ParseError:
            continue
        out[p.name or f.stem] = p
    return out


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else \
        "/home/andy/.steam/debian-installation/steamapps/compatdata/359320/pfx/" \
        "drive_c/users/steamuser/AppData/Local/Frontier Developments/" \
        "Elite Dangerous/Options/Bindings"
    if Path(target).is_dir():
        presets = load_all_binds(target)
        print(f"{len(presets)} presets parsed:")
        for name, p in presets.items():
            bound = sum(1 for a in p.actions if a.is_bound)
            print(f"  {name:<24} v{p.version}  actions={len(p.actions):4d}  bound={bound}")
    else:
        p = parse_binds(target)
        print(json.dumps({
            "name": p.name, "version": p.version, "layout": p.keyboard_layout,
            "actions": len(p.actions),
            "settings": p.settings,
            "sample": [a.name for a in p.actions[:8]],
        }, indent=2))
