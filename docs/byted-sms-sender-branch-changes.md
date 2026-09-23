# 短信 Skill 改动同步说明（保留 1.4.5）

## 同步范围

本次将 `agent` 仓库的短信 Skill 同步到本仓库的
[`skills/byted-sms-sender/`](../skills/byted-sms-sender/SKILL.md)。

本仓库版本号继续保持 1.4.5。

| 项目 | 本次取值 |
| --- | --- |
| 同步日期 | 2026-09-22 |
| 当前仓库对比基线 | `cd45b7c3`，Skill 1.4.5 |
| 源仓库 | `/Users/shayne/workspace/ai/agent` |
| 源目录 | `skills/specs/skills/byted-sms-sender/` |
| 源提交 | `a7728f40d571f5bdb0c204db90cc999898e02261` |
| 源内容版本 | 1.4.5 |
| 本仓库版本 | 1.4.5，按用户要求保留 |
| 构建渠道 | `skills/profiles/public/agentkit.yaml` |
| 文件变化 | 累计 17 个发布文件修改，本轮更新其中 6 个；无新增或删除；全部 41 个发布文件与源生成包逐字节一致 |

使用源仓库的打包器和 `--require-clean` 从已提交内容生成包，再同步其完整 Skill 目录。
源仓库本轮也已将版本号调整为 1.4.5，无需额外修改。具体快照由源提交和下文的包校验值
记录。渠道发布资料、连接器、测试目录和本机缓存不属于本次同步内容；源仓库文件未修改。

本文按当前仓库 1.4.5 的实际文件差异梳理，不把源仓库全部历史提交算作本次新增能力。
此前文档描述的鉴权、服务开通和资质向导历史可从 Git 历史查看。

## 本轮新增改动

相对上次同步的 `d4ff594a`，本轮同步 `a7728f40` 的 6 个文件，将消息组查询统一为
`GetSubAccountListForAgent`：

- `scripts/action_contracts.py`：更新接口注册和允许查询的接口集合。
- `scripts/sms_cli.py`：消息组列表和全消息组范围的模板预览均使用更新后的接口。
- `scripts/qualification_mcp_server.py`：同步群发表单的消息组查询提示。
- `references/actions.md`、`references/application-contracts.md`、
  `references/delivery-contracts.md`：同步接口矩阵、参数及发送准备说明。

请求参数、分页方式和返回的 `subAccountId` 使用方式保持一致。

## 累计主要变化

### 资源查询保留完整业务信息

- 消息组列表改用 `GetSubAccountListForAgent`，返回 `subAccountId`、`subAccountName`、
  `status` 等字段。`list-message-groups` 默认读取完整分页，支持名称、分页和全部状态筛选。
- 签名查询增加 `ListSignaturesForAgent`，支持精确签名、项目、消息组、短信类型、
  行业和审核状态筛选。按接口返回的业务维度解释，保留二级签名的审核意见与关联范围。
- 资源查询移除容易遗漏新字段的输出白名单，保留业务长文本、嵌套结构和普通 URL 参数。
  凭据、证件材料和个人私密字段仍按输出边界处理；带签名或凭据的 URL 参数会脱敏。
- 分页按实际收到的记录数检查完整性，遇到重复页、提前空页或超过上限时明确报错。

### 模板匹配保留候选和查询错误

`match-template` 先读取模板目录，再逐个模板查询二级记录。短信类型改为可选筛选条件，
`BatchOnly=true` 的模板不进入普通正文匹配。

结果同时返回原始 `templateRecords` 和命中的 `matchingRecords`，保留变量定义、行业
和审核状态。只有查询完整时才给出 `none/single/ambiguous` 分类；部分查询失败时返回
失败状态、`complete=false`、已有候选及具体错误，避免把查询失败误解为没有可用模板。

关键词检索也不再静默过滤未审核通过的记录。内容匹配只提供比较依据，Agent 结合客户
用途和接口返回选择模板，发送是否被接受由提交接口决定。

### 发送预览减少无关查询依赖

单条和群发预览根据模板返回的签名、消息组范围、正文、变量和短信类型准备信息。
模板已经绑定具体消息组时直接使用该范围；适用全部消息组时，通过
`GetSubAccountListForAgent` 核实所选启用组。

预览不再依赖额外的消息组详情、签名汇总及资质查询来重复判断可发送性，避免这些接口
失败阻断已有模板的正文检查或表单初始化。多条审核记录的预览字段一致时共用预览，
存在多种正文、变量或短信类型时明确提示歧义。

`batch-content-check` 直接调用 `ValidateBatchTaskContentForAgent`，保留正文、
`Approved`、`Reason` 和诊断信息。群发启动通过任务详情绑定当前身份，再检查原有
本地确认记录和当前任务，继续保持预览确认与结果未知时查询核实的约束。

### 群发时间先在会话确认，再预填页面

