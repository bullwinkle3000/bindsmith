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
from .ingest import ingest_buttonmaps, GENERIC_ID
from .port import port
from .audit import audit
from .wizard import run as wizard_run, suggest_all

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
    # the generic fallback is a classifier, not a real bound device
    devices = {d: v for d, v in devices.items() if d != GENERIC_ID} \
        if not args.device else devices
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


def cmd_ingest(args: argparse.Namespace) -> None:
    data_dir = Path(args.data) if args.data else DATA_DIR / "devices"
    summary = ingest_buttonmaps(Path(args.buttonmaps), data_dir)
    print(f"data dir: {data_dir}")
    for section in ("created", "updated", "skipped"):
        if summary[section]:
            print(f"{section} ({len(summary[section])}):")
            for s in summary[section]:
                print(f"  {s}")
    print(f"done: {len(summary['created'])} created, "
          f"{len(summary['updated'])} updated, {len(summary['skipped'])} skipped")


def cmd_assign(args: argparse.Namespace) -> None:
    data_dir = DATA_DIR / "devices"
    devices = load_devices(data_dir)
    norm = {d.replace(":", ""): d for d in devices}
    key = args.device.replace(":", "")
    if key not in norm:
        sys.exit(f"device not in catalog: {args.device}; have: {sorted(devices)}")
    device = devices[norm[key]]

    if args.suggest:
        rows = suggest_all(device)
        for k, cur, sug in rows:
            mark = "" if cur else ("suggested" if sug else "  (none) ")
            print(f"  {k:<16} {cur or '-':<24} -> {sug or mark}")
        return

    wizard_run(device, interactive=not args.suggest,
               out=str(data_dir) if not args.dry_run else None)


def cmd_serve(args: argparse.Namespace) -> None:
    """Run the web app (FastAPI) — a thin presentation layer over the library."""
    try:
        import uvicorn
    except ImportError:
        sys.exit("uvicorn is required for `bindsmith serve` (pip install uvicorn fastapi)")
    uvicorn.run("bindsmith.server:app", host=args.host, port=args.port,
                reload=args.reload)


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

    g = sub.add_parser("ingest",
                       help="merge device descriptors from a .buttonMap directory "
                            "(e.g. EliteCustomButtonNames)")
    g.add_argument("buttonmaps")
    g.add_argument("--data", help="data/devices dir (default: repo data/devices)")
    g.set_defaults(fn=cmd_ingest)

    w = sub.add_parser("assign",
                       help="walk a device's controls and assign roles "
                            "(interactive wizard; --suggest previews)")
    w.add_argument("device", help="device ID, e.g. 231D0200 or T16000M")
    w.add_argument("--suggest", action="store_true",
                   help="non-interactive: print suggested roles, save nothing")
    w.add_argument("--dry-run", action="store_true",
                   help="run the wizard but write nothing")
    w.set_defaults(fn=cmd_assign)

    s = sub.add_parser("serve", help="run the web app (FastAPI) over the library")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8321)
    s.add_argument("--reload", action="store_true", help="auto-reload (dev only)")
    s.set_defaults(fn=cmd_serve)

    g2 = sub.add_parser("gen-devices",
                       help="build device skeletons from ED DeviceButtonMaps")
    g2.add_argument("buttonmaps")
    g2.add_argument("--out")
    g2.set_defaults(fn=cmd_gen_devices)

    args = ap.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
