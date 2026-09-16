"""User-contributed protocol for Huawei product 2NX2 (智能色温吸顶灯).

设备类型: 吸顶灯 (Ceiling Lamp), 型号 XD-396
制造商: 深圳大于智能有限公司 (DAYU)

核心服务:
   switch.on                     bool RW  开关 (1=开, 0=关)
   lightMode.mode                enum RW  灯光模式
   brightness.brightness         int  RW  亮度 1-100 (%)
   cct.colorTemperature          int  RW  色温 3000-6400 (K)
   commonMemorySwitch.status     enum RW  断电记忆 (0=关,1=开,2=保持上次状态)
   cleverSwitch.cleverSwitch     bool RW  凌动开关 (1=开, 0=关)
   Togglecct.Togglecct           bool RW  色温翻转 (1=开, 0=关)
   ChangeTime.ChangeTime         enum RW  渐变时间 (0=关闭,1=快,2=正常,3=慢)

本适配器暴露:
   1.  switch        开关
   2.  number        亮度
   3.  number        色温
   4.  select        灯光模式
   5.  switch        凌动开关
   6.  switch        色温翻转
   7.  select        断电记忆
   8.  select        渐变时间
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


# ---- 枚举映射 ------------------------------------------------------------

_LIGHT_MODE_OPTIONS = [
    "会客模式", "休闲模式", "观影模式", "用餐模式",
    "工作模式", "睡眠模式", "阅读模式", "夜间模式", "空场景",
]
_LIGHT_MODE_VALUES = [0, 1, 2, 3, 6, 7, 8, 13, 100]
_MODE_NAME_TO_VAL = dict(zip(_LIGHT_MODE_OPTIONS, _LIGHT_MODE_VALUES))
_MODE_VAL_TO_NAME = dict(zip(_LIGHT_MODE_VALUES, _LIGHT_MODE_OPTIONS))

_MEMORY_OPTIONS = ["关", "开", "保持上次状态"]
_MEMORY_VALUES = [0, 1, 2]
_MEMORY_NAME_TO_VAL = dict(zip(_MEMORY_OPTIONS, _MEMORY_VALUES))
_MEMORY_VAL_TO_NAME = dict(zip(_MEMORY_VALUES, _MEMORY_OPTIONS))

_CHANGE_TIME_OPTIONS = ["关闭", "快", "正常", "慢"]
_CHANGE_TIME_VALUES = [0, 1, 2, 3]
_CHANGE_TIME_NAME_TO_VAL = dict(zip(_CHANGE_TIME_OPTIONS, _CHANGE_TIME_VALUES))
_CHANGE_TIME_VAL_TO_NAME = dict(zip(_CHANGE_TIME_VALUES, _CHANGE_TIME_OPTIONS))


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


async def _set_brightness(context: DeviceContext, data: Mapping[str, Any]) -> None:
    value = _as_int(data.get("value"))
    if value is None:
        return
    value = max(1, min(100, value))
    await context.async_send_service("brightness", {"brightness": value})


async def _set_color_temp(context: DeviceContext, data: Mapping[str, Any]) -> None:
    value = _as_int(data.get("value"))
    if value is None:
        return
    value = max(3000, min(6400, value))
    await context.async_send_service("cct", {"colorTemperature": value})


async def _select_light_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _MODE_NAME_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported light mode: {data.get('option')}")
    await context.async_send_service("lightMode", {"mode": val})


async def _set_clever_switch(context: DeviceContext, data: Mapping[str, Any]) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service(
        "cleverSwitch", {"cleverSwitch": 1 if is_on else 0}
    )


async def _set_toggle_cct(context: DeviceContext, data: Mapping[str, Any]) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service("Togglecct", {"Togglecct": 1 if is_on else 0})


async def _select_memory(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _MEMORY_NAME_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported memory option: {data.get('option')}")
    await context.async_send_service("commonMemorySwitch", {"status": val})


async def _select_change_time(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _CHANGE_TIME_NAME_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported change time: {data.get('option')}")
    await context.async_send_service("ChangeTime", {"ChangeTime": val})


# ---- 适配器 --------------------------------------------------------------

class Product2NX2Adapter:
    """2NX2 智能色温吸顶灯适配器。"""

    prod_id = "2NX2"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        # ---- 状态读取 ----------------------------------------------------

        def power_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value("switch", "on"))}

        def brightness_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _as_int(device.value("brightness", "brightness"))}

        def color_temp_state(device: DeviceContext) -> Mapping[str, Any]:
            return {
                "native_value": _as_int(device.value("cct", "colorTemperature"))
            }

        def light_mode_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("lightMode", "mode"))
            return {
                "current_option": _MODE_VAL_TO_NAME.get(val, _LIGHT_MODE_OPTIONS[0])
            }

        def clever_switch_state(device: DeviceContext) -> Mapping[str, Any]:
            return {
                "is_on": _as_bool(device.value("cleverSwitch", "cleverSwitch"))
            }

        def toggle_cct_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value("Togglecct", "Togglecct"))}

        def memory_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("commonMemorySwitch", "status"))
            return {
                "current_option": _MEMORY_VAL_TO_NAME.get(val, _MEMORY_OPTIONS[0])
            }

        def change_time_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("ChangeTime", "ChangeTime"))
            return {
                "current_option": _CHANGE_TIME_VAL_TO_NAME.get(
                    val, _CHANGE_TIME_OPTIONS[0]
                )
            }

        # ---- 实体列表 ----------------------------------------------------

        return (
            EntitySpec(
                platform="switch",
                key="power",
                name="开关",
                state=power_state,
                actions={"turn_on": _turn_on, "turn_off": _turn_off},
            ),
            EntitySpec(
                platform="number",
                key="brightness",
                name="亮度",
                state=brightness_state,
                metadata={"min": 1, "max": 100, "step": 1, "unit": "%"},
                actions={"set_value": _set_brightness},
            ),
            EntitySpec(
                platform="number",
                key="color_temp",
                name="色温",
                state=color_temp_state,
                metadata={"min": 3000, "max": 6400, "step": 1, "unit": "K"},
                actions={"set_value": _set_color_temp},
            ),
            EntitySpec(
                platform="select",
                key="light_mode",
                name="灯光模式",
                state=light_mode_state,
                metadata={"options": _LIGHT_MODE_OPTIONS},
                actions={"select_option": _select_light_mode},
            ),
            EntitySpec(
                platform="switch",
                key="clever_switch",
                name="凌动开关",
                state=clever_switch_state,
                actions={"turn_on": _set_clever_switch, "turn_off": _set_clever_switch},
            ),
            EntitySpec(
                platform="switch",
                key="toggle_cct",
                name="色温翻转",
                state=toggle_cct_state,
                actions={"turn_on": _set_toggle_cct, "turn_off": _set_toggle_cct},
            ),
            EntitySpec(
                platform="select",
                key="memory",
                name="断电记忆",
                state=memory_state,
                metadata={"options": _MEMORY_OPTIONS},
                actions={"select_option": _select_memory},
            ),
            EntitySpec(
                platform="select",
                key="change_time",
                name="渐变时间",
                state=change_time_state,
                metadata={"options": _CHANGE_TIME_OPTIONS},
                actions={"select_option": _select_change_time},
            ),
        )


ADAPTER = Product2NX2Adapter()