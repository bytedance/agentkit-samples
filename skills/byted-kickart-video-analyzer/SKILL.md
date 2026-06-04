---
name: byted-kickart-video-analyzer
description: 视频解析SKILL：提供视频解析、视频分析、视频反解、视频分镜提取、视频元数据提取等功能。适用于需要对本地或网络视频文件进行内容解析、分镜提取和元数据分析的场景，支持MP4、MOV等主流视频格式。当用户提及'视频解析、视频分析、视频反解、视频分镜、视频元数据提取、本地视频分析'或表达等价意图时触发
version: 1.0.7
---

# 视频解析SKILL

## 📋 工具说明

### 核心功能
提供视频解析、视频分析、视频反解、视频分镜提取、视频元数据提取等功能，解析本地或网络视频文件，提取视频元数据（时长、分辨率）、视频分镜信息和内容分析。

### 可用命令

| 命令 | 功能 | 说明 |
|------|------|------|
| `python3.12 ./scripts/plan.py` | 套餐查询 | 查询用户当前的 Ark Claw 套餐 |
| `python3.12 ./scripts/upload.py --file <视频路径>` | 视频上传 | 上传本地或网络视频文件获取媒资ID |
| `python3.12 ./scripts/analyze.py --media-id <媒资ID> --output <输出文件>` | 视频解析 | 解析视频，提取分镜和元数据 |

### 📥 视频获取方式
支持以下两种方式获取视频：
1. **本地文件**：直接提供本地视频文件的绝对路径
2. **网络视频**：先使用下载工具（如curl、wget或浏览器）将视频保存到本地，再提供本地路径进行反解

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
   > 请你提供火山账号AK&SK，用于检查火山创作Agent是否已开通套餐和有可用的创点！
2. 收到用户发送的ACCESS_KEY_ID/SECRET_ACCESS_KEY后，执行配置命令：
   ```bash
   export ACCESS_KEY_ID=用户提供的ACCESS_KEY_ID值
   export SECRET_ACCESS_KEY=用户提供的SECRET_ACCESS_KEY值
   ```
3. 配置完成后告知用户：
   > 已完成AK&SK临时配置，当前配置仅在本次会话生效，不会持久化存储，请放心使用。
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
  python3.12 -m ./scripts/plan.py
  ```
- **步骤4：结果处理逻辑**
  - ✅ **套餐有效**：返回结果中的 `message` 字段为有效截止时间（北京时间），校验通过
  - ❌ **套餐已过期**：`message` 小于等于当前时间，引导用户开通套餐，终止流程
  - ❌ **接口调用错误**：参考「错误处理规范」匹配错误码，向用户明确告知错误原因和解决方案，并且终止流程

### 3. 技能版本校验
- **步骤1：执行版本检查命令**
  ```bash
  python3.12 -m ./scripts/upgrade.py
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

## 🛠️ 视频解析执行流程

### 完整流程概览
```
用户请求 → 强制前置校验 → 用户输入收集 → 视频上传 → 视频解析 → 结果返回
```

### 前置准备
1. 确保输出目录存在：`mkdir -p /tmp/openclaw/byted-kickart-video-analyzer/output`
2. 生成唯一输出文件名：`video_analysis_result_<timestamp>_<random>.json`

### 执行步骤
1. **步骤0：强制前置校验**（必须按顺序执行，任意不通过直接终止流程）
   - 执行「🚨 强制前置校验流程」中的所有校验步骤
   - ✅ 火山鉴权校验通过
   - ✅ 套餐有效性校验通过
   - ✅ 技能版本校验通过
   - 只有全部校验通过后，才能进入下一步

2. **步骤1：视频上传引导**
   - 询问用户：「请先提供要解析的视频：可以发我视频tos链接，或上传 MP4/MOV 文件（≤60s、≤50MB、≥480p）」
   - 支持两种上传方式：
     - **本地文件**：直接提供本地视频文件的绝对路径（如 `/Users/user/video.mp4`）
     - **公网URL**：提供可直接访问的视频链接（如 `https://example.com/video.mp4`）

3. **步骤2：视频预处理**
   - 若用户提供的是公网URL，先下载到本地：
     ```bash
     mkdir -p /tmp/openclaw/byted-kickart-video-analyzer/input
     curl -L -o /tmp/openclaw/byted-kickart-video-analyzer/input/downloaded_video.mp4 "<视频URL>"
     ```
   - 检查文件是否存在：`ls -la /tmp/openclaw/byted-kickart-video-analyzer/input/downloaded_video.mp4`
   - 检查文件类型是否为有效视频（仅支持MP4/MOV格式）：
     ```bash
     file /tmp/openclaw/byted-kickart-video-analyzer/input/downloaded_video.mp4 | grep -qE "ISO Media|MPEG v4|QuickTime" && echo "valid" || echo "invalid"
     ```
   - 若文件不存在或类型无效，**终止流程并提示用户**：
     > 文件不可用，请检查路径是否正确，或确认文件为有效视频格式（仅支持 MP4/MOV）

