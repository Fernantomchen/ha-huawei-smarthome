"""User-contributed protocol for Huawei product 21I3 (三思插座小夜灯).

设备类型: 智能照明 (C21HI-TP5-1W)，插座 + 感应小夜灯
本适配器暴露:
   1. switch 插座开关 (switch.on)
   2. select 夜灯模式 (yedengsw: 关闭/感应/常亮)
   3. binary_sensor 夜灯状态 (yedengstatus)

说明: timer/delay 为定时任务数组协议，暂不适配。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_NIGHT_MODE_OPTIONS = ("关闭", "感应", "常亮")
_NIGHT_MODE_VALUES = {"关闭": 0, "感应": 1, "常亮": 2}


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


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


class Product21I3Adapter:
    """Keep all 21I3 entity and command choices in this file."""

    prod_id = "21I3"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="switch",
                key="socket",
                name="插座",
                state=lambda device: {
                    "is_on": _bool(device.value("switch", "on")) is True
                },
                actions={
                    "turn_on": lambda d, _data: d.async_send_service("switch", {"on": 1}),
                    "turn_off": lambda d, _data: d.async_send_service("switch", {"on": 0}),
                },
            )
        ]

        if context.has_service("yedengsw"):
            entities.append(
                EntitySpec(
                    platform="select",
                    key="night_light_mode",
                    name="夜灯模式",
                    state=lambda device: {
                        "current_option": next(
                            (
                                label
                                for label, raw in _NIGHT_MODE_VALUES.items()
                                if _number(device.value("yedengsw", "yedengsw")) == raw
                            ),
                            None,
                        )
                    },
                    metadata={"options": _NIGHT_MODE_OPTIONS},
                    actions={
                        "select_option": _select_night_mode,
                    },
                )
            )
        if context.has_service("yedengstatus"):
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="night_light_on",
                    name="夜灯状态",
                    state=lambda device: {
                        "is_on": _number(device.value("yedengstatus", "yedengstatus")) == 1
                    },
                )
            )
        return tuple(entities)


async def _select_night_mode(device: DeviceContext, data: Mapping[str, Any]) -> None:
    option = str(data.get("option"))
    if option not in _NIGHT_MODE_VALUES:
        raise ValueError(f"unknown night light mode: {option}")
    await device.async_send_service(
        "yedengsw", {"yedengsw": _NIGHT_MODE_VALUES[option]}
    )


ADAPTER = Product21I3Adapter()
