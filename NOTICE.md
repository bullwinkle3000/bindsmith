# Notices

## bindsmith

Copyright (C) 2026 Andrew Langton.

bindsmith is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. The full text is in `LICENSE`.

It is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE. See the GNU General Public License for more details.

## EliteCustomButtonNames (EDCD)

The `.buttonMap` files in `data/buttonmaps/` are vendored verbatim from:

> **EliteCustomButtonNames** — Elite Dangerous Community Discord (EDCD)
> https://github.com/EDCD/EliteCustomButtonNames
> MIT License, Copyright (c) 2025 Richard Buckle.

The full MIT license text lives in the upstream repository (LICENSE.txt) and
is reproduced here in `NOTICE_LICENSE_EDCD.txt`. MIT is compatible with this
project's GPL-3.0-or-later licensing; these data files remain under MIT.

Device labels in `data/devices/*.json` (the `label` field of every control,
plus the control inventories of the 38 non-curated devices and the
`GENERIC.json` fallback template) are derived from those same maps by
`bindsmith ingest`, which may be re-run as the upstream evolves.

The two hand-curated descriptors (`231D0200.json` — VKB Gladiator NXT R,
`231D012C.json` — VKB STECS Mini Plus) predate the ingest; their role
assignments are the user's own curation, merged over the upstream control
inventory.

## Frontier Developments

Elite Dangerous is a trademark of Frontier Developments plc. This project
reads and writes the game's configuration files and is neither affiliated
with nor endorsed by Frontier Developments.