4. **步骤3：上传视频获取媒资信息**
   - 执行 `python3.12 ./scripts/upload.py --file <视频路径>` 命令
   - 返回字段说明：
     | 字段 | 类型 | 说明 |
     |------|------|------|
     | `id` | string | 媒资ID（唯一标识） |
     | `url` | string | 视频访问URL |
     | `duration` | number | 视频时长（秒） |

5. **步骤4：解析媒资信息**
   - 从上传输出中提取 `id` 作为媒资ID
   - 提取 `duration` 用于视频分析

6. **步骤5：执行视频解析**
   - 执行以下命令：
     ```bash
     python3.12 ./scripts/analyze.py \
       --media-id <媒资ID> \
       --output /tmp/openclaw/byted-kickart-video-analyzer/output/video_analysis_result_<timestamp>_<random>.json
     ```
   - **重要**：
     - `--media-id` 参数值为媒资ID（通过上传脚本获取）
     - `--output` 参数值为**结果JSON文件的绝对路径**；脚本会同时输出两个文件：
       - 格式化后的JSON文件：`<output>.json`（原始格式，用于SKILL消息模板渲染）
       - seedance格式JSON文件：`<output>_seedance.json`（符合seedance格式，用于视频生成）

7. **步骤6：解析结果**
   - **读取结果文件**：脚本会同时生成两个文件，均需读取并持久化
   - **持久化存储**：将解析结果和两个输出文件路径（原始格式 + Seedance格式）持久化到会话上下文，供后续流程使用

8. **步骤7：询问输出格式**
   - **询问用户**：「解析完成！请选择输出格式：
     - 原始格式：适合查看详细解析结果
     - Seedance格式：适合用于视频生成

     请回复「原始格式」或「Seedance格式」」
   - **等待用户回复**：根据用户选择决定后续输出方式

9. **步骤8：结果输出**
   - **原始格式**：读取 `<output>.json` 文件内容，使用「原始格式消息模板」输出
   - **Seedance格式**：读取 `<output>_seedance.json` 文件内容，使用「Seedance格式消息模板」输出

#### 7.1 输出文件说明

脚本执行后会同时生成两个JSON文件：

| 文件类型 | 文件路径 | 用途 |
|---------|---------|------|
| 原始格式 | `<output>.json` | 用于SKILL消息模板渲染，提供完整的视频解析信息，适合查看详细解析结果 |
| Seedance格式 | `<output>_seedance.json` | 符合Seedance视频生成接口格式，适合用于视频生成 |

#### 7.2 原始格式文件结构（用于消息模板渲染）

**字段提取路径（供Agent使用）：**

| 模板变量 | JSON路径 | 说明 |
|---------|---------|------|
| `{video_duration}` | `$.video_info.video_duration` | 视频时长（秒） |
| `{product_title}` | `$.product_info.product_title` | 商品名称 |
| `{product_description}` | `$.product_info.product_description` | 商品描述 |
| `{shot_table_rows}` | `$.video_info.shot_breakdown` | 分镜表格数据 |

**分镜数据提取规则：**

遍历 `$.video_info.shot_breakdown` 数组，每行分镜数据提取：
| 字段 | JSON路径 | 说明 |
|------|---------|------|
| `{shot_number}` | `[i].shot_number` | 分镜编号 |
| `{start_time}` | `[i].start_time` | 开始时间 |
| `{end_time}` | `[i].end_time` | 结束时间 |
| `{camera_language}` | `[i].camera_language` | 镜头语言 |
| `{main_subject}` | `[i].main_subject` | 镜头主体 |
| `{marketing_intent}` | `[i].marketing_intent` | 营销意图 |
| `{on_camera_speech}` | `[i].on_camera_speech` | 口播 |
| `{voiceover_text}` | `[i].voiceover_text` | 旁白 |
| `{bgm}` | `[i].bgm` | BGM |
| `{stickers}` | `[i].stickers` | 花字&字幕 |

#### 7.3 Seedance格式文件结构（用于视频生成）

Seedance格式文件用于视频生成，仅保留指定字段：

##### 7.3.1 字段映射规则

| 原字段路径 | 映射字段 | 说明 |
|-----------|---------|------|
| `$.video_info.video_duration` | `video_duration` | 视频时长 |
| `$.product_info.product_title` | `product_title` | 商品名称 |
| `$.product_info.product_description` | `product_description` | 商品描述 |
| `$.video_info.shot_breakdown[].shot_number` | `shots[].shot_number` | 分镜编号 |
| `$.video_info.shot_breakdown[].start_time` | `shots[].start_time` | 开始时间 |
| `$.video_info.shot_breakdown[].end_time` | `shots[].end_time` | 结束时间 |
| `$.video_info.shot_breakdown[].camera_language` | `shots[].camera_language` | 镜头语言 |
| `$.video_info.shot_breakdown[].main_subject` | `shots[].main_subject` | 镜头主体 |
| `$.video_info.shot_breakdown[].marketing_intent` | `shots[].marketing_intent` | 营销意图 |
| `$.video_info.shot_breakdown[].on_camera_speech` | `shots[].on_camera_speech` | 口播 |
| `$.video_info.shot_breakdown[].voiceover_text` | `shots[].voiceover_text` | 旁白 |
| `$.video_info.shot_breakdown[].bgm` | `shots[].bgm` | BGM |
| `$.video_info.shot_breakdown[].stickers` | `shots[].stickers` | 屏幕贴纸&字幕文案 |
| `$.video_info.shot_breakdown[].text_style` | `shots[].text_style` | 字幕样式 |
| `$.scene_info.role_list[*].vocal_attributes` | `vocal_attributes` | 音色参数列表（所有角色） |
| `$.scene_info.subject_anchors` | `subject_definition.characters/props` | 主体定义（角色/道具） |
| `$.scene_info.voice` | `subject_definition.voice` | 音色字典 |

