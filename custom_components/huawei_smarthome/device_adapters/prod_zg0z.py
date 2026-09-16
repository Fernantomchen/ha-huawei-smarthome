"""User-contributed protocol for Huawei product ZG0Z (华为 智能开关1键).

设备类型: 开关 (Switch), 型号 OSLO-SS1
核心服务:
   switch1.on              bool RW  电源开关
   mode1.mode              enum RW  按键模式(1 开关模式 / 2 场景模式)
   childLockSwitch.on      bool RW  按键锁
   backlight.on            bool RW  指示灯开关
   brightness.brightness   int  RW  指示灯亮度(H5 实际范围 1-100%)
   memorySwitch.on         bool RW  断电记忆
   faultDetection.status   bool RW  故障告警
   faultDetection.code     enum RW  故障码

本适配器暴露:
   1. switch        开关一
   2. select        按键一模式
   3. switch        按键锁定
   4. switch        指示灯
   5. number        指示灯亮度
   6. switch        断电记忆
   7. sensor        故障状态
   8. binary_sensor 故障告警
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_SWITCH_SID = "switch1"
_MODE_SID = "mode1"
_LOCK_SID = "childLockSwitch"
_BACKLIGHT_SID = "backlight"
_BRIGHTNESS_SID = "brightness"
_MEMORY_SID = "memorySwitch"
_FAULT_SID = "faultDetection"

_FLAG_FIELD = "on"
_MODE_FIELD = "mode"
_BRIGHTNESS_FIELD = "brightness"
_FAULT_STATUS_FIELD = "status"
_FAULT_CODE_FIELD = "code"

_MODE_VALUES = (1, 2)
_MODE_OPTIONS = ("开关模式", "场景模式")
_BRIGHTNESS_RANGE = (1.0, 100.0)
_FAULT_BITS = ((1, "过温保护"), (2, "继电器故障"))


def _service(profile: Any, sid: str) -> Any:
    if profile is None:
        return None
    for service in profile.get("services", ()):
        if service.get("serviceId") == sid:
            return service
    return None


def _field(profile: Any, sid: str, name: str) -> Mapping[str, Any] | None:
    service = _service(profile, sid)
    if service is None:
        return None
    for characteristic in service.get("characteristics", ()):
        if characteristic.get("characteristicName") == name:
            return characteristic
    return None


def _flag_value(raw: Any) -> bool | None:
    """Convert only the Profile's valid 0/1 values to a boolean."""

    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    try:
        number = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if number == 1:
        return True
    if number == 0:
        return False
    return None


def _number(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _flag_action(sid: str, value: int):
    async def action(context: DeviceContext, data: Mapping[str, Any]) -> None:
        del data
        await context.async_send_service(sid, {_FLAG_FIELD: value})

    return action


def _flag_switch(key: str, name: str, sid: str) -> EntitySpec:
    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=lambda context: {
            "is_on": _flag_value(context.value(sid, _FLAG_FIELD))
        },
        actions={
            "turn_on": _flag_action(sid, 1),
            "turn_off": _flag_action(sid, 0),
        },
    )


def _mode_state(context: DeviceContext) -> str | None:
    raw = context.value(_MODE_SID, _MODE_FIELD)
    if raw is None:
        return None
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    try:
        return _MODE_OPTIONS[_MODE_VALUES.index(value)]
    except ValueError:
        return None


async def _select_mode(
    context: DeviceContext, data: Mapping[str, Any]
) -> None:
    option = data.get("option")
    if not isinstance(option, str):
        return
    try:
        value = _MODE_VALUES[_MODE_OPTIONS.index(option)]
    except ValueError:
        return
    await context.async_send_service(_MODE_SID, {_MODE_FIELD: value})


async def _set_brightness(
    context: DeviceContext, data: Mapping[str, Any]
) -> None:
    value = _number(data.get("value"))
    if value is None:
        return
    minimum, maximum = _BRIGHTNESS_RANGE
    clamped = max(minimum, min(maximum, value))
    await context.async_send_service(
        _BRIGHTNESS_SID, {_BRIGHTNESS_FIELD: int(clamped)}
    )


def _fault_state(context: DeviceContext) -> str | None:
    raw = context.value(_FAULT_SID, _FAULT_CODE_FIELD)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        code = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if code < 0:
        return None
    if code == 0:
        return "正常"

    labels: list[str] = []
    known_mask = 0
    for bit, label in _FAULT_BITS:
        if code & bit:
            labels.append(label)
            known_mask |= bit

    unknown_mask = code & ~known_mask
    bit_position = 0
    while unknown_mask:
        if unknown_mask & 1:
            labels.append(f"未知({bit_position})")
        unknown_mask >>= 1
        bit_position += 1
    return "、".join(labels)


class ProductZG0ZAdapter:
    """OSLO-SS1 one-key smart switch."""

    prod_id = "ZG0Z"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        if context.has_service(_SWITCH_SID) and _field(
            profile, _SWITCH_SID, _FLAG_FIELD
        ) is not None:
            entities.append(_flag_switch("switch_1", "开关一", _SWITCH_SID))

        if context.has_service(_MODE_SID) and _field(
            profile, _MODE_SID, _MODE_FIELD
        ) is not None:
            entities.append(
                EntitySpec(
                    platform="select",
                    key="key_1_mode",
                    name="按键一模式",
                    state=lambda ctx: {"current_option": _mode_state(ctx)},
                    metadata={"options": list(_MODE_OPTIONS)},
                    actions={"select_option": _select_mode},
                )
            )

        for sid, key, name in (
            (_LOCK_SID, "key_lock", "按键锁定"),
            (_BACKLIGHT_SID, "indicator_light", "指示灯"),
            (_MEMORY_SID, "power_loss_memory", "断电记忆"),
        ):
            if context.has_service(sid) and _field(
                profile, sid, _FLAG_FIELD
            ) is not None:
                entities.append(_flag_switch(key, name, sid))

        if context.has_service(_BRIGHTNESS_SID) and _field(
            profile, _BRIGHTNESS_SID, _BRIGHTNESS_FIELD
        ) is not None:
            entities.append(
                EntitySpec(
                    platform="number",
                    key="indicator_brightness",
                    name="指示灯亮度",
                    state=lambda ctx: {
                        "native_value": _number(
                            ctx.value(_BRIGHTNESS_SID, _BRIGHTNESS_FIELD)
                        )
                    },
                    metadata={
                        "min": _BRIGHTNESS_RANGE[0],
                        "max": _BRIGHTNESS_RANGE[1],
                        "step": 1.0,
                        "unit": "%",
                    },
                    actions={"set_value": _set_brightness},
                )
            )

        if context.has_service(_FAULT_SID) and _field(
            profile, _FAULT_SID, _FAULT_CODE_FIELD
        ) is not None:
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="fault_state",
                    name="故障状态",
                    state=lambda ctx: {"native_value": _fault_state(ctx)},
                )
            )

        if context.has_service(_FAULT_SID) and _field(
            profile, _FAULT_SID, _FAULT_STATUS_FIELD
        ) is not None:
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="fault_problem",
                    name="故障告警",
                    state=lambda ctx: {
                        "is_on": _flag_value(
                            ctx.value(_FAULT_SID, _FAULT_STATUS_FIELD)
                        )
                    },
                    metadata={"device_class": "problem"},
                )
            )

        return tuple(entities)


ADAPTER = ProductZG0ZAdapter()
