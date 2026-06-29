---
name: byted-acep-api
description: 通过本地 Python CLI 和 OpenAPI 客户端管理、排查火山云手机资源。适用于查询实例和资源、截图、执行命令、查看任务、检查应用、主机和机房容量、标签、DNS、路由，以及操作已授权的测试云手机实例。
license: Apache-2.0
version: 1.1.0
---

# 火山云手机 Skill

当用户要求查看或操作已配置测试业务下的火山云手机资源时，使用这个 skill。

## 运行约束

- 不要静态配置 DC。应根据用户请求或当前资源可用性选择 DC。
- 先通过 `list-products` 查业务 ID，再在每条命令里显式传入 `product_id`。
- 创建和订购资源时必须显式选择业务资源类型：云盘存储使用 `100`，本地存储使用 `200`。
- 更新实例镜像或规格时，优先先关机；涉及强制更新时，提醒用户确认可能带来的影响。
- 后付费实例资源组只支持复购。在订购后付费资源前，先确认该业务已经在火山云手机控制台下过单，并且能查到 `OrderId`。
- 截图优先使用直连方式 `get-presigned-edge-url --api-type TakeScreenshot`。
- `batch-screen-shot` 作为回退方式使用；当业务已配置截图存储且用户明确需要该链路时再用。
- 除非用户明确要求，否则不要输出签名 URL。
- 查询已安装应用时优先使用 `get-pod-app-list`；仅在确有需要时才回退到 Android `pm list packages`。
- 除非用户明确要求，否则不要输出 access key、secret key、Authorization header 或完整签名 URL。
- 创建、删除、开关机、重启、重置、安装/卸载、文件传输、应用启动/关闭，以及 Android 命令执行都属于有状态变更操作。除非用户明确要求执行该操作，否则先确认。

## 命令入口

以下示例默认在当前 skill 包目录下执行：

```bash
python3 scripts/vephone_cli.py <command> [args]
```

这个 skill 已内置 `scripts/vephone_cli.py` 和 `scripts/core/`，可以直接运行，不依赖仓库根目录下的实现。

命令以显式 flags 的形式暴露常用参数。除 `list-products` 等少数查询命令外，大多数业务命令都把 `product_id` 作为第一个位置参数；查看某个命令支持哪些过滤条件时，直接用 `python3 scripts/vephone_cli.py <command> -h`。如果认证配置不在默认位置，可以用 `--config /path/to/config.json` 指定配置文件路径；这个全局参数放在子命令前后都可以。

如果现有命令还没有覆盖到目标 OpenAPI Action，可以使用通用命令：

```bash
python3 scripts/vephone_cli.py action-call ListOperableProduct --json-body --param Count=10 --param CloudphoneProductType=5
python3 scripts/vephone_cli.py action-call GetProductResource --product-id <product_id>
python3 scripts/vephone_cli.py action-call SetProxy --json-body --params-json '{"ProductId":"<product_id>","PodIdList":["pod-1"],"ProxyStatus":1,"ProxyConfig":{"version":"v2","type":"socks5","address":"203.0.113.52","port":"12345"}}'
```

`action-call` 的 `--param` 使用 `Key=Value` 形式，`Value` 会优先按 JSON 解析，失败时按字符串处理，所以可以直接传 `true`、`123`、`[1,2]`、`{"k":"v"}`。注意在常见 shell 中如果不对 `Key=Value` 做引用/转义，形如 `--param Foo={"k":"v"}` 的双引号可能会被 shell 吞掉，导致程序实际收到 `Foo={k:v}` 并触发 JSON 解析失败；当 `Value` 含双引号、空格或复杂 JSON 时，请用单引号包裹整个 `Key=Value`（如 `--param 'Foo={"k":"v"}'` / `--param 'PodIdList=["pod-1"]'`），或优先使用 `--params-json`（如 `--params-json '{"Foo":{"k":"v"}}'`）。若希望强制按字符串传入 `true`/`123` 等，请使用 JSON 字符串形式：`--param Name='"123"'`。需要批量传参时用 `--params-json`；如果同时传了同名键，`--param` 会覆盖 `--params-json`。默认按 query string 调用，带 `--json-body` 时改为 JSON body。

## 实例管理

只读操作：

```bash
python3 scripts/vephone_cli.py list-products --count 10
python3 scripts/vephone_cli.py list-pods <product_id> --max-results 10
python3 scripts/vephone_cli.py list-pods <product_id> --configuration-code-list <code1,code2> --dc-list <dc1,dc2> --online-list 1,2 --next-token <token>
python3 scripts/vephone_cli.py detail-pod <product_id> <pod_id>
python3 scripts/vephone_cli.py get-pod-metric <product_id> <pod_id>
python3 scripts/vephone_cli.py get-pod-property <product_id> <pod_id>
```

有状态变更操作：

