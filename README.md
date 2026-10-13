# chatgpt3api-mihomo

Status: current

独立部署的 Mihomo 代理服务，带中文订阅管理后台。与 `chatgpt3api` 分成两套 Docker Compose；后台通过宝塔反代独立域名访问。

镜像：`ghcr.io/suxinwl/chatgpt3api-mihomo:latest`。固定版本使用 `:v1.0.2`，支持 Linux amd64 / arm64，内核固定为 Mihomo v1.19.32。

支持：

- 添加多个 Clash/Mihomo YAML 或 VLESS Base64 订阅，改名、手动更新、按小时自动更新、切换和删除。
- 从文件或文本导入 YAML/JSON 的 `proxies` 节点、原始 VLESS 链接或 Base64 订阅。VLESS 链接支持 TCP、WS、gRPC 与 TLS/Reality、TCP Vision；YAML/JSON 中的 TUIC、Hysteria2、SOCKS5 等协议由内核校验。
- 选择节点、单节点测速、全部测速，以及 Auto 自动选择出口。
- 每个订阅可独立查看已保存的节点、逐个或全部测速并停止；未启用订阅也可测试，结果留在对应订阅中，当前出口和“节点选择”保持不变。
- 后台密码登录；订阅、当前选择和管理会话签名密钥持久化到 `/data`。
- 下载或校验失败时保留已保存的配置；切换失败时恢复原配置。

只导入节点，不会采用订阅中的规则、DNS、TUN、端口和控制器设置。订阅需要包含 1–512 个实际节点；仅包含 `proxy-providers` 的配置、其他协议的原始链接及 VLESS 的 XHTTP/mKCP 等传输需要先转换为本内核支持的 Clash/Mihomo YAML。不支持 YAML 别名。Base64 可以使用标准或 URL-safe 编码、换行和省略末尾补位；节点名称重复时，VLESS 导入会添加编号。下载、转换或校验失败会保留已保存的配置。第一次添加订阅会自动启用；当前订阅需先切换到其他订阅才能删除。

公开源码、示例和镜像不包含用户现有节点、订阅地址或密码。所有部署操作、宝塔设置和迁移步骤见 [部署说明](docs/runbooks/deployment.md)。

两个容器的连接：

| 服务 | 独立编排 | 对外访问 | 内部连接 |
| --- | --- | --- | --- |
| Mihomo 与订阅后台 | [compose.yaml](compose.yaml) | 宝塔 → `127.0.0.1:48800` | `mihomo:7890` |
| chatgpt3api | [平台编排](deploy/chatgpt3api.compose.yaml) | 保留原平台域名与 `127.0.0.1:48764` | 平台代理地址 `socks5h://mihomo:7890` |

订阅后台管理的是代理订阅与节点。ChatGPT 平台的上游账户仍在平台后台管理。

开发结构与验证、发布方式见 [文档索引](docs/README.md)。Mihomo 上游来源和分发说明见 [NOTICE](NOTICE)，本项目使用 [GPL-3.0-or-later](LICENSE)。
