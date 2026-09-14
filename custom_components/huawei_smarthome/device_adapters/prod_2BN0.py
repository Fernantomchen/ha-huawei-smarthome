"""User-contributed protocol for Huawei product 2BN0 (领普三键单火开关MESH).

设备类型: 智能开关 (Q4S-BLE-W3(HW))
本适配器暴露:
   1. switch 总开关 (switch.on)
   2. switch ×3 按键开关 (switch1~switch3.on)
   3. select ×3 按键模式 (开关模式/联动模式)

说明: button1~button3.num 为场景联动编号（1~16），依赖华为场景系统，暂不暴露。
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


class Product2BN0Adapter:
    """Keep all 2BN0 entity and command choices in this file."""

    prod_id = "2BN0"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None or not context.has_service("switch"):
            return ()

        entities: list[EntitySpec] = []

        switch_services: tuple[tuple[str, str], ...] = (
            ("switch", "总开关"),
            ("switch1", "按键1"),
            ("switch2", "按键2"),
            ("switch3", "按键3"),
        )
        for sid, name in switch_services:
            if not context.has_service(sid):
                continue

            def switch_state(
                device: DeviceContext, _sid: str = sid
            ) -> Mapping[str, Any]:
                return {"is_on": _bool(device.value(_sid, "on")) is True}

            async def turn(
                device: DeviceContext,
                data: Mapping[str, Any],
                _sid: str = sid,
            ) -> None:
                await device.async_send_service(_sid, {"on": 1 if data else 0})

            entities.append(
                EntitySpec(
                    platform="switch",
                    key=f"sw_{sid}",
                    name=name,
                    state=switch_state,
                    actions={
                        "turn_on": lambda d, _data, _s=sid: turn(d, {"on": 1}, _s),
                        "turn_off": lambda d, _data, _s=sid: turn(d, {}, _s),
                    },
                )
            )

        for key_num in ("1", "2", "3"):
            mode_sid = f"mode{key_num}"
            if not context.has_service(mode_sid):
                continue

            def mode_state(
                device: DeviceContext, _sid: str = mode_sid
            ) -> Mapping[str, Any]:
                value = _number(device.value(_sid, "mode"))
                for label, raw in _KEY_MODE_VALUES.items():
                    if value == raw:
                        return {"current_option": label}
                return {"current_option": None}

            async def set_mode(
                device: DeviceContext,
                data: Mapping[str, Any],
                _sid: str = mode_sid,
            ) -> None:
                option = str(data.get("option"))
                if option not in _KEY_MODE_VALUES:
                    raise ValueError(f"unknown key mode: {option}")
                await device.async_send_service(
                    _sid, {"mode": _KEY_MODE_VALUES[option]}
                )

            entities.append(
                EntitySpec(
                    platform="select",
                    key=f"mode_{key_num}",
                    name=f"按键{key_num}模式",
                    state=mode_state,
                    metadata={"options": _KEY_MODE_OPTIONS},
                    actions={"select_option": set_mode},
                )
            )
        return tuple(entities)


ADAPTER = Product2BN0Adapter()
