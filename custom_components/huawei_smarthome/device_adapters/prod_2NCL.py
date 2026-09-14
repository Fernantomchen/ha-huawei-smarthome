"""User-contributed protocol for Huawei product 2NCL (梦百合0压智能床).

设备类型: 智能床 (Smart Bed), 型号 MLB-WBB-S, MLILY 梦百合
Profile: https://smarthome-drcn.dbankcdn.com/device/guide/2NCL/2NCL.json

核心服务(本次使用的):
   modeSelect.action      enum RW (1=0压力,2=阅读,3=观影,7=打鼾干预,
                                   8=助力起床,9=平躺深睡,10=瑜伽,100=关闭)
   headControl.action     enum RW (0=暂停,1=上升,2=下降,100=升到极限,200=降到极限)
   legControl.action      enum RW (同 headControl)
   oneKeyReset.action     enum RW (1=开启复位,0=停止)
   oneKeyReset.status     enum R  (10=复位完成,11=正在执行复位,13=复位遇阻)
   memoryControl1.action  enum RW (0=删除记忆,1=运行到记忆位置,2=记忆当前位置)
   GetMemoryMode.*        enum R  (0=未记忆,1=已记忆, 共7个记忆位)

本适配器暴露:
   1. select   床体模式（8 档）
   2. button   头部/腿部调节（上升/下降/暂停/两个极限位）
   3. button   一键复位启动/停止复位
   4. button   记忆位置运行/保存/删除
   5. sensor   复位状态
   6. binary_sensor ×7 各记忆位是否已记忆
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _service(profile: Mapping[str, Any], sid: str) -> Mapping[str, Any] | None:
    for service in profile.get("services", ()):
        if isinstance(service, Mapping) and service.get("serviceId") == sid:
            return service
    return None


def _field(
    profile: Mapping[str, Any],
    sid: str,
    name: str,
) -> Mapping[str, Any] | None:
    service = _service(profile, sid)
    if service is None:
        return None
    for field in service.get("characteristics", ()):
        if isinstance(field, Mapping) and field.get("characteristicName") == name:
            return field
    return None


def _coerce_profile_value(
    value: Any,
    field: Mapping[str, Any] | None,
) -> Any:
    """Encode a Profile value using its declared characteristic type."""

    data_type = str((field or {}).get("characteristicType") or "").casefold()
    if data_type in {"int", "integer", "enum"}:
        number = _number(value)
        if number is not None:
            return int(number) if float(number).is_integer() else number
    if data_type in {"float", "double", "number"}:
        number = _number(value)
        if number is not None:
            return float(number)
    if not data_type:
        number = _number(value)
        if number is not None:
            return number
    return value


def _enum_options(
    field: Mapping[str, Any],
) -> tuple[tuple[str, str], ...]:
    """Return (label, enumVal) pairs of a characteristic's enumList."""

    return tuple(
        (str(option.get("descCh") or option.get("enumVal")), str(option.get("enumVal")))
        for option in field.get("enumList", ())
        if isinstance(option, Mapping)
    )


def _enum_label(
    field: Mapping[str, Any],
    value: Any,
) -> str | None:
    for label, raw in _enum_options(field):
        if _number(raw) == _number(value):
            return label
    return None


def _empty_state(_device: DeviceContext) -> Mapping[str, Any]:
    return {}


