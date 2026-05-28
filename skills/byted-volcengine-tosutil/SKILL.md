---
name: "byted-volcengine-tosutil"
description: "围绕火山引擎对象存储 tosutil 生成与校验命令、规划桶/对象操作并诊断错误。用户提到 tosutil、TOS 桶对象管理、批量上传下载或相关排障时调用。"
---

# 火山引擎 tosutil Skill

这个 Skill 面向火山引擎对象存储 TOS 的 `tosutil` 命令行工具，负责把用户意图转换成安全、可执行、可校验的 `tosutil` 操作流程。

## 目标一句话

把“要对 TOS 做什么操作”的需求，转换成**默认只预览**的 `tosutil` 命令，并在需要执行时输出**结构化 JSON 结果 + 可复现证据 + 可诊断建议**。

## 输入与输出

- 输入：目标命令（如 `ls/cp/rm/du/setmeta`）+ 最少必要参数（如 `tos://` 地址、本地路径、递归开关）+ 可选公共参数（`endpoint/region/credentials/conf`）。
- 输出：统一 JSON 协议（`ok/code/message/data/ts`），包含 `preview.shell`（脱敏后的可复现命令）、执行摘要、失败时的 `advice.code` 与 `next_actions`。

## 默认行为（降低用户成本 + 安全）

- 默认只生成命令预览，不执行（需要显式 `--run` 才会执行）。
- 破坏性命令（例如 `rm`）默认不执行：必须显式 `--yes`（或 legacy 模式下 `--assume-yes`）才会真正运行。
- 输出默认脱敏：不会回显 AK/SK/Token。

## 何时使用

当用户要求以下任一场景时调用本 Skill：

- 使用 `tosutil` 初始化或更新 TOS 配置
- 创建桶、列举桶/对象、查询对象属性
- 上传、下载、复制、批量删除对象
- 计算对象容量、设置对象元数据
- 分析 `Http status [403]`、连通性失败、命令参数错误等问题
- 为 `share`、`set-acl`、`mount`、`probe`、`netdig` 等高级命令生成执行方案

## 文档事实基线

基于 `tosutil` 文档体系，可确认以下事实：

- `tosutil` 是访问和管理火山引擎对象存储 TOS 的命令行工具，适合本地与 TOS 之间的批量数据处理、脚本集成和中小数据迁移。
- 核心命令包括 `ls`、`mkdir`、`du`、`mb`、`cp`、`setmeta`、`stat`、`rm`、`share`、`set-acl`、`mount`。
- 辅助命令包括 `config`、`help`、`probe`、`netdig`、`hash`、`fcp`、`clear`、`version`、`ping`、`connect`、`traceroute`、`curl`。
- 初始化配置支持永久密钥、STS 临时密钥和匿名访问三种方式。
- 初始化时应使用 TOS 协议域名，而不是 S3 协议域名。
- `rm` 默认存在二次确认；递归和批量删除必须显式评估风险。
- `du` 在百万级对象下可能耗时较长，优先按目录拆分计算。

## 下载与安装

`tosutil` 支持 Windows、Linux 和 macOS。使用本 Skill 前，建议先根据当前操作系统与芯片架构下载对应版本，并完成执行权限设置。

### 官方下载建议

- Linux amd64：支持直接下载二进制并执行
- macOS amd64（Intel）：支持直接下载二进制并执行
- macOS arm64（Apple M 系列芯片）：支持直接下载二进制并执行
- Windows 64bit：下载 `tosutil.exe`
- 官方同时提供对应的 `sha256` 校验文件，建议下载后做完整性校验
- 当前 `tosutil` 最新版本主要适用于 Windows、macOS 和 Linux amd 系统

### 安装命令

Linux：

```bash
wget https://m645b3e1bb36e-mrap.mrap.accesspoint.tos-global.volces.com/linux/amd64/tosutil
chmod a+x tosutil
sudo mv tosutil /usr/local/bin
```

macOS Intel：

```bash
wget https://m645b3e1bb36e-mrap.mrap.accesspoint.tos-global.volces.com/darwin/amd64/tosutil
chmod a+x tosutil
sudo mv tosutil /usr/local/bin
```

macOS Apple Silicon：

