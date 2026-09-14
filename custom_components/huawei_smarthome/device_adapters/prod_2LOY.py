"""User-contributed protocol for Huawei product 2LOY (海雀智能摄像头3i 2.5K版).

设备类型: 网络摄像头 (AG432IG2S400S1)
本适配器暴露:
   1. switch 设备开关 (switch.on)
   2. switch 视频开关 (videoSwitch.on)
   3. switch 巡航开关 (cruiseSwitch.on)
   4. switch 抓拍开关 (shootSwitch.on)
   5. binary_sensor 告警 (alarmEvent.alarm)

说明: 看点(visitPoint)/VoIP 通话/云存储等复杂协议暂不适配。
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


def _make_switch(sid: str, key: str, name: str) -> EntitySpec:
    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=lambda device: {"is_on": _bool(device.value(sid, "on")) is True},
        actions={
            "turn_on": lambda d, _data, _s=sid: d.async_send_service(_s, {"on": 1}),
            "turn_off": lambda d, _data, _s=sid: d.async_send_service(_s, {"on": 0}),
        },
    )


class Product2LOYAdapter:
    """Keep all 2LOY entity and command choices in this file."""

    prod_id = "2LOY"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        entities: list[EntitySpec] = [_make_switch("switch", "camera", "设备开关")]

        for sid, key, name in (
            ("videoSwitch", "video", "视频开关"),
            ("cruiseSwitch", "cruise", "巡航开关"),
            ("shootSwitch", "shoot", "抓拍开关"),
        ):
            if context.has_service(sid):
                entities.append(_make_switch(sid, key, name))

        if context.has_service("alarmEvent"):
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="alarm",
                    name="告警",
                    state=lambda device: {
                        "is_on": _number(device.value("alarmEvent", "alarm")) == 1
                    },
                )
            )
        return tuple(entities)


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


ADAPTER = Product2LOYAdapter()
