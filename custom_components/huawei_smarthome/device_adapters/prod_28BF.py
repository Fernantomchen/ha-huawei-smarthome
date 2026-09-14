"""User-contributed protocol for Huawei product 28BF (无线续航自然风风扇).

设备类型: 风扇 (FL-12138DRR(WF)-1W)
本适配器暴露:
   1. fan 风扇（开关 / 8 档风速 / 摇头角度 / 3 种风类预设）
      - 风速: Profile speed 1~8 ↔ HA percentage 0~100
      - 摇头: Profile angle 0=固定, 30/60/90/120=摇头角度
      - 预设: mode 0=正常风 1=睡眠风 2=自然风

说明: endTime 定时为剩余时间协议，暂不适配。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_PRESET_MODES = ("正常风", "睡眠风", "自然风")
_PRESET_VALUES = {"正常风": 0, "睡眠风": 1, "自然风": 2}
_SPEED_MIN = 1
_SPEED_MAX = 8
_DEFAULT_OSCILLATE_ANGLE = 90


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


def _speed_to_percentage(speed: Any) -> int | None:
    number = _number(speed)
    if number is None:
        return None
    number = min(max(number, _SPEED_MIN), _SPEED_MAX)
    return round((number - _SPEED_MIN) * 100 / (_SPEED_MAX - _SPEED_MIN))


def _percentage_to_speed(percentage: Any) -> int:
    number = _number(percentage)
    if number is None:
        return _SPEED_MIN
    number = min(max(float(number), 0.0), 100.0)
    return int(round(_SPEED_MIN + number * (_SPEED_MAX - _SPEED_MIN) / 100))


class Product28BFAdapter:
    """Keep all 28BF entity and command choices in this file."""

    prod_id = "28BF"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not all(
            context.has_service(sid) for sid in ("switch", "fan")
        ):
            return ()

        def fan_state(device: DeviceContext) -> Mapping[str, Any]:
            angle = _number(device.value("fan", "angle"))
            mode = _number(device.value("mode", "mode"))
            preset = next(
                (label for label, raw in _PRESET_VALUES.items() if mode == raw),
                None,
            )
            return {
                "is_on": _bool(device.value("switch", "on")) is True,
                "percentage": _speed_to_percentage(device.value("fan", "speed")),
                "preset_mode": preset,
                "oscillating": angle is not None and angle != 0,
            }

        async def apply_speed(
            device: DeviceContext, percentage: Any
        ) -> None:
            await device.async_send_service(
                "fan", {"speed": _percentage_to_speed(percentage)}
            )

        async def turn_on(device: DeviceContext, data: Mapping[str, Any]) -> None:
            await device.async_send_service("switch", {"on": 1})
            if data.get("percentage") is not None:
                await apply_speed(device, data["percentage"])
            if data.get("preset_mode") is not None:
                option = str(data["preset_mode"])
                if option in _PRESET_VALUES:
                    await device.async_send_service(
                        "mode", {"mode": _PRESET_VALUES[option]}
                    )

        async def turn_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("switch", {"on": 0})

        async def set_percentage(
            device: DeviceContext, data: Mapping[str, Any]
        ) -> None:
            await apply_speed(device, data.get("percentage"))

        async def set_preset_mode(
            device: DeviceContext, data: Mapping[str, Any]
        ) -> None:
            option = str(data.get("preset_mode"))
            if option not in _PRESET_VALUES:
                raise ValueError(f"unknown fan preset: {option}")
            await device.async_send_service(
                "mode", {"mode": _PRESET_VALUES[option]}
            )

        async def oscillate(device: DeviceContext, data: Mapping[str, Any]) -> None:
            enabled = bool(data.get("oscillating"))
            angle = _DEFAULT_OSCILLATE_ANGLE if enabled else 0
            await device.async_send_service("fan", {"angle": angle})

        return (
            EntitySpec(
                platform="fan",
                key="fan",
                name="风扇",
                state=fan_state,
                metadata={
                    "supports_percentage": True,
                    "percentage_step": round(100.0 / (_SPEED_MAX - _SPEED_MIN)),
                    "preset_modes": _PRESET_MODES,
                    "supports_oscillation": True,
                },
                actions={
                    "turn_on": turn_on,
                    "turn_off": turn_off,
                    "set_percentage": set_percentage,
                    "set_preset_mode": set_preset_mode,
                    "oscillate": oscillate,
                },
            ),
        )


ADAPTER = Product28BFAdapter()
