"""User-contributed protocol for Huawei product A0NT (智能双通道插座).

设备类型: 智能插排 (MultiSocket), 型号 Smart socket
制造商: 酷宅科技 (CoolKit)

核心服务:
   switch.switch     bool   RW  总开关 (1=开, 0=关)
   switch1.on        bool   RW  插口1 开关 (1=开, 0=关)
   switch1.name      string RW  插口1 名称 (最长 16 字符)
   switch2.on        bool   RW  插口2 开关 (1=开, 0=关)
   switch2.name      string RW  插口2 名称 (最长 16 字符)

本适配器暴露:
   1. switch  总开关
   2. switch  插口1
   3. switch  插口2
   4. sensor  插口1 名称
   5. sensor  插口2 名称
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


# ---- 工具函数 ------------------------------------------------------------

def _as_bool(value: Any) -> bool | None:
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


# ---- 动作工厂 ------------------------------------------------------------

def _make_switch_action(service_id: str):
    async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(service_id, {"on": 1})

    async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(service_id, {"on": 0})

    return {"turn_on": _turn_on, "turn_off": _turn_off}


def _make_switch_state(service_id: str):
    def _state(device: DeviceContext) -> Mapping[str, Any]:
        return {"is_on": _as_bool(device.value(service_id, "on"))}
    return _state


def _make_name_state(service_id: str):
    def _state(device: DeviceContext) -> Mapping[str, Any]:
        val = device.value(service_id, "name")
        return {"native_value": str(val) if val not in (None, "") else None}
    return _state


# ---- 适配器 --------------------------------------------------------------

class ProductA0NTAdapter:
    """A0NT 智能双通道插座适配器。"""

    prod_id = "A0NT"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="switch",
                key="power",
                name="总开关",
                state=_make_switch_state("switch"),
                actions=_make_switch_action("switch"),
            ),
        ]

        # 通道 1 与通道 2
        for idx, sid in ((1, "switch1"), (2, "switch2")):
            if not context.has_service(sid):
                continue
            entities.append(
                EntitySpec(
                    platform="switch",
                    key=f"channel{idx}",
                    name=f"插口{idx}",
                    state=_make_switch_state(sid),
                    actions=_make_switch_action(sid),
                )
            )
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key=f"channel{idx}_name",
                    name=f"插口{idx} 名称",
                    state=_make_name_state(sid),
                    metadata={"icon": "mdi:tag-text"},
                )
            )

        return tuple(entities)


ADAPTER = ProductA0NTAdapter()