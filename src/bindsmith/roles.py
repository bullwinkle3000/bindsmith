"""The role vocabulary: what a control MEANS, independent of hardware or preset.

This is the heart of the tool. A preset is a mapping from ED *actions* to
*roles*; a device descriptor maps *controls* to *roles*. Instantiation is the
join of the two. A role is deliberately coarse-grained (a "thrust axis", not
"left stick Y") so that many devices and many players' layouts can be
expressed.

Roles are grouped by the control's capability class, and each class carries a
menu of offered roles (what the CLI/website suggests to a user). The class is
derived from the control:

  * axis, 2-direction capable (any single Joy axis is bidirectional)
      -> pitch / yaw / roll  (rotation)
         thrust fwd-aft / left-right  (translation)
         throttle / rudder / tune  (one-function axes)
  * axis, 3-axis cluster (X+Y together, or a 3D stick)
      -> the pitch/yaw/roll pitch/yaw/roll / pitch/roll / yaw/roll combos
  * single-direction axis (a physical throttle lever, a pedal, a wheel that
      only goes one way)
      -> throttle / tune / speed presets
  * button
      -> toggle_* / press_* / menu_navigate / wingman_n / power_* / gear /
         lights / night_vision / cargo / ...
  * pov (hat / d-pad / 4-way)
      -> menu_up/down/left/right, wingman_*, power_distribution, ...

The offered menus below implement exactly that: `offered_roles(capability)`
returns the list of role strings a control of that capability should present.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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

_AXIS_ROTATION = ["pitch", "yaw", "roll"]

_AXIS_TRANS_LATERAL = ["thrust_left", "thrust_right"]
_AXIS_TRANS_VERT = ["thrust_up", "thrust_down"]
_AXIS_TRANS_FWD = ["thrust_fwd", "thrust_aft"]

_AXIS_ONE_FUNC = [
    "throttle", "rudder", "tune", "throttle_range",
    "invert_yaw", "invert_pitch", "invert_roll",
]

_PITCH_YAW_ROLL_COMBOS = [
    "pitch/yaw/roll",     # 3-axis stick: X=yaw Y=pitch Z=roll (conventional)
    "yaw/roll/pitch",
    "pitch/roll/yaw",
    "yaw/pitch/roll",
    "pitch/yaw (Z=free)",
    "yaw/roll (Y=free)",
    "pitch/roll (X=free)",
]

_POV_MENUS = [
    "menu_navigate (up/down/left/right)",
    "wingman_commands (4 dirs)",
    "power_distribution (4 dirs)",
    "camera_orbit",
    "target_selection",
]

_BUTTON_MENU = [
    "toggle_gear", "toggle_lights", "toggle_night_vision",
    "toggle_cargo", "toggle_safe_mode", "toggle_brake",
    "toggle_landing_gear_locked", "toggle_afterburner",
    "press_forward", "press_back", "press_up", "press_down",
    "toggle_boost", "toggle_target", "toggle_map", "toggle_comms",
    "menu_confirm", "menu_cancel", "menu_back",
    "wingman_select_1", "wingman_select_2", "wingman_select_3", "wingman_select_4",
    "wingman_order_follow", "wingman_order_wait", "wingman_order_hold",
    "power_engine", "power_shields", "power_weapons", "power_all_off",
    "brake", "reverse", "turret_up", "turret_down", "turret_left", "turret_right",
]


def offered_roles(cap: Capability) -> list[str]:
    """Return the role menu to offer for a control of this capability."""
    if cap.is_cluster:
        # 3-axis or 2-axis stick: offer the rotation combos.
        if cap.axis_count >= 3:
            return list(_PITCH_YAW_ROLL_COMBOS)
        # 2-axis (X+Y): pitch/yaw with the Z-free style.
        return [
            "yaw (X) / pitch (Y)",
            "pitch (X) / yaw (Y)",
            "roll (X) / yaw (Y)",
            "pitch (X) / roll (Y)",
        ]
    if cap.is_axis and cap.direction == "one":
        # Single-direction: throttle / tune / speed.
        return ["throttle", "tune", "throttle_up", "throttle_down",
                "speed_presets", "invert_throttle"]
    if cap.is_axis:
        # A single bidirectional axis: rotation or translation or one-function.
        return (
            list(_AXIS_ROTATION)
            + list(_AXIS_TRANS_LATERAL)
            + list(_AXIS_TRANS_VERT)
            + list(_AXIS_TRANS_FWD)
            + list(_AXIS_ONE_FUNC)
        )
    if cap.kind == "pov":
        return list(_POV_MENUS)
    if cap.kind == "button":
        return list(_BUTTON_MENU)
    return []


# ---------------------------------------------------------------------------
# Role groups — for rendering the UI menu and for preset semantics
# ---------------------------------------------------------------------------

ROLE_GROUPS: dict[str, list[str]] = {
    "Rotation": _AXIS_ROTATION,
    "Translation": _AXIS_TRANS_LATERAL + _AXIS_TRANS_VERT + _AXIS_TRANS_FWD,
    "One-function axes": _AXIS_ONE_FUNC,
    "Stick combos": _PITCH_YAW_ROLL_COMBOS,
    "POV / hats": _POV_MENUS,
    "Buttons": _BUTTON_MENU,
}


def role_group(role: str) -> str:
    for g, roles in ROLE_GROUPS.items():
        if role in roles:
            return g
    return "Other"
