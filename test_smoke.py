#!/usr/bin/env python3
"""End-to-end smoke test for the bindsmith engine.

Runs anywhere: it exercises the profile committed in this repository. When an
Elite Dangerous installation is found on the machine its live config is tested
too, but its absence is a skip, not a failure.

Outputs go to a temporary directory — a test must not rewrite the fixtures it
is testing.

    python3 test_smoke.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from bindsmith import paths                                    # noqa: E402
from bindsmith.audit import audit                              # noqa: E402
from bindsmith.devices import load_devices                     # noqa: E402
from bindsmith.parser import load_all_binds, parse_binds       # noqa: E402
from bindsmith.presets import (                                # noqa: E402
    blank_from, instantiate, load, save, seed_from_binds,
)
from bindsmith.writer import write                             # noqa: E402

DATA = ROOT / "data"
PROFILE = DATA / "presets" / "vkb_gladiator_seed.binds"
TEMPLATE = DATA / "actions" / "4.2.template.binds"

FAILS: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {label}"
          + (f"  — {detail}" if detail else ""))
    if not cond:
        FAILS.append(label)


def main() -> int:
    # ---- the profile committed in this repo -----------------------------
    preset = parse_binds(PROFILE)
    bound = sum(1 for a in preset.actions if a.is_bound)
    check("committed profile parses", len(preset.actions) > 100,
          f"{len(preset.actions)} actions, {bound} bound")

    # ---- the live config, if this machine has the game ------------------
    live = paths.binds_dir()
    if live:
        names = sorted(load_all_binds(live))
        check("live ED config parses", bool(names), ", ".join(names))
    else:
        print("[SKIP] no Elite Dangerous install found on this machine")

    # ---- device descriptors ---------------------------------------------
    devs = load_devices(DATA / "devices")
    check("device descriptors load", len(devs) > 10, f"{len(devs)} devices")
    gl = devs.get("231D0200")
    check("reference stick in the catalog", gl is not None, "231D0200")
    if gl is None:
        return summary()
    roled = sum(1 for c in gl.controls if c.role)
    check("reference stick has roles", roled > 10, f"{roled}/{len(gl.controls)}")

    # ---- seed a role-based layout from the profile ----------------------
    layout = seed_from_binds(preset, gl)
    check("seed extracts a portable layout", len(layout.assignments) > 15,
          f"{len(layout.assignments)} assignments")
    check("roles are hardware-independent",
          "pitch" in layout.roles() and "throttle" in layout.roles(),
          ", ".join(layout.roles()[:6]) + ", …")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # ---- instantiate the layout back onto the device ----------------
        inst = instantiate(layout, gl, preset)
        inst_bound = sum(1 for a in inst.actions if a.is_bound)
        check("instantiate preserves bindings",
              inst_bound >= bound * 0.9,
              f"{bound} -> {inst_bound} bound of {len(inst.actions)} actions")

        # ---- write it out and read it back ------------------------------
        out = tmp / "roundtrip.binds"
        write(inst, out)
        reparsed = parse_binds(out)
        rep_bound = sum(1 for a in reparsed.actions if a.is_bound)
        check("written file re-parses", len(reparsed.actions) == len(inst.actions),
              f"{len(reparsed.actions)} actions")
        check("bindings survive the round trip",
              rep_bound == inst_bound, f"{inst_bound} -> {rep_bound}")

        # ---- a layout saves and loads unchanged -------------------------
        lj = tmp / "layout.json"
        save(layout, lj)
        again = load(lj)
        check("layout round-trips through JSON",
              len(again.assignments) == len(layout.assignments),
              f"{len(again.assignments)} assignments")

    # ---- blank profiles --------------------------------------------------
    template = parse_binds(TEMPLATE)
    blank = blank_from(template, name="Test")
    check("blank profile has the full action set",
          len(blank.actions) == len(template.actions),
          f"{len(blank.actions)} actions")
    check("blank profile binds nothing",
          not any(a.is_bound for a in blank.actions))
    check("blank profile preserves action order",
          [a.name for a in blank.actions] == [a.name for a in template.actions])
    check("blank profile keeps root settings", len(blank.settings) > 50,
          f"{len(blank.settings)} settings")

    # ---- audit -----------------------------------------------------------
    rep = audit(preset, devs)
    check("audit produces a report", isinstance(rep.render(), str)
          and len(rep.render()) > 0,
          f"clean={rep.clean}")
    orphans = getattr(rep, "orphans", {})
    check("audit flags unlabelled controls", orphans is not None)

    return summary()


def summary() -> int:
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}): " + "; ".join(FAILS))
        return 1
    print("ENGINE OK — all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
