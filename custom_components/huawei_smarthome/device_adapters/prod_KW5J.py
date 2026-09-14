"""User-contributed protocol for Huawei product KW5J (华为智能门锁 Plus, AGS-X11).

v2 完整版。暴露实体：
  1. lock 门锁（只读：不提供远程 lock/unlock，杜绝误开门）
  2. sensor 门锁状态 / 固件版本 / 网络状态 / 网络信号强度
  3. sensor 门锁电池 / 猫眼电池（device_class=battery）
  4. binary_sensor 门锁告警(problem) / 门未关 / 已反锁
  5. sensor 最近开门记录（指纹/密码/人脸/门卡/手表/钱包/临时密码=室外，门内开锁=室内）
  6. sensor 最近门锁事件（含门铃、反锁、布防撤防、添加删除用户等全部 userOperation）
  7. sensor 最近门锁告警（event.doorAlarmState 15 种告警描述）
  8. sensor 告警描述（lockAlarm.alarm）
  9. switch ×9 告警提醒设置（alarmEventSetting 读写开关）
 10. select ×2 布防告警延时（门外 5/10/15 秒、门内 5/15/30 秒）

暂不适配：临时密码/用户/指纹/门卡/人脸/手表/钱包钥匙管理（object 型服务），
门锁音量（Profile 未提供 min/max），猫眼设置与 OTA（低频管理功能）。

可用性说明：门锁是低功耗设备，休眠期间华为云端会将其标记为离线
（networkConnectState.state：0=离线、1=休眠、2=在线）。休眠期间最后
缓存状态仍然有效，因此本适配器通过 EntitySpec.availability（核心
PR #67 提供的实体级回调）声明单品级可用性：state 为休眠(1)/在线(2)
时保持可用，真正的离线(0)或字段缺失时回退到全局 context.available，
不影响其他设备型号。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_LOCK_STATUS = {
    1: "门未关异常上锁",
    2: "已开锁",
    3: "已上锁",
    4: "已关门",
    6: "已反锁",
}

_NETWORK_STATES = {0: "离线", 1: "休眠", 2: "在线"}

# networkConnectState.state 值域（KW5J Profile 明确提供）：
# 0=离线（不可用），1=休眠（保持可用并显示最后缓存），2=在线（可用）。
_NET_STATE_OFFLINE = 0
_NET_STATE_SLEEPING = 1
_NET_STATE_ONLINE = 2
_NET_AVAILABLE_STATES = {_NET_STATE_SLEEPING, _NET_STATE_ONLINE}

_LOCK_ALARM_DESCRIPTIONS = {
    1: "故障",
    2: "低电量告警",
    3: "门锁长时间未上线，请检查门锁是否离线",
}

# event.userOperation 中属于“开门”的操作：
# 0-7 为门外各种方式开锁（室外开门），24 为门内开锁（室内开门）。
_OUTDOOR_OPEN_OPERATIONS = {
    0: "指纹开锁",
    1: "密码开锁",
    2: "人脸开锁",
    3: "门卡开锁",
    4: "手表手环开锁",
    5: "华为钱包开锁",
    6: "临时密码开门",
    7: "物理钥匙开门",
}
_INDOOR_OPEN_OPERATIONS = {24: "门内开锁"}

_USER_OPERATIONS = {
    **{op: f"{text}（室外）" for op, text in _OUTDOOR_OPEN_OPERATIONS.items()},
    **{op: f"{text}（室内）" for op, text in _INDOOR_OPEN_OPERATIONS.items()},
    8: "添加密码",
    9: "删除密码",
    10: "添加指纹",
    11: "删除指纹",
    12: "添加人脸",
    13: "删除人脸",
    14: "添加门卡",
    15: "删除门卡",
    16: "添加手表手环",
    17: "删除手表手环",
    18: "添加钱包钥匙",
    19: "删除钱包钥匙",
    20: "添加用户",
    21: "删除用户",
    22: "门铃响铃",
    23: "编辑用户",
    25: "反锁",
    26: "解除反锁",
    27: "开启布防",
    28: "解除布防",
    29: "敲门事件",
    30: "连续按门铃",
    31: "门内sensor检测靠近",
    32: "开始视频通话",
    33: "开始视频录制",
}

_DOOR_ALARM_STATES = {
    1: "门未关告警",
    2: "门虚掩告警",
    3: "门未锁(故障)告警",
    4: "低电告警",
    5: "网络质量差告警",
    6: "指纹连续错误告警",
    7: "密码连续错误告警",
    8: "人脸连续错误告警",
    9: "挟持告警",
    10: "布防告警",
    11: "可疑逗留",
    12: "被撬告警",
    13: "遮挡告警",
    14: "过爆告警",
    15: "长时间未开门",
}

# (characteristicName, 中文开关名)
_ALARM_SWITCHES = (
    ("doorNotCLoseSwitch", "门未关提醒"),
    ("unlockSwitch", "开锁提醒"),
    ("lockBrokenSwitch", "防撬告警提醒"),
    ("forceUnlockedSwitch", "非法开锁告警提醒"),
    ("alertModeUnlockedSwitch", "警戒模式开锁提醒"),
    ("lowBatterySwitch", "低电量提醒"),
    ("takeSnapshotSwitch", "异常抓拍"),
    ("doorOpenSwitch", "门外开门提醒"),
    ("messagePushSwitch", "消息推送总开关"),
)

_OUT_ALARM_TIME_OPTIONS = {"0": "5秒", "1": "10秒", "2": "15秒"}
_IN_ALARM_TIME_OPTIONS = {"0": "5秒", "1": "15秒", "2": "30秒"}


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def lock_available(device: DeviceContext) -> bool:
    """Entity-level availability override (EntitySpec.availability, core PR #67).

    The lock sleeps most of the time and the cloud then reports it offline
    while its cached state stays valid. Sleep(1)/online(2) keep entities
    available; a genuine offline(0) or a missing networkConnectState service
    falls back to the global context.available.
    """

    state = _number(device.value("networkConnectState", "state"))
    if state is not None:
        return state in _NET_AVAILABLE_STATES
    return device.available


def _battery_level(value: Any) -> int | None:
    number = _number(value)
    if number is None or number < 0:
        return None
    return int(number)


def _format_event_time(value: Any) -> str | None:
    """Compress '20260914T013015Z' style stamps into '09-14 01:30'."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z") and "T" in text:
        try:
            parsed = datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
            return parsed.strftime("%m-%d %H:%M")
        except ValueError:
            pass
    return text


