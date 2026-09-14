"""User-contributed protocol for Huawei product 20KM (鸿雁WIFI智能排插).

设备类型: 智能插排 (IHC8345A)，总开关 + 4 分路 + 童锁
本适配器暴露:
   1. switch 总开关
   2. switch ×4 分路开关 (switch1~switch4)
   3. switch 童锁开关 (switchLock)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


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


class Product20KMAdapter:
    """Keep all 20KM entity and command choices in this file."""

    prod_id = "20KM"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        entities: list[EntitySpec] = []

        switch_services: tuple[tuple[str, str], ...] = (
            ("switch", "总开关"),
            ("switch1", "插孔1"),
            ("switch2", "插孔2"),
            ("switch3", "插孔3"),
            ("switch4", "插孔4"),
            ("switchLock", "童锁开关"),
        )
        for sid, name in switch_services:
            if not context.has_service(sid):
                continue

            def switch_state(
                device: DeviceContext, _sid: str = sid
            ) -> Mapping[str, Any]:
                return {"is_on": _bool(device.value(_sid, "on")) is True}

            async def turn_on(
                device: DeviceContext, _data: Mapping[str, Any], _sid: str = sid
            ) -> None:
                await device.async_send_service(_sid, {"on": 1})

            async def turn_off(
                device: DeviceContext, _data: Mapping[str, Any], _sid: str = sid
            ) -> None:
                await device.async_send_service(_sid, {"on": 0})

            entities.append(
                EntitySpec(
                    platform="switch",
                    key=f"sw_{sid}",
                    name=name,
                    state=switch_state,
                    actions={"turn_on": turn_on, "turn_off": turn_off},
                )
            )
        return tuple(entities)


ADAPTER = Product20KMAdapter()
