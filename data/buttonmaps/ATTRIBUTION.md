# Button map sources

`*.buttonMap` files in this directory are Elite Dangerous control-label maps.
They tell the game what to *call* each button and axis of a device.

Two provenances are mixed here:

1. **Community set — [EDCD/EliteCustomButtonNames](https://github.com/EDCD/EliteCustomButtonNames)**
   Copyright (c) 2025 Richard Buckle, MIT licensed. Vendored here so the tool
   works offline and reproducibly. The community set is better than ED's
   auto-generated maps: it carries human-written names and icon hints, e.g.

   ```
   <Joy_RXAxis>LSTECS OTS Vertical [x52prox]</Joy_RXAxis>
   ```

2. **Frontier Developments' own maps**, auto-generated per attached device,
   found in a player's `Options/DeviceButtonMaps/` folder.

## Why this matters to the tool

The maps are the **inventory** half of a device descriptor: what controls
exist and what they're called. Nobody should type that by hand, and the tool
should not guess it. The **meaning** half — which control plays which role
(pitch, throttle, gear) — is human judgement and lives in `data/roles/`.

Keeping those separate is what lets a new device be supported by writing a
~20-line role file instead of a 50-line control list.

## Known gap: maps do not cover every control

ED's shipped map for the VKB STECS Mini Plus defines 41 controls, but the
device reports more. Binds in the wild reference `Joy_18`, `Joy_20`,
`Joy_42`–`Joy_45`, which **no bundled map names** — so the game displays them
as bare "Joy 42". These are real, bindable controls; the gap is in labelling,
not in the hardware.

A map placed in the player's **Bindings** folder (not `ControlSchemes/`) is
not overwritten by game updates, so those gaps can be filled in locally.
