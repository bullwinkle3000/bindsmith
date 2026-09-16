# bindsmith

Port, audit, and share Elite Dangerous controller bindings across machines and
hardware. A Python engine (CLI) plus a thin web presentation layer over the
same library.

The engine treats a control layout as a **role-based preset** — a mapping from
ED *actions* (e.g. `PrimaryFire`, `PitchAxisRaw`) to hardware-agnostic *roles*
(`fire_primary`, `pitch`, …). A device descriptor maps a device's *controls*
to those same roles. A preset instantiated onto a device joins the two and
produces a real `.binds` file the game will load. That one join is what lets a
layout survive a hardware swap, a machine move, or a share.

## Commands

```
bindsmith parse BINDS            # read a .binds and report its shape
bindsmith audit BINDS [--device ID,...]   # unknown devices, orphans, conflicts, coverage
bindsmith port BINDS --from A --to B [--via role|index]   # remap a layout device->device
bindsmith gen-devices BUTTONMAPS --out DIR  # build device skeletons from ED DeviceButtonMaps
bindsmith ingest BUTTONMAPS [--data DIR]    # merge curated device labels/inventory (EDCD)
```

Run from the repo root: `PYTHONPATH=src python3 -m bindsmith.cli ...`

## Layout

```
src/bindsmith/
  parser.py    .binds XML <-> Preset/Action/Binding (raw tree preserved for lossless write-back)
  writer.py    Preset -> valid .binds
  devices.py   Device/Control descriptors (VID:PID -> controls with roles)
  roles.py     the role vocabulary + capability-based menus
  presets.py   role-based PresetLayout; seed_from_binds / instantiate / port
  port.py      device->device remap via role matching (with index fallback)
  audit.py     unknown devices, orphan keys, conflicts, per-device coverage
  ingest.py    merge .buttonMap files (EDCD) into device descriptors
  cli.py       argparse front-end
data/devices/  device descriptors (one JSON per device; see NOTICE.md for EDCD attribution)
data/presets/  role-based presets (.json) + instantiated .binds outputs
web/           (planned) presentation layer over this library
```

## Data provenance

See **NOTICE.md**. Button labels and control inventories are largely derived
from the EDCD *EliteCustomButtonNames* project (MIT, © Richard Buckle); the
VKB descriptors are hand-curated on top of that.
