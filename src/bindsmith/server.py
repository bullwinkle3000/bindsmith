"""FastAPI web layer for bindsmith: a thin presentation over the library.

Endpoints (all under /api):
  GET  /api/health                          liveness + env
  GET  /api/devices                         device descriptors (id, name, controls)
  GET  /api/devices/{key}                   one descriptor (full)
  PUT  /api/devices/{key}/controls/{ckey}   assign/clear a control's role
  GET  /api/devices/{key}/controls/{ckey}/roles   role menu for a control
  GET  /api/roles                           the full role vocabulary
  GET  /api/presets                         list preset files in data/presets
  GET  /api/presets/{name}                  preset layout {action: {role,...}}
  PUT  /api/presets/{name}                  save layout assignments
  GET  /api/presets/{name}/bindings?device= resolve a layout onto a device
  GET  /api/audit/{name}                    audit report for a preset .binds
  GET  /api/port/{name}?from=&to=           preview a .binds port (no write)
  POST /api/port/{name}                     port + write <name>-to-<to>.binds
  POST /api/seed/{name}                     seed a fresh layout from an ED .binds

The page at / is a self-contained single-file editor (no build step).
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bindsmith import __version__
from bindsmith.audit import audit
from bindsmith.devices import Device, load_devices, save_device
from bindsmith.parser import parse_binds
from bindsmith.presets import (
    Assignment,
    PresetLayout,
    instantiate,
    load,
    save,
    seed_from_binds,
)
from bindsmith.port import port
from bindsmith.roles import Capability, all_roles, offered_roles, role_group
from bindsmith.writer import write

REPO = Path(__file__).resolve().parent.parent.parent  # .../bindsmith
DATA_DIR = REPO / "data"
PRESET_DIR = DATA_DIR / "presets"
DEVICES_DIR = DATA_DIR / "devices"
WEB_DIR = REPO / "web"

ED_BINDS_DIR = (
    Path.home() / ".steam/debian-installation/steamapps/compatdata/359320/pfx/"
    "drive_c/users/steamuser/AppData/Local/Frontier Developments/"
    "Elite Dangerous/Options/Bindings"
)

app = FastAPI(title="bindsmith", version=__version__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _key_to_id(key: str) -> str:
    return key.replace(":", "")


def _get_device(key: str) -> tuple[str, Device]:
    devices = load_devices(DEVICES_DIR)
    k = _key_to_id(key)
    for did, dev in devices.items():
        if _key_to_id(did) == k or _key_to_id(dev.id) == k:
            return did, dev
    raise HTTPException(404, f"unknown device {key!r}; known: "
                             f"{sorted(_key_to_id(d) for d in devices if d != 'GENERIC')}")


def _preset_path(name: str) -> Path:
    if not name or "/" in name or name.startswith(".") or not name.endswith(".json"):
        raise HTTPException(400, "preset name must be a bare *.json filename")
    p = PRESET_DIR / name
    if not p.exists():
        raise HTTPException(404, f"no such preset: {name}")
    return p


def _load_layout(name: str) -> PresetLayout:
    try:
        return load(_preset_path(name))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"failed to load preset {name}: {e}") from e


def _binds_skeleton(name: str):
    """The .binds sibling of a preset (the full ordered action set)."""
    b = _preset_path(name).with_suffix(".binds")
    if b.exists():
        return parse_binds(b)
    raise HTTPException(404, f"no .binds sibling for {name}")


def _cap(control) -> Capability:
    return Capability(kind=control.type, axis=control.axis,
                      direction=control.direction if hasattr(control, "direction") else "both")


# ---------------------------------------------------------------------------
# health / vocabulary
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    devs = load_devices(DEVICES_DIR)
    return {
        "ok": True,
        "version": __version__,
        "presets": len(list(PRESET_DIR.glob("*.json"))),
        "devices": len([d for d in devs if d != "GENERIC"]),
        "ed_binds_dir": ED_BINDS_DIR.exists(),
        "ed_binds_files": sorted(f.name for f in ED_BINDS_DIR.glob("*.binds"))
        if ED_BINDS_DIR.exists() else [],
    }


@app.get("/api/roles")
def roles():
    return {"roles": all_roles()}


# ---------------------------------------------------------------------------
# devices
# ---------------------------------------------------------------------------

@app.get("/api/devices")
def list_devices():
    out = []
    for key, dev in sorted(load_devices(DEVICES_DIR).items()):
        if key == "GENERIC":
            continue
        out.append({
            "id": dev.id,
            "key": _key_to_id(key),
            "name": dev.name,
            "vendor": dev.vendor,
            "kind": dev.kind,
            "control_count": len(dev.controls),
            "roled": sum(1 for c in dev.controls if c.role),
        })
    return out


@app.get("/api/devices/{key}")
def get_device(key: str):
    did, dev = _get_device(key)
    return {
        "id": dev.id,
        "key": _key_to_id(did),
        "name": dev.name,
        "vendor": dev.vendor,
        "kind": dev.kind,
        "controls": [
            {"key": c.key, "label": c.label, "type": c.type,
             "axis": c.axis, "role": c.role, "group": c.group,
             "inverted": c.inverted, "deadzone": c.deadzone}
            for c in dev.controls
        ],
    }


class ControlPatch(BaseModel):
    role: str | None
    inverted: bool | None = None
    deadzone: float | None = None


@app.put("/api/devices/{key}/controls/{ckey}")
def set_control(key: str, ckey: str, patch: ControlPatch):
    did, dev = _get_device(key)
    ctl = dev.by_key(ckey)
    if ctl is None:
        raise HTTPException(404, f"no control {ckey!r} on device {key}")
    ctl.role = patch.role
    if patch.inverted is not None:
        ctl.inverted = patch.inverted
    if patch.deadzone is not None:
        ctl.deadzone = patch.deadzone
    save_device(dev, DEVICES_DIR)
    return {"ok": True, "key": ckey, "role": patch.role,
            "inverted": ctl.inverted, "deadzone": ctl.deadzone}


@app.get("/api/devices/{key}/controls/{ckey}/roles")
def control_roles(key: str, ckey: str):
    _, dev = _get_device(key)
    ctl = dev.by_key(ckey)
    if ctl is None:
        raise HTTPException(404, f"no control {ckey!r} on device {key}")
    return {
        "key": ctl.key,
        "role": ctl.role,
        "menu": offered_roles(_cap(ctl)),
        "group": role_group(ctl.role) if ctl.role else None,
    }


# ---------------------------------------------------------------------------
# presets
# ---------------------------------------------------------------------------

@app.get("/api/presets")
def list_presets():
    out = []
    for f in sorted(PRESET_DIR.glob("*.json")):
        try:
            layout = load(f)
            out.append({
                "name": f.name,
                "id": layout.id,
                "title": layout.name,
                "ed_version": layout.ed_version,
                "actions": len(layout.assignments),
                "has_binds": f.with_suffix(".binds").exists(),
            })
        except Exception:  # noqa: BLE001
            out.append({"name": f.name, "error": "unreadable"})
    return out


@app.get("/api/presets/{name}")
def get_preset(name: str):
    layout = _load_layout(name)
    return {
        "name": name,
        "id": layout.id,
        "title": layout.name,
        "description": layout.description,
        "ed_version": layout.ed_version,
        "assignments": [
            {"action": a.action, "role": a.role, "inverted": a.inverted,
             "deadzone": a.deadzone, "note": a.note}
            for a in layout.assignments
        ],
    }


class AssignmentPatch(BaseModel):
    action: str
    role: str | None
    inverted: bool | None = None
    deadzone: float | None = None
    note: str | None = None


class LayoutBody(BaseModel):
    assignments: list[AssignmentPatch]
    title: str | None = None
    description: str | None = None


@app.put("/api/presets/{name}")
def save_preset(name: str, body: LayoutBody):
    layout = _load_layout(name)
    by_action = {a.action: a for a in layout.assignments}
    for p in body.assignments:
        if p.role:
            if p.action in by_action:
                a = by_action[p.action]
                a.role = p.role
                if p.inverted is not None:
                    a.inverted = p.inverted
                if p.deadzone is not None:
                    a.deadzone = p.deadzone
                if p.note is not None:
                    a.note = p.note
            else:
                layout.assignments.append(Assignment(
                    action=p.action, role=p.role,
                    inverted=bool(p.inverted),
                    deadzone=p.deadzone or 0.0,
                    note=p.note or "",
                ))
                by_action[p.action] = layout.assignments[-1]
        else:  # role None == unbind this action
            layout.assignments = [a for a in layout.assignments if a.action != p.action]
            by_action.pop(p.action, None)
    if body.title is not None:
        layout.name = body.title
    if body.description is not None:
        layout.description = body.description
    save(layout, _preset_path(name))
    return {"ok": True, "name": name, "actions": len(layout.assignments)}


@app.get("/api/presets/{name}/bindings")
def preset_bindings(name: str, device: str):
    layout = _load_layout(name)
    _, dev = _get_device(device)
    skeleton = _binds_skeleton(name)
    result = instantiate(layout, dev, skeleton)
    out = []
    for action in result.actions:
        if not action.is_bound:
            continue
        b = action.primary or (action.secondary or (action.extra or [None])[0])
        if b is None:
            continue
        ctl = dev.by_key(b.key)
        out.append({
            "action": action.name,
            "device": b.device,
            "key": b.key,
            "label": ctl.label if ctl else b.key,
            "role": (layout.role_for(action.name) or Assignment(action.name, "")).role,
            "inverted": b.inverted,
            "deadzone": b.deadzone,
        })
    return {"device": dev.id, "count": len(out), "bindings": out}


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------

@app.get("/api/audit/{name}")
def audit_preset(name: str):
    layout = _load_layout(name)  # ensures it loads
    preset = _binds_skeleton(name)
    rep = audit(preset, load_devices(DEVICES_DIR))
    return {
        "ok": rep.ok,
        "clean": rep.clean,
        "render": rep.render(),
        "unknown_devices": sorted(set(rep.unknown_devices)),
        "fallback_classified": rep.fallback_classified,
        "orphans": rep.orphans,
        "coverage": rep.coverage,
        "conflicts": rep.conflicts,
    }


# ---------------------------------------------------------------------------
# port
# ---------------------------------------------------------------------------

def _port_result(name: str, frm: str, to: str):
    preset = _binds_skeleton(name)
    _, src = _get_device(frm)
    _, dst = _get_device(to)
    return port(preset, src, dst)


@app.get("/api/port/{name}")
def port_preview(name: str, frm: str, to: str):
    res = _port_result(name, frm, to)
    return {
        "from": frm, "to": to,
        "remapped": res.remapped,
        "unmapped": res.unmapped,
        "unchanged": res.unchanged,
    }


class PortBody(BaseModel):
    from_device: str
    to_device: str


@app.post("/api/port/{name}")
def port_save(name: str, body: PortBody):
    res = _port_result(name, body.from_device, body.to_device)
    dest = _preset_path(name).with_name(
        f"{name[:-5]}-to-{_key_to_id(body.to_device)}.binds"
    )
    write(res.preset, dest)
    return {
        "ok": True,
        "written": str(dest),
        "remapped": len(res.remapped),
        "unmapped": len(res.unmapped),
        "unchanged": res.unchanged,
    }


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------

class SeedBody(BaseModel):
    ed_binds: str      # filename in ED_BINDS_DIR (e.g. "VKB.4.2.binds")
    device: str        # descriptor key the roles should be attributed to
    title: str | None = None


@app.post("/api/seed/{name}")
def seed(name: str, body: SeedBody):
    if not name.endswith(".json") or "/" in name:
        raise HTTPException(400, "preset name must be a bare *.json filename")
    if _preset_path(name).exists():
        raise HTTPException(409, f"preset {name} already exists")
    src = ED_BINDS_DIR / body.ed_binds
    if not src.exists():
        raise HTTPException(404, f"no ED binds file {body.ed_binds!r} in {ED_BINDS_DIR}")
    binds = parse_binds(src)
    _, dev = _get_device(body.device)
    layout = seed_from_binds(binds, dev)
    if body.title:
        layout.name = body.title
    save(layout, _preset_path(name))
    write(binds, _preset_path(name).with_suffix(".binds"))
    return {"ok": True, "name": name, "actions": len(layout.assignments)}


# ---------------------------------------------------------------------------
# static frontend
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
