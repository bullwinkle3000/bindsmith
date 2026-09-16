"""bindsmith CLI.

  bindsmith parse  BINDS_DIR_OR_FILE
  bindsmith audit  BINDS  --device ID...
  bindsmith port   BINDS  --src ID --dst ID --out OUT.binds
  bindsmith gen-devices  BUTTONMAPS_DIR  --out devices.json   (seed catalog)

The library is importable; this is a thin command layer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .parser import parse_binds, load_all_binds, Preset
from .writer import write
from .devices import load_devices, generate_from_button_map
from .port import port
from .audit import audit

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load_preset(path: str) -> Preset:
    p = Path(path)
    if p.is_dir():
        presets = load_all_binds(p)
        if len(presets) == 1:
            return next(iter(presets.values()))
        names = ", ".join(sorted(presets))
        sys.exit(f"multiple presets in {p}: {names} — pass a .binds file")
    return parse_binds(p)


def cmd_parse(args: argparse.Namespace) -> None:
    p = _load_preset(args.target)
    bound = sum(1 for a in p.actions if a.is_bound)
    print(json.dumps({
        "name": p.name, "version": p.version, "layout": p.keyboard_layout,
        "actions": len(p.actions), "bound": bound,
        "settings": p.settings,
    }, indent=2))


def cmd_audit(args: argparse.Namespace) -> None:
    preset = _load_preset(args.binds)
    devices = load_devices(DATA_DIR / "devices")
    if args.device:
        devices = {d: devices[d] for d in args.device if d in devices}
    report = audit(preset, devices)
    print(report.render())


def cmd_port(args: argparse.Namespace) -> None:
    preset = _load_preset(args.binds)
    devices = load_devices(DATA_DIR / "devices")
    src = devices.get(args.src)
    dst = devices.get(args.dst)
    if not src or not dst:
        missing = [d for d in (args.src, args.dst) if d not in devices]
        sys.exit(f"device(s) not in catalog: {missing}; have: {sorted(devices)}")
    result = port(preset, src, dst,
                  strategies=tuple(s for s in args.strategy.split(",")))
    out = Path(args.out)
    write(result.preset, out)
    print(f"ported {src.id} -> {dst.id}: "
          f"{len(result.remapped)} remapped, {len(result.unmapped)} unmapped")
    if result.remapped:
        for r in result.remapped[:40]:
            print(f"  [{r['strategy']:<5}] {r['action']:<28} "
                  f"{r['from']:>10} -> {r['to']:<10} ({r.get('role','')})")
        if len(result.remapped) > 40:
            print(f"  ... and {len(result.remapped)-40} more")
    if result.unmapped:
        for u in result.unmapped[:20]:
            print(f"  [UNMAPPED] {u['action']:<28} {u['device']} {u['key']}")
    print(f"wrote {out}")


def cmd_gen_devices(args: argparse.Namespace) -> None:
    src = Path(args.buttonmaps)
    out = []
    for f in sorted(src.glob("*.buttonMap")):
        dev = generate_from_button_map(f)
        if dev is None:
            continue
        out.append({
            "id": dev.id, "name": dev.name, "vendor": "",
            "kind": "unknown",
            "controls": [
                {"key": c.key, "label": c.label, "type": c.type,
                 "axis": c.axis, "role": c.role, "group": c.group,
                 "deadzone": c.deadzone, "inverted": c.inverted}
                for c in dev.controls
            ],
        })
    payload = json.dumps(out, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"wrote {len(out)} device skeletons to {args.out}")
    else:
        print(payload)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bindsmith", description=__doc__)
    ap.add_argument("--version", action="version", version=f"bindsmith {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="parse and summarise a .binds file or directory")
    p.add_argument("target")
    p.set_defaults(fn=cmd_parse)

    a = sub.add_parser("audit", help="audit a preset against the device catalog")
    a.add_argument("binds")
    a.add_argument("--device", action="append",
                   help="restrict to these device IDs (repeatable)")
    a.set_defaults(fn=cmd_audit)

    t = sub.add_parser("port", help="port a preset from one device onto another")
    t.add_argument("binds")
    t.add_argument("--src", required=True)
    t.add_argument("--dst", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--strategy", default="role,index",
                   help="comma list of: role, index (default both)")
    t.set_defaults(fn=cmd_port)

    g = sub.add_parser("gen-devices",
                       help="build device skeletons from ED DeviceButtonMaps")
    g.add_argument("buttonmaps")
    g.add_argument("--out")
    g.set_defaults(fn=cmd_gen_devices)

    args = ap.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