Agent 先确认客户要立即发送还是定时发送，再打开私密表单：

- MCP：立即发送传 `scheduled=false`；定时发送传 `scheduled=true` 和 `sendTime`。
- CLI：立即发送用 `--immediate`；定时发送用 `--scheduled --send-time`。
- 页面按 Asia/Shanghai 展示已确认时间，客户仍可修改，并在上传名单后最终确认。
- 同时指定立即发送和定时时间时，在查询资源之前报错。
- 未传发送方式的旧调用保留默认定时行为；页面初次打开不立即显示缺少时间的红色错误，
  在客户操作时间控件或上传名单后再提示。

### 试发结果与原消息精确关联

`send-status` 增加可选查询时间范围。私密表单记录每次试发开始时间，查询本次时间段内
精确匹配的 Message ID，不再把唯一一条但 ID 不同的记录当作结果。

页面将状态分别显示为“已发送，等待回执”“发送失败”和“已收到成功回执”。
接口没有提供状态时显示“未知”，保留已有发送时间、回执时间和错误信息。

### 精简 Skill 入口和任务参考

`SKILL.md` 同步源仓库最新内容，版本号保留 1.4.5；保留工具入口、隐私与确认边界及按任务读取的参考表。
同步更新消息组 ID、签名筛选、模板匹配、发送时间、试发查询和文件回退的说明。

### 统一资质图片上传配置

ImageX 服务 ID 从现有运行配置统一读取，实际服务地址和 ID 保持不变。
配置缺失时明确报错，不使用隐藏默认值。

## 修改文件

| 文件 | 变化 |
| --- | --- |
| `SKILL.md` | 能力描述及精简后的任务入口，版本号保留 1.4.5 |
| `scripts/action_contracts.py` | 新查询接口、业务结果保留及私密字段声明 |
| `scripts/api_client.py` | 业务字段透传与凭据、URL 脱敏 |
| `scripts/sms_cli.py` | 分页、签名筛选、模板匹配、预览、群发时间及试发查询 |
| `scripts/qualification_mcp_server.py` | 群发发送方式和时间参数透传、表单提示 |
| `scripts/qualification_upload.py`、`scripts/runtime_environment.py`、`scripts/runtime_environment.json` | 资质图片上传服务 ID 从现有配置统一读取 |
| `assets/batch_wizard.jsx`、`assets/batch_wizard.css`、`assets/batch_wizard.js` | 时间预填、延后错误提示、回执文案及对应构建产物 |
| `references/actions.md`、`references/application-contracts.md` | 查询接口、参数和返回维度 |
| `references/batch-form.md`、`references/batch-file-fallback.md` | 群发时间确认、表单与 CLI 回退 |
| `references/delivery-contracts.md`、`references/workflows.md` | 模板选择、发送预览、记录查询和组合流程 |

## 构建与核验

源仓库根目录的构建命令如下，`<新输出目录>` 必须尚不存在：

```bash
python3 -E -B skills/scripts/package_skill.py \
  --skill byted-sms-sender --env prod \
  --profile skills/profiles/public/agentkit.yaml \
  --output <新输出目录> --require-clean
```

用于同步对比的源构建包：`byted-sms-sender-1.4.5-prod.zip`，与本仓库 Skill 内容一致。

SHA-256：`22e51c874bf3848c8425faf8cd33b0ee83fb0ca1eae0b876f54ed029b366a158`。

本次实际完成：

- Python 离线测试 **151/151 通过**。复用源仓库 16 个测试模块，在临时测试目录中引用
  本仓库同步后的脚本和资源；没有把测试代码加入发布包。
- 上一轮 ImageX 定向检查 **2/2 通过**：模拟上传申请与提交请求，验证地址和服务 ID；
  移除必填服务 ID 后，入口明确失败。本轮上传代码未变化，沿用这些结果。
- 上一轮页面测试 **6/6 通过**，`esbuild 0.25.5` 重新编译的 JSX 与发布脚本逐字节一致。
  本轮页面资源未变化，沿用这些结果。
- 11 个 Python 脚本通过 Python 3.10 语法检查；页面脚本此前已通过 `node --check`。
- `quick_validate.py`、CLI `--help`、`batch-wizard --help` 和 `runtime-info` 通过。
- `git diff --check` 通过；全部 41 个发布文件的 SHA-256 与源构建记录一致。

Python 测试在宿主机执行，以支持本机表单用例的端口监听。
本次测试使用模拟接口，没有执行真实账号登录、上传、创建任务或短信发送；未运行源仓库
其他渠道的打包测试或远端 CI。

按 `codex-code-review` 审查后，未发现本次同步额外引入的阻断问题。业务规则仍在短信
Skill 内，未改动仓库通用平台代码；沿用源实现，没有增加额外抽象或测试专用生产分支。
本文记录同步内容与验证结果，提交、合并和发布状态以 Git 及平台实际记录为准。
