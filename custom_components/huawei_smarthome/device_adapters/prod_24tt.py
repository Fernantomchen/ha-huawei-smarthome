"""User-contributed protocol for Huawei product 24TT (欧普Balance读写台灯).

设备类型: 智能台灯 (Table Lamp), 型号 MT001-13.5SF
制造商: 欧普照明 (opple)

核心服务:
   switch.on                    bool RW  开关 (1=开, 0=关)
   brightness.brightness        int  RW  亮度 1-100
   cct.colorTemperature         int  RW  色温 3000-5000
   colourMode.mode              enum R   颜色模式(0=彩光,1=冷暖光,4=设备预置模式)
   lightMode.mode               enum RW  灯光模式
   tomatoClk.enable             bool RW  番茄钟开关
   tomatoClk.status             enum R   番茄钟状态(0=工作中,1=休息中)
   tomatoClk.num                int  RW  番茄钟循环次数 1-6
   nightWakeup.enable           bool RW  夜间唤醒开关
   rhythm.rhythm                bool RW  节律光开关
   delayclose.delayclose        bool RW  延时关闭开关

本适配器暴露:
   1.  switch        开关
   2.  number        亮度
   3.  number        色温
   4.  sensor        颜色模式
   5.  select        灯光模式
   6.  switch        番茄钟
   7.  sensor        番茄钟状态
   8.  number        番茄钟循环次数
   9.  switch        夜间唤醒
   10. switch        节律光
   11. switch        延时关闭
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


# ---- 枚举映射 ------------------------------------------------------------

_LIGHT_MODE_OPTIONS = [
    "专注模式", "放松模式", "最爱模式", "夜灯模式", "阅读模式", "智能感光模式",
]
_LIGHT_MODE_VALUES = [6, 1, 3, 4, 8, 10]
_MODE_NAME_TO_VAL = dict(zip(_LIGHT_MODE_OPTIONS, _LIGHT_MODE_VALUES))
_MODE_VAL_TO_NAME = dict(zip(_LIGHT_MODE_VALUES, _LIGHT_MODE_OPTIONS))

_COLOUR_MODE_TEXT = {
    0: "彩光",
    1: "冷暖光",
    4: "设备预置模式",
}

_TOMATO_STATUS_TEXT = {
    0: "工作中",
    1: "休息中",
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
    value = max(3000, min(5000, value))
    await context.async_send_service("cct", {"colorTemperature": value})


async def _select_light_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _MODE_NAME_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported light mode: {data.get('option')}")
    await context.async_send_service("lightMode", {"mode": val})


async def _set_tomato_enable(context: DeviceContext, data: Mapping[str, Any]) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service(
        "tomatoClk", {"enable": 1 if is_on else 0}
    )


async def _set_tomato_num(context: DeviceContext, data: Mapping[str, Any]) -> None:
    value = _as_int(data.get("value"))
    if value is None:
        return
    value = max(1, min(6, value))
    await context.async_send_service("tomatoClk", {"num": value})


async def _set_night_wakeup(context: DeviceContext, data: Mapping[str, Any]) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service(
        "nightWakeup", {"enable": 1 if is_on else 0}
    )


async def _set_rhythm(context: DeviceContext, data: Mapping[str, Any]) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service("rhythm", {"rhythm": 1 if is_on else 0})


async def _set_delayclose(context: DeviceContext, data: Mapping[str, Any]) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service(
        "delayclose", {"delayclose": 1 if is_on else 0}
    )


# ---- 适配器 --------------------------------------------------------------

class Product24TTAdapter:
    """24TT 欧普Balance读写台灯适配器。"""

    prod_id = "24TT"

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

        def colour_mode_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("colourMode", "mode"))
            return {"native_value": _COLOUR_MODE_TEXT.get(val, "未知")}

        def light_mode_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("lightMode", "mode"))
            return {
                "current_option": _MODE_VAL_TO_NAME.get(
                    val, _LIGHT_MODE_OPTIONS[0]
                )
            }

        def tomato_enable_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value("tomatoClk", "enable"))}

        def tomato_status_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("tomatoClk", "status"))
            return {"native_value": _TOMATO_STATUS_TEXT.get(val, "未知")}

        def tomato_num_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _as_int(device.value("tomatoClk", "num"))}

        def night_wakeup_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value("nightWakeup", "enable"))}

        def rhythm_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value("rhythm", "rhythm"))}

        def delayclose_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value("delayclose", "delayclose"))}

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
                metadata={"min": 3000, "max": 5000, "step": 1, "unit": "K"},
                actions={"set_value": _set_color_temp},
            ),
            EntitySpec(
                platform="sensor",
                key="colour_mode",
                name="颜色模式",
                state=colour_mode_state,
                metadata={"icon": "mdi:palette"},
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
                key="tomato_enable",
                name="番茄钟",
                state=tomato_enable_state,
                actions={
                    "turn_on": _set_tomato_enable,
                    "turn_off": _set_tomato_enable,
                },
                metadata={"icon": "mdi:timer-sand"},
            ),
            EntitySpec(
                platform="sensor",
                key="tomato_status",
                name="番茄钟状态",
                state=tomato_status_state,
                metadata={"icon": "mdi:timer-outline"},
            ),
            EntitySpec(
                platform="number",
                key="tomato_num",
                name="番茄钟循环次数",
                state=tomato_num_state,
                metadata={"min": 1, "max": 6, "step": 1},
                actions={"set_value": _set_tomato_num},
            ),
            EntitySpec(
                platform="switch",
                key="night_wakeup",
                name="夜间唤醒",
                state=night_wakeup_state,
                actions={
                    "turn_on": _set_night_wakeup,
                    "turn_off": _set_night_wakeup,
                },
                metadata={"icon": "mdi:weather-night"},
            ),
            EntitySpec(
                platform="switch",
                key="rhythm",
                name="节律光",
                state=rhythm_state,
                actions={"turn_on": _set_rhythm, "turn_off": _set_rhythm},
                metadata={"icon": "mdi:sun-clock-outline"},
            ),
            EntitySpec(
                platform="switch",
                key="delayclose",
                name="延时关闭",
                state=delayclose_state,
                actions={
                    "turn_on": _set_delayclose,
                    "turn_off": _set_delayclose,
                },
                metadata={"icon": "mdi:timer-off-outline"},
            ),
        )


ADAPTER = Product24TTAdapter()