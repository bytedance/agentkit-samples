---
name: byted-kickart-marketing-material-generator
description: 基于火山引擎 KickArt 一键成片服务生成抖店/抖音商品营销短视频，支持提供商品链接或商品 ID、上传自定义图片/视频素材、提交异步成片任务、查询进度、获取结果视频并同步创作产物。当用户发送抖店/抖音商品链接、提及「上传素材」「添加图片」「添加视频」「一键成片」「生成短视频」「营销视频」「商品视频」「生成成片」「查询成片进度」时使用本技能。
version: 2.3.1
---

# 营销视频Skill

## 🚨 强制前置校验流程

所有 KickArt 操作必须先完成 CLI 可用性与 OAuth 登录态检查：

1. **KickArt CLI 校验**
   - 读取 `references/CLI前置校验指南.md`。
   - 使用 `command -v npm` 检查 `npm exec` 是否可用。所有命令通过 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli` 调用固定版本，无需全局或项目级安装。
   - 执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_token >/dev/null` 检查登录态，禁止展示、记录或持久化 token。
   - 尚未登录或凭据失效时，执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_login` 获取授权链接并展示给用户；该命令立即返回，不会轮询授权状态。
   - 等待用户明确确认已完成网页授权后，单次执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_complete` 获取 token 并完成登录，再次检查登录态；禁止自动轮询或在用户确认前执行。
   - npm exec 下载包失败或 CLI 仍不可用时，反馈脱敏后的 npm 错误并终止操作。
   - 不要求用户提供长期密钥，不读取或回显 OAuth token，禁止直接请求 OpenAPI。

## 🎯 意图识别与任务执行指南（基于对话历史自动识别）

结合当前用户输入和历史记录判断意图后，必须严格读取并遵循对应执行依据指南，不可凭空猜测执行步骤。

