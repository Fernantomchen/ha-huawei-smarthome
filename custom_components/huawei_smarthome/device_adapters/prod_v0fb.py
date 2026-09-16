"""User-contributed protocol for Huawei product V0FB (华为智慧屏 Vision 5).

设备类型: 智慧屏 (Intelligent Vision), 型号 NYHS-370A
制造商: 华为 (HUAWEI)

核心服务:
   devicestate.screenState    bool RGP  屏幕状态 (0=已熄屏, 1=在线, 2=离线)

其余服务均不在本适配器中映射:
   messageboard    留言(只读)
   remotecontrol   遥控认证/配对信息(只读)
   autoconfig      HMS登录校验信息(只读)
   generalcommand  通用预留透传
   logreport       Beta日志上报

本适配器暴露:
   1. sensor  屏幕状态
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


# ---- 枚举映射 ------------------------------------------------------------

_SCREEN_STATE_TEXT = {
    0: "已熄屏",
    1: "在线",
    2: "离线",
}


# ---- 工具函数 ------------------------------------------------------------

def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        try:
            return int(round(float(value.strip())))
        except (TypeError, ValueError):
            return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


# ---- 适配器 --------------------------------------------------------------

class ProductV0FBAdapter:
    """V0FB 华为智慧屏 Vision 5 适配器。"""

    prod_id = "V0FB"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("devicestate"):
            return ()

        # ---- 状态读取 ----------------------------------------------------

        def screen_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("devicestate", "screenState"))
            return {"native_value": _SCREEN_STATE_TEXT.get(val, "未知")}

        # ---- 实体列表 ----------------------------------------------------

        return (
            EntitySpec(
                platform="sensor",
                key="screen_state",
                name="屏幕状态",
                state=screen_state,
                metadata={"icon": "mdi:monitor"},
            ),
        )


ADAPTER = ProductV0FBAdapter()