```bash
python3 scripts/vephone_cli.py create-pod <product_id> --name <name> --template-id <template_id> --configuration-code <code> --dc-id <dc> --resource-type 200 --image-id <image_id> --display-layout-id <layout_id> --phone-template-id <template_id>
python3 scripts/vephone_cli.py update-pod <product_id> <pod_id> --image-id <image_id> --display-layout-id <layout_id> --configuration-code <code>
python3 scripts/vephone_cli.py update-pod <product_id> <pod_id> --image-id <image_id> --force
python3 scripts/vephone_cli.py delete-pod <product_id> <pod_id>
python3 scripts/vephone_cli.py power-on-pod <product_id> <pod_id>
python3 scripts/vephone_cli.py power-off-pod <product_id> <pod_id>
python3 scripts/vephone_cli.py reboot-pod <product_id> <pod_id>
python3 scripts/vephone_cli.py reset-pod <product_id> <pod_id>
python3 scripts/vephone_cli.py create-pod-one-step <product_id> --configuration-code <code> --dc <dc> --app-list <app_id:version_id,...>
python3 scripts/vephone_cli.py update-pod-property <product_id> --pod-id <pod_id> --pod-settings '[{"SettingsName":"locale_language","SettingsType":"global","SettingsValue":"zh-CN","SettingsValueType":"string"}]'
python3 scripts/vephone_cli.py update-pod-resource-apply-num <product_id> --resource-set-id <resource_set_id> --apply-num <num>
python3 scripts/vephone_cli.py backup-pod <product_id> --pod-id-list <pod_id1,pod_id2>
python3 scripts/vephone_cli.py restore-pod <product_id> --pod-id-list <pod_id1,pod_id2>
python3 scripts/vephone_cli.py pod-mute <product_id> --pod-id <pod_id> --mute true --display-list <display1,display2>
python3 scripts/vephone_cli.py pod-adb <product_id> --pod-id <pod_id> --enable true
python3 scripts/vephone_cli.py pod-stop <product_id> --pod-id <pod_id>
python3 scripts/vephone_cli.py pod-data-delete <product_id> --pod-id <pod_id> --file-path-list </sdcard,/data/data> --package-list <pkg1,pkg2>
python3 scripts/vephone_cli.py set-proxy <product_id> --pod-id-list <pod_id1,pod_id2> --proxy-status 1 --proxy-config '{"version":"v2","type":"socks5","address":"203.0.113.52","port":"12345"}'
python3 scripts/vephone_cli.py get-proxy <product_id> --pod-id-list <pod_id1,pod_id2>
python3 scripts/vephone_cli.py backup-data <product_id> --pod-id-list <pod_id1,pod_id2> --backup-all false --include-path-list </data/app,/data/data> --exclude-path-list </data/anr>
python3 scripts/vephone_cli.py restore-data <product_id> --backup-data-id <backup_data_id> --pod-id-list <pod_id1,pod_id2>
python3 scripts/vephone_cli.py list-backup-data <product_id> --status completed --max-results 20
python3 scripts/vephone_cli.py delete-backup-data <product_id> --backup-data-id-list <backup_data_id1,backup_data_id2>
```

`list-pods` 支持通过 `--max-results` 和 `--next-token` 分页。`create-pod` 可以用 `--image-id` 指定初始镜像。`delete-pod`、`reset-pod`、`update-pod --force` 这类操作有明显影响，执行前先确认。像 `--app-list`、`--pod-settings`、`--specify-host-list`、`--proxy-config` 这类结构化参数，直接看对应命令的 `-h` 获取格式说明。

## 资源、DC、主机与镜像查询

```bash
python3 scripts/vephone_cli.py list-dcs <product_id>
python3 scripts/vephone_cli.py get-dc-bandwidth-daily-peak <product_id> <dc_id_list>
python3 scripts/vephone_cli.py list-pod-resources <product_id>
python3 scripts/vephone_cli.py get-product-resource <product_id>
python3 scripts/vephone_cli.py list-products --count 10
python3 scripts/vephone_cli.py list-configurations <product_id>
python3 scripts/vephone_cli.py list-instance-configuration-specs <product_id>
python3 scripts/vephone_cli.py list-phone-templates <product_id>
python3 scripts/vephone_cli.py get-phone-template <product_id> <phone_template_id>
python3 scripts/vephone_cli.py list-hosts <product_id>
python3 scripts/vephone_cli.py detail-host <product_id> <host_id>
python3 scripts/vephone_cli.py update-host <product_id> <host_id1,host_id2> --configuration-code <pod_config_code>
python3 scripts/vephone_cli.py reboot-host <product_id> <host_id1,host_id2> --force
python3 scripts/vephone_cli.py reset-host <product_id> <host_id1,host_id2> --force
python3 scripts/vephone_cli.py list-image-resources <product_id>
python3 scripts/vephone_cli.py list-aosp-images <product_id> --is-public --max-results 20
python3 scripts/vephone_cli.py list-aosp-images <product_id> --max-results 20
python3 scripts/vephone_cli.py get-image-preheating <product_id> <image_id>
```

