---
name: huawei-hilink-adapter
description: Analyze and assemble Huawei HiLink MQTT commands and device state synchronization for community adapters. Use for prodId/deviceTypeId/sid/st analysis, official service-composition rules, payload targets, command sequencing, ACK handling, and deviceDataChanged state merging.
metadata:
  short-description: Huawei HiLink MQTT command and sync helper
---

# Huawei HiLink MQTT 适配辅助

这个 Skill 只处理华为协议层：如何从 Profile 和官方服务模型确定服务成员、组装 MQTT 命令、验证 ACK，以及同步 `deviceDataChanged` 状态。


## 证据优先级

按以下顺序判断协议行为：

1. 真实设备的官方 App 控制捕获。
2. 该 `prodId` 的官方插件/运行时调用。
3. 本 Skill 预置的 `deviceServiceHelp` 和 `profileDataHelp`。
4. 设备 Product Profile、云端实际服务清单。
5. 通用协议推断；只能用于只读解析，不能直接生成写命令。

如果高优先级证据和低优先级配置冲突，以高优先级证据为准，并记录冲突。

## 协议对象

- `prodId`、`deviceTypeId`：产品和设备类型匹配键。
- `sid`：服务实例的协议主键。命令目标和状态缓存都按 `(devId, sid)` 处理。
- `st`：服务类型元数据。它不是服务顺序，也不是可靠的命令顺序。
- `characteristicName`：服务内部字段名，必须来自 Profile 或真实捕获。
- `serviceId` 表达式：官方服务组合模型中的逻辑成员关系，例如 `switch&brightness`。
- MQTT `services[]` 顺序：当前消息携带更新的排列，不承载组合语义或发送顺序。

## 分析流程

1. 收集 `prodId`、`deviceTypeId`、Product Profile、云端实际服务清单和脱敏 MQTT/官方调用捕获。
2. 优先读取仓库内 `references/official/` 的四个预置资源，并记录版本号。
3. 标准化 Profile：保留每个 `sid`、`serviceType`、characteristic、类型、权限、范围和枚举。
4. 用 `deviceServiceHelp` 按 `deviceTypeId` 和 `trustProdIds` 查找服务组合；精确产品匹配优先于设备类型匹配。
5. 解析组合表达式：
   - `&` 表示同一协议能力的成员服务，不自动证明发送顺序。
   - `|` 表示并列数据成员，不表示任选一个，也不表示 MQTT 顺序。
6. 用 `profileDataHelp` 确定状态字段来源和缩放，例如 `temperature/current`、`{temperature/current}/10`。
7. 为每个控制动作建立协议命令计划：每一步明确 `sid`、payload、顺序、失败策略、ACK 和状态确认条件。
8. 为每个状态事件建立同步计划：按 `devId` 路由，按 `sid` patch，按 `ts` 处理旧消息。
9. 用脱敏 fixture 验证最终 target、body、ACK 和状态合并结果。

## MQTT 命令规则

云端服务命令的目标通常是：

```text
target = /devices/{devId}/services/{sid}
body   = 该 sid 的 characteristic payload
```

官方 App 的调用层次是：

```text
产品控制入口
  → HWMqttViewModel / HWDeviceManager
  → HWMqttRequest + HWMqttHeader
  → common_mqtt_sdk.HWMqttClient
  → MQTT Broker
```

命令计划必须遵守：

- `st` 不进入 target；除非真实捕获明确证明它进入 body，否则也不把 `st` 放入 body。
- 单个 `sid` 的 body 只包含该服务的 characteristic 数据。
- 同一设备、同一 `sid` 默认单飞。
- 同一组合能力的多步命令默认顺序执行；没有证据时标记 `order: unknown`。
- 组合配置只能说明成员关系，不能单独证明命令顺序。
- 区分云端 MQTT 路径和官方 App 的 local-control 路径；没有本地控制证据时不要混用。
- 某一步失败时默认中止后续步骤，除非设备测试证明可以继续。

### ACK 与状态确认

```text
PUBACK          ≠ 业务 ACK
commandRsp      = 云端命令处理结果
deviceDataChanged = 设备状态来源
```

`commandRsp.body.errcode == 0` 只代表云端接受/处理成功，不应直接写入设备当前状态。

服务端返回的 `requestId` 可能与出站 request id 不一致。默认使用：

```text
(connection_generation, devId, sid)
```

作为当前单飞命令的主关联键；原始 request id 只作为辅助诊断字段。

## MQTT 状态同步规则

对 `deviceDataChanged`：

```text
decode envelope
  → 检查 header.notifyType
  → 按 body.devId 路由
  → 遍历 body.services[]
  → 按 sid 找状态槽
  → 只 patch data 中出现的字段
  → 按 ts 丢弃旧更新
```

单个服务项通常具有：

```json
{
  "sid": "brightness",
  "st": "brightness",
  "ts": "20260901T010203Z",
  "data": {"brightness": 80}
}
```

必须做到：

- 状态主键使用 `(home_id, dev_id, sid)` 或等价的设备范围键。
- 本次消息未出现的字段保持旧值。
- 一条消息含多个 `sid` 时逐项处理，不依赖数组位置。
- 多 `sid` 的组合状态由上层适配器读取各自缓存后计算。
- 不把一个服务的状态伪造成另一个服务。
- 没有状态确认时，不把命令期望值冒充设备实际值。

## 失败关闭

遇到以下情况，停止自动写入并输出协议缺口：

- Profile 没有目标 `sid` 或 characteristic。
- 设备实际服务清单没有目标 `sid`。
- 只有 `deviceServiceHelp` 组合信息，没有命令顺序证据。
- 同一字段在不同 `prodId` 上有不同缩放或枚举含义。
- ACK 成功但没有可验证的 `deviceDataChanged`/状态快照。
- 只能根据名称、`st` 或 MQTT 数组顺序猜测写入逻辑。

## 参考资料

- [protocol-model.md](references/protocol-model.md)
- [official/README.md](references/official/README.md)
- [official/deviceServiceHelp.json](references/official/deviceServiceHelp.json)
- [official/profileDataHelp.json](references/official/profileDataHelp.json)
- [official/deviceServiceHelpVersion.json](references/official/deviceServiceHelpVersion.json)
- [official/profileDataHelpVersion.json](references/official/profileDataHelpVersion.json)
