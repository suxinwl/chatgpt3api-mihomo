# 独立部署与迁移

Status: current

## 1. 部署 Mihomo

在宝塔服务器新建独立编排目录，例如 `/www/server/panel/data/compose/chatgpt3api-mihomo`，保存仓库根目录的 `compose.yaml` 与 `.env.example`。也可直接克隆公开源码，容器运行时无需在服务器构建：

```bash
git clone https://github.com/suxinwl/chatgpt3api-mihomo.git
cd chatgpt3api-mihomo
cp .env.example .env
mkdir -p data
chmod 700 data
chmod 600 .env
```

编辑 `.env`：用户名默认 `admin`，`MIHOMO_ADMIN_PASSWORD` 填写至少 12 位独立密码，`PUBLIC_ORIGIN` 填实际后台地址，例如 `https://proxy.example.com`。密码中有 `$` 或 `#` 时使用单引号包住整个值，以免 Compose 插值或截断；真实 `.env` 不上传 Git。

```bash
docker compose pull
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:48800/health
```

健康接口返回 `{"status":"ok"}`。启动时未导入节点的代理拒绝转发；登录后添加第一个订阅会自动启用。8080 是后台服务，7890 同时支持 HTTP 和 SOCKS5；7890 未映射到公网，控制器 9091 仅在容器回环地址监听。

## 2. 宝塔反代独立域名

为后台新建独立站点，域名解析到当前服务器；在宝塔申请证书并开启 HTTPS，反代地址填 `http://127.0.0.1:48800`。参考 [Nginx 示例](../../deploy/nginx.conf.example)，保留 Host 请求头，设置 `client_max_body_size 10m` 与 60 秒读取超时。

`.env` 的 `PUBLIC_ORIGIN` 必须与浏览器地址完全一致，且不包含末尾 `/` 或子路径。使用根路径域名访问。此模板 `COOKIE_SECURE=true`，登录需要 HTTPS。若在隔离环境直接用 HTTP 测试，临时把编排的 `COOKIE_SECURE` 改成 `false`；公开 HTTPS 部署保持 `true`。

用 `.env` 中的用户名和密码登录。添加订阅时选择“订阅链接”或“导入配置”。链接响应支持 Clash/Mihomo YAML/JSON 或 VLESS Base64 订阅；导入配置支持文件、原始 VLESS 链接和 Base64 文本。格式限制见 [功能说明](../../README.md)。订阅列表仅显示来源主机名，不返回完整私密链接；编辑时链接留空保留原地址。导入配置的节点变更通过添加新配置后切换完成。

## 3. 连接独立平台容器

先启动 Mihomo，它创建 `chatgpt3api-egress` Docker 网络。平台独立编排使用 [chatgpt3api.compose.yaml](../../deploy/chatgpt3api.compose.yaml)，将其作为平台目录的 `docker-compose.yaml`，并参考 [环境变量示例](../../deploy/chatgpt3api.env.example) 在平台目录填写原有管理密钥和原有公网域名。

示例保留平台原有 runtime 卷名 `chatgpt3api-runtime`，数据目录、配置文件挂载与端口。平台原有域名应保留为实际使用的地址；不要填写 Mihomo 的后台域名。若实际部署路径不同，先修改绑定挂载路径。

```bash
# 在平台独立编排目录执行
docker compose up -d
```

在平台“代理管理”中使用 `socks5h://mihomo:7890`，检测后设为需要的代理组或默认出口。切换 Mihomo 订阅/节点会影响通过此地址建立的新连接；平台代理组名称无需随订阅变化。

## 4. 从原有组合编排迁移

1. 备份平台业务数据、配置、现有 Compose 和服务器私有节点 YAML；保留原平台 runtime 卷。节点备份只放在服务器私有目录。
2. 在旧平台编排目录执行 `docker compose stop mihomo`、`docker compose rm -f mihomo`，释放同名 `chatgpt3api-mihomo` 容器；平台服务可以继续运行。
3. 启动新的独立 Mihomo 编排，配置宝塔后台域名并登录，通过“导入配置”导入服务器原有节点配置。旧配置不复制到公开源码、镜像构建目录或 Git。
4. 在旧平台编排中移除原 `mihomo` 服务，并给平台添加 `external: true`、名称 `chatgpt3api-egress` 的网络，或使用提供的独立平台模板；保留原平台所有环境值与数据挂载。
5. 在平台目录执行 `docker compose up -d chatgpt3api`，随后确认 `socks5h://mihomo:7890` 检测成功，实际生图和历史图片正常。

平台原有账户、会话和图片仍由平台数据挂载保存。迁移无需删除原 runtime 卷，**不要执行 `docker compose down -v`**。本项目不会自动读取旧服务的私有节点配置。

## 5. 升级、备份、恢复

升级代理服务只需在其独立目录执行 `docker compose pull && docker compose up -d`，不会更新平台容器。镜像不覆盖 `/data` 中的订阅。

备份范围是 Mihomo 的 `.env` 和整个 `data/`。订阅链接、节点凭据与管理员签名密钥均属于私有数据。停掉 Mihomo 后备份或恢复 `data/`，保留目录权限 0700、文件权限 0600，再启动同版本镜像。备份不得上传公开仓库。

更新失败时后台显示“更新失败，继续使用已保存的配置”；检查订阅地址、证书和服务器公网连接。只支持公网 HTTP/HTTPS 订阅，拒绝内网目标和 HTTPS 降级跳转。失去后台登录密码时在 `.env` 修改密码并重建容器；已有登录 Cookie 会失效，订阅数据保留。

容器内核异常退出时管理服务尝试重新启动最后保存的配置。持续启动失败时检查 `docker compose logs --tail=100`、端口占用和数据卷权限。日志不会输出完整订阅链接或原始节点配置。
