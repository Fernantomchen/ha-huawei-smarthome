"""User-contributed protocol for Huawei product 2N2V (慧曼流光系列洗碗机 B1max-4).

设备类型: 洗碗机 (HTD-B1max-4)
本适配器暴露:
   1. switch 电源开关
   2. select 洗涤模式 (17 档)
   3. button 启动 / 暂停 (action.action: 1=启用 0=暂停)
   4. select 亮碟剂档位 / 软水盐档位 (1~6 档)
   5. number 预约时间 (appointment.time，0~1440 分钟)
   6. sensor 工作状态 / 剩余时间(分钟) / 舱内温度 / 故障代码
   7. binary_sensor 门开合

说明: modeFeature（分层洗等增强功能）暂不适配。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_MODE_OPTIONS = (
    "未选择", "智能洗", "日常洗", "强净洗", "经济洗", "快速洗",
    "晶柔洗", "果蔬洗", "宝宝除菌", "单独保管", "火锅洗", "静音洗",
    "增压洗", "海鲜洗", "除菌洗", "预冲洗", "自清洁",
)
_MODE_VALUES = {
    "未选择": 0, "智能洗": 1, "日常洗": 2, "强净洗": 3, "经济洗": 4,
    "快速洗": 5, "晶柔洗": 6, "果蔬洗": 7, "宝宝除菌": 8, "单独保管": 9,
    "火锅洗": 10, "静音洗": 11, "增压洗": 12, "海鲜洗": 13, "除菌洗": 14,
    "预冲洗": 15, "自清洁": 16,
}
_LEVEL_OPTIONS = ("一档", "二档", "三档", "四档", "五档", "六档")
_STATUS_VALUES = {
    0: "待机", 1: "洗涤", 2: "除菌", 3: "烘干", 100: "换气",
    101: "暂停", 102: "预约", 103: "保管",
}
_ERROR_VALUES = {
    0: "无故障", 1: "E01 热敏电阻短路", 2: "E02 热敏电阻开路",
    3: "E03 机器不加热", 4: "E04 进水阀故障", 5: "E05 溢水",
    6: "E06 机器加热异常", 7: "E07 高水位异常", 8: "E10 进水异常",
    9: "E11 分水阀故障", 10: "E12 缺水",
}


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


def _empty_state(_device: DeviceContext) -> Mapping[str, Any]:
    return {}


def _make_level_select(sid: str, key: str, name: str):
    def state(device: DeviceContext) -> Mapping[str, Any]:
        value = _number(device.value(sid, "value"))
        label = (
            _LEVEL_OPTIONS[int(value) - 1]
            if value is not None and 1 <= int(value) <= 6
            else None
        )
        return {"current_option": label}

    async def set_option(device: DeviceContext, data: Mapping[str, Any]) -> None:
        option = str(data.get("option"))
        if option not in _LEVEL_OPTIONS:
            raise ValueError(f"unknown {name} option: {option}")
        await device.async_send_service(
            sid, {"value": _LEVEL_OPTIONS.index(option) + 1}
        )

    return EntitySpec(
        platform="select",
        key=key,
        name=name,
        state=state,
        metadata={"options": _LEVEL_OPTIONS},
        actions={"select_option": set_option},
    )


class Product2N2VAdapter:
    """Keep all 2N2V entity and command choices in this file."""

    prod_id = "2N2V"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="switch",
                key="power",
                name="电源",
                state=lambda device: {
                    "is_on": _bool(device.value("switch", "on")) is True
                },
                actions={
                    "turn_on": lambda d, _data: d.async_send_service("switch", {"on": 1}),
                    "turn_off": lambda d, _data: d.async_send_service("switch", {"on": 0}),
                },
            )
        ]

        if context.has_service("mode"):
            async def set_mode(device: DeviceContext, data: Mapping[str, Any]) -> None:
                option = str(data.get("option"))
                if option not in _MODE_VALUES:
                    raise ValueError(f"unknown dishwasher mode: {option}")
                await device.async_send_service("mode", {"mode": _MODE_VALUES[option]})

            entities.append(
                EntitySpec(
                    platform="select",
                    key="wash_mode",
                    name="洗涤模式",
                    state=lambda device: {
                        "current_option": next(
                            (
                                label
                                for label, raw in _MODE_VALUES.items()
                                if _number(device.value("mode", "mode")) == raw
                            ),
                            None,
                        )
                    },
                    metadata={"options": _MODE_OPTIONS},
                    actions={"select_option": set_mode},
                )
            )

        if context.has_service("action"):
            async def start(device: DeviceContext, _data: Mapping[str, Any]) -> None:
                await device.async_send_service("action", {"action": 1})

            async def pause(device: DeviceContext, _data: Mapping[str, Any]) -> None:
                await device.async_send_service("action", {"action": 0})

            entities.append(
                EntitySpec(
                    platform="button", key="start", name="启动",
                    state=_empty_state, actions={"press": start},
                )
            )
            entities.append(
                EntitySpec(
                    platform="button", key="pause", name="暂停",
                    state=_empty_state, actions={"press": pause},
                )
            )

        if context.has_service("rinse"):
            entities.append(_make_level_select("rinse", "rinse_level", "亮碟剂档位"))
        if context.has_service("salt"):
            entities.append(_make_level_select("salt", "salt_level", "软水盐档位"))

        if context.has_service("appointment"):
            async def set_appointment(
                device: DeviceContext, data: Mapping[str, Any]
            ) -> None:
                value = _number(data.get("value"))
                if value is None:
                    raise ValueError("appointment value is required")
                value = min(max(int(value), 0), 1440)
                await device.async_send_service("appointment", {"time": value})

            entities.append(
                EntitySpec(
                    platform="number",
                    key="appointment",
                    name="预约时间",
                    state=lambda device: {
                        "native_value": _number(device.value("appointment", "time"))
                    },
                    metadata={"min": 0, "max": 1440, "step": 1, "unit": "分钟"},
                    actions={"set_value": set_appointment},
                )
            )

        if context.has_service("status"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="work_status",
                    name="工作状态",
                    state=lambda device: {
                        "native_value": _STATUS_VALUES.get(
                            _number(device.value("status", "status"))
                        )
                    },
                )
            )
        if context.has_service("remainTime"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="remain_time",
                    name="剩余时间",
                    state=lambda device: {
                        "native_value": _number(device.value("remainTime", "value"))
                    },
                    metadata={"unit_of_measurement": "s"},
                )
            )
        if context.has_service("curTemp"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="current_temp",
                    name="舱内温度",
                    state=lambda device: {
                        "native_value": _number(device.value("curTemp", "value"))
                    },
                    metadata={"unit_of_measurement": "℃"},
                )
            )
        if context.has_service("errorTip"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="error_code",
                    name="故障代码",
                    state=lambda device: {
                        "native_value": _ERROR_VALUES.get(
                            _number(device.value("errorTip", "errorCode"))
                        )
                    },
                )
            )
        if context.has_service("doorOpen"):
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="door_open",
                    name="门开合",
                    state=lambda device: {
                        "is_on": _bool(device.value("doorOpen", "value")) is True
                    },
                )
            )
        return tuple(entities)


ADAPTER = Product2N2VAdapter()