`list-image-resources` 用于查看当前业务正在使用的镜像资源。`list-aosp-images --is-public` 查询公共镜像；省略 `--is-public` 则查询自定义镜像。

创建实例前，先看 `list-pod-resources`，选择有可用余量的 `(ConfigurationCode, Dc)` 组合，并带上匹配的 `--resource-type`。

资源订购操作属于有状态变更，并且可能产生费用。后付费实例资源组只适用于已有下单历史的业务，执行前先确认。

本地存储主机订购时，明确传目标 pod 规格、主机类型、机房、数量和资源类型：

```bash
python3 scripts/vephone_cli.py subscribe-resource-auto \
  <product_id> \
  --configuration-code <pod_config_code> \
  --server-type-code <host_server_type_code> \
  --dc <dc> \
  --apply-num <num> \
  --resource-type 200 \
  --charge-type host_post_daily \
  --region <region> \
  --volc-region inner
```

温州 03-ppe 双开规格示例：

```bash
python3 scripts/vephone_cli.py subscribe-resource-auto \
  <product_id> \
  --configuration-code g3.pod8c24g.type2 \
  --server-type-code g3.host8c24g256g \
  --dc zjwz-ctcucm-03-47frx0k0 \
  --apply-num 3 \
  --resource-type 200 \
  --charge-type host_post_daily \
  --region cn-east \
  --volc-region inner
```

复购前，先通过现有订单或资源记录确认该后付费资源组有下单历史。订购或退订后，用 `list-pod-resources` 和 `list-hosts` 做结果校验。

续费与退订：

```bash
python3 scripts/vephone_cli.py renew-resource-auto <product_id> --resource-set-id <resource_set_id> --term <n> --period <period> --round-id <round_id>
python3 scripts/vephone_cli.py unsubscribe-host-resource <product_id> <host_id1,host_id2> --force
```

执行退订后，继续用资源列表和主机列表确认主机/资源数量变化。

云盘存储业务使用 `ResourceType=100`，本地存储业务使用 `ResourceType=200`。

## 应用管理

只读操作：

```bash
python3 scripts/vephone_cli.py get-pod-app-list <product_id> <pod_id>
python3 scripts/vephone_cli.py list-apps <product_id>
python3 scripts/vephone_cli.py detail-app <product_id> <app_id>
python3 scripts/vephone_cli.py list-app-version-deploys <product_id> <app_id>
python3 scripts/vephone_cli.py get-app-crash-log <product_id> <pod_id1,pod_id2> --start-time <unix_seconds> --end-time <unix_seconds>
```

有状态变更操作：

```bash
python3 scripts/vephone_cli.py install-app <product_id> <pod_id> <app_id> <version_id>
python3 scripts/vephone_cli.py launch-app <product_id> <pod_id> <package_name>
python3 scripts/vephone_cli.py close-app <product_id> <pod_id> <package_name>
python3 scripts/vephone_cli.py uninstall-app <product_id> <pod_id> <app_id>
python3 scripts/vephone_cli.py auto-install-app <product_id> --pod-id-list <pod_id1,pod_id2> --download-url <url>
```

`auto-install-app` 既可以通过下载地址安装，也可以结合镜像路径做批量安装。具体参数组合直接查看 `python3 scripts/vephone_cli.py auto-install-app -h`。

## 截图、文件与命令操作

截图：

```bash
python3 scripts/vephone_cli.py get-presigned-edge-url <product_id> <pod_id> \
  --api-type TakeScreenshot \
  --payload RoundId=<unique_round_id> \
  --payload MimeType=png \
  --timeout 5 \
  --ttl 60

python3 scripts/vephone_cli.py batch-screen-shot <product_id> <pod_id>
```

普通截图优先使用 `get-presigned-edge-url --api-type TakeScreenshot`。`product_id` 和 `pod_id` 都是位置参数；如果用户只是想看截图结果，优先走直连截图链路。`batch-screen-shot` 作为回退方式保留，适合业务已配置截图存储且明确要走该能力的场景。

直连边缘 URL：

```bash
python3 scripts/vephone_cli.py get-presigned-edge-url <product_id> <pod_id> \
  --api-type TakeScreenshot \
  --payload RoundId=<unique_round_id> \
  --payload MimeType=png \
  --timeout 5 \
  --ttl 60
```

`get-presigned-edge-url` 是截图和直连访问的首选链路，其中普通截图优先使用 `--api-type TakeScreenshot`。签名 URL 属于敏感信息，除非用户明确要求，否则不要直接输出。不同场景下的 `--api-type`、`--api-path` 和 `--payload` 组合较多，直接查看 `python3 scripts/vephone_cli.py get-presigned-edge-url -h`。

