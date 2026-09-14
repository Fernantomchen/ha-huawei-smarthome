"""User-contributed protocol for Huawei product 2ANZ (领普单键单火开关MESH).

设备类型: 智能开关 (Q4S-BLE-W1(HW))
本适配器暴露:
   1. switch 开关 (switch.on)
   2. select 按键模式 (mode1.mode: 开关模式/联动模式)

说明: button1.num 为场景联动编号（1~16），依赖华为场景系统，暂不暴露。
与 2BN0（三键版）同系列；本文件覆盖单键版产品 ID 2ANZ。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_KEY_MODE_OPTIONS = ("开关模式", "联动模式")
_KEY_MODE_VALUES = {"开关模式": 1, "联动模式": 2}


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


class Product2ANZAdapter:
    """Keep all 2ANZ entity and command choices in this file."""

    prod_id = "2ANZ"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None or not context.has_service("switch"):
            return ()

        entities: list[EntitySpec] = []

        def switch_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _bool(device.value("switch", "on")) is True}

        async def turn_on(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("switch", {"on": 1})

        async def turn_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("switch", {"on": 0})

        entities.append(
            EntitySpec(
                platform="switch",
                key="sw_switch",
                name="开关",
                state=switch_state,
                actions={"turn_on": turn_on, "turn_off": turn_off},
            )
        )

        if context.has_service("mode1"):

            def mode_state(device: DeviceContext) -> Mapping[str, Any]:
                value = _number(device.value("mode1", "mode"))
                for label, raw in _KEY_MODE_VALUES.items():
                    if value == raw:
                        return {"current_option": label}
                return {"current_option": None}

            async def set_mode(
                device: DeviceContext, data: Mapping[str, Any]
            ) -> None:
                option = str(data.get("option"))
                if option not in _KEY_MODE_VALUES:
                    raise ValueError(f"unknown key mode: {option}")
                await device.async_send_service(
                    "mode1", {"mode": _KEY_MODE_VALUES[option]}
                )

            entities.append(
                EntitySpec(
                    platform="select",
                    key="mode_1",
                    name="按键模式",
                    state=mode_state,
                    metadata={"options": _KEY_MODE_OPTIONS},
                    actions={"select_option": set_mode},
                )
            )
        return tuple(entities)


ADAPTER = Product2ANZAdapter()