##### 7.3.2 完整格式示例

```json
{
  "video_duration": 44.5,
  "product_title": "商品名称",
  "product_description": "商品描述",
  "shots": [
    {
      "shot_number": 1,
      "start_time": 0,
      "end_time": 2.2,
      "camera_language": "近景平视",
      "main_subject": "BB霜",
      "marketing_intent": "产品展示",
      "on_camera_speech": "口播内容",
      "voiceover_text": "旁白内容",
      "bgm": "背景音乐",
      "stickers": "花字字幕",
      "vocal_attributes": ["音色参数1", "音色参数2"]
    }
  ],
  "subject_definition": {
    "characters": "角色1,角色2",
    "props": "道具1,道具2",
    "voice": "key1:value1;key2:value2"
  }
}
```

### Agent执行特殊要求
1. **超时设置**：调用exec工具启动脚本时，设置≥180000ms（3分钟）的yieldMs
2. **友好提示**：若脚本未立即返回结果，先回复用户："正在为您进行视频解析，任务执行时间可能较长，请您稍候~"
3. **异常处理**：若脚本因超时/异常退出，立即使用持久化的Task ID调用任务查询接口确认后端状态，禁止直接判定任务失败

### 回复用户消息模板

#### 【原始格式回复模板】

**严格要求**：视频信息、商品信息、分镜脚本、完整数据四个模块标题使用加粗格式，其余内容为普通正文，必须严格保留每一行的换行符！

解析完成后，使用以下模板回复用户：

```
🎬 链接解析成功，解析结果如下

---
**🔍 视频信息**
| 项 | 内容 |
| --- | --- |
| 视频时长 | {video_duration}s |
---
**🛍️ 商品信息**
✅ 商品名称： {product_title}
✅ 商品描述： {product_description}
---
**📸 分镜脚本**
| 分镜编号 | 时间 | 镜头语言 | 镜头主体 | 营销意图 | 口播 | 旁白 | BGM | 屏幕贴纸&字幕文案 | 字幕样式 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{shot_table_rows}

---
**📋 完整数据：**
{raw_json}
```

**新模板变量说明：**
- `{video_duration}`：视频时长
- `{product_title}`：商品名称
- `{product_description}`：商品描述
- `{shot_table_rows}`：分镜表格行，每行格式为：`| {shot_number} | {start_time}-{end_time}s | {camera_language} | {main_subject} | {marketing_intent} | {on_camera_speech} | {voiceover_text} | {bgm} | {stickers} | {text_style} |`
- `{raw_json}`：完整解析结果（json格式）

---

#### 【Seedance格式消息模板】

```
【全局开场】
视频时长：{video_duration}秒。

【主体定义】
角色:{role_id_list}
道具:{product_description}
音色:{role_list[*].vocal_attributes}

【时间轴分镜】
{start_time}-{end_time}:{main_subject}。镜头:{camera_language}。
角色台词:{on_camera_speech}
画外音:{voiceover_text}
音效:{bgm}
音乐:{bgm}
字幕:{stickers}

(下一段时间轴依次拼接...)

【约束】
{marketing_intent}
```

**Seedance格式模板变量说明：**
- `{video_duration}`：视频时长
- `{product_title}`：商品名称
- `{product_description}`：商品描述
- `{start_time}`：分镜开始时间
- `{end_time}`：分镜结束时间
- `{main_subject}`：镜头主体
- `{camera_language}`：镜头语言
- `{on_camera_speech}`：口播
- `{voiceover_text}`：旁白
- `{bgm}`：背景音乐
- `{stickers}`：花字&字幕
- `{marketing_intent}`：营销意图
- `{role_list[*].vocal_attributes}`：音色参数列表，逐条展示（每条格式为 `音色{i}:{音色描述}`，多条用换行分隔）
- `{subject_definition.characters}`：主体定义中的角色（来自 `scene_info.subject_anchors` 中的 character 类型）
- `{subject_definition.props}`：主体定义中的道具（来自 `scene_info.subject_anchors` 中的非 character 类型）
- `{subject_definition.voice}`：音色字典（来自 `scene_info.voice`，格式为 `key1:value1;key2:value2`）

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
| 其他 | \- | 未明确列出的其他错误情况 | 稍后重试，如问题持续请联系火山技术支持 |
---