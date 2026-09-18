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

Early, but the engine works end to end against a real 700-hour VKB setup:

- parses a `.binds` file faithfully (422 actions, raw structure preserved)
- re-emits a valid `.binds` that the game's own reader accepts
- seeds a role-based layout from an existing config (24 roles from the
  reference VKB setup)
- instantiates that layout back onto a device — verified round-trip, 289 of
  289 bound actions preserved
- audits a config for unknown devices, unlabelled controls, and coverage
- ports bindings between devices by role, falling back to index
- ships a web editor: assign roles per control from a capability-aware menu,
  edit a preset's assignments, resolve it onto a device, audit it, and port it
  to other hardware — all backed by the same library the CLI uses
- creates profiles: blank (the full action set, nothing bound), a copy of
  another profile, or a copy of a config from the game with roles read off a
  chosen device — plus delete

Not built yet: mode-aware conflict checks (flight / SRV / on-foot), a packaged
release, and CI.

## Layout

```
src/bindsmith/     engine (stdlib only)
  parser.py        .binds -> model, structure preserved
  writer.py        model -> .binds, ED's own format
  devices.py       descriptors, generation from button maps
  ingest.py        button maps -> descriptors (merging, idempotent)
  roles.py         the role vocabulary and capability menus
  presets.py       role-based layouts: seed, instantiate, save
  port.py          remap between devices (role, then index)
  audit.py         coverage, unknowns, conflicts
  wizard.py        interactive role assignment
  server.py        FastAPI layer (optional extra)
  cli.py           parse / audit / port / ingest / assign / serve / gen-devices
data/
  buttonmaps/      38 control-label maps (see ATTRIBUTION.md)
  actions/         <version>.template.binds — the blank action set
  devices/         descriptors: full inventory + curated roles
  presets/         profiles: a role-based layout + its .binds
web/index.html     self-contained editor (no build step)
tools/
  reingest.py      refresh descriptors from button maps
  make_template.py regenerate the blank action set from a real config
  check_coverage.py  report controls ED's maps have no label for
  smoke_web.py     exercise every API endpoint
  ui_check.mjs     drive the editor headlessly, catch JS errors
  shot.mjs         capture the editor's views as PNGs
  check_pngs.py    verify captures are real renders, not blank pages
```

## Usage

```bash
pip install -e ".[web]"          # engine needs nothing; web is the extra

# what's this config made of?
bindsmith parse ~/.steam/.../Bindings

# check it against the device catalog
bindsmith audit config.binds

# move a layout onto different hardware
bindsmith port config.binds --src 231D0200 --dst 231D012C --out ported.binds

# the editor
bindsmith serve                  # then open http://127.0.0.1:8770
```

## Contributing a device

1. Drop the device's `.buttonMap` in `data/buttonmaps/`.
2. Write `data/roles/<ID>.json` assigning roles to the controls that matter.
3. `python3 tools/ingest_buttonmaps.py` regenerates the descriptor.

Role files stay short because the inventory is generated, not typed.

## Credits

- Control-label maps from [EDCD/EliteCustomButtonNames](https://github.com/EDCD/EliteCustomButtonNames) (MIT, (c) 2025 Richard Buckle) — see `data/buttonmaps/ATTRIBUTION.md` and `NOTICE.md`.
- Elite Dangerous is a trademark of Frontier Developments plc. This tool
  reads and writes the game's config files; it is not affiliated with or
  endorsed by Frontier.

## License

GPL-3.0-or-later — see [`LICENSE`](LICENSE). Bundled third-party data keeps
its own license: the control-label maps are MIT. Full attribution in
[`NOTICE.md`](NOTICE.md).
