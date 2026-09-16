"""User-contributed protocol for Huawei product 105M (欧瑞博智能插座 S30c).

设备类型: 智能插座 (Socket), 型号 S30c
制造商: 欧瑞博 (ORVIBO)

核心服务:
   switch.on    bool RW  电源开关 (0=关, 1=开)

其余服务均不在本适配器中映射:
   timer / delay   云端定时与倒计时(对象数组结构复杂, UI 由云侧管理)
   timerID         定时与场景关联 ID
   update          OTA 升级

本适配器暴露:
   1. switch  电源
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


# ---- 动作函数 ------------------------------------------------------------

async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("switch", {"on": 1})


async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("switch", {"on": 0})


# ---- 适配器 --------------------------------------------------------------

class Product105MAdapter:
    """105M 欧瑞博智能插座 S30c 适配器。"""

    prod_id = "105M"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        def power_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value("switch", "on"))}

        return (
            EntitySpec(
                platform="switch",
                key="power",
                name="电源",
                state=power_state,
                actions={"turn_on": _turn_on, "turn_off": _turn_off},
            ),
        )


ADAPTER = Product105MAdapter()