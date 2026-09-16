"""Interactive role-assignment wizard for a device descriptor.

The descriptor carries the control *inventory* (keys + labels, usually from an
EDC/ED buttonMap) but the *roles* are the value this project adds, and that is
a human decision. This module walks the controls in order and, for each one,
offers the capability-appropriate menu of roles (see ``roles.offered_roles``).

Interaction (one prompt per control):

  0 / <empty> / s   skip — keep the current role
  <number>          assign that role
  .                 clear the role (mark intentionally unbound)
  <return>          apply the suggested role if there is one, else skip
  q                 quit (discard unsaved changes, with confirmation)

A light convention-based suggestion is shown (marked ``->``) as a starting
point; it is never authoritative and can always be overridden.

Run non-interactively with ``--suggest`` to just print the suggested
assignment (useful as a first pass to review before editing by hand).
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from .devices import Device, Control, load_devices, save_device
from .roles import Capability, offered_roles


# Convention-based starting point for a single bidirectional axis. The
# curation's own scheme (VKB Gladiator: X=roll Y=pitch RZ=yaw Z=throttle
# U=tune) is a "yaw-stick" layout; these defaults are a neutral starting
# point the user adjusts, not gospel.
_AXIS_SUGGEST = {
    "X": "yaw", "Y": "pitch", "Z": "throttle",
    "RX": "yaw", "RY": "pitch", "RZ": "roll",
    "U": "tune", "V": "tune",
}


def capability_for(c: Control) -> Capability:
    """Derive a control's capability class (what it can physically do)."""
    if c.type == "axis":
        return Capability(kind="axis", axis=c.axis, direction="both")
    if c.type == "pov":
        return Capability(kind="pov", group=c.group)
    if c.type == "button":
        return Capability(kind="button")
    return Capability(kind=c.type or "button")


def suggest_role(c: Control) -> str:
    """A convention-based role suggestion ("" = no suggestion)."""
    if c.type == "axis":
        return _AXIS_SUGGEST.get(c.axis, "")
    if c.type == "pov":
        return "menu_navigate"
    return ""


def _menu_for(c: Control, current: str):
    """Return [(number, role, is_current, is_suggested), ...]."""
    menu = offered_roles(capability_for(c))
    sug = suggest_role(c)
    out = []
    for i, r in enumerate(menu, start=1):
        out.append((i, r, r == current, r == sug and bool(sug)))
    return out


def render_prompt(idx: int, total: int, c: Control) -> str:
    kind = c.type if c.type else "unknown"
    extra = f" axis={c.axis}" if c.type == "axis" else (
        f" group={c.group}" if c.type == "pov" else "")
    cur = c.role or "<none>"
    sug = suggest_role(c)
    head = f"[{idx}/{total}] {c.key} ({kind}{extra}) {c.label!r}"
    line = f"  current: {cur}" + (f"   suggested: {sug}" if sug else "")
    return head + "\n" + line


def _read_line(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return "q"


def run(device: Device, interactive: bool = True, out: str | None = None) -> Device:
    """Walk the controls, assigning roles. Returns the (possibly changed) Device."""
    total = len(device.controls)
    changed = 0
    if interactive:
        print(f"Role wizard for {device.id} — {device.name or device.id}")
        print(f"{total} controls. s/skip, <n>=assign, .=clear, <return>=suggestion, q=quit\n")
        for i, c in enumerate(device.controls, start=1):
            head = render_prompt(i, total, c)
            print(head)
            menu = _menu_for(c, c.role)
            for num, role, is_cur, is_sug in menu:
                mark = (" *" if is_cur else "") + (" ->" if is_sug else "")
                print(f"  {num:>2}. {role}{mark}")
            ans = _read_line("  role> ").strip()
            if ans in ("q", "Q"):
                confirm = _read_line("  quit and discard changes? (y/n)> ").strip().lower()
                if confirm != "y":
                    continue
                print("  aborted; nothing saved.")
                return device
            if ans in ("", "0", "s", "S"):
                # <return> applies the suggestion if present; else skip
                if ans == "" and suggest_role(c) and not c.role:
                    c.role = suggest_role(c)
                    changed += 1
                continue
            if ans in (".", "u", "U"):
                c.role = ""
                changed += 1
                continue
            if ans.isdigit():
                n = int(ans)
                if 1 <= n <= len(menu):
                    role = menu[n - 1][1]
                    if role != c.role:
                        c.role = role
                        changed += 1
                continue
            print("  (unrecognized input, skipping)")

    # Non-interactive: just apply suggestions to unassigned controls.
    if not interactive:
        for c in device.controls:
            if not c.role:
                s = suggest_role(c)
                if s:
                    c.role = s
                    changed += 1

    if out is not None:
        save_device(device, Path(out))
        print(f"\nsaved -> {out}  ({changed} roles changed)")
    return device


def suggest_all(device: Device) -> list[tuple[str, str, str]]:
    """Return [(key, current_role, suggested_role)] for every control."""
    out = []
    for c in device.controls:
        out.append((c.key, c.role or "", suggest_role(c)))
    return out
