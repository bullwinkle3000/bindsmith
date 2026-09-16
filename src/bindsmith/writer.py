"""Write a Preset back out as an ED .binds file, reproducing ED's own layout.

Fidelity matters: the file is consumed by the game, and a malformed or
re-ordered file is worse than a broken bind. We re-emit the exact element
order and attributes the parser preserved, only changing the (Device, Key)
values (and Inverted/Deadzone) where a port requested it.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .parser import Preset, RawChild


def _emit_raw(rc: RawChild, elem: ET.Element) -> None:
    for ch in rc.children:
        child = ET.SubElement(elem, ch.tag, dict(ch.attrs))
        _emit_raw(ch, child)


def render(preset: Preset, indent: str = "\t") -> bytes:
    root = ET.Element("Root", {
        "PresetName": preset.name,
        "MajorVersion": str(preset.major),
        "MinorVersion": str(preset.minor),
    })
    ET.SubElement(root, "KeyboardLayout").text = preset.keyboard_layout

    for tag, value in preset.settings.items():
        el = ET.SubElement(root, tag)
        if value not in (None, ""):
            el.set("Value", value)
        else:
            el.text = ""

    for action in preset.actions:
        ael = ET.SubElement(root, action.name)
        for rc in action.children:
            child = ET.SubElement(ael, rc.tag, dict(rc.attrs))
            _emit_raw(rc, child)

    # ED's files are tab-indented with a CRLF-flavoured look; we emit 2-space
    # pretty + trailing newline. ED tolerates any valid XML; the indentation
    # is not load-bearing (the parser proved it).
    _indent_xml(root, indent)
    return (
        '<?xml version="1.0" encoding="UTF-8" ?>\n'
        + ET.tostring(root, encoding="unicode")
        + "\n"
    ).encode("utf-8")


def _indent_xml(elem: ET.Element, indent: str) -> None:
    # Minimal pretty-printer (no external dep).
    def _walk(e: ET.Element, level: int) -> None:
        pad = indent * level
        if len(e):
            for i, c in enumerate(e):
                _walk(c, level + 1)
                if i < len(e) - 1:
                    c.tail = "\n" + pad + indent
            e.tail = "\n" + pad
        else:
            e.tail = "\n" + pad
    _walk(elem, 0)


def write(preset: Preset, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render(preset))
    return path