```bash
wget https://m645b3e1bb36e-mrap.mrap.accesspoint.tos-global.volces.com/darwin/arm64/tosutil
chmod a+x tosutil
sudo mv tosutil /usr/local/bin
```

Windows：

```bash
wget https://m645b3e1bb36e-mrap.mrap.accesspoint.tos-global.volces.com/windows/tosutil -O tosutil.exe
```

### 安装注意事项

- macOS 默认可能拦截未验证开发者应用；如果首次执行 `tosutil` 时被系统阻止，需要在系统安全设置中放行
- Linux / macOS 下载后通常需要执行 `chmod a+x tosutil`
- 如果希望在任意目录直接执行 `tosutil`，建议将二进制移动到已加入 `PATH` 的目录，例如 `/usr/local/bin`
- 如果二进制没有加入 `PATH`，请使用绝对路径调用，例如 `/absolute/path/to/tosutil version`
- 本 Skill 在未加入 `PATH` 的场景下，建议通过 `--tosutil-binary <absolute-path>` 显式指定二进制位置，避免找不到工具

### 安装后校验

如果已加入 `PATH`：

```bash
tosutil version
tosutil config
tosutil ls
```

如果未加入 `PATH`：

```bash
/absolute/path/to/tosutil version
/absolute/path/to/tosutil config
/absolute/path/to/tosutil ls
```

结合本 Skill 的建议：

- 先用 `version` 验证二进制是否可执行
- 再用 `config` 确认配置文件路径
- 最后用 `ls` 验证凭证、地域和网络连通性

如果 `tosutil` 已加入 `PATH`，可这样调用本 Skill：

```bash
python3 .trae/skills/byted-volcengine-tosutil/scripts/main.py \
  ls \
  --preflight
```

如果 `tosutil` 未加入 `PATH`，可这样调用本 Skill：

```bash
python3 .trae/skills/byted-volcengine-tosutil/scripts/main.py \
  ls \
  --tosutil-binary /absolute/path/to/tosutil \
  --preflight
```

## 工作原则

- 优先确认目标是“读操作”还是“写操作/删操作”。
- 优先生成最小可行命令，避免一次性拼接过多危险参数。
- 对批量上传、下载、复制任务，先确认并发和分片阈值，再执行。
- 对删除类任务，默认给出预检查步骤和回滚提示，不直接跳过确认。
- 遇到高级命令且参数未完全确认时，优先结合 `tosutil help <command>` 校验，不臆造参数。

## 标准流程

### 1. 识别场景

将用户请求归类到以下场景之一：

- 初始化配置：`config`
- 桶操作：`ls`、`mb`、`stat`
- 对象传输：`cp`
- 对象删除：`rm`
- 对象元数据：`setmeta`
- 容量统计：`du`
- 故障诊断：`version`、`ls`、`help`、`probe`、`netdig`、`ping`、`connect`、`traceroute`

### 2. 预检查

执行或建议以下检查：

```bash
tosutil version
tosutil config
tosutil ls
```

检查重点：

- 工具是否已安装且可执行
- `Endpoint` 是否为 TOS 协议域名
- `Region` 与目标桶地域是否一致
- `AK/SK` 或 `STS Token` 是否存在且权限足够
- 返回结果中是否出现 `Bucket number is:`、`Http status [403]`、`A connection attempt failed`

### 3. 参数归一化

在生成命令前，统一整理以下参数：

- 资源地址：本地路径、`tos://bucket`、`tos://bucket/prefix`
- 凭证模式：永久密钥、STS、匿名访问
- 公共参数：`-e`、`-re`、`-i`、`-k`、`-t`、`-conf`
- 桶类型：`-bt=fns|hns`
- 批量任务并发：`-j`
- 分片并发或分片任务控制：`-p`、`-threshold`、`-ps`
- 结果输出目录：`-o`

### 4. 命令生成

根据资源类型自动选择命令模式：

- 本地 -> TOS：上传
- TOS -> 本地：下载
- TOS -> TOS：对象复制
- 单对象：单任务模式
- 目录或前缀：递归模式 `-r`
- 大文件：根据阈值切换分片任务

### 5. 输出校验

解析执行结果中的以下信号：

