"""User-contributed protocol for Huawei product KW5O (华为智能门锁 2尊享版).

设备类型: 智能门锁 (SmartLock), 型号 AGS-Q21
制造商: 华为 (HUAWEI)

核心服务:
   networkConnectState.state    int  R   网络连接状态(0=离线,1=休眠,2=在线)
   lockStatus.status            int  RW  门锁状态(1=门未关异常上锁,2=已开锁,3=已上锁,4=已关门,6=已反锁)
   doorBattery.level            int  R   门锁电池电量(-1~100, -1 表示未知)
   catEyeBattery.level          int  R   猫眼电池电量(-1~100, -1 表示未知)
   lockAlarm.alarm              int  R   门锁告警(1=故障,2=低电量,3=长时间未上线)
   alarmEventSetting.*          enum RW 告警事件开关
   securitySetting.*            enum RW 安全设置
   catEyeSetting.*              enum RW 猫眼设置

本适配器暴露:
   1.  sensor        门锁状态
   2.  sensor        门锁电池电量
   3.  sensor        猫眼电池电量
   4.  sensor        网络连接状态
   5.  binary_sensor 门锁告警
   6.  switch        消息推送
   7.  switch        门未关告警
   8.  switch        开锁告警
   9.  switch        被撬告警
   10. switch        低电量告警
   11. switch        布防
   12. switch        双重验证
   13. switch        逗留拍照
   14. switch        实时视频
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


# ---- 枚举 / 文本映射 ------------------------------------------------------

_LOCK_STATUS_TEXT = {
    1: "门未关异常上锁",
    2: "已开锁",
    3: "已上锁",
    4: "已关门",
    6: "已反锁",
}

_NETWORK_STATE_TEXT = {
    0: "离线",
    1: "休眠",
    2: "在线",
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


async def _set_enum_switch(
    context: DeviceContext,
    service_id: str,
    char_name: str,
    data: Mapping[str, Any],
) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service(service_id, {char_name: 1 if is_on else 0})


# ---- 适配器 --------------------------------------------------------------

class ProductKW5OAdapter:
    """KW5O 华为智能门锁 2尊享版适配器。"""

    prod_id = "KW5O"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("lockStatus"):
            return ()

        # ---- 状态读取 ---------------------------------------------------

        def lock_status_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("lockStatus", "status"))
            return {"native_value": _LOCK_STATUS_TEXT.get(val, "未知")}

        def door_battery_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("doorBattery", "level"))
            # -1 表示未知/不可用
            return {"native_value": val if val is not None and val >= 0 else None}

        def cateye_battery_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("catEyeBattery", "level"))
            return {"native_value": val if val is not None and val >= 0 else None}

        def network_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("networkConnectState", "state"))
            return {"native_value": _NETWORK_STATE_TEXT.get(val, "未知")}

        def alarm_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("lockAlarm", "alarm"))
            return {"is_on": val in (1, 2, 3)}

        # ---- 开关工厂 ---------------------------------------------------

        def _switch_state(service_id: str, char_name: str):
            def _get(device: DeviceContext) -> Mapping[str, Any]:
                val = _as_int(device.value(service_id, char_name))
                return {"is_on": bool(val)}
            return _get

        def _switch_actions(service_id: str, char_name: str):
            async def _turn_on(ctx: DeviceContext, _data: Mapping[str, Any]) -> None:
                await _set_enum_switch(ctx, service_id, char_name, {"is_on": True})

            async def _turn_off(ctx: DeviceContext, _data: Mapping[str, Any]) -> None:
                await _set_enum_switch(ctx, service_id, char_name, {"is_on": False})

            return {"turn_on": _turn_on, "turn_off": _turn_off}

        def _make_switch(
            key: str,
            name: str,
            service_id: str,
            char_name: str,
        ) -> EntitySpec:
            return EntitySpec(
                platform="switch",
                key=key,
                name=name,
                state=_switch_state(service_id, char_name),
                actions=_switch_actions(service_id, char_name),
            )

        # ---- 实体列表 ---------------------------------------------------

        return (
            # 状态类
            EntitySpec(
                platform="sensor",
                key="lock_status",
                name="门锁状态",
                state=lock_status_state,
            ),
            EntitySpec(
                platform="sensor",
                key="door_battery",
                name="门锁电池电量",
                state=door_battery_state,
                metadata={"unit": "%", "device_class": "battery"},
            ),
            EntitySpec(
                platform="sensor",
                key="cateye_battery",
                name="猫眼电池电量",
                state=cateye_battery_state,
                metadata={"unit": "%", "device_class": "battery"},
            ),
            EntitySpec(
                platform="sensor",
                key="network_state",
                name="网络连接状态",
                state=network_state,
            ),
            EntitySpec(
                platform="binary_sensor",
                key="alarm",
                name="门锁告警",
                state=alarm_state,
                metadata={"device_class": "problem"},
            ),

            # 告警事件设置
            _make_switch(
                "message_push", "消息推送",
                "alarmEventSetting", "messagePushSwitch",
            ),
            _make_switch(
                "door_not_close_alarm", "门未关告警",
                "alarmEventSetting", "doorNotCLoseSwitch",
            ),
            _make_switch(
                "unlock_alarm", "开锁告警",
                "alarmEventSetting", "unlockSwitch",
            ),
            _make_switch(
                "lock_broken_alarm", "被撬告警",
                "alarmEventSetting", "lockBrokenSwitch",
            ),
            _make_switch(
                "low_battery_alarm", "低电量告警",
                "alarmEventSetting", "lowBatterySwitch",
            ),

            # 安全设置
            _make_switch(
                "deployment", "布防",
                "securitySetting", "deploymentSwitch",
            ),
            _make_switch(
                "double_check", "双重验证",
                "securitySetting", "doubleCheckSwitch",
            ),

            # 猫眼设置
            _make_switch(
                "stay_snapshot", "逗留拍照",
                "catEyeSetting", "staySnapshotSwitch",
            ),
            _make_switch(
                "live_video", "实时视频",
                "catEyeSetting", "liveVideoSwitch",
            ),
        )


ADAPTER = ProductKW5OAdapter()