def _event_summary(device: DeviceContext) -> tuple[Any, ...]:
    """Return (userOperation, userName, doorAlarmState, eventTime) of last event."""
    return (
        _number(device.value("event", "userOperation")),
        device.value("event", "userName"),
        _number(device.value("event", "doorAlarmState")),
        device.value("event", "eventTime"),
    )


def _compose_event_text(
    operation: int | float | None,
    user_name: Any,
    time_text: str | None,
) -> str | None:
    parts: list[str] = []
    operation_text = _USER_OPERATIONS.get(int(operation)) if operation is not None else None
    if operation_text:
        parts.append(operation_text)
    if isinstance(user_name, str) and user_name.strip():
        parts.append(user_name.strip())
    if time_text:
        parts.append(time_text)
    return " · ".join(parts) if parts else None


def _alarm_switch_state(characteristic: str):
    def state(device: DeviceContext) -> Mapping[str, Any]:
        value = _number(device.value("alarmEventSetting", characteristic))
        return {"is_on": None if value is None else value == 1}

    return state


def _alarm_switch_actions(characteristic: str) -> Mapping[str, Any]:
    async def turn_on(device: DeviceContext, data: Mapping[str, Any]) -> None:
        await device.async_send_service("alarmEventSetting", {characteristic: 1})

    async def turn_off(device: DeviceContext, data: Mapping[str, Any]) -> None:
        await device.async_send_service("alarmEventSetting", {characteristic: 0})

    return {"turn_on": turn_on, "turn_off": turn_off}


