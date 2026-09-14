# 官方协议参考数据

本目录预置从官方 Huawei SmartHome iOS App 提取的、与 MQTT 命令和状态同步有关的 JSON：

- `deviceServiceHelp.json`：设备类型、产品覆盖和多 `sid` 服务组合。
- `profileDataHelp.json`：标准数据名到 `sid/characteristic` 的读取和换算规则。
- 两个 `*Version.json`：对应配置版本。

当前预置版本为 `versionCode: 11`。预置的 `deviceServiceHelp.json` 已移除与 MQTT 服务组合无关的扩展字段；其协议组合字段保持不变。

这些文件是协议研究和社区适配参考数据，不是 MQTT 实现本身，也不包含账号、Token 或设备运行状态。使用时仍须用具体 Product Profile 和真实控制捕获验证命令权限、payload 和顺序。
