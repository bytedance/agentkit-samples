---
name: byted-vms-voice-notify
version: 2.0.0
description: 火山云通信语音通知 Skill. 在用户提到「语音通知 / 语音播报 / 自动外呼通知 / 语音提醒」并给出被叫号码与播报内容时调用. 支持单次发送 (SingleBatchAppend) 与批量任务 (CreateTask). 同时是所有 TTS 模板操作 (创建 / 更新 / 删除 / 查询) 以及录音文件 / 通用资源管理 (创建 / 查询 / 删除 / 直传 / 列表 / 可用资源 / 改名 / 删除) 的唯一入口.
license: Apache-2.0
metadata:
  author: leixin.alex@bytedance.com
  homepage: https://www.volcengine.com/docs/6358/172952?lang=zh
  knowledge_base: references/vms-fundamentals.md
  openclaw:
    emoji: "📞"
    requires:
      env:
        - VOLC_ACCESS_KEY
        - VOLC_SECRET_KEY
    os:
      - darwin
      - linux
    triggers:
      - 发送语音通知
      - 语音通知
      - 语音播报
      - 自动外呼通知
      - 语音提醒
      - 给.*打语音
      - 创建TTS模板
      - 创建tts模板
      - 更新TTS模板
      - 删除TTS模板
      - 查询TTS模板
      - 上传录音文件
      - 创建录音
      - 删除录音
      - 查询录音
      - 录音直传
      - 录音资源列表
      - 可用资源
---

# byted-vms-voice-notify · 火山云通信语音通知

封装火山云通信 TOP 语音通知接口, 支持「单次发送」「批量任务」「号码池查询」「TTS 模板全套生命周期管理 (创建 / 更新 / 删除 / 查询)」「录音文件管理 (创建 / 查询 / 删除 / 直传)」「通用资源管理 (列表 / 可用 / 改名 / 删除)」.

## 何时使用

用户出现以下表达时:

- 「给 138xxxxxxxx 发语音通知」「打语音电话提醒」「语音播报」
- 「批量给一批号码外呼提醒」「创建语音通知任务」
- 「查一下我的语音文件 / TTS 模板」「我的号码池有哪些」
- 「创建 / 更新 / 删除 / 查询 TTS 模板」
- 「上传录音 (公网 URL)」「列出我的录音」「删掉这个录音」「录音直传」
- 「列出录音 / IVR 资源」「查可用资源」「改录音名字」「删除某个资源」

默认走 `SingleBatchAppend` 单次发送. 仅当用户明确要求「创建批量任务 / 任务化外呼 / 定时外呼」时切到 `CreateTask`.

> **TTS / 录音 / 通用资源的唯一入口**: 所有 TTS 模板操作 (`open_create_tts` / `delete_tts` / `list_resource --type 1`) 与所有录音 / 通用资源操作 (`create_voice` / `query_voice` / `delete_voice` / `get_upload_url` / `submit_upload` / `list_usable` / `update_resource` / `delete_resource`) 都在本 skill 内. `byted-vms-configure` 不再提供任何 TTS / 录音 / 资源入口, 它只保留跨业务的 `query_risk_deny` / `query_can_call` / `query_auth`.

## 环境变量

按以下优先级解析鉴权:

1. `ARK_SKILL_API_KEY` + `ARK_SKILL_API_BASE` → 火山引擎 arkclaw 企业版. 请先在火山后台页面配置好 AK/SK, 由 arkclaw 注入这两个环境变量 (`ARK_SKILL_API_KEY` 为 API 密钥, `ARK_SKILL_API_BASE` 为 API 基础地址), 脚本以 `Bearer` 鉴权直连该网关, 无需本地签名;
2. `VOLC_ACCESS_KEY` + `VOLC_SECRET_KEY` (兼容 `VOLCENGINE_ACCESS_KEY`/`VOLCENGINE_SECRET_KEY`) → 个人版 arkclaw / openclaw / coco / aime / claudecode 等普通 agent, 用户直接把 AK/SK 告诉 agent, 脚本本地做 HMAC-SHA256 (Volc V4) 签名;
3. 否则报错并提示用户填入 AK/SK.

