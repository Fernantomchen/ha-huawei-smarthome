"""User-contributed protocol for Huawei product 005E (华为AI音箱mini).

Profile: hwaccount.activeState (enum RW, -1/1..7=未授权, 0=在线) /
speakerState.State (enum R, 0=待机中/1=拾音中/2=等待响应/3=语音播报) /
smartspeaker.playControl (enum RW, 0=停止播放/1=启动播放/2=上一首&下一首) /
audioplayer.playState (enum RW, 0=暂停/1=播放中/2=停止).

Exposed:
- media_player  播放控制: 基于 audioplayer.playState 的播放/暂停/停止.
- sensor        音箱状态: 基于 speakerState.State 的当前活动 (待机/拾音/等待/播报).
- binary_sensor 授权状态: 基于 hwaccount.activeState, 0=在线 (is_on=True).

Not exposed (宁可不出):
- smartspeaker.playControl: 值 0/1 与 audioplayer.playState 功能重叠;
  值 2 在 Profile 中同时映射 "上一首" 和 "下一首" (enumVal 重复),
  无法可靠区分, 故不暴露.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


# ---- 枚举映射 ------------------------------------------------------------

_SPEAKER_STATE_LABELS: dict[int, str] = {
    0: "待机中",
    1: "拾音中",
    2: "等待响应",
    3: "语音播报",
}

_PLAY_STATE_TO_HA: dict[int, str] = {
    0: "paused",
    1: "playing",
    2: "stopped",
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


# ---- 动作函数 ------------------------------------------------------------

async def _media_play(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("audioplayer", {"playState": 1})


async def _media_pause(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("audioplayer", {"playState": 0})


async def _media_stop(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("audioplayer", {"playState": 2})


# ---- 适配器 --------------------------------------------------------------

class Product005EAdapter:
    """005E 华为AI音箱mini 适配器。"""

    prod_id = "005E"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None:
            return ()

        entities: list[EntitySpec] = []

        # ---- media_player: 播放控制 --------------------------------------
        if context.has_service("audioplayer"):

            def player_state(device: DeviceContext) -> Mapping[str, Any]:
                play_state = _as_int(device.value("audioplayer", "playState"))
                return {
                    "is_on": play_state == 1,
                    "state": _PLAY_STATE_TO_HA.get(play_state, "unknown"),
                }

            entities.append(
                EntitySpec(
                    platform="media_player",
                    key="player",
                    name="AI音箱",
                    state=player_state,
                    actions={
                        "media_play": _media_play,
                        "media_pause": _media_pause,
                        "media_stop": _media_stop,
                    },
                )
            )

        # ---- sensor: 音箱状态 --------------------------------------------
        if context.has_service("speakerState"):

            def speaker_state(device: DeviceContext) -> Mapping[str, Any]:
                val = _as_int(device.value("speakerState", "State"))
                return {
                    "native_value": _SPEAKER_STATE_LABELS.get(val, "未知"),
                }

            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="speaker_state",
                    name="音箱状态",
                    state=speaker_state,
                    metadata={},
                )
            )

        # ---- binary_sensor: 授权状态 -------------------------------------
        if context.has_service("hwaccount"):

            def authorized_state(device: DeviceContext) -> Mapping[str, Any]:
                val = _as_int(device.value("hwaccount", "activeState"))
                return {"is_on": val == 0}

            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="authorized",
                    name="授权状态",
                    state=authorized_state,
                    metadata={"device_class": "connected"},
                )
            )

        return tuple(entities)


ADAPTER = Product005EAdapter()