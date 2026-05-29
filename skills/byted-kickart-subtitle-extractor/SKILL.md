---
name: byted-kickart-subtitle-extractor
description: 视频字幕提取SKILL：从视频文件自动提取、识别视频中已有的字幕并导出，支持导出为标准SRT格式字幕文件。适用于视频提取字幕、提取视频内已有的字幕、视频字幕识别、字幕导出、视频转字幕等场景。触发时机：当用户提及或表达等价意图（帮我从视频中提取字幕、提取视频里的字幕、从视频里抠字幕、视频字幕提取、导出视频自带字幕、视频字幕识别、字幕导出、视频转字幕）时，调用此SKILL执行字幕提取任务。
version: 1.0.2
---

# 视频字幕提取SKILL

## 📋 工具说明

### 核心功能
1. 从指定的视频文件提取字幕
2. 支持生成标准SRT规范的字幕文件

### 可用命令
| 命令 | 功能 | 说明 |
|------|------|------|
| `python3.12 scripts/plan.py` | 套餐查询 | 查询用户当前的 Ark Claw 套餐 |
| `python3.12 scripts/upload.py --file <视频路径>` | 视频上传 | 上传本地视频文件获取媒资ID |
| `python3.12 scripts/extractor.py --media-id <媒资ID> --output <输出文件>` | 视频字幕提取 | 从指定视频提取字幕 |

---

## 🚨 强制前置校验流程（必须按顺序执行，任意不通过直接终止流程）
所有用户请求必须先完成以下3步校验，不得跳过：

### 1. 火山鉴权校验
- 执行环境变量检查命令：
  ```bash
  echo "ARK_SKILL_API_BASE: $ARK_SKILL_API_BASE" && echo "ARK_SKILL_API_KEY: $ARK_SKILL_API_KEY" && echo "ACCESS_KEY_ID: $ACCESS_KEY_ID" && echo "SECRET_ACCESS_KEY: $SECRET_ACCESS_KEY"
  ```
- 判断鉴权结果（按优先级）：
  - **第一优先级（Bearer Token）**：`ARK_SKILL_API_BASE` 和 `ARK_SKILL_API_KEY` 均为非空值 → 鉴权通过
  - **第二优先级（AK/SK签名）**：`ACCESS_KEY_ID` 和 `SECRET_ACCESS_KEY` 均为非空值 → 鉴权通过
  - **鉴权不通过**：执行以下引导方案

#### ❌ 鉴权未配置时的引导方案
1. 引导用户直接在聊天中发送ACCESS_KEY_ID/SECRET_ACCESS_KEY内容：
   > 请你提供火山账号AK&SK，用于检查火山创作Agent是否已开通套餐和有可用的创点
2. 收到用户发送的ACCESS_KEY_ID/SECRET_ACCESS_KEY后，执行配置命令：
   ```bash
   export ACCESS_KEY_ID=用户提供的ACCESS_KEY_ID值
   export SECRET_ACCESS_KEY=用户提供的SECRET_ACCESS_KEY值
   ```
3. 配置完成后告知用户：
   > 已完成ACCESS_KEY_ID/SECRET_ACCESS_KEY临时配置，当前配置仅在本次会话生效，不会持久化存储，请放心使用
4. 后续所有相关脚本执行时，均会自动通过`export`指定这两个环境变量，确保鉴权正常，无需用户重复配置

### 2. 套餐有效性校验
- **步骤1：Python版本校验**
  ```bash
  python3.12 --version || (echo "❌ Python 3.12+ 未安装，请先安装Python 3.12" && exit 1)
  ```
- **步骤2：依赖包安装校验**
  ```bash
  python3.12 -m pip install -r ./scripts/requirements.txt
  ```
- **步骤3：执行套餐查询命令**
  ```bash
  python3.12 -m scripts/plan.py
  ```
- **步骤4：结果处理逻辑**
  - ✅ **套餐有效**：返回结果中的 `message` 字段为有效截止时间（北京时间），校验通过
  - ❌ **套餐已过期**：`message` 小于等于当前时间，引导用户开通套餐，终止流程
  - ❌ **接口调用错误**：参考「错误处理规范」匹配错误码，向用户明确告知错误原因和解决方案，并且终止流程

### 3. 技能版本校验
- **步骤1：执行版本检查命令**
  ```bash
  python3.12 -m scripts/upgrade.py
  ```
- **步骤2：解析返回结果**
  返回格式示例：
  ```json
  {"code":"0","message":"success","data":"{\"install_command\":\"\",\"latest_version\":\"1.0.0\",\"latest_version_number\":100000000,\"update_message\":\"\"}"}
  ```
  - `latest_version`：最新版本号（如 "1.0.0"）
  - `install_command`：新版本安装指令
- **步骤3：版本对比逻辑**
  - ✅ **当前版本 >= 最新版本**：版本校验通过，继续后续流程
  - ⚠️ **当前版本 < 最新版本**：执行以下更新询问流程
    1. 询问用户是否更新到最新版本：
       > 检测到技能有新版本 {latest_version}，是否更新？（是/否）
    2. 用户确认更新（是）：执行 `install_command` 安装新版本
    3. 用户不更新（否）：跳过更新，继续后续流程