class Product2NCLAdapter:
    """Keep all 2NCL entity and command choices in this file."""

    prod_id = "2NCL"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None or not context.has_service("modeSelect"):
            return ()

        entities: list[EntitySpec] = []

        # ------------------------------------------------------------------
        # select 床体模式
        # ------------------------------------------------------------------
        mode_field = _field(profile, "modeSelect", "action") or {}
        mode_options = _enum_options(mode_field)

        def mode_state(device: DeviceContext) -> Mapping[str, Any]:
            value = _number(device.value("modeSelect", "action"))
            label = _enum_label(mode_field, value) if value is not None else None
            return {"current_option": label}

        async def set_mode(device: DeviceContext, data: Mapping[str, Any]) -> None:
            target = next(
                (raw for label, raw in mode_options if label == data["option"]),
                None,
            )
            if target is None:
                raise ValueError(f"unknown bed mode: {data['option']}")
            await device.async_send_service(
                "modeSelect",
                {"action": _coerce_profile_value(target, mode_field)},
            )

        entities.append(
            EntitySpec(
                platform="select",
                key="mode",
                name="床体模式",
                state=mode_state,
                metadata={"options": tuple(label for label, _ in mode_options)},
                actions={"select_option": set_mode},
            )
        )

        # ------------------------------------------------------------------
        # button 头部/腿部调节、一键复位、一键记忆
        # ------------------------------------------------------------------
        def make_press(sid: str, char: str, raw: str, field: Mapping[str, Any]):
            async def _press(device: DeviceContext, _data: Mapping[str, Any]) -> None:
                await device.async_send_service(
                    sid,
                    {char: _coerce_profile_value(raw, field)},
                )

            return _press

        button_specs: tuple[tuple[str, str, str, str, str], ...] = (
            # (serviceId, characteristicName, enumVal, key, 名称)
            ("headControl", "action", "1", "head_up", "头部上升"),
            ("headControl", "action", "2", "head_down", "头部下降"),
            ("headControl", "action", "0", "head_stop", "头部暂停"),
            ("headControl", "action", "100", "head_up_limit", "头部升到极限"),
            ("headControl", "action", "200", "head_down_limit", "头部降到极限"),
            ("legControl", "action", "1", "leg_up", "腿部上升"),
            ("legControl", "action", "2", "leg_down", "腿部下降"),
            ("legControl", "action", "0", "leg_stop", "腿部暂停"),
            ("legControl", "action", "100", "leg_up_limit", "腿部升到极限"),
            ("legControl", "action", "200", "leg_down_limit", "腿部降到极限"),
            ("oneKeyReset", "action", "1", "reset_start", "一键复位"),
            ("oneKeyReset", "action", "0", "reset_stop", "停止复位"),
            ("memoryControl1", "action", "1", "memory_run", "运行到记忆位置"),
            ("memoryControl1", "action", "2", "memory_save", "记忆当前位置"),
            ("memoryControl1", "action", "0", "memory_delete", "删除记忆"),
        )
        for sid, char, raw, key, name in button_specs:
            field = _field(profile, sid, char)
            if field is None or not context.has_service(sid):
                continue
            entities.append(
                EntitySpec(
                    platform="button",
                    key=key,
                    name=name,
                    state=_empty_state,
                    actions={"press": make_press(sid, char, raw, field)},
                )
            )

        # ------------------------------------------------------------------
        # sensor 复位状态
        # ------------------------------------------------------------------
        reset_field = _field(profile, "oneKeyReset", "status")
        if reset_field is not None and context.has_service("oneKeyReset"):

            def reset_state(device: DeviceContext) -> Mapping[str, Any]:
                value = _number(device.value("oneKeyReset", "status"))
                return {"native_value": _enum_label(reset_field, value)}

            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="reset_status",
                    name="复位状态",
                    state=reset_state,
                )
            )

        # ------------------------------------------------------------------
        # binary_sensor ×7 记忆位
        # ------------------------------------------------------------------
        memory_service = _service(profile, "GetMemoryMode")
        if memory_service is not None and context.has_service("GetMemoryMode"):
            for char in memory_service.get("characteristics", ()):
                if not isinstance(char, Mapping):
                    continue
                char_name = str(char.get("characteristicName") or "")
                if not char_name:
                    continue
                label = str(
                    char.get("descCh") or char.get("attrName") or char_name
                )

                def memory_state(
                    device: DeviceContext, _char: str = char_name
                ) -> Mapping[str, Any]:
                    value = _number(device.value("GetMemoryMode", _char))
                    return {"is_on": value == 1}

                entities.append(
                    EntitySpec(
                        platform="binary_sensor",
                        key=f"memory_{char_name.casefold()}",
                        name=f"记忆·{label}",
                        state=memory_state,
                    )
                )

        return tuple(entities)


ADAPTER = Product2NCLAdapter()
