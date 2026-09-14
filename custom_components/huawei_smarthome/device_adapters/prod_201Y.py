"""User-contributed protocol for Huawei product 201Y (领普双键无线开关MESH).

设备类型: 场景面板 / 无线开关 (K9BB(HW))
本适配器暴露:
   1. sensor 电池电量 (%)
   2. binary_sensor 电池低电量

说明: 按键触发为场景事件（scene.num 上报 1~8 按键编号），需要事件通道支持，
当前适配器框架的事件接口未在本适配器中使用，故暂不暴露按键实体。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


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


class Product201YAdapter:
    """Keep all 201Y entity and command choices in this file."""

    prod_id = "201Y"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("battery"):
            return ()

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="sensor",
                key="battery_level",
                name="电池电量",
                state=lambda device: {
                    "native_value": _number(device.value("battery", "level"))
                },
                metadata={"unit_of_measurement": "%"},
            ),
            EntitySpec(
                platform="binary_sensor",
                key="battery_low",
                name="电池低电量",
                state=lambda device: {
                    "is_on": _bool(device.value("battery", "alarm")) is True
                },
            ),
        ]
        return tuple(entities)


ADAPTER = Product201YAdapter()
