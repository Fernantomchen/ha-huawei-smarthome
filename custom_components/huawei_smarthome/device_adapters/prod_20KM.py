"""Product adapter for Huawei product 20KM.

产品: 鸿雁 WIFI 智能排插
厂商: 杭州鸿雁智能科技有限公司
型号: IHC8345A / deviceTypeId 01E / protocolType WiFi
Profile: https://smarthome-drcn.dbankcdn.com/device/guide/20KM/20KM.json

═══════════════════════════════════════════════════════════════════
为什么重写
═══════════════════════════════════════════════════════════════════

这台「鸿雁插排」（书房）身上只有 **5 个实体，全都是 2026-09-09 18:57
那一批泛化引擎的产物**，key 就是裸的字段名：

    switch / switch1 / switch2 / switch3 / switch4

问题：

  * 五个都叫「Switch」，HA 里 entity_id 被挤成
    ``hong_yan_cha_pai_switch`` / ``_1`` / ``_2`` / ``_3`` / ``_4``，
    **根本分不清哪个是总开关、哪个是几号插孔**；
  * Profile 里明明白白有的 **童锁（switchLock）** 和
    **断电记忆（protect.status）** 完全没被映射；
  * 每个插孔还有一个 ``name`` 字段（厂商 App 里可以给插孔改名），也没用上。

本版的 7 个 key 与历史上的 5 个 **全部零重合**，旧实体可以一次性删干净。

═══════════════════════════════════════════════════════════════════
⚠️ 文件名：prod_20KM.py（大写 KM），覆盖同名文件
═══════════════════════════════════════════════════════════════════

上游已合并过早期版本（PR #71，仅暴露 6 个 switch 实体），本文件是对它的
**增强更新**：补全断电记忆 select、插孔自定义名、Profile 声明门控。

这里沿用大写 ``KM`` 只有一个理由：**上一轮交付的修复包里，这个文件就叫
``prod_20KM.py``**。如果你已经把那份装上过，那用同名覆盖是安全的；
反过来，如果我这次交付成 ``prod_20km.py``，在 Linux 上就是**第二个文件**，
``loader.py`` 会把两个都加载，``casefold()`` 后 prod_id 相同 →

    ValueError: duplicate product adapter: 20KM

→ config entry setup 失败 → **整个集成起不来，所有华为设备掉线**。

**安装前确认一下** ``device_adapters/`` 目录里没有第二个大小写变体
（``prod_20km.py`` 和 ``prod_20KM.py`` 不能同时存在）。

═══════════════════════════════════════════════════════════════════
实体清单（7 个）
═══════════════════════════════════════════════════════════════════

   outlet_master         switch 总开关       <- switch.on
   outlet_1 .. outlet_4  switch 插孔 1..4    <- switch1..4.on
   child_lock_switch     switch 童锁         <- switchLock.on
   power_loss_behavior   select 断电记忆     <- protect.status

插孔显示名**优先读设备上的自定义名**（``switchN.name``，厂商 App 里设的，
比如「台灯」「充电器」），没设就回退成「插孔 N」。

═══════════════════════════════════════════════════════════════════
按你的取舍决定
═══════════════════════════════════════════════════════════════════

1. **插孔用设备自定义名**（你选的）。
   代价说清楚：名字是**建实体那一刻**读的，之后你在 App 里改插孔名，
   HA 这边的实体名**不会跟着变**（集成没有 text 平台，无法做成可编辑字段）。
   要改名就在 HA 里直接改实体名；想让新名字生效，需要删掉实体再重启 HA。
   另一面：如果你重启 HA 时设备正好离线，读不到自定义名，会回退成「插孔 N」。

2. **netInfo 不映射**（沿用 2MFF 的实测结论：这个服务在 WiFi 设备上完全不上报）。

3. **不映射的其余字段**：
   * ``switch1..4.name`` 虽然是 RW 字符串，但本集成**没有 text 平台**，
     做不出「在 HA 里给插孔改名」的实体 —— 只能读，不能写；
   * ``update.*``（OTA）—— 设备信息里已有 sw_version，且由 App 管理；
   * ``protect.status`` 只有 0/1 两个取值，做成 select 而不是 switch，
     因为它的语义是「断电后恢复成什么状态」，不是开/关。

═══════════════════════════════════════════════════════════════════
已知限制
═══════════════════════════════════════════════════════════════════

编写时这台设备 **offline**（5 个旧实体全部 unavailable），**没有真机实测**。
映射依据是官方 Profile + 同厂商 IHC8301C（prodId 203I）的兄弟产品对照
—— 两者的 switch / switchLock / protect 服务字段名完全一致。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

# ---------------------------------------------------------------- 服务标识

_SID_MAIN = "switch"
_SID_LOCK = "switchLock"
_SID_PROTECT = "protect"

_SLOTS = (1, 2, 3, 4)


def _slot_sid(index: int) -> str:
    return f"switch{index}"


# ---------------------------------------------------------------- 常量

# protect.status —— 取值与文案均对齐 Profile enumList
# （verify 脚本会断言这两张表与 Profile 一致，固件改描述时会立刻暴露）
_POWER_LOSS_OPTIONS: tuple[tuple[int, str], ...] = (
    (0, "默认开关状态(关)"),
    (1, "保持断电前状态"),
)


# ---------------------------------------------------------------- 值解析


def _as_bool(value: Any) -> bool | None:
    """华为 bool 字段会上报 1/0、"1"/"0"、True/False，统一解析。"""

    if value is None:
        return None
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


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Profile 辅助


def _declared(profile: Mapping[str, Any] | None, sid: str, field: str) -> bool:
    """Profile 里声明了这个服务字段吗。

    用它做门控：固件没声明的字段不建实体，避免出现永远 unavailable 的空壳。
    """

    if profile is None:
        return False
    for service in profile.get("services", ()):
        if not isinstance(service, Mapping) or service.get("serviceId") != sid:
            continue
        for item in service.get("characteristics", ()):
            if isinstance(item, Mapping) and item.get("characteristicName") == field:
                return True
    return False


# ---------------------------------------------------------------- 实体工厂


def _outlet_switch(key: str, name: str, sid: str) -> EntitySpec:
    """一个插孔/总开关：读 ``{sid: {on: 0|1}}``，写同结构。"""

    def state(context: DeviceContext) -> Mapping[str, Any]:
        return {"is_on": _as_bool(context.value(sid, "on"))}

    async def turn_on(context: DeviceContext, data: Mapping[str, Any]) -> None:
        del data
        await context.async_send_service(sid, {"on": 1})

    async def turn_off(context: DeviceContext, data: Mapping[str, Any]) -> None:
        del data
        await context.async_send_service(sid, {"on": 0})

    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=state,
        actions={"turn_on": turn_on, "turn_off": turn_off},
    )


def _slot_name(context: DeviceContext, index: int) -> str:
    """插孔显示名：优先用厂商 App 里设的自定义名，没设就回退「插孔 N」。

    只在建实体那一刻读一次 —— 之后在 App 里改名 HA 不会同步。
    """

    value = context.value(_slot_sid(index), "name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return f"插孔 {index}"


# ---------------------------------------------------------------- 适配器


class Product20KMAdapter:
    """鸿雁 WIFI 智能排插 IHC8345A。

    7 个实体，key 与历史版本零重合，每个都用 Profile 声明做过门控。
    """

    prod_id = "20KM"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        specs: list[EntitySpec] = []

        def supported(sid: str, field: str) -> bool:
            return context.has_service(sid) and _declared(profile, sid, field)

        # ---------- 总开关 ----------
        if supported(_SID_MAIN, "on"):
            specs.append(_outlet_switch("outlet_master", "总开关", _SID_MAIN))

        # ---------- 插孔 1..4 ----------
        for index in _SLOTS:
            sid = _slot_sid(index)
            if not supported(sid, "on"):
                continue
            specs.append(_outlet_switch(f"outlet_{index}", _slot_name(context, index), sid))

        # ---------- 童锁 ----------
        if supported(_SID_LOCK, "on"):
            specs.append(_outlet_switch("child_lock_switch", "童锁", _SID_LOCK))

        # ---------- 断电记忆（select）----------
        if supported(_SID_PROTECT, "status"):
            options = tuple(label for _value, label in _POWER_LOSS_OPTIONS)
            by_label = {label: value for value, label in _POWER_LOSS_OPTIONS}

            def power_loss_state(context: DeviceContext) -> Mapping[str, Any]:
                raw = _as_int(context.value(_SID_PROTECT, "status"))
                if raw is None:
                    return {"current_option": None}
                for value, label in _POWER_LOSS_OPTIONS:
                    if value == raw:
                        return {"current_option": label}
                # 固件给了没见过的取值：显示未知，不猜
                return {"current_option": None}

            async def select_power_loss(
                context: DeviceContext, data: Mapping[str, Any]
            ) -> None:
                option = data.get("option")
                value = by_label.get(str(option)) if option is not None else None
                if value is None:
                    raise ValueError(f"20KM unsupported power-loss option: {option!r}")
                await context.async_send_service(_SID_PROTECT, {"status": value})

            specs.append(
                EntitySpec(
                    platform="select",
                    key="power_loss_behavior",
                    name="断电记忆",
                    state=power_loss_state,
                    metadata={"options": list(options)},
                    actions={"select_option": select_power_loss},
                )
            )

        return tuple(specs)


ADAPTER = Product20KMAdapter()