## 核心命令

```bash
# 1. 查可用语音资源 (录音 type=0 / TTS 模板 type=1 / IVR type=2)
#    支持 --resource-key 精确过滤, 可替代独立的 query_tts.
python3 scripts/send_voice_notify.py list_resource \
    [--type 0|1|2] [--keyword 欠费] [--resource-key <ResourceKey>]

# 2. 查号码池
python3 scripts/send_voice_notify.py list_number_pool [--keyword 北京]

# 3. 单次发送语音通知 (SingleBatchAppend)
python3 scripts/send_voice_notify.py single_append \
    --phone <Phone> \
    --resource <ResourceKey> \
    --number-pool-no <NumberPoolNo> \
    [--type 0|1|2] \
    [--phone-param '{"name":"<UserName>"}'] \
    [--ring-again-times 1] [--ring-again-interval 5] \
    [--ext "biz=<BizTag>"]

# 4. 批量任务 (CreateTask)
python3 scripts/send_voice_notify.py create_task \
    --name "<TaskName>" \
    --type 1 \
    --resource <ResourceKey> \
    --number-pool-no <NumberPoolNo> \
    --start-time "2026-05-28 10:00:00" \
    --end-time   "2026-05-28 18:00:00" \
    --concurrency 5 \
    [--select-number-rule 1]   # 服务端必填: 1=随机 (默认) / 2=轮询 / 3=尾号匹配
    --phone-list-json '[{"Phone":"<Phone>","PhoneParam":{"name":"<UserName>"}}]'

# 5. TTS 模板生命周期 (本 skill 是 TTS 唯一入口)
#    5.1 创建 (审核后才能用)
python3 scripts/send_voice_notify.py open_create_tts \
    --content "您好, <模板文案>" --name "<模板名称>" [--lang zh] [--remark "..."]
#    注意: 仅当用户明确给出全部模板参数 (文案 + 语速/音调/音量等) 时才允许直接调用;
#    若用户仅提模糊的「定制化模板」诉求, 必须先引导跳转控制台手工配置, 见下文「定制化模板诉求」章节.

#    5.2 删除 (内部走 OpenDeleteResource; TOP 没有独立 OpenDeleteTts)
python3 scripts/send_voice_notify.py delete_tts --resource-key <ResourceKey>

#    注: TTS 模板平台不支持 OpenAPI 改文案 / 改名 / 改语速音调等;
#         如需调整请前往控制台手工修改并重审: https://console.volcengine.com/cloud_vms/voice-file

#    5.3 查询 (统一走 list_resource --type 1)
python3 scripts/send_voice_notify.py list_resource --type 1 \
    [--resource-key <ResourceKey>] [--keyword <Name关键字>]

# 6. 单次发送结果查询 (按 SingleOpenId)
python3 scripts/send_voice_notify.py query_single --single-open-id <SingleOpenId>

# 7. 单次发送取消 (尚未拨打前可取消)
python3 scripts/send_voice_notify.py cancel_single --single-open-id <SingleOpenId>

# 8. 批量任务追加号码 (BatchAppend, 单次 ≤ 1 万)
python3 scripts/send_voice_notify.py batch_append \
    --task-open-id <TaskOpenId> \
    --phones <PhoneA>,<PhoneB>
# 或用 JSON, 支持每个号码携带 PhoneParam:
python3 scripts/send_voice_notify.py batch_append \
    --task-open-id <TaskOpenId> \
    --phone-list-json '[{"Phone":"<Phone>","PhoneParam":{"name":"<UserName>"}}]'

# 9. 任务生命周期控制
python3 scripts/send_voice_notify.py pause_task  --task-open-id <TaskOpenId>
python3 scripts/send_voice_notify.py resume_task --task-open-id <TaskOpenId>
python3 scripts/send_voice_notify.py stop_task   --task-open-id <TaskOpenId>

# 10. 更新任务参数 (执行窗口 / 并发 / 重呼策略 / 禁呼时段)
python3 scripts/send_voice_notify.py update_task \
    --task-open-id <TaskOpenId> \
    [--start-time "2026-05-28 10:00:00"] [--end-time "2026-05-28 18:00:00"] \
    [--concurrency 5] \
    [--ring-again-times 1] [--ring-again-interval 5] \
    [--forbid-time-list-json '[{"BeginTime":"12:00","EndTime":"13:30"}]'] \
    [--recall true]

# 11. 录音文件管理
#     11.1 上传录音 (TOP 没有 OpenCreateVoice, 必须走直传两步法)
#          step1: 申请直传 URL
python3 scripts/send_voice_notify.py get_upload_url \
    --file-name hello.wav --content-type audio/wav --sub-service-type 102
#          step2: 用返回的 UploadUrl 直接 PUT 文件 (curl/客户端自行完成)
#          step3: 提交注册
python3 scripts/send_voice_notify.py submit_upload \
    --upload-id <UploadId> --name "欢迎语" --sub-service-type 102
#          (旧的 create_voice 子命令已弃用, 调用会返回 ApiNotSupported 引导文案)
#     11.2 查录音 (按 ResourceKey 精确 / Name 模糊本地过滤)
python3 scripts/send_voice_notify.py query_voice \
    [--sub-service-type 102] [--resource-key <Key>] [--name 关键词] [--limit 20]
#     11.3 删除录音
python3 scripts/send_voice_notify.py delete_voice --resource-key <ResourceKey>

# 12. 通用资源管理
#     12.1 查可用 (审核通过) 资源
python3 scripts/send_voice_notify.py list_usable --type 0   # 0录音 1TTS 2IVR
#     12.2 改资源 Name (录音/IVR; TTS 模板不支持改名)
python3 scripts/send_voice_notify.py update_resource --resource-key <Key> --name "新名字"
#     12.3 通用资源删除 (TTS 请用 delete_tts)
python3 scripts/send_voice_notify.py delete_resource --resource-key <Key>
```