---

## 🛠️ 视频字幕提取执行流程

### 完整流程概览
```
用户请求 → 强制前置校验 → 用户提供视频 → 视频字幕提取 → 结果返回
```

### 前置准备
1. 确保输出目录存在：`mkdir -p /tmp/openclaw/subtitle-extractor/output`
2. 生成唯一输出文件名：`subtitle_<timestamp>_<random>.json`

### 执行步骤
1. **步骤0：强制前置校验**（必须按顺序执行，任意不通过直接终止流程）
   - 执行「🚨 强制前置校验流程」中的所有校验步骤
   - ✅ 火山鉴权校验通过
   - ✅ 套餐有效性校验通过
   - ✅ 技能版本校验通过
   - 只有全部校验通过后，才能进入下一步

2. **步骤1：视频上传引导**
   - 询问用户：「请先提供要提取字幕的视频：可以发我视频tos链接，或上传 MP4/MOV 文件（建议≤10分钟、≤200MB、≥480p，预期处理时长5分钟以内）」
   - 支持两种上传方式：
     - **本地文件**：直接提供本地视频文件的绝对路径（如 `/Users/user/video.mp4`）
     - **公网URL**：提供可直接访问的视频链接（如 `https://example.com/video.mp4`）

3. **步骤2：视频预处理**
   - 若用户提供的是公网URL，先下载到本地：
     ```bash
     mkdir -p /tmp/openclaw/byted-kickart-video-analyzer/input
     curl -L -o /tmp/openclaw/byted-kickart-video-analyzer/input/downloaded_video.mp4 "<视频URL>"
     ```
   - 检查文件是否存在：`ls -la "<视频路径>"`
   - 检查文件类型是否为有效视频（仅支持MP4/MOV格式）：
     ```bash
     file /tmp/openclaw/byted-kickart-video-analyzer/input/downloaded_video.mp4 | grep -qE "ISO Media|MPEG v4|QuickTime" && echo "valid" || echo "invalid"
     ```
   - 若文件不存在或类型无效，**终止流程并提示用户**：
     > 文件不可用，请检查路径是否正确，或确认文件为有效视频格式（仅支持 MP4/MOV）
4. **步骤3：上传视频获取媒资信息**
   - 执行 `python3.12 scripts/upload.py --file <视频路径>` 命令
   - 返回字段说明：
     | 字段 | 类型 | 说明 |
     |------|------|------|
     | `id` | string | 媒资ID（唯一标识） |
     | `url` | string | 视频访问URL |
     | `duration` | number | 视频时长（秒） |

5. **步骤4：调用工具提取视频字幕**
   - 执行字幕提取命令：
     ```bash
     python3.12 scripts/extractor.py --media-id <媒资ID> --output <输出文件路径>
     ```
   - 参数说明：
     | 参数 | 类型 | 说明 |
     |------|------|------|
     | `--media-id` | string | 步骤3获取的媒资ID |
     | `--output` | string | 字幕结果输出文件路径（JSON格式） |
   - 执行流程：
     1. 调用ICCP服务提交字幕提取任务
     2. 轮询任务状态（每30秒查询一次，最多5分钟）
     3. 任务完成后将结果保存到指定输出文件
   - 返回结果说明（JSON格式）：
     | 字段 | 类型 | 说明 |
     |------|------|------|
     | `video_url` | string | 视频访问URL |
     | `captions` | object | 字幕信息对象 |
     | `captions.end_time` | number | 字幕结束时间（毫秒） |
     | `captions.start_time` | number | 字幕开始时间（毫秒） |
     | `captions.attribute` | object | 字幕属性（预留字段） |
     | `captions.text` | string | 字幕完整文本内容 |
     | `captions.words` | array | 分词列表 |
     | `captions.words[].end_time` | number | 单词结束时间（毫秒） |
     | `captions.words[].start_time` | number | 单词开始时间（毫秒） |
     | `captions.words[].attribute` | object | 单词属性（预留字段） |
     | `captions.words[].text` | string | 单个单词文本 |

6. **步骤5：SRT字幕文件生成（可选）**
   - **触发条件**：用户需要标准SRT格式字幕文件
   - **触发方式**：字幕提取成功后，在消息模板中询问用户是否需要SRT格式字幕文件
   - **生成方式**：Agent根据字幕JSON结果直接生成标准SRT格式字幕文件，不依赖脚本
   - SRT格式说明：
     ```
     1
     00:00:00,000 --> 00:00:01,800
     it's a filter in a bottle with SPF!
     
     2
     00:00:01,800 --> 00:00:10,200
     This isnt even a foundation
     ```


### Agent执行特殊要求
1. **超时设置**：调用exec工具启动脚本时，设置≥180000ms（3分钟）的yieldMs
2. **友好提示**：若脚本未立即返回结果，先回复用户："正在为您进行视频分析，任务执行时间可能较长，请您稍候~"
3. **异常处理**：若脚本因超时/异常退出，立即使用持久化的Task ID调用任务查询接口确认后端状态，禁止直接判定任务失败

