---
name: byted-livesaas-master
description: 企业直播 / LiveSaaS 控播 Skill。支持通过 `bytedlive` CLI 操作直播间（创建/配置/状态）、评论、系统消息、观众管控，以及 OpenAPI 兜底调用。覆盖场景包括：直播间生命周期管理、直播数据与观众画像分析、商品卡片运营（上架/讲解）、营销互动工具（卡券）与连麦协同控制、媒资库运维及账号/权益信息查询。触发词：企业直播、控播、直播间、ActivityId、评论、弹幕、禁言、拉黑、踢人、商品卡片、直播数据、观众画像、火山引擎 livesaas。
version: 1.0.1
---

# byted-livesaas-master（企业直播控播）

## 1. 适用范围

### When to use

当用户意图涉及以下任一场景时触发本 Skill：

- **直播间生命周期管理与管控**：创建/删除直播间，查询列表，修改基础配置（名称/时间/模式），控制状态（开播/锁定/恢复/下播/封禁）
- **直播数据分析与观众画像**：查询直播间观看时长分布统计、拉取观众用户画像明细用于洞察
- **商品库与卡片运营**：直播中对商品卡片进行上架、讲解态切换，查询商品状态或统计数据
- **评论治理与内容分析**：发送/查询/轮询评论，删除用户消息，配置敏感词，或获取评论的分析结果（含大模型分析）
- **账号基础信息与媒资库运维**：获取账号配置/全局权益额度信息，批量删除媒资库视频，检查文档库容量
- **营销互动与连麦控制**：创建直播间卡券等互动工具，管理网页直播连麦协同状态
- **系统消息**：向直播间推送系统定制消息
- **观众管控**：针对观众的禁言、拉黑、踢出
- **观看页外观**：切换主题（暗黑/清爽/经典/传统节庆）
- **OpenAPI 兜底**：上述未明确覆盖到的其余企业直播能力操控需求，通过调用企业直播OpenAPI来实现

### When NOT to use

- **推流/拉流/编码等底层媒体问题** → 不属于本 Skill
- **WebSDK 接入 / 小程序进房 / 观看端 Token** → 使用 **byted-livesaas-dev** Skill
- **账号计费 / 套餐管理** → 引导用户至火山引擎控制台
- **非企业直播产品**（如视频点播、RTC）→ 不属于本 Skill

## 2. 架构概览

```
用户意图 → Skill（路由 + 约束） → Agent 生成 CLI 命令 → bytedlive CLI 执行
```

- **Skill 层**：定义意图到 CLI 子命令的映射 + 执行约束（不含可执行脚本）
- **Agent 层**：根据路由表与约束拼装 `bytedlive` 命令并执行
- **CLI 层**：封装凭证管理、签名、请求发送、确认交互与 JSON 结果

> **唯一执行入口**：所有命令必须通过 `bytedlive` CLI，禁止手写 curl 或未文档化的 HTTP 请求。

## 3. 首次使用引导与依赖安装（Onboarding）

**触发条件**：本 Skill 被首次激活时（即用户第一次发出匹配 §1 触发词的请求），Agent **必须**先执行 onboarding 流程（含 CLI 自动安装与凭证配置），再处理用户的实际请求。

### 3.1 Onboarding 检查与安装流程

```
Step 0: 环境检查与 CLI 自动安装
  ├─ 检查依赖：执行 `bytedlive --version` 判断是否已安装
  ├─ 未安装时先引导安装（外网客户默认 `bytedlive-cli`；内网研发可走 bnpm / 源码）：
  │    ├─ 外网 / 客户侧（默认）：`npm i -g bytedlive-cli`
  │    ├─ 内网 bnpm：`npm i -g @byted-vcloud/bytedlive-cli`（使用公司 bnpm registry）
  │    └─ 内网源码兜底：从内网 `byted-live-cli` 仓库以 git+ssh 安装 release 分支
  ├─ Agent 有权限时可静默执行安装；外网场景默认 `npm i -g bytedlive-cli`
  ├─ 成功：执行 `bytedlive --version` 验证后进入 Step 1
  └─ 失败：输出【CLI 安装失败引导】（见 3.2），中止后续流程，等待用户手动处理
Step 1: 检查凭证 → bytedlive openapi check-credentials --pretty
  ├─ 成功（已配置） → 跳过引导，直接处理用户请求
  └─ 失败（未配置 / 凭证无效） → 进入 Step 2
Step 2: 输出【AK/SK 本地配置引导消息】（见 3.3）
Step 3: 用户在本地终端执行 set-credentials，CLI 写入凭证并验证
Step 4: 验证通过 → 继续处理用户的原始请求
```

