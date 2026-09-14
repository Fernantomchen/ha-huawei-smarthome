"""User-contributed protocol for Huawei product 2CUS (麦乐克紧急按钮传感器).

设备类型: 紧急按钮 (MIR-SO100)
本适配器暴露:
   1. binary_sensor 紧急按钮按下
   2. sensor 电池电量 (%)
   3. binary_sensor 电池低电量

说明: 按钮按压为瞬时事件，binary_sensor 反映的是最近一次上报的按下状态。
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


class Product2CUSAdapter:
    """Keep all 2CUS entity and command choices in this file."""

    prod_id = "2CUS"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("pushButton"):
            return ()

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="binary_sensor",
                key="pressed",
                name="紧急按钮按下",
                state=lambda device: {
                    "is_on": _number(device.value("pushButton", "on")) == 1
                },
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


ADAPTER = Product2CUSAdapter()
