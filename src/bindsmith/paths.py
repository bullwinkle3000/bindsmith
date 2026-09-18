"""Where Elite Dangerous keeps its configuration, and how to find it.

On Linux the game runs through Proton, so its config lives inside a Wine
prefix under a Steam library. Which library, and which prefix, depends on the
installation — so nothing here assumes a particular user, home directory or
Steam layout. Callers get a resolved path or None, and are expected to say so
plainly rather than guess.

Resolution order:

1. ``$BINDSMITH_ED_BINDS`` — an explicit override, for a config kept anywhere
   else (a backup, another drive, a different prefix name).
2. The Standard Steam library layouts, checked in order, for the Odyssey
   prefix (app 359320).
"""
from __future__ import annotations

import os
from pathlib import Path

#: Environment variable that overrides all detection.
ENV_OVERRIDE = "BINDSMITH_ED_BINDS"

#: Elite Dangerous' Steam application id.
ED_APP_ID = "359320"

#: Path from a Proton prefix root to the game's Options directory.
_PREFIX_OPTIONS = Path(
    "drive_c/users/steamuser/AppData/Local/Frontier Developments/Elite Dangerous/Options"
)

#: Where Steam libraries commonly live, relative to $HOME. Covers the distro
#: package (debian-installation), the upstream tarball, and the Flatpak.
_STEAM_LIBRARY_ROOTS = (
    f".steam/debian-installation/steamapps/compatdata/{ED_APP_ID}/pfx",
    f".steam/steam/steamapps/compatdata/{ED_APP_ID}/pfx",
    f".local/share/Steam/steamapps/compatdata/{ED_APP_ID}/pfx",
    f".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata/{ED_APP_ID}/pfx",
)


def _candidates() -> list[Path]:
    home = Path.home()
    return [home / rel for rel in _STEAM_LIBRARY_ROOTS]


def prefix_roots() -> list[Path]:
    """Every Proton prefix that actually exists on this machine."""
    return [p for p in _candidates() if p.is_dir()]


def options_dir() -> Path | None:
    """The game's ``Options`` directory, or None if it cannot be found."""
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        p = Path(override).expanduser()
        # Accept either the Bindings dir itself or any ancestor of it.
        for cand in (p, p / "Options", p.parent, p.parent / "Options"):
            if (cand / "Bindings").is_dir():
                return cand
        return p if p.is_dir() else None
    for root in prefix_roots():
        cand = root / _PREFIX_OPTIONS
        if cand.is_dir():
            return cand
    return None


def binds_dir() -> Path | None:
    """Where ``*.binds`` files live: ``Options/Bindings``."""
    opts = options_dir()
    if opts is None:
        return None
    b = opts / "Bindings"
    return b if b.is_dir() else None


def buttonmaps_dir() -> Path | None:
    """Where ED's own ``*.buttonMap`` files live, if the game wrote any."""
    opts = options_dir()
    if opts is None:
        return None
    b = opts / "DeviceButtonMaps"
    return b if b.is_dir() else None


def describe() -> str:
    """A one-line human summary, for CLI output and the web UI."""
    b = binds_dir()
    if b is None:
        return (f"Elite Dangerous config not found (set ${ENV_OVERRIDE} to point "
                f"at a Bindings directory)")
    return f"{b}"
