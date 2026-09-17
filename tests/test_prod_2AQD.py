"""Test suite for the 2AQD product adapter.

Drop this file next to ``prod_2AQD.py`` in the repository's tests directory
and adapt the import path to the project's existing test layout.

Covered behaviour
-----------------
* prod_id discovery and entity set
* brightness scaling in both directions (Profile 1..100 <-> HA 0..255)
* cct projection gating by colourMode
* scene select mutual exclusion with colourMode
* enum write payloads and unknown-option failure
* graceful degradation when services are missing
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from custom_components.huawei_smarthome.device_adapters import prod_2AQD

ADAPTER = prod_2AQD.ADAPTER

PROFILE: dict[str, Any] = {
    "prodId": "2AQD",
    "deviceTypeId": "01B",
    "services": [
        {
            "serviceId": "switch",
            "serviceType": "switch",
            "characteristics": [
                {
                    "characteristicName": "on",
                    "characteristicType": "bool",
                    "method": "RW",
                    "permission": "GPR",
                    "enumList": [
                        {"enumVal": "1", "descCh": "开"},
                        {"enumVal": "0", "descCh": "关"},
                    ],
                }
            ],
        },
        {
            "serviceId": "brightness",
            "serviceType": "brightness",
            "characteristics": [
                {
                    "characteristicName": "brightness",
                    "characteristicType": "int",
                    "method": "RW",
                    "permission": "GPR",
                    "min": "1",
                    "max": "100",
                    "step": 1,
                }
            ],
        },
        {
            "serviceId": "cct",
            "serviceType": "cct",
            "characteristics": [
                {
                    "characteristicName": "colorTemperature",
                    "characteristicType": "int",
                    "method": "RW",
                    "permission": "GPR",
                    "min": "2800",
                    "max": "6000",
                    "step": 1,
                }
            ],
        },
        {
            "serviceId": "colourMode",
            "serviceType": "colourMode",
            "characteristics": [
                {
                    "characteristicName": "mode",
                    "characteristicType": "enum",
                    "method": "R",
                    "permission": "GR",
                    "enumList": [
                        {"enumVal": "0", "descCh": "彩色"},
                        {"enumVal": "1", "descCh": "单色"},
                        {"enumVal": "2", "descCh": "预置流光"},
                        {"enumVal": "3", "descCh": "自定义流光"},
                        {"enumVal": "4", "descCh": "设备预置模式"},
                    ],
                }
            ],
        },
        {
            "serviceId": "lightMode",
            "serviceType": "lightMode",
            "characteristics": [
                {
                    "characteristicName": "mode",
                    "characteristicType": "enum",
                    "method": "RW",
                    "permission": "GPR",
                    "enumList": [
                        {"enumVal": "0", "descCh": "会客模式"},
                        {"enumVal": "1", "descCh": "休闲模式"},
                        {"enumVal": "2", "descCh": "观影模式"},
                        {"enumVal": "9", "descCh": "清扫模式"},
                    ],
                }
            ],
        },
        {
            "serviceId": "natural",
            "serviceType": "natural",
            "characteristics": [
                {
                    "characteristicName": "on",
                    "characteristicType": "bool",
                    "method": "RW",
                    "permission": "GPR",
                }
            ],
        },
        {
            "serviceId": "nightmode",
            "serviceType": "nightmode",
            "characteristics": [
                {
                    "characteristicName": "on",
                    "characteristicType": "bool",
                    "method": "RW",
                    "permission": "GPR",
                }
            ],
        },
        {
            "serviceId": "lampswitch",
            "serviceType": "lampswitch",
            "characteristics": [
                {
                    "characteristicName": "switch",
                    "characteristicType": "enum",
                    "method": "RW",
                    "permission": "GPR",
                    "enumList": [
                        {"enumVal": "0", "descCh": "全亮"},
                        {"enumVal": "1", "descCh": "区域1"},
                        {"enumVal": "2", "descCh": "区域2"},
                    ],
                }
            ],
        },
    ],
}


class FakeContext:
    """Minimal DeviceContext stand-in; records outbound service writes."""

    def __init__(self, profile: Mapping[str, Any] | None = PROFILE) -> None:
        self.profile = profile
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self._state: dict[str, dict[str, Any]] = {}

    def has_service(self, sid: str) -> bool:
        if self.profile is None:
            return False
        return any(
            service.get("serviceId") == sid
            for service in self.profile.get("services", ())
        )

    def value(self, sid: str, field: str) -> Any:
        return self._state.get(sid, {}).get(field)

    def set(self, sid: str, **data: Any) -> None:
        self._state.setdefault(sid, {}).update(data)

    async def async_send_service(self, sid: str, data: Mapping[str, Any]) -> None:
        assert self.has_service(sid), f"service not on device: {sid}"
        self.sent.append((sid, dict(data)))


def _entities(context: FakeContext):
    return {spec.key: spec for spec in ADAPTER.entities(context)}


def test_prod_id() -> None:
    assert ADAPTER.prod_id == "2AQD"


def test_entity_set() -> None:
    specs = ADAPTER.entities(FakeContext())
    assert tuple(spec.key for spec in specs) == (
        "light",
        "natural_light",
        "night_mode",
        "scene_mode",
        "lamp_switch",
        "colour_mode",
    )
    assert tuple(spec.platform for spec in specs) == (
        "light",
        "switch",
        "switch",
        "select",
        "select",
        "sensor",
    )


@pytest.mark.parametrize(
    ("device_value", "ha_value"),
    [(1, 0), (50, 126), (100, 255)],
)
def test_brightness_read_scaling(device_value: int, ha_value: int) -> None:
    context = FakeContext()
    context.set("brightness", brightness=device_value)
    context.set("colourMode", mode=1)
    light = _entities(context)["light"]
    assert light.state(context)["brightness"] == ha_value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ha_value", "device_value"),
    [(0, 1), (1, 1), (255, 100)],
)
async def test_brightness_write_scaling(ha_value: int, device_value: int) -> None:
    context = FakeContext()
    light = _entities(context)["light"]
    await light.actions["turn_on"](context, {"brightness": ha_value})
    assert [sid for sid, _ in context.sent] == ["switch", "brightness"]
    assert dict(context.sent[1][1]) == {"brightness": device_value}


@pytest.mark.parametrize(
    ("colour_mode", "expected"),
    [
        (0, None),
        (1, "color_temp"),
        (2, None),
        (3, None),
        (4, None),
        (None, None),
    ],
)
def test_cct_projection_gating(colour_mode: int | None, expected: str | None) -> None:
    context = FakeContext()
    context.set("switch", on=1)
    context.set("cct", colorTemperature=4000)
    context.set("colourMode", mode=colour_mode)
    assert _entities(context)["light"].state(context)["color_mode"] == expected


@pytest.mark.asyncio
async def test_turn_on_drives_colour_mode_before_cct() -> None:
    context = FakeContext()
    light = _entities(context)["light"]
    await light.actions["turn_on"](context, {"color_temp_kelvin": 6000})
    assert [sid for sid, _ in context.sent] == ["switch", "colourMode", "cct"]
    assert dict(context.sent[1][1]) == {"mode": 1}


def test_scene_hidden_unless_colour_mode_is_device_preset() -> None:
    context = FakeContext()
    context.set("lightMode", mode=5)
    scene = _entities(context)["scene_mode"]
    for colour_mode in (0, 1, 2, 3, None):
        context.set("colourMode", mode=colour_mode)
        assert scene.state(context)["current_option"] is None
    context.set("lightMode", mode=1)
    context.set("colourMode", mode=4)
    assert scene.state(context)["current_option"] == "休闲模式"


@pytest.mark.asyncio
async def test_scene_write_drives_colour_mode_first() -> None:
    context = FakeContext()
    scene = _entities(context)["scene_mode"]
    await scene.actions["select_option"](context, {"option": "观影模式"})
    assert [sid for sid, _ in context.sent] == ["colourMode", "lightMode"]
    assert dict(context.sent[0][1]) == {"mode": 4}
    assert dict(context.sent[1][1]) == {"mode": 2}


@pytest.mark.asyncio
async def test_unknown_scene_option_raises_and_writes_nothing() -> None:
    context = FakeContext()
    scene = _entities(context)["scene_mode"]
    with pytest.raises(ValueError):
        await scene.actions["select_option"](context, {"option": "不存在"})
    assert context.sent == []


@pytest.mark.asyncio
async def test_lampswitch_select() -> None:
    context = FakeContext()
    spec = _entities(context)["lamp_switch"]
    assert spec.metadata["options"] == ("全亮", "区域1", "区域2")
    await spec.actions["select_option"](context, {"option": "区域2"})
    assert context.sent == [("lampswitch", {"switch": 2})]
    context.set("lampswitch", switch=1)
    assert spec.state(context)["current_option"] == "区域1"


def test_colour_mode_sensor_is_read_only() -> None:
    context = FakeContext()
    spec = _entities(context)["colour_mode"]
    assert spec.actions == {}
    for raw, label in ((0, "彩色"), (1, "单色"), (2, "预置流光"),
                       (3, "自定义流光"), (4, "设备预置模式")):
        context.set("colourMode", mode=raw)
        assert spec.state(context)["state"] == label
    context.set("colourMode", mode=None)
    assert spec.state(context)["state"] == "未知"


def test_missing_core_service_yields_no_entities() -> None:
    profile = {
        **PROFILE,
        "services": [s for s in PROFILE["services"] if s["serviceId"] != "cct"],
    }
    assert ADAPTER.entities(FakeContext(profile)) == ()


def test_missing_optional_services_are_skipped() -> None:
    profile = {
        **PROFILE,
        "services": [
            s
            for s in PROFILE["services"]
            if s["serviceId"] not in {"lightMode", "lampswitch", "colourMode"}
        ],
    }
    keys = tuple(spec.key for spec in ADAPTER.entities(FakeContext(profile)))
    assert keys == ("light", "natural_light", "night_mode")


def test_no_profile_yields_no_entities() -> None:
    assert ADAPTER.entities(FakeContext(None)) == ()