| 任务类型 | 触发意图与关键词 | 执行依据（强制首要读取） | 输出要求 | 前置要求 |
|---------|----------------|----------------------|---------|---------|
| **进度查询** | 【最高优先级】用户提及「查询进度」「查看结果」「生成怎么样了」「好了吗」或查询某个具体任务 ID 的状态时。 | 读取 `references/任务查询指南.md`，执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli query_task_v2 --task-id <ID> --source kickart_ai_material --auto-publish true`。 | 解析 stdout JSON 并输出当前状态或结果。 | 需从会话上下文获取对应任务 ID；无有效 ID 时直接告知用户未查询到相关任务。 |
| **独立素材入库** | 用户明确要求「上传到 KickArt」「创建媒资」「保存到素材库」或「查询媒资」，且不是在为生成任务提供输入素材。 | 读取 `references/素材上传指南.md`，执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli material_pipeline_v2 --file-path <绝对路径>`。 | 从 stdout JSON 输出 `created.media_id` 和 `origin_url`。 | 生成任务中的图片和视频不得触发本流程；本地素材由提交命令自动上传。 |
| **一键成片** | 当用户需要一键端到端生成成片视频，提到「一键成片」「生成成片」「生成营销视频」「提交成片任务」「生成商品视频」时。 | 读取 `references/一键成片指南.md`，执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli submit_marketing_task_v2`。 | 解析 stdout JSON 并输出任务 ID；后续通过 `query_task_v2` 获取结果。 | 必须严格按照指南 Phase 0 逐步收集信息，模板固定为 978755842：素材与商品信息（条件必传，四项至少一项）、视频时长（必填，15/30/45/60秒）、画幅比例、语言、视频用途、创意指令、字幕、字幕擦除和明水印。所有列出的可选参数必须逐一询问，提交前必须展示成片信息并进行二次确认与合规提示。 |
| **视频参考** | 用户主动提供视频、视频链接，或表示要上传视频时。 | 读取 `references/视频参考指南.md`，校验并记录本地绝对路径或公网 URL；不预先上传。 | 获取可直接传给 `submit_marketing_task_v2 --user-videos` 的素材列表。 | 本地视频格式 MP4/MOV，单个 ≤50MB；最多 10 个。 |

## ⚠️ 错误处理规范

所有错误必须明确告知原因和可执行解决方案，禁止模糊提示。

| 错误码 | 错误类型 | 错误描述 | 详细说明 | 用户处理建议 |
| --- | --- | --- | --- | --- |
| 0 | Success | 任务成功 | 任务处理完成，结果已生成 | - |
| 1000 | AsyncTaskRunning | 任务运行中 | 任务正在处理，请稍后轮询结果 | - |
| 1300 | AuthFailed | OAuth 认证失败 | 登录凭据无效或已过期 | 依次执行 `auth_login` 获取授权链接、等待用户完成网页授权、执行 `auth_complete` 完成登录；禁止自动重试付费提交，重新提交前须再次展示成片信息并取得二次确认 |
| 1400 | ParamErr | 参数错误 | 请求中包含无效或缺失的参数 | 请对照文档检查请求体结构、字段类型和必填项 |
| 1401 | ConcurrentErr | 并发超限 | 当前的并发请求数超过了约定的上限 | 请降低请求频率，或联系商务代表调整并发额度 |
| 1402 | InsufficientPoints | 创点不足 | 账户余额不足以支付本次任务消耗 | 请前往 [创点充值页面](https://console.volcengine.com/kickart/agent-skill-combo-package) 充值创点或升级套餐 |
| 1403 | QuotaErr | 无权限 | 套餐不足 | 请联系管理员开通，或访问 [Kickart 套餐购买页面](https://console.volcengine.com/kickart/agent-skill-combo-package) 订阅套餐 |
| 1404 | QuotaErr | 无权限 | 套餐不足 | 请联系管理员开通，或访问 [Kickart 套餐购买页面](https://console.volcengine.com/kickart/agent-skill-combo-package) 订阅套餐 |
| 1410 | TemplateIdNotExist | 模板不存在 | 请求的 template_id 无效或对应的模板未上线 | 请确认模板ID是否正确（当前模板ID: 978755842） |
| 1412 | ImageFormatErr | 图片格式错误 | 输入的图片格式不受支持或文件已损坏 | 建议使用 JPEG 或 PNG 格式 |
| 1413 | InvalidMediaUrlErr | 媒体 URL 无效 | 媒体URL无法访问 | 请确保 URL 是公网可达的，且未过期；推荐接入火山对象存储 |
| 1418 | InvalidDurationBillingErr | 无效时长参数 | 入参时长参数不满足接口入参要求 | 请检查参考视频时长是否满足要求（>5秒且≤60秒） |
| 1422 | GetDouDianProductInfoError | 商品信息获取失败 | 服务端无法从提交的抖店/抖音链接或商品ID解析商品信息 | 请确认链接关联了可访问的商品，或改用商品ID、商品图片；修改后重新展示成片信息并取得二次确认，禁止自动重试 |
| 1423 | VideoResolutionError | 参考视频分辨率错误 | 参考视频分辨率不符合要求 | 请检查视频分辨率是否≥480p |
| 1424 | VideoDurationError | 参考视频时长错误 | 参考视频时长不符合要求 | 请检查视频时长是否在>5秒且≤60秒范围内 |
| 1425 | VideoFormatError | 参考视频格式错误 | 参考视频格式不支持 | 请检查视频格式是否为MP4或MOV |
| 1426 | VideoSizeError | 视频大小错误 | 本地视频文件大小超出媒资工具限制 | 请检查视频大小是否≤50MB |
| 1427 | RefVideoError | 参考视频链接错误 | 参考视频链接无效或无法访问 | 请检查您提供的视频URL是否正确 |
| 1428 | LanguageEnumError | 语言枚举值错误 | 请求的语言参数不在支持的枚举列表内 | 请检查语言参数是否为以下有效值：zh、en、en-us、pt-br、ja、es-mx、id、ms、tl |
| 1450 | InputValidationErr | 模板入参校验失败 | message会列出多个字段与规则 | 按提示修正后重新展示成片信息并取得二次确认，禁止自动重试 |
| 1500 | InternalErr | 内部错误 | 服务端发生未知错误 | 请记录 request_id 并联系技术支持 |
| 1600 | AsyncTaskNotExist | 任务不存在 | task_id无效 | 请检查任务ID是否正确 |
| 1601 | AsyncTaskTimeoutErr | 任务超时 | 任务执行超过系统设定的最长处理时间（当前为1小时） | 请联系技术支持核实任务状态；如需新建任务，必须重新展示成片信息并取得二次确认 |
| 2000 | AsyncTaskFailed | 任务失败 | 任务在执行过程中失败 | 请查看message中的具体失败原因；如需修正后新建任务，必须重新展示成片信息并取得二次确认 |
| x01401 | TokenFailed | 令牌获取失败 | 当前用户没有套餐权限 | 请联系管理员开通，或访问 [Kickart 套餐购买页面](https://console.volcengine.com/kickart/agent-skill-combo-package) 订阅套餐 |
