# bindsmith

**Port and share Elite Dangerous controller bindings across hardware.**

Rebinding a HOTAS in Elite Dangerous is a rite of passage nobody enjoys:
hundreds of actions, a hand-edited XML file, and device IDs that differ
between machines even for identical hardware. bindsmith's premise is that the
pain is unnecessary.

If we know a controller's **brand and model**, we know what its controls are.
So a layout built for one stick can be moved to another by re-resolving *what
each control means* rather than copying device IDs around.

## How it works

A binding has two halves, and bindsmith keeps them apart:

| | What it is | Where it lives | Who writes it |
|---|---|---|---|
| **Inventory** | Every control a device has, and its label | `data/buttonmaps/*.buttonMap` | Generated from ED's + community maps |
| **Meaning** | Which role each control plays (`pitch`, `gear`, `throttle`) | `data/roles/<ID>.json` | Human judgement, ~20 lines per device |

Join them and you get a **descriptor** (`data/devices/*.json`): a complete,
self-describing picture of a controller. A **preset** is then a layout written
in roles rather than control names — which is what makes it portable:

```
preset  (PitchAxisRaw -> role "pitch")     # hardware-independent
   + descriptor (role "pitch" -> Joy_YAxis on this stick)
   = concrete .binds for this machine
```

## Status

Early. The engine works end to end against a real 700-hour VKB setup:

- parses a `.binds` file faithfully (422 actions, raw structure preserved)
- re-emits a valid `.binds` that the game's own reader accepts
- seeds a role-based layout from an existing config (24 roles from the
  reference VKB setup)
- instantiates that layout back onto a device — verified round-trip, 289 of
  289 bound actions preserved
- audits a config for unknown devices, unlabelled controls, and coverage
- ports bindings between devices by role, falling back to index

Not built yet: the web UI, mode-aware conflict checks (flight / SRV / on-foot),
and a packaged release.

## Layout

```
src/bindsmith/     engine (stdlib only)
  parser.py        .binds -> model, structure preserved
  writer.py        model -> .binds, ED's own format
  devices.py       descriptors, generation from button maps
  roles.py         the role vocabulary and capability menus
  presets.py       role-based layouts: seed, instantiate, save
  port.py          remap between devices (role, then index)
  audit.py         coverage, unknowns, conflicts
  cli.py           parse / audit / port / gen-devices
data/
  buttonmaps/      38 control-label maps (see ATTRIBUTION.md)
  roles/           hand-authored roles, one small file per device
  devices/         generated descriptors (full inventory + roles)
  presets/         role-based layouts
tools/             ingest + coverage-report helpers
web/               (next) thin presentation layer over the same engine
```

## Usage

```bash
# what's this config made of?
PYTHONPATH=src python3 -m bindsmith.cli parse ~/.steam/.../Bindings

# check it against the device catalog
PYTHONPATH=src python3 -m bindsmith.cli audit config.binds --data data

# move a layout onto different hardware
PYTHONPATH=src python3 -m bindsmith.cli port config.binds \
    --src 231D0200 --dst 231D012C --out ported.binds
```

## Contributing a device

1. Drop the device's `.buttonMap` in `data/buttonmaps/`.
2. Write `data/roles/<ID>.json` assigning roles to the controls that matter.
3. `python3 tools/ingest_buttonmaps.py` regenerates the descriptor.

Role files stay short because the inventory is generated, not typed.

## Credits

- Control-label maps from [EDCD/EliteCustomButtonNames](https://github.com/EDCD/EliteCustomButtonNames) (MIT, (c) 2025 Richard Buckle) — see `data/buttonmaps/ATTRIBUTION.md`.
- Elite Dangerous is a trademark of Frontier Developments plc. This tool
  reads and writes the game's config files; it is not affiliated with or
  endorsed by Frontier.
