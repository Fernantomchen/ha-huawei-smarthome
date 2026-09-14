"""User-contributed protocol for Huawei product 2BE7 (麦乐克水浸传感器).

设备类型: 水浸探测器 (MIR-WA100)
本适配器暴露:
   1. binary_sensor 水浸告警 (device_class=moisture)
   2. sensor 电池电量 (%)
   3. binary_sensor 电池低电量
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


def _empty_state(_device: DeviceContext) -> Mapping[str, Any]:
    return {}


class Product2BE7Adapter:
    """Keep all 2BE7 entity and command choices in this file."""

    prod_id = "2BE7"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("alarm"):
            return ()

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="binary_sensor",
                key="water_leak",
                name="水浸告警",
                state=lambda device: {"is_on": _number(device.value("alarm", "alarm")) == 1},
                metadata={"device_class": "moisture"},
            ),
        ]

        if context.has_service("battery"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="battery_level",
                    name="电池电量",
                    state=lambda device: {
                        "native_value": _number(device.value("battery", "level"))
                    },
                    metadata={"unit_of_measurement": "%"},
                )
            )
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="battery_low",
                    name="电池低电量",
                    state=lambda device: {
                        "is_on": _bool(device.value("battery", "alarm")) is True
                    },
                )
            )
        return tuple(entities)


ADAPTER = Product2BE7Adapter()
