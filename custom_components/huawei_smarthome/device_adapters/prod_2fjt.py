"""User-contributed protocol for Huawei product 2FJT (SKG 按摩腰带 Hi-W7).

设备类型: 按摩器 (Massager), 型号 S0409AA
制造商: 深圳未来健康医疗有限公司

核心服务:
   switch.switch                  bool RW  电源开关 (1=开, 0=关)
   collection.collection          int  RW  收藏设定 0-10
   SceneMode.SceneMode            enum RW  场景模式 (0=久坐舒缓, 1=居家放松, 2=酸痛缓解)
   customMode.CustomMode          enum RW  自定义模式 (0=按压, 1=拍打, 2=揉捏, 3=锻炼)
   EmsLevel.MasgLevel             int  RW  按摩力度 0-9
   BattPower.batteryPower         int  R   电池电量 0-100
   HeatLevel.HeatLevel            enum RW  热敷 (0=关闭, 1=低温, 2=中温, 3=高温)
   MasgTimer.MassageTimer         int  RW  按摩时间 5-25 step=5
   massageKeyLock.MassageKeyLock  int  RW  按摩键锁定 0/1

本适配器暴露:
   1. switch       电源
   2. switch       按摩键锁定
   3. select       场景模式
   4. select       自定义模式
   5. select       热敷
   6. number       按摩力度
   7. number       按摩时间
   8. number       收藏设定
   9. sensor       电池电量
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

# ---- 枚举映射 ------------------------------------------------------------

_SCENE_MODE_OPTIONS = ["久坐舒缓", "居家放松", "酸痛缓解"]
_SCENE_MODE_TO_VAL = {name: i for i, name in enumerate(_SCENE_MODE_OPTIONS)}

_CUSTOM_MODE_OPTIONS = ["按压", "拍打", "揉捏", "锻炼"]
_CUSTOM_MODE_TO_VAL = {name: i for i, name in enumerate(_CUSTOM_MODE_OPTIONS)}

_HEAT_LEVEL_OPTIONS = ["关闭", "低温", "中温", "高温"]
_HEAT_LEVEL_TO_VAL = {name: i for i, name in enumerate(_HEAT_LEVEL_OPTIONS)}

# ---- 工具函数 ------------------------------------------------------------

def _as_int(value: Any) -> int | None:
    """容忍 int / 数字字符串 / bool。"""
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

async def _set_power(context: DeviceContext, data: Mapping[str, Any]) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service("switch", {"on": 1 if is_on else 0})


async def _set_key_lock(context: DeviceContext, data: Mapping[str, Any]) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service(
        "massageKeyLock", {"MassageKeyLock": 1 if is_on else 0}
    )


async def _select_scene_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _SCENE_MODE_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported scene mode: {data.get('option')}")
    await context.async_send_service("SceneMode", {"SceneMode": val})


async def _select_custom_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _CUSTOM_MODE_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported custom mode: {data.get('option')}")
    await context.async_send_service("customMode", {"CustomMode": val})


async def _select_heat_level(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _HEAT_LEVEL_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported heat level: {data.get('option')}")
    await context.async_send_service("HeatLevel", {"HeatLevel": val})


async def _set_ems_level(context: DeviceContext, data: Mapping[str, Any]) -> None:
    value = _as_int(data.get("value"))
    if value is None:
        return
    value = max(0, min(9, value))
    await context.async_send_service("EmsLevel", {"MasgLevel": value})


async def _set_timer(context: DeviceContext, data: Mapping[str, Any]) -> None:
    value = _as_int(data.get("value"))
    if value is None:
        return
    # 步长 5，钳制到 5–25
    value = max(5, min(25, value))
    value = 5 * round(value / 5)
    await context.async_send_service("MasgTimer", {"MassageTimer": value})


async def _set_collection(context: DeviceContext, data: Mapping[str, Any]) -> None:
    value = _as_int(data.get("value"))
    if value is None:
        return
    value = max(0, min(10, value))
    await context.async_send_service("collection", {"collection": value})


# ---- 适配器 --------------------------------------------------------------

class Product2FJTAdapter:
    """2FJT SKG 按摩腰带适配器。"""

    prod_id = "2FJT"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        # ---- 状态读取 ----------------------------------------------------

        def power_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value("switch", "on"))}

        def key_lock_state(device: DeviceContext) -> Mapping[str, Any]:
            return {
                "is_on": _as_bool(device.value("massageKeyLock", "MassageKeyLock"))
            }

        def scene_mode_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("SceneMode", "SceneMode"))
            return {
                "current_option": _SCENE_MODE_OPTIONS[val]
                if val is not None and 0 <= val < len(_SCENE_MODE_OPTIONS)
                else _SCENE_MODE_OPTIONS[0]
            }

        def custom_mode_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("customMode", "CustomMode"))
            return {
                "current_option": _CUSTOM_MODE_OPTIONS[val]
                if val is not None and 0 <= val < len(_CUSTOM_MODE_OPTIONS)
                else _CUSTOM_MODE_OPTIONS[0]
            }

        def heat_level_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("HeatLevel", "HeatLevel"))
            return {
                "current_option": _HEAT_LEVEL_OPTIONS[val]
                if val is not None and 0 <= val < len(_HEAT_LEVEL_OPTIONS)
                else _HEAT_LEVEL_OPTIONS[0]
            }

        def ems_level_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _as_int(device.value("EmsLevel", "MasgLevel"))}

        def timer_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _as_int(device.value("MasgTimer", "MassageTimer"))}

        def collection_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _as_int(device.value("collection", "collection"))}

        def battery_state(device: DeviceContext) -> Mapping[str, Any]:
            return {
                "native_value": _as_int(device.value("BattPower", "batteryPower"))
            }

        # ---- 实体列表 ----------------------------------------------------

        return (
            EntitySpec(
                platform="switch",
                key="power",
                name="电源",
                state=power_state,
                actions={
                    "turn_on": lambda ctx, _: _set_power(ctx, {"is_on": True}),
                    "turn_off": lambda ctx, _: _set_power(ctx, {"is_on": False}),
                },
            ),
            EntitySpec(
                platform="switch",
                key="key_lock",
                name="按摩键锁定",
                state=key_lock_state,
                actions={
                    "turn_on": lambda ctx, _: _set_key_lock(ctx, {"is_on": True}),
                    "turn_off": lambda ctx, _: _set_key_lock(ctx, {"is_on": False}),
                },
            ),
            EntitySpec(
                platform="select",
                key="scene_mode",
                name="场景模式",
                state=scene_mode_state,
                metadata={"options": _SCENE_MODE_OPTIONS},
                actions={"select_option": _select_scene_mode},
            ),
            EntitySpec(
                platform="select",
                key="custom_mode",
                name="自定义模式",
                state=custom_mode_state,
                metadata={"options": _CUSTOM_MODE_OPTIONS},
                actions={"select_option": _select_custom_mode},
            ),
            EntitySpec(
                platform="select",
                key="heat_level",
                name="热敷",
                state=heat_level_state,
                metadata={"options": _HEAT_LEVEL_OPTIONS},
                actions={"select_option": _select_heat_level},
            ),
            EntitySpec(
                platform="number",
                key="ems_level",
                name="按摩力度",
                state=ems_level_state,
                metadata={"min": 0, "max": 9, "step": 1},
                actions={"set_value": _set_ems_level},
            ),
            EntitySpec(
                platform="number",
                key="timer",
                name="按摩时间",
                state=timer_state,
                metadata={"min": 5, "max": 25, "step": 5, "unit": "min"},
                actions={"set_value": _set_timer},
            ),
            EntitySpec(
                platform="number",
                key="collection",
                name="收藏设定",
                state=collection_state,
                metadata={"min": 0, "max": 10, "step": 1},
                actions={"set_value": _set_collection},
            ),
            EntitySpec(
                platform="sensor",
                key="battery",
                name="电池电量",
                state=battery_state,
                metadata={"unit": "%", "device_class": "battery"},
            ),
        )


ADAPTER = Product2FJTAdapter()