"""Product adapter for Huawei product 2MFF (Z1-Z3B-101/ZK).

产品: 佛山照明智能插座（转换插座）
厂商: 佛山照明 (foshanlighting)
型号: Z1-Z3B-101/ZK (deviceTypeId 01D, uiType H5, WiFi)

Profile 服务一览（含未映射项）:
  switch.on                 bool   RW  1=开 0=关      电源开关  -> power_switch
  indicator.on              bool   RW  1=开 0=关      指示灯    -> indicator_switch
  childLockSwitch.on        bool   RW  1=开 0=关      童锁      -> child_lock_switch
  power.current             int    R   当前功率 (W)             -> active_power
  power.maximum             int    R   峰值功率 (W)     固件恒 0，不映射
  power.load                int    R   负载百分比 (%)   固件恒 0，不映射
  electric.voltage          int    R   电压 (V)                 -> mains_voltage
  electric.current          int    R   电流 (mA)                -> line_current
  electric.totalElectricity float  R   总用电量 (kWh) 优先      -> energy_total
  electric.totalConsum      int    R   总用电量 (kWh) 回退      -> energy_total
  electric.saveConsum       int    R   节约电量        语义不明，不映射
  faultDetection.code       enum   R   0=正常 1=电流过载        -> overload_warning
  faultDetection.status     enum   R   0=正常 1=设备运行异常    -> device_malfunction
  netInfo.*                 设备不上报，全部不映射
  timer.* / delay.*         定时与倒计时 array[object]，无法映射
  update.*                  固件升级（低频运维功能，不映射）

关于电流单位：Profile 上报 **mA**，保持原样输出。
HA 的 current device_class 原生支持 mA，UI 与统计会按需自动换算。

关于固件版本：部分设备上报 update.version 为空串（尚未上报），
转为 None 以免实体显示成空白。

注意：设备在线状态由华为云端决定，离线时本集成会把全部实体置为
unavailable（框架行为，适配器无法覆盖），需检查设备供电与 Wi-Fi。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_SID_SWITCH = "switch"
_SID_INDICATOR = "indicator"
_SID_LOCK = "childLockSwitch"
_SID_POWER = "power"
_SID_ELECTRIC = "electric"
_SID_FAULT = "faultDetection"
_SID_UPDATE = "update"


def _as_bool(value: Any) -> bool | None:
    """华为 bool 字段会上报 1/0、"1"/"0"、True/False，统一解析。"""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"1", "true", "on", "open"}:
            return True
        if lowered in {"0", "false", "off", "close"}:
            return False
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return None if number is None else int(number)


def _switch_spec(key: str, name: str, sid: str) -> EntitySpec:
    """可读写布尔开关：state 与 turn_on/turn_off 成对生成。"""

    def state(context: DeviceContext) -> Mapping[str, Any]:
        return {"is_on": _as_bool(context.value(sid, "on"))}

    async def set_on(context: DeviceContext, data: Mapping[str, Any]) -> None:
        del data
        await context.async_send_service(sid, {"on": 1})

    async def set_off(context: DeviceContext, data: Mapping[str, Any]) -> None:
        del data
        await context.async_send_service(sid, {"on": 0})

    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=state,
        actions={"turn_on": set_on, "turn_off": set_off},
    )


def _numeric_sensor(
    key: str,
    name: str,
    sid: str,
    field: str,
    unit: str,
    device_class: str | None = None,
    state_class: str | None = None,
) -> EntitySpec:
    """数值传感器。

    无数据时返回 ``None`` 而不是 0 —— 设备刚上线还没上报时谎报 0
    会让能源统计出现假的低谷。
    """

    def state(context: DeviceContext) -> Mapping[str, Any]:
        raw = _as_float(context.value(sid, field))
        if raw is None:
            return {"native_value": None}
        if abs(raw - round(raw)) < 1e-9:
            return {"native_value": float(round(raw))}
        return {"native_value": round(raw, 3)}

    metadata: dict[str, Any] = {"unit": unit}
    if device_class:
        metadata["device_class"] = device_class
    if state_class:
        metadata["state_class"] = state_class
    return EntitySpec(
        platform="sensor",
        key=key,
        name=name,
        state=state,
        metadata=metadata,
    )


def _energy_state(context: DeviceContext) -> Mapping[str, Any]:
    """总用电量：优先浮点 totalElectricity，缺失回退整型 totalConsum。"""

    raw = context.value(_SID_ELECTRIC, "totalElectricity")
    if raw is None:
        raw = context.value(_SID_ELECTRIC, "totalConsum")
    value = _as_float(raw)
    return {"native_value": None if value is None else round(value, 3)}


def _overload_state(context: DeviceContext) -> Mapping[str, Any]:
    # faultDetection.code: 0=正常, 1=电流过载
    code = _as_int(context.value(_SID_FAULT, "code"))
    if code is None:
        return {"is_on": None}
    return {"is_on": code != 0}


def _fault_state(context: DeviceContext) -> Mapping[str, Any]:
    # faultDetection.status: 0=运行正常, 1=设备运行异常
    status = _as_int(context.value(_SID_FAULT, "status"))
    if status is None:
        return {"is_on": None}
    return {"is_on": status != 0}


def _firmware_state(context: DeviceContext) -> Mapping[str, Any]:
    """固件版本（update.version）。

    部分设备上报空串（尚未上报），转成 None 以免实体显示成空白。
    """

    raw = context.value(_SID_UPDATE, "version")
    if not isinstance(raw, str):
        return {"native_value": None}
    version = raw.strip()
    return {"native_value": version or None}


class Product2MFFAdapter:
    """佛山照明智能插座 (Z1-Z3B-101/ZK)。

    控制 ×3（电源 / 指示灯 / 童锁）、电力测量 ×4（功率 / 电压 / 电流 /
    总用电量）、故障 ×2（电流过载 / 设备异常），外加固件版本 ×1，共 10 个实体。

    注意：设备在线状态由华为云端决定，离线时本集成会把全部实体置为
    unavailable（框架行为，适配器无法覆盖），需检查设备供电与 Wi-Fi。
    """

    prod_id = "2MFF"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        del context  # 本产品实体固定，不依赖运行时状态
        return (
            # ---------- 控制（switch ×3）----------
            _switch_spec("power_switch", "电源开关", _SID_SWITCH),
            _switch_spec("indicator_switch", "指示灯", _SID_INDICATOR),
            _switch_spec("child_lock_switch", "童锁", _SID_LOCK),
            # ---------- 电力测量（sensor ×4）----------
            _numeric_sensor(
                "active_power", "实时功率", _SID_POWER, "current",
                "W", "power", "measurement",
            ),
            _numeric_sensor(
                "mains_voltage", "电压", _SID_ELECTRIC, "voltage",
                "V", "voltage", "measurement",
            ),
            # 设备上报毫安，保持原样；HA 的 current 类型原生支持 mA
            _numeric_sensor(
                "line_current", "电流", _SID_ELECTRIC, "current",
                "mA", "current", "measurement",
            ),
            EntitySpec(
                platform="sensor",
                key="energy_total",
                name="总用电量",
                state=_energy_state,
                metadata={
                    "unit": "kWh",
                    "device_class": "energy",
                    "state_class": "total_increasing",
                },
            ),
            # ---------- 故障（binary_sensor ×2）----------
            EntitySpec(
                platform="binary_sensor",
                key="overload_warning",
                name="电流过载",
                state=_overload_state,
                metadata={"device_class": "problem"},
            ),
            EntitySpec(
                platform="binary_sensor",
                key="device_malfunction",
                name="设备异常",
                state=_fault_state,
                metadata={"device_class": "problem"},
            ),
            # ---------- 运维信息（sensor ×1）----------
            EntitySpec(
                platform="sensor",
                key="firmware_version",
                name="固件版本",
                state=_firmware_state,
            ),
        )


ADAPTER = Product2MFFAdapter()