- 成功标志：`successfully`、`Bucket number is:`、`Succeed count is:`、`Task id is:`
- 权限问题：`Http status [403]`
- 网络问题：`A connection attempt failed`
- 参数问题：命令帮助输出、必选参数缺失、路径格式错误
- 清理建议：断点续传失败时考虑 `clear`

## 命令映射

### 初始化配置

永久密钥（推荐）：

```bash
tosutil config -i <ak> -k <sk> -e <endpoint> -re <region>
```
endpoint和region 可以参考“附录：地域及访问域名”，优先使用内网endpoint，若内网endpoint不可用则使用公网网endpoint

STS：

```bash
tosutil config -i <ak> -k <sk> -t <token> -e <endpoint> -re <region>
```

匿名访问：

```bash
tosutil config -i= -k= -t= -e <endpoint> -re <region>
```

### 桶与对象常见命令

```bash
tosutil ls
tosutil mb tos://bucketname
tosutil cp /local/file.txt tos://bucketname/file.txt
tosutil cp tos://bucketname/file.txt /local/file.txt
tosutil rm tos://bucketname/file.txt
tosutil du tos://bucketname
tosutil setmeta tos://bucketname/object.png -meta aaa:bbb#ccc:ddd
```

## 安全策略

- 删除对象前先判断是否为单对象、目录前缀、桶级删除。
- 对 `rm -r`、`rm -f`、批量元数据更新、批量复制等操作，先输出影响范围说明。
- 如用户只要求“生成命令”，默认不直接执行。
- 如需执行高风险命令，先建议列举目标对象或做 `dryRun` 风格校验；若命令本身不支持 `dryRun`，先做只读检查。

## 集成实现建议

本 Skill 的实现以“本地 CLI 封装层”而不是“直接调用 TOS HTTP API”为主，因为文档主体提供的是 `tosutil` 命令接口。

### 脚本入口（推荐子命令模式）

命令预览（不执行）：

```bash
python3 .trae/skills/byted-volcengine-tosutil/scripts/main.py ls --cloud-url tos://bucketname
```

执行并返回结构化结果：

```bash
python3 .trae/skills/byted-volcengine-tosutil/scripts/main.py ls --cloud-url tos://bucketname --preflight --run
```

高风险删除（必须显式确认）：

```bash
python3 .trae/skills/byted-volcengine-tosutil/scripts/main.py rm --cloud-url tos://bucketname/prefix/ --recursive --run --yes
```

兼容旧入口（legacy）：

```bash
python3 .trae/skills/byted-volcengine-tosutil/scripts/main.py --command ls --cloud-url tos://bucketname
```

推荐目录结构：

```text
.trae/skills/byted-volcengine-tosutil/
├── SKILL.md
├── references/
│   └── doc-survey.md
└── scripts/
    ├── main.py
    ├── models.py
    ├── result_handler.py
    └── tosutil_service.py
```

推荐核心类：

- `CommonOptions` / `CredentialMode`：封装永久密钥、STS、匿名模式和公共参数
- `TosResource`：封装本地路径与 `tos://` 资源的解析结果
- `CommandSpec`：封装命令名、参数列表、风险级别、是否破坏性操作
- `TosutilRunner`：统一执行 `tosutil` 命令并收集退出码、标准输出、标准错误
- `result_handler`：统一负责结果解析、错误映射与结构化输出字段整理
- `tosutil_service`：统一负责命令构建、预检查、执行、脱敏和公共校验逻辑

## 关键规则

### 配置规则

- `config` 写入的是本机配置文件，默认位于用户目录下的 `.tosutilconfig`
- `-conf` 只能指向已有配置文件路径，不负责自动创建新文件
- 优先建议使用显式 `region + endpoint`，避免跨地域误操作

### 传输规则

- `cp` 需要根据源和目标地址类型自动推断是上传、下载还是云上复制
- 批量任务的实际并发需综合 `-j` 与分片并发参数评估，避免盲目调大
- 大文件和批量任务优先显式设置阈值、并发和输出目录，便于排错

### 统计规则

- `du` 在海量对象场景下不要默认全桶递归扫描
- 如桶开启版本控制，可按需加入版本相关参数并拆分统计范围

### 元数据规则

- `setmeta` 支持单对象和批量前缀模式
- 批量模式必须明确 `-r`，并限制最大并发 `-j`

## 故障诊断提示

### 权限问题

