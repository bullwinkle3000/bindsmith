#!/usr/bin/env python3
"""Exercise every bindsmith web API endpoint against a running server.

    python3 tools/smoke_web.py [base_url]

Exits non-zero if any endpoint misbehaves. Read-only except for one
round-trip write that it reverts.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8770"
FAILS: list[str] = []


def call(method: str, path: str, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            ctype = r.headers.get("Content-Type", "")
            if "json" not in ctype:
                return r.status, raw      # HTML / plain text (e.g. GET /)
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


def check(label: str, cond: bool, detail: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {label}" + (f"  — {detail}" if detail else ""))
    if not cond:
        FAILS.append(label)


def main() -> int:
    st, h = call("GET", "/api/health")
    check("GET /api/health", st == 200 and h.get("ok"), f"v{h.get('version')} "
          f"devices={h.get('devices')} presets={h.get('presets')}")
    check("health lists ED binds", bool(h.get("ed_binds_files")),
          ", ".join(h.get("ed_binds_files") or []))

    st, roles = call("GET", "/api/roles")
    check("GET /api/roles", st == 200 and len(roles.get("roles", [])) > 20,
          f"{len(roles.get('roles', []))} roles")

    st, devs = call("GET", "/api/devices")
    check("GET /api/devices", st == 200 and len(devs) > 0, f"{len(devs)} devices")
    keys = [d["key"] for d in devs]
    check("VKB Gladiator in catalog", "231D0200" in keys)
    check("VKB STECS in catalog", "231D012C" in keys)

    st, dev = call("GET", "/api/devices/231D0200")
    check("GET /api/devices/{key}", st == 200 and len(dev["controls"]) > 20,
          f"{dev['name']} — {len(dev['controls'])} controls")

    st, menu = call("GET", "/api/devices/231D0200/controls/Joy_POV1Up/roles")
    check("GET control role menu", st == 200 and len(menu["menu"]) > 0,
          f"{len(menu['menu'])} options for a POV control")

    st, amenu = call("GET", "/api/devices/231D0200/controls/Joy_YAxis/roles")
    check("axis role menu includes rotation+thrust",
          "pitch" in amenu["menu"] and "thrust_fwd" in amenu["menu"],
          f"{len(amenu['menu'])} options")

    # ---- write round-trip (set a role, then clear it) -------------------
    st, w = call("PUT", "/api/devices/231D0200/controls/Joy_4", {"role": "menu_confirm"})
    check("PUT control role", st == 200 and w.get("role") == "menu_confirm")
    st, dev2 = call("GET", "/api/devices/231D0200")
    ctl = next((c for c in dev2["controls"] if c["key"] == "Joy_4"), None)
    check("role persisted", ctl is not None and ctl["role"] == "menu_confirm",
          f"Joy_4 role={ctl['role'] if ctl else '?'}")
    st, _ = call("PUT", "/api/devices/231D0200/controls/Joy_4", {"role": None})
    st, dev3 = call("GET", "/api/devices/231D0200")
    ctl = next((c for c in dev3["controls"] if c["key"] == "Joy_4"), None)
    check("role cleared (reverted)", ctl is not None and not ctl["role"])

    st, pre = call("GET", "/api/presets")
    check("GET /api/presets", st == 200 and len(pre) > 0,
          f"{len(pre)} preset(s): {', '.join(p['name'] for p in pre)}")
    name = pre[0]["name"]

    st, lay = call("GET", f"/api/presets/{name}")
    check("GET /api/presets/{name}", st == 200 and len(lay["assignments"]) > 0,
          f"{len(lay['assignments'])} assignments")

    st, bind = call("GET", f"/api/presets/{name}/bindings?device=231D0200")
    check("GET bindings resolved for device", st == 200 and bind["count"] > 10,
          f"{bind['count']} bound actions")

    st, aud = call("GET", f"/api/audit/{name}")
    check("GET audit", st == 200 and isinstance(aud.get("render"), str),
          f"clean={aud.get('clean')} unknown={aud.get('unknown_devices')}")

    st, prt = call("GET", f"/api/port/{name}?frm=231D0200&to=231D012C")
    check("GET port preview", st == 200 and "remapped" in prt,
          f"remapped={len(prt.get('remapped') or [])} "
          f"unmapped={len(prt.get('unmapped') or [])} unchanged={prt.get('unchanged')}")

    st, _ = call("GET", "/")
    check("GET / serves the editor", st == 200)

    st, bad = call("GET", "/api/devices/NOPE")
    check("unknown device -> 404", st == 404)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} — " + "; ".join(FAILS))
        return 1
    print("ALL ENDPOINTS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
