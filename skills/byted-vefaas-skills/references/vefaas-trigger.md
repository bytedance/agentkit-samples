# 触发器与 APIG Route

本页用于指导函数的 APIG 触发器，以及沙箱应用的网关路由配置。控制台里沙箱定制项叫“网关路由配置”，底层只支持 APIG。触发器/网关路由会影响线上访问入口；涉及写操作时必须先确认目标资源。

## 适用场景

先读本页：

- 用户要绑定 APIG 触发器、查看触发器、创建访问入口。
- 用户要管理 Timer、Kafka、RocketMQ、BMQ、TLS 等函数触发器。
- 用户要修改 APIG route 的 path、method、timeout、CORS 或完整 MatchRule / AdvancedSetting。
- 用户遇到 APIG 权限不足、route 找不到、函数 ID 不存在、访问地址不可用。
- 用户需要线上 HTTP 访问入口，而不只是 TestInvoke 测试。单纯测试函数调用属于函数管理流程，不需要先绑定触发器。
- 用户操作沙箱时，应使用“网关路由配置”的心智模型；不要暗示沙箱还有 Timer/Kafka/TOS 等其他触发器类型。

## 触发器列表

查看函数触发器：

```bash
vefaas fn trigger list --id <function-id> -o json
```

查看沙箱应用触发器：

```bash
vefaas sandbox trigger list --id <sandbox-application-id> -o json
```

沙箱列表命令保留 `trigger` 是为了兼容 CLI 命名；对用户解释时称为网关路由配置。

如果当前目录有 `.vefaas/config.json`，CLI 可能自动使用 linked function / sandbox。写操作前仍要用 list/info 确认目标资源和当前账号一致。

## 绑定 APIG 触发器

绑定前确认函数已经发布；未发布函数不能稳定绑定 APIG 触发器。先查可用 gateway：

```bash
vefaas gateway list --first
```

为函数绑定：

```bash
vefaas trigger apig --id <function-id> --gateway-id <gateway-id>
vefaas trigger apig bind --id <function-id> --gateway-id <gateway-id> --service-id <service-id>
```

为沙箱应用绑定：

```bash
vefaas sandbox trigger apig --id <sandbox-application-id> --gateway-id <gateway-id>
```

绑定会创建或关联 APIG service、upstream 和 route。沙箱也可以在创建应用时直接指定网关路由配置，见 [沙箱管理](vefaas-sandbox.md)。遇到 APIG 权限不足时，优先提示用户切换 AK/SK 登录并给出 https://console.volcengine.com/iam/keymanage，或到控制台操作；不要反复重试同一个 SSO 凭据。

## 编辑 APIG Route

route 编辑会影响线上访问入口。执行前先确认 route ID、函数/沙箱 ID、当前 path/methods 和预期修改。

已知 route ID 时：

```bash
vefaas trigger apig update --route-id <route-id> --path /api --methods GET,POST
vefaas trigger apig update --route-id <route-id> --timeout 30
vefaas trigger apig update --route-id <route-id> --cors
vefaas trigger apig update --route-id <route-id> --no-cors
```

让 CLI 从函数已绑定 APIG 触发器自动定位 route：

```bash
vefaas trigger apig edit --id <function-id> --path /api
vefaas sandbox trigger apig edit --id <sandbox-application-id> --path /api
```

如果一个函数关联多个 APIG route，CLI 会要求显式传 `--route-id`。不要自行猜一个 route 更新。

需要完整替换 APIG MatchRule / AdvancedSetting 时，优先先看 help：

```bash
vefaas trigger apig update --help
```

再使用 JSON 参数：

```bash
vefaas trigger apig update --route-id <route-id> --match-rule-json '{"Method":["GET"],"Path":{"MatchType":"Prefix","MatchContent":"/api"}}'
vefaas trigger apig update --route-id <route-id> --advanced-setting-json '{"TimeoutSetting":{"Enable":true,"Timeout":30},"CorsPolicySetting":{"Enable":false}}'
```

CLI 会清理空的 `Header` / `QueryString` 匹配项。复杂 APIG 能力如果高阶命令无法覆盖，再读 [OpenAPI 调用](vefaas-openapi.md)，并使用 `vefaas api <Action> --service apig --api-version 2022-11-12 --help` 查看字段。

## 非 APIG 函数触发器

Timer、Kafka、RocketMQ、BMQ、TLS 触发器使用类型化子命令管理。复杂配置优先放在 JSON 文件里，并用 `--body @file.json` 传入；也支持直接 JSON 字符串或从 stdin 读取，具体以 help 为准。

```bash
vefaas fn trigger timer create --id <function-id> --body @timer.json
vefaas fn trigger kafka get --id <function-id> --trigger-id <trigger-id> -o json
vefaas fn trigger rocketmq update --id <function-id> --trigger-id <trigger-id> --body @trigger.json
vefaas fn trigger tls delete --id <function-id> --trigger-id <trigger-id>
```

写操作前先用 `vefaas fn trigger list --id <function-id> -o json` 确认当前触发器 ID、类型和配置。删除或更新生产触发器前必须向用户展示目标 trigger ID 和影响。

TOS 触发器涉及 TOS Bucket Notification 等跨服务配置，当前不要把它当作普通函数触发器 CRUD；需要时先确认控制台语义，再走 OpenAPI 或提示用户在控制台处理。

## 排障顺序

1. `vefaas login --check`：确认凭据类型、来源和环境。
2. `vefaas fn info --id <function-id>` 或 `vefaas sandbox info --id <sandbox-application-id>`：确认当前账号能访问资源。
3. `vefaas fn trigger list --id <function-id> -o json`：确认触发器和 APIG 关联。
4. 需要 APIG 底层字段时，再查 `vefaas api ListRoutes20221112 --service apig --api-version 2022-11-12 --help`。

## 安全与确认

- 不要明文输出 AK/SK、session token、OAuth token 或 `.env` value。
- 修改 route 前必须确认目标 ID 和预期变更。
- 生产 route 的 path/method/CORS/timeout 修改属于高风险操作，不要静默加 `--yes`。
- 如果本地 `.vefaas/config.json` 指向的 function 在当前账号下 `ResourceNotFound`，先提示账号/资源不一致，不要继续做写操作。