- 如果结果出现 `Http status [403]`，优先检查 AK/SK、STS 是否失效，以及目标桶/对象权限

### 网络问题

- 如果结果出现 `A connection attempt failed`，优先检查网络、代理、防火墙和 `Endpoint`

### 参数问题

- 如果高级命令参数不确定，先执行 `tosutil help <command>`

### 清理问题

- 断点续传或异常中断后，可考虑 `clear` 清理记录文件并尽力做云端清理

## 最佳实践

- 首次接管环境时，先执行 `version`、`config`、`ls` 三连检查
- 初始化必须使用 TOS 协议域名
- 匿名访问只适用于公开读或公共写场景
- 百万级对象统计按目录拆分
- 批量任务先保守设置并发，再逐步调优
- 对高风险命令保留二次确认和影响面说明

## 交互模板

### 用户想上传文件

1. 确认本地路径、目标桶、目标对象名
2. 判断是否需要递归上传
3. 检查配置与连通性
4. 生成 `cp` 命令
5. 返回成功判据与失败排查点

### 用户想删除目录

1. 先确认目标前缀
2. 先建议 `ls` 验证影响范围
3. 再生成 `rm -r`
4. 如用户确认强制删除，再考虑 `-f`

### 用户想排查无法访问

1. 检查 `version`
2. 检查 `config`
3. 执行 `ls`
4. 根据 `403`、连接失败、参数错误做分类诊断

## 测试要求

- 用文档示例作为命令构造测试样本
- 用示例输出作为解析器快照样本
- 对 `403`、网络失败、空配置、匿名访问、递归删除等场景做单元测试
- 对 `cp` 的上传/下载/云上复制三种方向分别做集成测试
- 对 `rm`、`setmeta`、`du` 的批量参数做边界测试

## 限制说明

- 本 Skill 优先覆盖文档中最核心的 `config`、`ls`、`mb`、`cp`、`rm`、`du`、`setmeta`、`stat`、`help`、`version`
- `share`、`set-acl`、`mount`、`probe`、`netdig`、`curl` 等高级命令采用扩展适配模式
- 如果某个高级命令的参数未在当前引用资料中完整展开，必须先通过 `help` 或补充文档确认后再执行

<br />

## **附录：地域及访问域名 **

- 地域（Region）：表示 TOS 的数据中心所在物理位置。
- 访问域名（Endpoint）：表示 TOS 对外服务的访问域名。

| Region 中文名称 | Region ID      | Endpoint (内网/外网)                                                    | S3 Endpoint (内网/外网)                                                       |
| ----------- | -------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| 华北2（北京）     | cn-beijing     | 内网: tos-cn-beijing.ivolces.com外网: tos-cn-beijing.volces.com         | 内网: tos-s3-cn-beijing.ivolces.com外网: tos-s3-cn-beijing.volces.com         |
| 华南1（广州）     | cn-guangzhou   | 内网: tos-cn-guangzhou.ivolces.com外网: tos-cn-guangzhou.volces.com     | 内网: tos-s3-cn-guangzhou.ivolces.com外网: tos-s3-cn-guangzhou.volces.com     |
| 华东2（上海）     | cn-shanghai    | 内网: tos-cn-shanghai.ivolces.com外网: tos-cn-shanghai.volces.com       | 内网: tos-s3-cn-shanghai.ivolces.com外网: tos-s3-cn-shanghai.volces.com       |
| 中国香港        | cn-hongkong    | 内网: tos-cn-hongkong.ivolces.com外网: tos-cn-hongkong.volces.com       | 内网: tos-s3-cn-hongkong.ivolces.com外网: tos-s3-cn-hongkong.volces.com       |
| 亚太东南（柔佛）    | ap-southeast-1 | 内网: tos-ap-southeast-1.ivolces.com外网: tos-ap-southeast-1.volces.com | 内网: tos-s3-ap-southeast-1.ivolces.com外网: tos-s3-ap-southeast-1.volces.com |
| 亚太东南（雅加达）   | ap-southeast-3 | 内网: tos-ap-southeast-3.ivolces.com外网: tos-ap-southeast-3.volces.com | 内网: tos-s3-ap-southeast-3.ivolces.com外网: tos-s3-ap-southeast-3.volces.com |