### 3.2 CLI 安装失败引导模板

当 Step 0 的自动安装失败（如缺少 Node 环境、无权限等）时，Agent **必须**向用户输出以下消息：

> ⚠️ **环境依赖缺失**
> 
> 抱歉，我尝试为你自动安装底层依赖工具 `bytedlive-cli` 但失败了（通常是因为当前环境未安装 Node.js / npm 或缺少全局写入权限）。
> 
> 请在你的本地终端中执行以下命令手动安装（外网客户默认）：
> ```bash
> npm i -g bytedlive-cli
> ```
> 内网研发也可改用 bnpm 包：
> ```bash
> npm i -g @byted-vcloud/bytedlive-cli
> ```
> 安装完成后执行 `bytedlive --version` 验证，并回复我“**已安装**”，我将带你继续下一步配置。

### 3.3 AK/SK 本地配置引导模板

当检测到凭证未配置时，Agent **必须**输出以下消息（可根据上下文微调措辞，但核心信息不可缺少）：

---

> 👋 **欢迎使用企业直播控播 Skill！**
>
> 检测到你还没有绑定企业直播账号，需要先完成一次配置。
>
> 请在你的**本地终端**执行下面的命令，按提示隐藏输入 **Access Key（AK）** 和 **Secret Key（SK）**：
>
> ```bash
> bytedlive openapi set-credentials
> ```
>
> - 获取路径：[火山引擎控制台](https://console.volcengine.com/iam/keymanage/) → 密钥管理
>
> ⚠️ 不要把 AK/SK 发到对话里。CLI 会把密钥缓存在本地 `~/.bytedlive/openapi-credentials.json`，后续命令会自动读取。
>
> 配置成功后回复我“已配置”，我会继续处理刚才的请求。

---

### 3.4 凭证写入与验证

用户在本地终端执行：

```bash
bytedlive openapi set-credentials
```

| 验证结果 | Agent 行为 |
|----------|-----------|
| 成功（`set-credentials` 返回 ok） | 输出 `✅ 账号绑定成功！`，然后继续处理用户的原始请求 |
| 失败（401/403/签名错误） | 输出 `❌ 凭证验证失败，请检查 AK/SK 是否正确。`，引导用户在本地终端重新执行 `bytedlive openapi set-credentials` |
| 失败（网络错误） | 输出 `⚠️ 网络连接异常，请稍后重试。` |

### 3.5 Onboarding 状态记忆

- 凭证验证通过后，**本会话内不再重复 onboarding**
- 凭证已持久化到 `~/.bytedlive/openapi-credentials.json`，后续会话自动加载，无需重复配置
- 如果后续操作中出现凭证失效（401/403），按 §7 错误恢复策略处理，不重新走完整 onboarding

### 3.6 快速能力概览（验证通过后附带）

凭证验证通过后，在确认消息中**追加一段能力概览**，帮助用户快速了解可以做什么：

> ✅ **账号绑定成功！** 以下是我可以帮你做的事情：
>
> | 能力 | 示例指令 |
> |------|---------|
> | 🎬 直播间管理 | "创建一个明天下午3点的直播间" / "查看最近的直播间" |
> | 💬 评论互动 | "帮我在直播间发一条评论" / "查看最近的弹幕" |
> | 📢 系统消息 | "发一条系统公告" |
> | 🚫 观众管控 | "禁言某个用户" / "把捣乱的人踢出去" |
> | 📊 数据与画像 | "查询直播间观看时长" / "获取观众画像详情" |
> | 🛒 商品与卡片 | "给商品卡片上架" / "切换到讲解状态" |
> | 🎨 观看页外观 | "切换到暗黑模式" |
> | 🔧 OpenAPI | "调用 GetActivityAPI 查直播间详情" |
>
> 现在帮你处理刚才的请求 👇

## 4. 凭证与 Base URL

| 项目 | 规则 |
|------|------|
| **AK/SK** | 必需。执行任何 OpenAPI 操作前，必须先执行 `bytedlive openapi check-credentials --pretty`。若本地缓存可用，直接复用；若不可用，只引导用户在本地终端运行 `bytedlive openapi set-credentials`，禁止在对话中索要 AK/SK |
| **Base URL** | 固定 `https://livesaas.volcengineapi.com/`，**不向用户询问**。仅用户主动提供专用 endpoint 时通过 `BYTEDLIVE_BASE_URL` 覆盖 |
| **缓存优先级** | 命令行/环境变量 → 会话缓存 → 本地文件 `~/.bytedlive/openapi-credentials.json` |
| **凭证失效** | 401/403/签名错误时，引导用户本地执行 `bytedlive openapi clear-credentials` 后再执行 `bytedlive openapi set-credentials` |

## 5. 安全机制：确认与黑名单

### 5.1 拟人化业务确认（所有写操作必做）

1. 组装候选命令（**仅在后台准备，绝对不向用户展示具体的 CLI 命令、代码或 JSON 参数**）。
2. 用“大白话”向用户确认**业务意图**，例如：“我准备为您创建名为『测试签到』的直播间，时间是今天下午 3 点。确认要建吗？”
3. 仅当用户明确同意后才执行。

### 5.2 黑名单二次确认（高风险操作）

命中以下操作时，在常规确认通过后，**再追加一次确认**：

| 黑名单操作 | 示例命令 |
|-----------|---------|
| 所有删除类（含 `delete/remove/del/删除`） | `bytedlive control room ...`（删除相关） |
| 观众踢出 | `bytedlive control audience kick ...` |
| 观众封禁/拉黑 | `bytedlive control audience block ...` |

二次确认话术需同样拟人化：`您正在进行高风险操作（例如：踢出某个观众），这可能会影响观众体验或导致数据丢失。请最后确认一次是否继续？`

## 6. 参数获取引导（缺参时 Agent 怎么办）

| 缺失参数 | Agent 应做的事 |
|----------|---------------|
| `--activity-id` | 先执行 `bytedlive control room list` 查询最近直播间，让用户确认目标 |
| `--user-ids`（观众管控） | 询问用户提供目标用户标识，或引导查询评论列表获取 |
| 直播间图片素材（封面/角标/装饰图等） | **不支持直接上传图片配置直播间**。优先让客户提供可访问的图片 URL 并继续后续配置流程；若客户无法提供 URL，则引导客户直接使用火山引擎控制台完成上传与配置（无回调流程） |
| AK/SK | 先执行 `bytedlive openapi check-credentials --pretty`；无缓存或验证失败时，引导用户本地执行 `bytedlive openapi set-credentials`，不要在对话中索要 |
| 不确定的 flag | 执行 `bytedlive control <子命令> --help` 查看帮助 |

## 7. 错误恢复策略

### 7.1 回答与执行约束（强制）

- **证据优先级**：必须优先基于本 Skill 已定义流程、已有 CLI 能力（`bytedlive control/openapi`）与本地知识库/参考文档作答和执行，不得跳过现有能力直接猜测。
- **官网补证**：当现有知识库、CLI 帮助与本地规则无法解决问题或无法确认参数/行为时，必须到 [火山引擎文档中心](https://www.volcengine.com/docs) 检索对应企业直播文档并据此补证后再回复。
- **无法实现/无法确认兜底**：若已穷尽本地能力与官网检索仍无法落地，必须明确告知用户「当前暂无法实现该能力」或「当前暂无法准确回答该问题」，并说明卡点；禁止编造接口、版本、字段、结果或“肯定可行”的承诺。

| 错误类型 | Agent 处理方式 |
|----------|---------------|
| `missing openapi credentials` | 引导用户本地执行 `bytedlive openapi set-credentials` |
| 401 / 403 / 签名错误 | 凭证可能过期或错误，提示用户本地执行 `bytedlive openapi clear-credentials` 后再执行 `bytedlive openapi set-credentials` |
| `InvalidActionOrVersion` / Action 不存在 | 按 §11 流程进行大模型静默自愈。失败则动用联网搜索查真实版本号并重试。期间安抚用户，切勿抛出生涩的原始报错信息。 |
| 参数错误 / 缺必传字段 | 检查字段名是否与官方文档一致（参考 §10 字段名规范），补全后重试 |
| 网络超时 | 重试 1 次，仍失败则告知用户 |
| 未知错误 | 查 [火山引擎企业直播文档](https://www.volcengine.com/docs/3019/66792?lang=zh)，无法解决则建议工单 |

## 8. 全局选项

| 选项 | 作用 |
|------|------|
| `--pretty` | JSON 美化输出 |
| `--non-interactive` | 禁止交互；缺参或缺凭证则直接失败 |
| `-y` / `--yes` | 跳过操作前确认（凭证仍需可用） |

## 9. 命令路由表

### 9.1 直播间（`bytedlive control room`）

| 场景 | 命令 | API | 关键参数 |
|------|------|-----|---------|
| 创建直播间 | `bytedlive control room create` | CreateActivityAPIV2 | `--name`、`--start`/`--live-time`、`--end`/`--end-time` |
| 直播间列表 | `bytedlive control room list` | ListActivityAPI | `--page`/`--page-size`、`--name`、`--status`、`--sort-by`/`--sort-order` |
| 读基础配置 | `bytedlive control room config get --activity-id <id>` | GetActivityBasicConfigAPI | |
| 更新基础配置 | `bytedlive control room config update --activity-id <id>` | UpdateActivityBasicConfigAPI | `--name`、`--start`、`--end`、`--view-url-path`、`--activity-type`、`--live-mode` |
| 设置活动状态 | `bytedlive control room status set --activity-id <id>` | UpdateActivityStatusAPI | `--op`（3/4/5）或 `--action recover\|lock\|release` |

### 9.2 评论（`bytedlive control comment`）

| 场景 | 命令 | API | 关键参数 |
|------|------|-----|---------|
| 发送评论 | `bytedlive control comment send --activity-id <id> --comment <文本>` | PresenterChatAPIV2 | 可选 `--audience-group-id`、`--top-status` |
| 评论列表 | `bytedlive control comment list --activity-id <id>` | ListActivityChatAPI | 可选分页、时间、`--chat-type`、`--top-status` |
| 轮询评论 | `bytedlive control comment poll --activity-id <id>` | PollingChatAPI | 可选 `--last-chat-id`、`--page-size`、`--start-time`/`--end-time` |

### 9.3 系统消息（`bytedlive control system-message`）

| 场景 | 命令 | API | 关键参数 |
|------|------|-----|---------|
| 发送系统消息 | `bytedlive control system-message send --activity-id <id> --content <文本>` | SendCustomSystemMessageAPI | 可选 `--message-type` |

### 9.4 观众管控（`bytedlive control audience`）

均需 `--activity-id`。用户标识常用 `--user-ids`，部分场景可用 `--cookies` 或 `--external-user-ids`（以 `--help` 为准）。

| 场景 | 命令 |
|------|------|
| 禁言 | `bytedlive control audience mute --activity-id <id> --user-ids <...>` |
| 拉黑（⚠️ 黑名单） | `bytedlive control audience block --activity-id <id> --user-ids <...>` |
| 踢人（⚠️ 黑名单） | `bytedlive control audience kick --activity-id <id> --user-ids <...>` |

### 9.5 观看页外观（主题切换）

当用户意图是「切换主题/换皮肤/外观设置」时，需做意图识别后再执行：

| 主题 | 同义词 |
|------|--------|
| **暗黑模式** | 暗黑、深色、夜间、黑色主题、dark |
| **清爽模式** | 清爽、浅色、简洁、明亮、light |
| **经典模式** | 经典、默认、原版、标准 |
| **传统节庆** | 节庆、喜庆、春节、新年红、红色主题 |

**规则**：
- 命中唯一主题 → 正常确认后执行
- 命中多个或未命中 → 反问：`你想切换到哪一种主题？可选：暗黑模式 / 清爽模式 / 经典模式 / 传统节庆。`
- 用户仅说「换个主题」等模糊描述 → 视为未命中，走反问

### 9.6 高频 OpenAPI 调用场景（使用兜底）

对于尚未被 CLI 工具（`control` 子命令）封装的高频业务场景，Agent 应当直接通过 `openapi call` 进行调用。常见高频场景和对应的 Action 如下（请勿编造 CLI 命令）：

| 场景分类 | 代表性 Action (API) | 用途说明 |
|----------|-------------------|----------|
| **直播数据与画像** | `AnalysisUserBehaviorPeopleV2` / `GetAccountUserTrackData` | 获取观看时长分布与观众画像详情 |
| **商品运营** | `EnableProduct` / `ExplainProduct` | 商品卡片上架与切换至讲解状态 |
| **账号与全局信息** | `GetAccount` / `GetAccountConfig` | 查询账号初始化信息与全局配置 |
| **媒资与文档库** | `DeleteMediaLibraryVideoAPI` / `CheckDocLibStorageCapacity` | 批量删除回放视频与查询文档容量 |
| **评论治理与分析** | `DeleteUserMessage` / `GetAccountCommentAnalysisLLMConsole` | 删除单条评论或获取大模型评论分析 |
| **线路与推拉流** | `ActivityLines` / `ActivityLinesPullInfoConsole` | 查询直播间线路与拉流配置详情 |
| **互动与协同** | `CreateActivityCouponsConsole` / `CloseLinkWebCast` | 创建卡券互动、关闭网页连麦 |

### 9.7 OpenAPI 兜底（`bytedlive openapi call`）

当 `control` 子命令不覆盖所需能力时（如 9.6 中的高频场景），使用 `openapi call` 直接调用任意 Action。

```bash
bytedlive openapi call --action <ActionName> [--api-version <Version>] \
  [--method POST] [--body '...'] [--body-file file.json] [--query '...']
```

**Version 解析优先级**：
1. 命令行 `--api-version` 显式指定
2. 静态表 `openapiActionVersions.json` 中的配置
3. 兜底默认 `2020-06-01`（`serviceDefaultVersion`）
4. 响应疑似 Version 错误时 → CLI 自动抓文档 HTML 解析并重试 1 次（可用 `--no-doc-version-retry` 关闭）

**查询 Version**：
```bash
查静态表：
bytedlive openapi get-version --action <ActionName> --pretty

尝试从文档页拉取：
bytedlive openapi get-version --action <ActionName> --refresh-doc --pretty
```

## 10. API 字段名规范（强制）

Body 和 Query 字段名**必须与火山引擎官方文档完全一致**，禁止凭记忆使用。

| 场景 | ❌ 错误 | ✅ 正确 | 说明 |
|------|---------|---------|------|
| 创建/更新/查询直播间 | `ActivityName` | `Name` | 直播间名称字段 |

**遇到「参数错误」类报错时**：优先检查字段名是否与文档一致，参考 [API 文档](https://www.volcengine.com/docs/3019/66792?lang=zh)。

## 11. OpenAPI 调用失败处理（大模型静默自愈机制）
 
 当调用 OpenAPI 遇到 `InvalidActionOrVersion`（接口版本错误或找不到）、参数缺失等报错时，**千万不要把 JSON 或生涩的报错信息直接抛给普通用户**。Agent 必须在后台静默执行以下自愈流程，并在期间用自然语言安抚用户（如：“接口版本有更新，我正在为您匹配最新协议，请稍候...”）：
 
 1. **尝试 CLI 自动解析**：执行 `bytedlive openapi get-version --action <X> --refresh-doc --pretty`。
 2. **大模型联网检索（关键兜底）**：如果 CLI 解析失败（未能从单次 HTTP 响应中解析 Version，或者依然报错），Agent **必须直接使用自带的联网搜索工具**，搜索 `"火山引擎 <Action名称> API 文档"`（例如：“火山引擎 SendCheckIn API”）。从最新的官方文档中提取出正确的“接口版本”（如：`2023-01-01` 或 `2023-08-01`）。
 3. **指定版本重试**：获取到正确的 Version 后，在原命令中加上 `--api-version <查到的真实版本号>` 重新发起 `openapi call`。
 4. **业务等价替代**：如果多次尝试依然失败，再用大白话向用户致歉，并询问是否使用其他功能的接口进行平替（例如，详情接口不通，则改用 List 列表接口过滤）。
 
 > **底线**：大模型禁止凭记忆编造接口版本号和参数字段；尽最大努力将开发视角的报错拦截在后台，对普通用户只展示业务维度的进度与结果。

## 12. 典型工作流示例

### 示例 0：首次使用（Onboarding）
 
 ```
 用户：帮我创建一个直播间
 Agent：
  1. Skill 首次激活 → 执行 onboarding 流程
  2. 检查发现未安装 CLI → 引导安装 `npm i -g bytedlive-cli`（内网可改用 bnpm 包名）并执行 `bytedlive --version` 验证
  3. 执行 bytedlive openapi check-credentials --pretty
  4. 失败（无凭证）→ 引导用户本地执行 bytedlive openapi set-credentials
  5. 用户回复已配置 → 再次 check-credentials → 验证通过
  6. 输出能力概览 + 继续处理"创建直播间"请求
 ```

### 示例 1：创建直播间
 
 ```
 用户：帮我创建一个明天下午3点开始的直播间，名字叫"产品发布会"
 Agent：
   1. 执行 bytedlive openapi check-credentials --pretty → 无缓存则引导本地 set-credentials
   2. 组装命令：bytedlive control room create --name "产品发布会" --start "2026-04-11 15:00:00"
   3. 向用户拟人化确认："我将为您创建名为『产品发布会』的直播间，时间是明天下午3点，确认执行吗？" → 确认后执行
 ```
 
 ### 示例 2：禁言某观众
 
 ```
 用户：把用户 user_123 禁言
 Agent：
   1. 确认 activity-id → 若无则先 room list 查询
   2. 组装命令：bytedlive control audience mute --activity-id <id> --user-ids user_123
   3. 向用户拟人化确认："请确认是否需要禁言指定用户？" → 用户同意
   4. 非黑名单操作，直接执行
 ```

### 示例 3：踢出观众（黑名单操作）

```
用户：把用户 user_456 踢出直播间
Agent：
  1. 确认 activity-id
  2. 组装命令：bytedlive control audience kick --activity-id <id> --user-ids user_456
   3. 向用户拟人化确认："请确认是否需要踢出用户？" → 用户同意
   4. 命中黑名单 → 二次确认："踢出用户属于高风险操作，可能会影响观众体验。请最后确认一次是否继续？"
   5. 用户再次确认 → 执行
 ```
 
 ### 示例 4：OpenAPI 兜底调用与版本自愈
 
 ```
 用户：帮我配置个签到
 Agent：
   1. control 子命令无此能力 → 走 openapi call (SendCheckIn 等)
   2. 执行报错：`InvalidActionOrVersion`
   3. 拦截报错，安抚用户："发现接口版本更新，我正在检索最新配置，请稍候..."
   4. 联网搜索 "火山引擎 SendCheckIn API 文档"，发现版本是 2023-08-01
   5. 组装新命令并确认："我将为您配置签到，请确认是否执行？"
   6. 执行：bytedlive openapi call --action SendCheckIn --api-version 2023-08-01 ...
 ```

## 13. 自测

```bash
bytedlive control test
```

运行 `byted-livesaas-master/references/tests` 下的基础测试。
