"""User-contributed protocol for Huawei product 20L5 (亚摩斯养生壶 YSH1258).

设备类型: 养生壶
本适配器暴露:
   1. switch 工作开关 (switch.on)
   2. select 烹煮模式 (mode.mode，21 档)
   3. select 目标功率 (targetPower.targetPower，100W~800W)
   4. number 目标温度 (targetTemp.targetTemp，40~90℃)
   5. sensor 工作状态 / 当前温度 / 剩余时间(分钟)
   6. binary_sensor 故障告警

说明: presetSwitch/preTimeStart（预约）与 faultDetection.code 暂只暴露核心项。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_MODE_OPTIONS = (
    "烧水", "参茶", "水果茶", "灵芝", "五谷粥", "银耳羹", "保温",
    "茉莉花茶", "枸杞菊花茶", "玫瑰花茶", "绿茶", "普洱茶", "柠檬茶",
    "冰糖雪梨汤", "桂圆莲子汤", "西洋参乌鸡汤", "养生粥", "红糖姜茶",
    "酸奶", "火锅",
)
_MODE_VALUES = {
    "烧水": 1, "参茶": 2, "水果茶": 11, "灵芝": 13, "五谷粥": 21,
    "银耳羹": 31, "保温": 32, "茉莉花茶": 100, "枸杞菊花茶": 101,
    "玫瑰花茶": 102, "绿茶": 103, "普洱茶": 104, "柠檬茶": 105,
    "冰糖雪梨汤": 106, "桂圆莲子汤": 107, "西洋参乌鸡汤": 108,
    "养生粥": 109, "红糖姜茶": 110, "酸奶": 111, "火锅": 112,
}
_POWER_OPTIONS = ("100W", "200W", "300W", "400W", "500W", "600W", "700W", "800W")
_STATUS_VALUES = {
    0: "待机", 1: "预约", 2: "升温中", 3: "制作中", 4: "保温中", 6: "完成",
}


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.casefold() in {"1", "true", "on"}:
            return True
        if value.casefold() in {"0", "false", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


class Product20L5Adapter:
    """Keep all 20L5 entity and command choices in this file."""

    prod_id = "20L5"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="switch",
                key="power",
                name="工作开关",
                state=lambda device: {
                    "is_on": _bool(device.value("switch", "on")) is True
                },
                actions={
                    "turn_on": lambda d, _data: d.async_send_service("switch", {"on": 1}),
                    "turn_off": lambda d, _data: d.async_send_service("switch", {"on": 0}),
                },
            )
        ]

        if context.has_service("mode"):
            async def set_mode(device: DeviceContext, data: Mapping[str, Any]) -> None:
                option = str(data.get("option"))
                if option not in _MODE_VALUES:
                    raise ValueError(f"unknown kettle mode: {option}")
                await device.async_send_service("mode", {"mode": _MODE_VALUES[option]})

            entities.append(
                EntitySpec(
                    platform="select",
                    key="mode",
                    name="烹煮模式",
                    state=lambda device: {
                        "current_option": next(
                            (
                                label
                                for label, raw in _MODE_VALUES.items()
                                if _number(device.value("mode", "mode")) == raw
                            ),
                            None,
                        )
                    },
                    metadata={"options": _MODE_OPTIONS},
                    actions={"select_option": set_mode},
                )
            )

        if context.has_service("targetPower"):
            async def set_power(device: DeviceContext, data: Mapping[str, Any]) -> None:
                option = str(data.get("option"))
                if option not in _POWER_OPTIONS:
                    raise ValueError(f"unknown target power: {option}")
                await device.async_send_service(
                    "targetPower", {"targetPower": _POWER_OPTIONS.index(option)}
                )

            entities.append(
                EntitySpec(
                    platform="select",
                    key="target_power",
                    name="目标功率",
                    state=lambda device: {
                        "current_option": next(
                            (
                                label
                                for label, raw in enumerate(_POWER_OPTIONS)
                                if _number(device.value("targetPower", "targetPower")) == raw
                            ),
                            None,
                        )
                    },
                    metadata={"options": _POWER_OPTIONS},
                    actions={"select_option": set_power},
                )
            )

        if context.has_service("targetTemp"):
            async def set_target_temp(
                device: DeviceContext, data: Mapping[str, Any]
            ) -> None:
                value = _number(data.get("value"))
                if value is None:
                    raise ValueError("target temperature value is required")
                value = min(max(int(value), 40), 90)
                await device.async_send_service("targetTemp", {"targetTemp": value})

            entities.append(
                EntitySpec(
                    platform="number",
                    key="target_temp",
                    name="目标温度",
                    state=lambda device: {
                        "native_value": _number(device.value("targetTemp", "targetTemp"))
                    },
                    metadata={"min": 40, "max": 90, "step": 5, "unit": "℃"},
                    actions={"set_value": set_target_temp},
                )
            )

        if context.has_service("status"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="work_status",
                    name="工作状态",
                    state=lambda device: {
                        "native_value": _STATUS_VALUES.get(
                            _number(device.value("status", "status"))
                        )
                    },
                )
            )
        if context.has_service("temperature"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="current_temp",
                    name="当前温度",
                    state=lambda device: {
                        "native_value": _number(device.value("temperature", "current"))
                    },
                    metadata={"unit_of_measurement": "℃"},
                )
            )
        if context.has_service("leftTime"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="left_time",
                    name="剩余时间",
                    state=lambda device: {
                        "native_value": _number(device.value("leftTime", "time"))
                    },
                    metadata={"unit_of_measurement": "min"},
                )
            )
        if context.has_service("faultDetection"):
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="fault",
                    name="故障告警",
                    state=lambda device: {
                        "is_on": _bool(device.value("faultDetection", "status")) is True
                    },
                )
            )
        return tuple(entities)


ADAPTER = Product20L5Adapter()
