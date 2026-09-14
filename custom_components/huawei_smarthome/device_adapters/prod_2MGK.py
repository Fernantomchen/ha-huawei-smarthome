"""User-contributed protocol for Huawei product 2MGK (杜亚智能窗帘 H5).

设备类型: 开合帘 (杜亚 DOOYA)
本适配器暴露:
   1. cover 窗帘：位置(0~100%，来自 opener.current/target)、开/关/停
   2. select 运行速度（switchSpeed.action：一档/二档/三档）
   3. button 改变方向 (Direction.Change)

Profile 说明:
   action.action  enum RW (0=关 1=开 2=暂停 3=开停 4=关停 5=开关停)
   opener.target  int RW 0~100 (%)   opener.current int R 0~100 (%)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_SPEED_OPTIONS = ("一档", "二档", "三档")
_SPEED_VALUES = {"一档": 0, "二档": 1, "三档": 2}


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _empty_state(_device: DeviceContext) -> Mapping[str, Any]:
    return {}


class Product2MGKAdapter:
    """Keep all 2MGK entity and command choices in this file."""

    prod_id = "2MGK"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not all(
            context.has_service(sid) for sid in ("opener", "action")
        ):
            return ()

        def cover_state(device: DeviceContext) -> Mapping[str, Any]:
            current = _number(device.value("opener", "current"))
            position = min(max(int(current), 0), 100) if current is not None else None
            return {
                "current_position": position,
                "is_closed": position == 0 if position is not None else None,
            }

        async def open_cover(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("action", {"action": 1})

        async def close_cover(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("action", {"action": 0})

        async def stop_cover(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("action", {"action": 2})

        async def set_position(
            device: DeviceContext, data: Mapping[str, Any]
        ) -> None:
            position = _number(data.get("position"))
            if position is None:
                raise ValueError("position is required")
            position = min(max(int(position), 0), 100)
            await device.async_send_service("opener", {"target": position})

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="cover",
                key="curtain",
                name="窗帘",
                state=cover_state,
                actions={
                    "open": open_cover,
                    "close": close_cover,
                    "stop": stop_cover,
                    "set_position": set_position,
                },
            )
        ]

        if context.has_service("switchSpeed"):
            def speed_state(device: DeviceContext) -> Mapping[str, Any]:
                value = _number(device.value("switchSpeed", "action"))
                label = next(
                    (label for label, raw in _SPEED_VALUES.items() if value == raw),
                    None,
                )
                return {"current_option": label}

            async def set_speed(
                device: DeviceContext, data: Mapping[str, Any]
            ) -> None:
                option = str(data.get("option"))
                if option not in _SPEED_VALUES:
                    raise ValueError(f"unknown curtain speed: {option}")
                await device.async_send_service(
                    "switchSpeed", {"action": _SPEED_VALUES[option]}
                )

            entities.append(
                EntitySpec(
                    platform="select",
                    key="speed",
                    name="运行速度",
                    state=speed_state,
                    metadata={"options": _SPEED_OPTIONS},
                    actions={"select_option": set_speed},
                )
            )

        if context.has_service("Direction"):
            async def change_direction(
                device: DeviceContext, _data: Mapping[str, Any]
            ) -> None:
                await device.async_send_service("Direction", {"Change": 0})

            entities.append(
                EntitySpec(
                    platform="button",
                    key="change_direction",
                    name="改变方向",
                    state=_empty_state,
                    actions={"press": change_direction},
                )
            )
        return tuple(entities)


ADAPTER = Product2MGKAdapter()
