"""User-contributed protocol for Huawei product 2AW5 (usmile U悦智能声波电动牙刷 X10).

设备类型: 牙刷
本适配器暴露:
   1. select 刷牙模式 (mode.mode，8 档)
   2. select 强度 (intensity.intensity: 低/中/高)
   3. select 刷牙时长 (time.time: 2分钟~4分钟)
   4. sensor 电池电量 (%) / binary_sensor 充电中 / binary_sensor 低电量
   5. sensor 刷头剩余寿命 (天)
   6. sensor 刷牙评分 (brushingHistory.score 0~100)

说明: mode/intensity/time 为 RW，但设备离手前写入是否生效未验证，
请以实际设备表现为准；startPositon/direction/splashProof/LED/handheldAwaken 暂不适配。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_MODE_OPTIONS = ("清洁", "亮白", "呵护", "按摩", "护龈", "烟渍", "舌苔", "抛光")
_MODE_VALUES = {
    "清洁": 100, "亮白": 101, "呵护": 102, "按摩": 103,
    "护龈": 200, "烟渍": 201, "舌苔": 202, "抛光": 203,
}
_INTENSITY_OPTIONS = ("低", "中", "高")
_INTENSITY_VALUES = {"低": 0, "中": 1, "高": 2}
_TIME_OPTIONS = ("2分钟", "2分30秒", "3分钟", "3分30秒", "4分钟")
_TIME_VALUES = {"2分钟": 0, "2分30秒": 1, "3分钟": 2, "3分30秒": 3, "4分钟": 4}


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


def _make_enum_select(
    sid: str,
    char: str,
    key: str,
    name: str,
    options: tuple[str, ...],
    values: Mapping[str, int],
):
    def state(device: DeviceContext) -> Mapping[str, Any]:
        value = _number(device.value(sid, char))
        label = next(
            (label for label, raw in values.items() if value == raw),
            None,
        )
        return {"current_option": label}

    async def set_option(device: DeviceContext, data: Mapping[str, Any]) -> None:
        option = str(data.get("option"))
        if option not in values:
            raise ValueError(f"unknown {name} option: {option}")
        await device.async_send_service(sid, {char: values[option]})

    return EntitySpec(
        platform="select",
        key=key,
        name=name,
        state=state,
        metadata={"options": options},
        actions={"select_option": set_option},
    )


class Product2AW5Adapter:
    """Keep all 2AW5 entity and command choices in this file."""

    prod_id = "2AW5"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("mode"):
            return ()

        entities: list[EntitySpec] = [
            _make_enum_select(
                "mode", "mode", "brush_mode", "刷牙模式",
                _MODE_OPTIONS, _MODE_VALUES,
            ),
        ]

        if context.has_service("intensity"):
            entities.append(
                _make_enum_select(
                    "intensity", "intensity", "intensity", "强度",
                    _INTENSITY_OPTIONS, _INTENSITY_VALUES,
                )
            )
        if context.has_service("time"):
            entities.append(
                _make_enum_select(
                    "time", "time", "brush_time", "刷牙时长",
                    _TIME_OPTIONS, _TIME_VALUES,
                )
            )
        if context.has_service("battery"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="battery_level",
                    name="电池电量",
                    state=lambda device: {
                        "native_value": _number(device.value("battery", "level"))
                    },
                    metadata={"unit_of_measurement": "%"},
                )
            )
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="charging",
                    name="充电中",
                    state=lambda device: {
                        "is_on": _number(device.value("battery", "charging")) == 1
                    },
                )
            )
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="battery_low",
                    name="电池低电量",
                    state=lambda device: {
                        "is_on": _bool(device.value("battery", "alarm")) is True
                    },
                )
            )
        if context.has_service("brushHeadLife"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="brush_head_life",
                    name="刷头剩余寿命",
                    state=lambda device: {
                        "native_value": _number(
                            device.value("brushHeadLife", "brushHeadLife")
                        )
                    },
                    metadata={"unit_of_measurement": "天"},
                )
            )
        if context.has_service("brushingHistory"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="brush_score",
                    name="刷牙评分",
                    state=lambda device: {
                        "native_value": _number(
                            device.value("brushingHistory", "score")
                        )
                    },
                )
            )
        return tuple(entities)


ADAPTER = Product2AW5Adapter()