### 📝 用户展示消息模板
**严格要求**：必须使用普通正文格式展示，绝不可使用加粗语法（**），并且必须严格保留每一行的换行符！

**视频上传成功模板：**
```
📤 视频上传成功！

🆔 媒资ID: {media_id}
🔗 视频URL: [点击查看]({url})
📊 分辨率: {width}x{height}
⏱️ 时长: {duration}秒
```

**字幕提取成功模板：**
```
✨ 字幕提取任务已完成！
🎥 视频链接
[点击查看视频]({video_url})

🔤 字幕全文
{full_text}

🔤 字幕分词详情

| 时间戳（秒） | 分词文本 |
|-------------|----------|
{word_rows}

---

📁 字幕JSON文件路径：{output_file_path}

需要帮你生成SRT格式的带时间戳字幕文件吗？
```
> {word_rows} 生成规则：遍历 `captions.words` 数组，过滤掉文本为空白的条目，将 start_time/end_time 除以 1000 转换为秒，每行格式为 `| {start_sec}-{end_sec} | {text} |`，必须完整生成所有非空分词条目，不得省略。

---

## ⚠️ 错误处理规范
所有错误必须明确告知原因和可执行解决方案，禁止模糊提示！！！

| 错误码 | 错误描述 | 详细说明 | 用户处理建议 |
| --- | --- | --- | --- |
| 0 | 无返回值 | 接口调用成功，但服务返回结果为空 | 请稍后重试，如问题持续请联系火山技术支持 |
| 1400 | ParamErr参数错误 | 参数错误 | 联系技术支持 |
| 1402 | 创点不足 | 调用接口时，用户账户的创点额度不足 | 请前往 [创点充值页面](https://console.volcengine.com/kickart/fusion/setting/combobuy?tab=additionalCombo) 充值创点或升级套餐 |
| 1410 | 服务ID不存在 | 调用接口时，输入参数中包含了不存在的服务ID | | 升级SKILL |
| 1411 | 输入分辨率错误 | 调用接口时，输入参数中的图片或视频分辨率不符合要求 | 请检查素材分辨率是否符合规格要求（如≥480p） |
| 1412 | 图片格式错误 | 调用接口时，输入参数中包含了非支持的图片格式 | 请检查图片格式是否为 jpg、png 等支持的格式 |
| 1413 | 无效的媒体URL错误 | 调用接口时，输入参数中包含了无效的媒体URL | 请检查您提供的URL是否正确，避免包含特殊字符或格式错误 |
| 1414 | 输入包含敏感信息错误 | 调用接口时，输入参数中包含了敏感信息，如个人隐私数据等 | 暂不可生成带人物的营销视频，请等待后续版本更新 |
| 1415 | 输出包含敏感信息错误 | 调用接口时，服务返回结果中包含了敏感信息，如个人隐私数据等 | 暂不可生成带人物的营销视频，请等待后续版本更新 |
| 1416 | 输入媒体数量错误 | 用户输入的素材数量超过限制 | 提供的媒体素材数量超出限制，多出的素材可能不会使用 |
| 1417 | 大模型调用错误 | 模型调用出错，通常是输入参数错误 | 媒体素材处理存在问题，请重新尝试，如问题持续请联系火山技术支持 |
| 1418 | 时长计费参数错误 | 提交时入参时间有问题 | 要求的成片时长不符合技能要求，请按照0-60s的时长限制提交制作需求，如问题持续请联系火山技术支持 |
| 1501 | 用户套餐过期 | 调用接口时，用户套餐已过期 | 请前往 [套餐开通页面](https://console.volcengine.com/kickart/fusion/setting/combobuy?tab=combo) 开通套餐 |
| 100010 | 签名验证失败 | AK/SK签名验证失败 | 请检查您提供的火山鉴权AK/SK是否正确，可访问[火山引擎控制台](https://console.volcengine.com/iam/keymanage)确认 |
| 100013 | 缺少服务权限 | 缺少iccloud\_muse服务的RegisterArkClawCombo权限 | 您的企业账号未开通Kickart权限，请联系火山主账号管理员为您开通，或详询火山技术支持 |
| x01001 | AK/SK未配置 | 用户未配置AK/SK | 请输入火山鉴权的AK/SK，可访问[火山引擎控制台](https://console.volcengine.com/iam/keymanage)获取 |
| x01010 | 有效套餐缺失 | 素材上传出现错误，通常是套餐原因 | 请前往 [套餐开通页面](https://console.volcengine.com/kickart/fusion/setting/combobuy?tab=combo) 开通套餐 |
| A0101 | Session元数据格式错误 | 接口传入的Session元数据格式错误 | 稍后重试，如问题持续请联系火山技术支持 |
| 1600 | 任务不存在 | 查询任务状态时，指定的任务ID不存在 | 请确认任务ID是否正确，或任务已被删除 |
| 其他 | \- | 未明确列出的其他错误情况 | 稍后重试，如问题持续请联系火山技术支持 |
---