如果用户明确要求访问 sandbox，可以使用以下命令：

```bash
python3 scripts/vephone_cli.py get-presigned-edge-url <product_id> <pod_id> --api-type Sandbox --api-path /sandbox/ws
python3 scripts/vephone_cli.py get-presigned-edge-url <product_id> <pod_id> --api-type Sandbox --api-path /sandbox/exec
python3 scripts/vephone_cli.py get-presigned-edge-url <product_id> <pod_id> --api-type Sandbox --api-path /sandbox/healthz
```

除非用户明确要求，否则不要执行 sandbox 直连访问测试。

录屏：

```bash
python3 scripts/vephone_cli.py start-recording <product_id> <pod_id> --duration-limit 60 --round-id <unique_round_id>
python3 scripts/vephone_cli.py stop-recording <product_id> <pod_id>
```

文件：

```bash
python3 scripts/vephone_cli.py push-file <product_id> <pod_id> ./app.apk /sdcard/Download/app.apk --overwrite
python3 scripts/vephone_cli.py pull-file <product_id> <pod_id> /sdcard/Download/file.txt --output ./file.txt
```

`push-file` 用于上传本地文件，`pull-file` 用于下载实例内文件到本地路径。

命令执行：

```bash
python3 scripts/vephone_cli.py run-command <product_id> <pod_id> "cmd"
python3 scripts/vephone_cli.py run-sync-command <product_id> <pod_id> "cmd" --permission-type root --timeout-second 10 --result-length 10240
```

诊断时使用无害命令（`ls`、`echo`、`pm list packages`）。会修改文件、安装包、修改设置，或启动/停止应用的命令都属于有状态变更操作。

对已聚焦的 Android 输入框，可以通过 IME 命令输入中文和英文：

```bash
python3 scripts/vephone_cli.py run-sync-command <product_id> <pod_id> 'ime inject_text "你好"'
python3 scripts/vephone_cli.py run-sync-command <product_id> <pod_id> 'ime inject_text "hello world"'
python3 scripts/vephone_cli.py run-sync-command <product_id> <pod_id> 'ime clear_input_text'
```

如果是替换已有内容，先用 `ime clear_input_text`，再用 `ime inject_text`。这些命令要求目标输入框已经处于聚焦状态，通常需要先通过 `input tap x y` 点击。

`pull-logcat` 用于拉取实例日志。支持输出路径、断点续传和分片相关参数；具体参数直接查看 `python3 scripts/vephone_cli.py pull-logcat -h`。

```bash
python3 scripts/vephone_cli.py pull-logcat <product_id> <pod_id> --output ~/Downloads/logcat_<pod_id>
python3 scripts/vephone_cli.py pull-logcat <product_id> <pod_id> --chunk-size 800 --concurrency 5 --retries 3
python3 scripts/vephone_cli.py pull-logcat <product_id> <pod_id> --resume
```

如果只需要常规日志导出，直接使用最简单的 `pull-logcat` 命令即可。

## 任务、布局、标签与网络查询

任务：

```bash
python3 scripts/vephone_cli.py list-tasks <product_id>
python3 scripts/vephone_cli.py get-task-info <product_id> <task_id>
```

屏幕布局：

```bash
python3 scripts/vephone_cli.py list-display-layouts <product_id>
python3 scripts/vephone_cli.py detail-display-layout <product_id> <display_layout_id>
```

标签：

```bash
python3 scripts/vephone_cli.py list-tags <product_id>
python3 scripts/vephone_cli.py create-tag <product_id> --tag-name <tag_name> --tag-desc <tag_desc>
python3 scripts/vephone_cli.py update-tag <product_id> --tag-id <tag_id> --tag-name <tag_name> --tag-desc <tag_desc>
python3 scripts/vephone_cli.py delete-tag <product_id> --tag-id-list <tag_id1,tag_id2>
python3 scripts/vephone_cli.py attach-tag <product_id> --tag-id <tag_id> --pod-id-list <pod_id1,pod_id2>
```

网络配置：

```bash
python3 scripts/vephone_cli.py list-port-mapping-rules <product_id>
python3 scripts/vephone_cli.py detail-port-mapping-rule <product_id> <port_mapping_rule_id>
python3 scripts/vephone_cli.py list-dns-rules <product_id>
python3 scripts/vephone_cli.py detail-dns-rule <product_id> <dns_id>
python3 scripts/vephone_cli.py list-custom-routes <product_id>
```

## 测试

```bash
python3 -m pytest
VEPHONE_TEST_PRODUCT_ID=<product_id> python3 -m pytest
```

变更类 live 测试需要显式开启，并提供资源 ID；不要对生产资源运行这类测试。
