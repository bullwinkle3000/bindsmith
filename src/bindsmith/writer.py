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

    # ED's files are tab-indented; we reproduce that. The indentation is not
    # load-bearing (ED parses any valid XML) but it keeps generated files
    # diffable against the game's own output.
    _indent_xml(root, indent)
    return (
        '<?xml version="1.0" encoding="UTF-8" ?>\n'
        + ET.tostring(root, encoding="unicode").rstrip("\n")
        + "\n"
    ).encode("utf-8")


def _indent_xml(elem: ET.Element, indent: str) -> None:
    # Minimal pretty-printer (no external dep). Two details matter:
    #   * a parent's .text puts its FIRST child on a fresh line, otherwise the
    #     first child is emitted straight after the opening tag;
    #   * the LAST child's tail uses the parent's indent, so the closing tag
    #     lines up with the opening tag instead of over-indenting.
    def _walk(e: ET.Element, level: int) -> None:
        pad = indent * level
        if len(e):
            e.text = "\n" + pad + indent
            for c in e:
                _walk(c, level + 1)
            last = len(e) - 1
            for i, c in enumerate(e):
                c.tail = ("\n" + pad + indent) if i < last else ("\n" + pad)
        e.tail = "\n" + pad
    _walk(elem, 0)


def write(preset: Preset, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render(preset))
    return path