def _alarm_delay_select(
    characteristic: str,
    options_map: Mapping[str, str],
    entity_key: str,
    entity_name: str,
) -> EntitySpec:
    label_to_value = {label: int(code) for code, label in options_map.items()}

    def state(device: DeviceContext) -> Mapping[str, Any]:
        value = _number(device.value("alarmEventSetting", characteristic))
        return {
            "current_option": None if value is None else options_map.get(str(int(value)))
        }

    async def select_option(device: DeviceContext, data: Mapping[str, Any]) -> None:
        option = data.get("option")
        value = label_to_value.get(str(option))
        if value is None:
            raise ValueError(f"unknown option for {characteristic}: {option!r}")
        await device.async_send_service(
            "alarmEventSetting", {characteristic: value}
        )

    return EntitySpec(
        platform="select",
        key=entity_key,
        name=entity_name,
        state=state,
        actions={"select_option": select_option},
        metadata={"options": list(options_map.values())},
        availability=lock_available,
    )


class ProductKW5JAdapter:
    """Keep all KW5J entity and command choices in this file."""

    prod_id = "KW5J"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("lockStatus"):
            return ()

        def lock_state(device: DeviceContext) -> Mapping[str, Any]:
            status = _number(device.value("lockStatus", "status"))
            # 1=门未关异常上锁 2=已开锁 3=已上锁 4=已关门 6=已反锁
            return {"is_locked": status in (3, 6)}

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="lock",
                key="lock",
                name="门锁",
                state=lock_state,
                availability=lock_available,
            )
        ]

        # ---- 锁体状态 ----
        entities.append(
            EntitySpec(
                platform="sensor",
                key="lock_status",
                name="门锁状态",
                state=lambda device: {
                    "native_value": _LOCK_STATUS.get(
                        int(status)
                    )
                    if (status := _number(device.value("lockStatus", "status")))
                    is not None
                    else None
                },
                availability=lock_available,
            )
        )
        entities.append(
            EntitySpec(
                platform="binary_sensor",
                key="door_not_closed",
                name="门未关",
                state=lambda device: {
                    "is_on": _number(device.value("lockStatus", "status")) == 1
                },
                metadata={"device_class": "door"},
                availability=lock_available,
            )
        )
        entities.append(
            EntitySpec(
                platform="binary_sensor",
                key="double_locked",
                name="已反锁",
                state=lambda device: {
                    "is_on": _number(device.value("lockStatus", "status")) == 6
                },
                availability=lock_available,
            )
        )

        # ---- 电池 ----
        if context.has_service("doorBattery"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="door_battery",
                    name="门锁电池",
                    state=lambda device: {
                        "native_value": _battery_level(
                            device.value("doorBattery", "level")
                        )
                    },
                    metadata={"device_class": "battery", "unit": "%", "state_class": "measurement"},
                    availability=lock_available,
                )
            )
        if context.has_service("catEyeBattery"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="cat_eye_battery",
                    name="猫眼电池",
                    state=lambda device: {
                        "native_value": _battery_level(
                            device.value("catEyeBattery", "level")
                        )
                    },
                    metadata={"device_class": "battery", "unit": "%", "state_class": "measurement"},
                    availability=lock_available,
                )
            )

        # ---- 网络 ----
        if context.has_service("networkConnectState"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="network_state",
                    name="网络状态",
                    state=lambda device: {
                        "native_value": _NETWORK_STATES.get(
                            int(value)
                        )
                        if (value := _number(device.value("networkConnectState", "state")))
                        is not None
                        else None
                    },
                    availability=lock_available,
                )
            )
        if context.has_service("netInfo"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="wifi_signal",
                    name="网络信号强度",
                    state=lambda device: {
                        "native_value": _battery_level(
                            device.value("netInfo", "intensity")
                        )
                    },
                    metadata={"unit": "%", "state_class": "measurement"},
                    availability=lock_available,
                )
            )

        # ---- 告警 ----
        if context.has_service("lockAlarm"):
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="alarm",
                    name="门锁告警",
                    state=lambda device: {
                        "is_on": (
                            value >= 1
                            if (value := _number(device.value("lockAlarm", "alarm")))
                            is not None
                            else None
                        )
                    },
                    metadata={"device_class": "problem"},
                    availability=lock_available,
                )
            )
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="alarm_detail",
                    name="告警描述",
                    state=lambda device: {
                        "native_value": _LOCK_ALARM_DESCRIPTIONS.get(
                            int(value)
                        )
                        if (value := _number(device.value("lockAlarm", "alarm")))
                        is not None
                        else None
                    },
                    availability=lock_available,
                )
            )

        # ---- 事件记录（开门记录 / 门铃 / 告警事件） ----
        if context.has_service("event"):

            def last_open_record(device: DeviceContext) -> Mapping[str, Any]:
                operation, user_name, _, event_time = _event_summary(device)
                if operation is None or int(operation) not in (
                    *_OUTDOOR_OPEN_OPERATIONS,
                    *_INDOOR_OPEN_OPERATIONS,
                ):
                    return {"native_value": None}
                return {
                    "native_value": _compose_event_text(
                        operation,
                        user_name,
                        _format_event_time(event_time),
                    )
                }

            def last_lock_event(device: DeviceContext) -> Mapping[str, Any]:
                operation, user_name, _, event_time = _event_summary(device)
                return {
                    "native_value": _compose_event_text(
                        operation,
                        user_name,
                        _format_event_time(event_time),
                    )
                }

            def last_lock_alarm(device: DeviceContext) -> Mapping[str, Any]:
                _, _, alarm_state, event_time = _event_summary(device)
                if alarm_state is None:
                    return {"native_value": None}
                parts = [
                    _DOOR_ALARM_STATES.get(int(alarm_state), f"未知告警({int(alarm_state)})")
                ]
                time_text = _format_event_time(event_time)
                if time_text:
                    parts.append(time_text)
                return {"native_value": " · ".join(parts)}

            entities.extend(
                (
                    EntitySpec(
                        platform="sensor",
                        key="last_open_record",
                        name="最近开门记录",
                        state=last_open_record,
                        metadata={"icon": "mdi:door-open"},
                        availability=lock_available,
                    ),
                    EntitySpec(
                        platform="sensor",
                        key="last_lock_event",
                        name="最近门锁事件",
                        state=last_lock_event,
                        metadata={"icon": "mdi:history"},
                        availability=lock_available,
                    ),
                    EntitySpec(
                        platform="sensor",
                        key="last_lock_alarm",
                        name="最近门锁告警",
                        state=last_lock_alarm,
                        metadata={"icon": "mdi:alarm-light"},
                        availability=lock_available,
                    ),
                )
            )

        # ---- 固件 ----
        if context.has_service("update"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="firmware",
                        name="固件版本",
                        state=lambda device: {
                            "native_value": device.value("update", "version")
                        },
                        availability=lock_available,
                    )
            )

        # ---- 告警提醒设置开关 ----
        if context.has_service("alarmEventSetting"):
            for characteristic, label in _ALARM_SWITCHES:
                entities.append(
                    EntitySpec(
                        platform="switch",
                        key=f"alarm_switch_{characteristic}",
                        name=label,
                        state=_alarm_switch_state(characteristic),
                        actions=_alarm_switch_actions(characteristic),
                        availability=lock_available,
                    )
                )
            entities.append(
                _alarm_delay_select(
                    "outAlarmTime",
                    _OUT_ALARM_TIME_OPTIONS,
                    "alarm_delay_out",
                    "门外告警延时",
                )
            )
            entities.append(
                _alarm_delay_select(
                    "inAlarmTime",
                    _IN_ALARM_TIME_OPTIONS,
                    "alarm_delay_in",
                    "门内告警延时",
                )
            )

        return tuple(entities)


ADAPTER = ProductKW5JAdapter()
