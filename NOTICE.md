# Third-party data

## EliteCustomButtonNames (EDCD)

Device button labels in `data/devices/*.json` (the `label` field of every
control, plus the control inventories of the 38 non-curated devices and the
`GENERIC.json` fallback template) are derived from:

> **EliteCustomButtonNames** — Elite Dangerous Community Discord (EDCD)
> https://github.com/EDCD/EliteCustomButtonNames
> MIT License, Copyright (c) 2025 Richard Buckle.

The full MIT license text lives in the upstream repository (LICENSE.txt) and
is reproduced here in `NOTICE_LICENSE_EDCD.txt`. The upstream files are
`.buttonMap` documents (ED's own label format, `files/INTO Bindings/
DeviceButtonMaps/`); this project converts them to device descriptors with
`bindsmith ingest`, which may be re-run as the upstream evolves.

The two hand-curated descriptors (`231D0200.json` — VKB Gladiator NXT R,
`231D012C.json` — VKB STECS Mini Plus) predate the ingest; their labels and
role assignments are the user's own curation, now merged over the upstream
control inventory.