## 标准执行流程 (SingleBatchAppend)

1. **预检 1: 资源**. 用户没指定 `Resource` 时, 先 `list_resource --keyword <用户语义>`. 找不到则:
   - **若用户表达了「定制化模板」诉求** (例如要求调整语速 / 音调 / 音量 / 音色 / 停顿 / 多变量替换 等任何模板细节, 但**未给出具体参数值**), **不要**直接 `open_create_tts`,
     而是引导用户跳转控制台手动配置: https://console.volcengine.com/cloud_vms/voice-file ,
     在该页面点击「文件转语音模板」, 添加模板时即可编辑「语速 / 音调 / 音量」等参数, 提交后等待审核;
   - **仅当用户已明确给出完整模板参数** (文案 + 语速 + 音调 + 音量 等) 时, 才允许直接帮用户走 `open_create_tts` 自动创建; 模板需要审核, 返回 `ResourceKey` 让用户后续关注审核状态;
   - 若用户只是没找到合适的现成资源、且没有定制诉求, 也可以引导其去 https://console.volcengine.com/cloud_vms/voice-file 添加资源.
2. **预检 2: 号码池**. 用户没指定 `NumberPoolNo` 时, 调用 `list_number_pool` 取第一个 `NumberCount > 0` 的池. 没有则提示用户购买号码: https://console.volcengine.com/cloud_vms/number.
3. **正式调用**: 组装参数 → `single_append`. `SingleOpenId` 由脚本内部用 `uuid.uuid4().hex` 生成, 实现幂等.
4. **结果归一**: 失败时脚本会输出 `errorCode + suggest`, Agent 直接翻译给用户; 成功时返回 `MessageId / RequestId`.

## 跨 skill 协作 (业务层 ↔ 通用层)

本 skill (`byted-vms-voice-notify`) 是**业务层**, 同时是 **TTS / 录音 / 通用资源** 的唯一管理入口. 号码池 / 资质 / 话单等其他通用配置由 Agent 显式调度对应**通用层 skill**:

| 用户诉求               | 调度的 skill              | 命令示例                                                 |
|------------------------|---------------------------|----------------------------------------------------------|
| 创建 / 删除 TTS        | `byted-vms-voice-notify` (本 skill) | `open_create_tts` / `delete_tts` (改名/改文案不支持, 走控制台) |
| 查询 TTS 模板          | `byted-vms-voice-notify` (本 skill) | `list_resource --type 1 [--resource-key <Key>]`          |
| 上传 / 删除 / 查录音   | `byted-vms-voice-notify` (本 skill) | `create_voice` / `query_voice` / `delete_voice`          |
| 录音直传 (大文件)      | `byted-vms-voice-notify` (本 skill) | `get_upload_url` → 客户端 PUT → `submit_upload`          |
| 列出录音 / IVR / TTS   | `byted-vms-voice-notify` (本 skill) | `list_resource --type 0|1|2`                             |
| 查可用资源 / 改资源名 / 通用删 | `byted-vms-voice-notify` (本 skill) | `list_usable` / `update_resource` / `delete_resource` |
| 风控黑名单 / 可呼性 / 主叫鉴权 | `byted-vms-configure`     | `query_risk_deny` / `query_can_call` / `query_auth`      |
| 创建 / 查询号码池      | `byted-vms-number-pool`         | `create_pool` / `list_pool`                              |
| 提交 / 查询资质        | `byted-vms-number-pool`         | `add_qualification` / `query_qualification`              |
| 查话单 / 查录音文件 URL| `byted-vms-cdr-record`          | `query_cdr` / `query_record_url`                         |

**重要**: 所有 TTS / 录音 / 通用资源操作一律由本 skill 处理, **不要**再调度 `byted-vms-configure`. `byted-vms-configure` 已不再封装这些接口, 只保留跨业务的号码风控 / 可呼性 / 鉴权查询.

## 标准执行流程 (CreateTask)

仅在用户明确说「创建任务 / 批量任务 / 定时外呼」时使用, 流程同上, 多需:
- `Name`: 用户未指定就根据语义自动取名;
- `StartTime` / `EndTime`: 任务执行窗口;
- `Concurrency`: 并发量, 默认 1;
- `PhoneList`: 通过 `--phone-list-json` 传入数组 (Phone 必填, PhoneParam / TtsContent / Ext 可选).

## 标准执行流程 (录音文件 / 录音直传)

> TOP 没有 `OpenCreateVoice` 这种「按公网 URL 创建录音」的开放接口, 录音注册
> **统一走直传两步法**. 旧的 `create_voice` 子命令保留作兼容入口, 调用会返回
> `ApiNotSupported` + 引导, 不会真去发请求.

### 录音直传 (统一流程, 大文件 / 小文件均适用)

1. 调 `get_upload_url` 拿到 `UploadId` + `UploadUrl`;
2. 客户端自行用 `PUT` 上传文件到 `UploadUrl`;
3. 调 `submit_upload` 用 `UploadId` 注册成正式录音资源, 进入审核流程;
4. 后续用 `query_voice` 查 `AuditStatus`.

## 定制化 TTS 模板诉求 (强约束)

当用户提出**定制化语音通知模板**相关请求, 例如:

- 「帮我做一个慢速播报的模板 / 调高音量的模板 / 换个音色的模板」
- 「我希望模板能控制语速、音调、音量」
- 「做一个适合老人听的语音模板」

**默认行为**: **不要**直接调用 `open_create_tts` 帮用户自动创建. 必须先引导用户跳转控制台手动配置:

> 推荐前往火山云通信控制台手工创建模板, 可视化设置参数:
>
> https://console.volcengine.com/cloud_vms/voice-file
>
> 进入后点击「文件转语音模板」→「添加模板」, 即可在同一表单内编辑:
> - **语速** (Speed): `-0.5x ~ 5.0x` (默认 `1.0x`, 即正常语速; 小于 1.0x 变慢, 大于 1.0x 变快)
> - **音调** (Pitch): `-50% ~ 50%` (默认 `0%`; 负数低沉、正数尖锐)
> - **音量** (Volume): `0 ~ 30` (默认 `15`; 数值越大声音越响)
> - 文案 / 占位变量 / 备注 等
>
> 提交后等待审核 (AuditStatus=1) 通过即可使用.

**例外 (允许自动创建)**: 当且仅当用户在请求中**已显式给出全部必要参数**——至少包含「文案 + 语速 + 音调 + 音量」——可以由 Agent 调度 `open_create_tts` 直接落地. 缺任何一项参数都视为「未给出具体参数」, 必须回到上面的跳转引导.

判定流程:

```
用户提到「定制 / 自定义 / 调语速 / 调音量 / 调音调 / 换音色 / 个性化模板」?
  ├─ 是 → 用户给出了「文案 + 语速 + 音调 + 音量」全部具体值?
  │        ├─ 是 → 可调用 open_create_tts (附带各参数)
  │        └─ 否 → 引导跳转 https://console.volcengine.com/cloud_vms/voice-file 手工配置
  └─ 否 → 走标准 list_resource / open_create_tts 流程
```

## 错误兜底

- 账号未实名: 引导用户去 https://console.volcengine.com/user/authentication/enterprise/.
- 资质未通过 / 缺号码池 / 缺资源: 见 `scripts/_topclient.py` 的 `ERROR_MAP`, 全部命令失败时都会附 `suggest` 字段.
- 鉴权失败: 提示检查 AK/SK. 普通 agent (个人版 arkclaw / openclaw / coco / aime / claudecode) 检查 `VOLC_ACCESS_KEY`/`VOLC_SECRET_KEY`; 火山引擎 arkclaw 企业版需先在火山后台页面配置好 AK/SK, 再确认 `ARK_SKILL_API_KEY`/`ARK_SKILL_API_BASE` 已注入.

## 参考接口

- [SingleBatchAppend](https://www.volcengine.com/docs/6358/172952?lang=zh)
- [CreateTask](https://www.volcengine.com/docs/6358/172955?lang=zh)
- [BatchAppend](https://www.volcengine.com/docs/6358/172955?lang=zh)
- [PauseTask / ResumeTask / StopTask / UpdateTask](https://www.volcengine.com/docs/6358/172955?lang=zh)
- [QuerySingleInfo / SingleCancel](https://www.volcengine.com/docs/6358/172952?lang=zh)
- [NumberPoolList](https://www.volcengine.com/docs/6358/173339?lang=zh)
- [OpenCreateTts / OpenUpdateTts / OpenDeleteTts](https://www.volcengine.com/docs/6358/166398?lang=zh)
- [OpenCreateVoice / OpenDeleteVoice](https://www.volcengine.com/docs/6358/166395?lang=zh)
- [GetResourceUploadUrl / OpenSubmitUpload](https://www.volcengine.com/docs/6358/166398?lang=zh)
- [QueryOpenGetResource / QueryUsableResource / OpenUpdateResource / OpenDeleteResource](https://www.volcengine.com/docs/6358/1722078?lang=zh)

## 📚 基础知识 / 参数传递参考

`SingleBatchAppend` 的 `PhoneParam` 字段需与模板占位符对齐, `CreateTask` 的
`PhoneList` 数组结构、`open_create_tts` 的语速 / 音调 / 音量取值, 以及录音
直传的 `UploadId` 流转, 都在本 skill 内置的本地基础知识文档中说明:

> `references/vms-fundamentals.md`

该文档覆盖 SubServiceType=102 / 号码状态映射 / CallId 业务前缀 (V) /
录音 CDN host / 出口 IP 白名单等通用规范. 所有 vms-* skill 共用,
本地加载无外网依赖. 飞书原文 (可选):
https://bytedance.sg.larkoffice.com/docx/Mv32dc0yooBn7txDxW8lsDdDgYb
