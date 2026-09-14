# Huawei HiLink MQTT 协议参考

## 预置官方资源

本 Skill 已在 `references/official/` 预置：

```text
deviceServiceHelp.json
profileDataHelp.json
deviceServiceHelpVersion.json
profileDataHelpVersion.json
```

默认优先读取仓库内副本；如果用户提供更新版本，使用更新版本并记录 `versionCode` 和来源。当前预置版本为 `11`。

## deviceServiceHelp：服务组合模型

结构重点：

```json
{
  "type": "Light",
  "scope": "home",
  "sequence": 6,
  "supportDevices": [
    {
      "deviceTypeId": "01B",
      "standard": 1,
      "serviceId": "switch&brightness",
      "trustProdIds": ["100z"]
    }
  ]
}
```

协议分析使用：

- `deviceTypeId`
- `standard`
- `serviceId`
- `trustProdIds`

`type/name/scope/sequence` 是官方分类元数据；`sequence` 是分类顺序，不是 sid 命令顺序。

已观察到的组合表达式：

```text
switch&brightness
switch&temperature
switch1&switch2
pm25|temperature|humidity
action&opener
mode&opener
motor&openLevel
```

解释规则：

- `&`：同一协议能力的成员服务。它不自动证明必须同时发送，也不自动证明先后顺序。
- `|`：并列数据成员。它不表示任选一个字段，也不表示 MQTT 数组顺序。
- `trustProdIds`：产品级覆盖优先于泛设备类型规则。
- `standard`：官方能力分类标记，不等于命令计划。

## profileDataHelp：状态字段归一化

典型规则：

```text
temperature/current
{temperature/current}/10
airDetector/temperature
{airDetector/humidity}/100
```

它用于确定：

- 状态读取的 `sid/field`。
- 单位和倍率转换。
- 产品之间的字段差异。

它不单独定义写命令。写命令仍需检查 Profile 的权限、范围、枚举和真实设备行为。

## Profile、sid、st

Profile 提供：

```text
sid/serviceId
serviceType/st
characteristicName
characteristicType
method/permission
min/max/step
enumList
```

状态项通常是：

```json
{
  "sid": "brightness",
  "st": "brightness",
  "ts": "20260901T010203Z",
  "data": {"brightness": 80}
}
```

实现应使用：

```text
(home_id, dev_id, sid)
```

作为状态槽主键。`st` 只作为元数据保存，不作为唯一索引、业务组合键或发送顺序。

官方 App 的本地服务表也使用：

```sql
PRIMARY KEY (devId, sid)
```

因此多个 sid 的关系是“分别缓存、上层读取组合”，而不是创建一个伪 sid。

## 官方 MQTT 调用模型

官方客户端的抽象调用链：

```text
产品控制入口
  → HWMqttViewModel / HWDeviceManager
  → HWMqttRequest + HWMqttHeader
  → common_mqtt_sdk.HWMqttClient
  → MQTT Broker
```

单服务命令通常使用：

```text
target = /devices/{devId}/services/{sid}
body   = {characteristicName: value}
```

不要把 `st` 或 `deviceServiceHelp.serviceId` 组合表达式直接当成 target；target 必须使用实际发送的单个 `sid`。

## 命令计划模板

```yaml
product:
  prod_id: 100z
  device_type_id: 01B
  profile_evidence: profile.json
  service_help_version: 11

group:
  expression: switch&brightness
  members: [switch, brightness]
  relation_evidence: deviceServiceHelp.json

commands:
  - name: turn_on_with_brightness
    steps:
      - sid: switch
        target: /devices/{devId}/services/switch
        body: {on: 1}
        order_evidence: runtime capture
      - sid: brightness
        target: /devices/{devId}/services/brightness
        body: {brightness: 80}
        order_evidence: runtime capture
    order: sequential
    ack_key: [connection_generation, devId, sid]
    state_confirmation:
      - sid: switch
        condition: data.on == 1
      - sid: brightness
        condition: data.brightness == 80
```

如果没有真实证据，`order` 必须写为 `unknown`。组合表达式本身不能填充这个字段。

## 状态同步计划

```text
MQTT envelope
  → header.notifyType == deviceDataChanged
  → body.devId
  → body.services[]
  → service_state[(devId, sid)]
  → patch data
  → compare ts
```

规则：

- `services[]` 可包含一个或多个 sid，逐项处理。
- 缺少的字段不清空旧状态。
- 数组顺序不参与语义判断。
- 旧 `ts` 的更新丢弃；没有时间戳时至少按接收顺序去重。
- 组合逻辑读取多个独立 sid 的缓存，不伪造服务事件。

## ACK 与真实状态

```text
PUBACK            = MQTT 发布层确认
commandRsp        = 云端命令处理结果
deviceDataChanged = 设备状态来源
```

`commandRsp.body.errcode == 0` 不等于设备已经达到目标状态。服务端返回的 request id 可能与出站 request id 不一致，因此同一设备/同一 sid 默认单飞，并用：

```text
(connection_generation, devId, sid)
```

作为主关联键，request id 只用于诊断。

## 适配器需要负责的部分

协议层之外，产品适配器仍然需要验证：

- 一个业务动作涉及哪些 sid。
- 每个 sid 的 characteristic payload。
- 多 sid 的真实顺序。
- 一步失败是否中止后续步骤。
- 哪些 `deviceDataChanged` 条件代表动作完成。
- 同一字段在不同产品上的倍率、枚举和特殊值。

通信层不应猜测这些信息；没有证据时输出待验证命令计划，而不是发送未经验证的命令。
