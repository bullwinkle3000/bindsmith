"""The role vocabulary: what a control MEANS, independent of hardware or preset.

This is the heart of the tool. A preset is a mapping from ED *actions* to
*roles*; a device descriptor maps *controls* to *roles*. Instantiation is the
join of the two. A role is deliberately coarse-grained (a "thrust axis", not
"left stick Y") so that many devices and many players' layouts can be
expressed.

The vocabulary below is the one used by the hand-curated device descriptors
and the VKB seed preset (fire_primary, menu_up, map_galaxy, ...). Roles are
grouped by the control's capability class; ``offered_roles(capability)``
returns the menu a wizard/UI should present for a control of that class.
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Capability classes
# ---------------------------------------------------------------------------

@dataclass
class Capability:
    """What a control can physically do — the input to role offering."""
    kind: str                       # axis | button | pov
    axis: str = ""                  # X|Y|Z|RX|RY|RZ|U|V for axes
    direction: str = "both"         # both | one   (throttle lever = one)
    group: int = 0                  # hat/pad group id
    axis_count: int = 1             # how many axes this control spans (stick=2/3)

    @property
    def is_axis(self) -> bool:
        return self.kind == "axis"

    @property
    def is_cluster(self) -> bool:
        return self.is_axis and self.axis_count >= 2


# ---------------------------------------------------------------------------
# Role menus per capability
# ---------------------------------------------------------------------------

# 3D sticks / 2-axis pairs: one axis per function, listed as "axis_role"
# pairs so the wizard knows both controls come as a set.
_STICK_COMBOS = [
    ("X=yaw", "Y=pitch"),          # conventional flight
    ("X=yaw", "Y=roll"),           # roll on the stick
    ("X=pitch", "Y=yaw"),
    ("X=roll", "Y=yaw"),
    ("X=pitch", "Y=roll"),
]

# Single bidirectional axis
_AXIS_ROTATION = ["pitch", "yaw", "roll"]
_AXIS_THRUST = ["thrust_fwd", "thrust_aft", "thrust_left", "thrust_right",
                "thrust_up", "thrust_down"]
_AXIS_SINGLE = ["throttle", "tune", "rudder"]

# One-direction axes (levers, wheels, pedals)
_AXIS_ONE_WAY = ["throttle", "tune", "throttle_range"]

_BUTTON_MENU = [
    # fire
    "fire_primary", "fire_secondary",
    # boost / hyperspace
    "use_boost", "hyperfuel_toggle", "hyperspace",
    # gear
    "toggle_gear", "gear", "toggle_brake", "brake", "toggle_safe_mode",
    # lights & nav
    "toggle_lights", "toggle_night_vision", "toggle_cargo",
    # maps
    "map_system", "map_galaxy", "map_starmap",
    # focus panels
    "focus_target", "focus_fss", "focus_radar", "focus_comms",
    "focus_right", "focus_left",
    # menus
    "menu_confirm", "menu_cancel", "menu_back",
    # misc toggles
    "toggle_assist", "toggle_freecam", "toggle_afterburner",
    "deploy_heatsink", "target_next", "target_prev",
    # wingman / comms
    "wingman_select_1", "wingman_select_2", "wingman_select_3",
    "wingman_order_follow", "wingman_order_wait", "wingman_order_hold",
    "comms_toggle", "comms_talk",
]

_POV_MENU = [
    "menu_navigate (up/down/left/right)",
    "camera_orbit",
    "target_selection",
    "wingman_commands (4 dirs)",
    "power_distribution (4 dirs)",
]

# Roles that a button, POV or axis may carry (for UI validation / menus).
ROLE_GROUPS: dict[str, list[str]] = {
    "Rotation": _AXIS_ROTATION,
    "Translation": _AXIS_THRUST,
    "Throttle / tune": _AXIS_SINGLE + ["throttle_range", "invert_throttle"],
    "Stick combos": [a for pair in _STICK_COMBOS for a in
                     (pair[0].split("=")[1], pair[1].split("=")[1])],
    "Buttons": _BUTTON_MENU,
    "POV / hats": ["menu_up", "menu_down", "menu_left", "menu_right",
                   "camera_orbit", "target_selection"],
}


def offered_roles(cap: Capability) -> list[str]:
    """Return the role menu to offer for a control of this capability."""
    if cap.is_cluster:
        # A 3D stick (RX/RY/RZ cluster) covers yaw+pitch+roll in one
        # control; a 2-axis pair covers two of them.
        if cap.axis_count >= 3:
            return ["yaw/roll/pitch (3-axis stick)",
                    "pitch/yaw/roll (3-axis stick)"]
        return list(_STICK_COMBOS)
    if cap.is_axis and cap.direction == "one":
        return list(_AXIS_ONE_WAY)
    if cap.is_axis:
        return list(_AXIS_ROTATION) + list(_AXIS_THRUST) + list(_AXIS_SINGLE)
    if cap.kind == "pov":
        return list(_POV_MENU)
    if cap.kind == "button":
        return list(_BUTTON_MENU)
    return []


def role_group(role: str) -> str:
    for g, roles in ROLE_GROUPS.items():
        if role in roles:
            return g
    return "Other"


def all_roles() -> list[str]:
    """Every role in the vocabulary (stable order), for UIs and checks."""
    out: list[str] = []
    for roles in ROLE_GROUPS.values():
        for r in roles:
            if r not in out:
                out.append(r)
    return out
