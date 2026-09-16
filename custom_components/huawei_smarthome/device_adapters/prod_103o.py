"""User-contributed protocol for Huawei product 103O (欧普香薰助眠灯).

设备类型: 智能照明 (lamp), 型号 OPXXD
制造商: 欧普照明 (OPPLE)

核心服务:
   switch.on                  bool RW  总开关 (0=关, 1=开)
   aroma.lightSwtich          bool RW  灯光开关 (0=关, 1=开)
   aroma.aromaSwtich          bool RW  香薰开关 (0=关, 1=开)
   aroma.lightMode            int  RW  灯光模式 0-10
   aroma.aromaMode            int  RW  香薰模式 (0=无效,1=60分钟,2=180模式,3=360模式,4=永久)
   brightness.brightness      int  RW  亮度
   colour.red/green/blue      int  RW  RGB 颜色
   faultDetection.code        string R  故障代码(1=低电量,2=缺水,3=风扇警告)

本适配器暴露:
   1.  switch        总开关
   2.  switch        灯光
   3.  switch        香薰
   4.  select        灯光模式
   5.  select        香薰模式
   6.  number        亮度
   7.  sensor        故障告警
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


# ---- 枚举映射 ------------------------------------------------------------

_LIGHT_MODE_OPTIONS = [
    "自定义模式", "会客模式", "休闲模式", "观影模式", "用餐模式",
    "变幻模式", "浪漫模式", "工作模式", "睡眠模式", "阅读模式", "清扫模式",
]
_LIGHT_MODE_VALUES = list(range(11))
_LIGHT_MODE_NAME_TO_VAL = dict(zip(_LIGHT_MODE_OPTIONS, _LIGHT_MODE_VALUES))
_LIGHT_MODE_VAL_TO_NAME = dict(zip(_LIGHT_MODE_VALUES, _LIGHT_MODE_OPTIONS))

_AROMA_MODE_OPTIONS = ["无效值", "60分钟", "180模式", "360模式", "永久"]
_AROMA_MODE_VALUES = [0, 1, 2, 3, 4]
_AROMA_MODE_NAME_TO_VAL = dict(zip(_AROMA_MODE_OPTIONS, _AROMA_MODE_VALUES))
_AROMA_MODE_VAL_TO_NAME = dict(zip(_AROMA_MODE_VALUES, _AROMA_MODE_OPTIONS))

_FAULT_TEXT = {
    "1": "低电量提醒",
    "2": "缺水警告",
    "3": "风扇警告",
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


# ---- 动作工厂 ------------------------------------------------------------

def _make_bool_action(service_id: str, char_name: str):
    async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(service_id, {char_name: 1})

    async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(service_id, {char_name: 0})

    return {"turn_on": _turn_on, "turn_off": _turn_off}


def _make_bool_state(service_id: str, char_name: str):
    def _state(device: DeviceContext) -> Mapping[str, Any]:
        return {"is_on": _as_bool(device.value(service_id, char_name))}
    return _state


# ---- 动作函数 ------------------------------------------------------------

async def _select_light_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _LIGHT_MODE_NAME_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported light mode: {data.get('option')}")
    await context.async_send_service("aroma", {"lightMode": val})


async def _select_aroma_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _AROMA_MODE_NAME_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported aroma mode: {data.get('option')}")
    await context.async_send_service("aroma", {"aromaMode": val})


async def _set_brightness(context: DeviceContext, data: Mapping[str, Any]) -> None:
    value = _as_int(data.get("value"))
    if value is None:
        return
    value = max(1, min(100, value))
    await context.async_send_service("brightness", {"brightness": value})


# ---- 适配器 --------------------------------------------------------------

class Product103OAdapter:
    """103O 欧普香薰助眠灯适配器。"""

    prod_id = "103O"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        # ---- 状态读取 ----------------------------------------------------

        def power_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value("switch", "on"))}

        def brightness_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _as_int(device.value("brightness", "brightness"))}

        def light_mode_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("aroma", "lightMode"))
            return {
                "current_option": _LIGHT_MODE_VAL_TO_NAME.get(
                    val, _LIGHT_MODE_OPTIONS[0]
                )
            }

        def aroma_mode_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("aroma", "aromaMode"))
            return {
                "current_option": _AROMA_MODE_VAL_TO_NAME.get(
                    val, _AROMA_MODE_OPTIONS[0]
                )
            }

        def fault_state(device: DeviceContext) -> Mapping[str, Any]:
            code = device.value("faultDetection", "code")
            if code is None:
                return {"native_value": None}
            code_s = str(code)
            return {"native_value": _FAULT_TEXT.get(code_s, f"未知({code_s})")}

        # ---- 实体列表 ----------------------------------------------------

        return (
            EntitySpec(
                platform="switch",
                key="power",
                name="总开关",
                state=power_state,
                actions={
                    "turn_on": lambda ctx, _: ctx.async_send_service("switch", {"on": 1}),
                    "turn_off": lambda ctx, _: ctx.async_send_service("switch", {"on": 0}),
                },
            ),
            EntitySpec(
                platform="switch",
                key="light_switch",
                name="灯光",
                state=_make_bool_state("aroma", "lightSwtich"),
                actions=_make_bool_action("aroma", "lightSwtich"),
                metadata={"icon": "mdi:lightbulb"},
            ),
            EntitySpec(
                platform="switch",
                key="aroma_switch",
                name="香薰",
                state=_make_bool_state("aroma", "aromaSwtich"),
                actions=_make_bool_action("aroma", "aromaSwtich"),
                metadata={"icon": "mdi:spray"},
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
                platform="select",
                key="aroma_mode",
                name="香薰模式",
                state=aroma_mode_state,
                metadata={"options": _AROMA_MODE_OPTIONS},
                actions={"select_option": _select_aroma_mode},
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
                platform="sensor",
                key="fault",
                name="故障告警",
                state=fault_state,
                metadata={"icon": "mdi:alert-circle-outline"},
            ),
        )


ADAPTER = Product103OAdapter()