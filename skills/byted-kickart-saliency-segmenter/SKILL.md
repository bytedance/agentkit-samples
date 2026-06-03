---
name: byted-kickart-saliency-segmenter
description: 智能抠图SKILL：从图片文件自动抠图。触发条件：当用户提及智能抠图、图片抠图、抠图、主体分割、去背景、背景剔除、商品抠图等关键词，或识别到用户表达等价意图时，调用此SKILL执行抠图任务。
version: 1.0.2
---

# 智能抠图SKILL

## 📋 工具说明

### 核心功能
从指定的图片文件抠图。

### 可用命令
| 命令 | 功能 | 说明 |
|------|------|------|
| `python3.12 ./scripts/plan.py` | 套餐查询 | 查询用户当前的 Ark Claw 套餐 |
| `python3.12 ./scripts/upload.py --file <图片路径>` | 图片上传 | 上传本地图片文件获取媒资ID |
| `python3.12 ./scripts/segment.py --media-ids <媒资ID列表>` | 批量图片抠图 | 支持多张图片并发抠图，多个媒资ID用逗号分隔 |

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
   > 已完成AK&SK临时配置，当前配置仅在本次会话生效，不会持久化存储，请放心使用
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

## 🛠️ 图片抠图执行流程

### 完整流程概览
```
用户请求 → 强制前置校验 → 用户提供图片 → 图片抠图 → 结果返回
```

### 前置准备
1. 确保输出目录存在：`mkdir -p /tmp/openclaw/byted-kickart-saliency-segmenter/output`
2. 生成唯一输出文件名：`segment_<timestamp>_<random>.json`

### 执行步骤
1. **步骤0：强制前置校验**（必须按顺序执行，任意不通过直接终止流程）
   - 执行「🚨 强制前置校验流程」中的所有校验步骤
   - ✅ 火山鉴权校验通过
   - ✅ 套餐有效性校验通过
   - ✅ 技能版本校验通过
   - 只有全部校验通过后，才能进入下一步

2. **步骤1：图片上传引导**
   - 询问用户：「请先提供要智能抠图的图片：可以发我图片tos链接，或上传 JPEG/PNG/WEBP 文件（≤8MB），也可以上传包含图片的ZIP压缩包，支持多张图片批量处理」
   - 支持三种上传方式：
     - **本地文件**：直接提供本地图片文件的绝对路径（如 `/Users/user/image1.jpg,/Users/user/image2.jpg`）
     - **公网URL**：提供可直接访问的图片链接（如 `https://example.com/image1.jpg,https://example.com/image2.jpg`）
     - **ZIP压缩包**：提供包含图片的ZIP文件路径或URL（如 `/Users/user/images.zip`）
   - 支持批量上传，多个文件路径或URL用逗号分隔

3. **步骤2：图片预处理**
   - **判断文件类型**：检查用户提供的是图片文件、图片列表还是ZIP压缩包
   - **ZIP解压处理**（如果是ZIP文件）：
     ```bash
     mkdir -p /tmp/openclaw/byted-kickart-saliency-segmenter/input
     unzip -o "<ZIP文件路径>" -d /tmp/openclaw/byted-kickart-saliency-segmenter/input/extracted/
     ```
   - **图片下载处理**（如果是公网URL）：
     ```bash
     mkdir -p /tmp/openclaw/byted-kickart-saliency-segmenter/input
     curl -L -o /tmp/openclaw/byted-kickart-saliency-segmenter/input/downloaded_image_<index>.jpg "<图片URL>"
     ```
   - **收集所有图片文件**：遍历输入目录，收集所有JPEG/PNG/WEBP格式的图片
   - **检查文件有效性**：
     - 检查每个文件是否存在：`ls -la "<图片路径>"`
     - 检查文件类型是否为有效图片：`file "<图片路径>" | grep -qE "image" && echo "valid" || echo "invalid"`
   - 若任一文件不存在或类型无效，**终止流程并提示用户**：
     > 文件不可用，请检查路径是否正确，或确认文件为有效图片格式（JPEG/PNG/WEBP）

4. **步骤3：上传图片获取媒资信息**
   - 遍历所有图片，依次执行 `python3.12 ./scripts/upload.py --file <图片路径>` 命令
   - 收集所有媒资ID
   - 返回字段说明：
     | 字段 | 类型 | 说明 |
     |------|------|------|
     | `id` | string | 媒资ID（唯一标识） |
     | `url` | string | 图片访问URL |

5. **步骤4：调用工具批量图片抠图**
   - 执行批量抠图命令：
     ```bash
     python3.12 ./scripts/segment.py --media-ids <媒资ID1>,<媒资ID2>,<媒资ID3>
     ```
   - 参数说明：
     | 参数 | 类型 | 说明 |
     |------|------|------|
     | `--media-ids` | string | 步骤3获取的媒资ID列表，用逗号分隔 |
   - 执行流程：
     1. 调用ICCP服务并发提交多个抠图任务
     2. 并发轮询所有任务状态（每30秒查询一次，最多5分钟）
     3. 汇总所有任务结果

   - 返回结果说明（JSON格式）：
     ```json
     {
       "code": "0",
       "message": "success",
       "data": {
         "total_count": 3,
         "success_count": 2,
         "failed_count": 1,
         "results": [
           {
             "media_id": "<媒资ID1>",
             "success": true,
             "data": "<抠图结果数据1>"
           },
           {
             "media_id": "<媒资ID2>",
             "success": false,
             "error": "错误信息"
           }
         ]
       }
     }
     ```


### Agent执行特殊要求
1. **超时设置**：调用exec工具启动脚本时，设置≥180000ms（3分钟）的yieldMs
2. **友好提示**：若脚本未立即返回结果，先回复用户："正在为您进行视频分析，任务执行时间可能较长，请您稍候~"
3. **异常处理**：若脚本因超时/异常退出，立即使用持久化的Task ID调用任务查询接口确认后端状态，禁止直接判定任务失败

### 📝 用户展示消息模板

**单张图片上传成功模板：**
```
📤 图片上传成功！

🆔 媒资ID: {media_id}
🔗 图片URL: [点击查看]({url})
📊 分辨率: {width}x{height}
```

**批量图片上传成功模板：**
```
📤 批量图片上传成功！

共上传 {count} 张图片，媒资ID列表：
{media_id_list}
```

**单张图片抠图成功模板：**
```
✨ 智能抠图成功！

🎯 主体图片：[点击预览]({subject_url})
🎭 蒙版图片：[点击预览]({mask_url})

📂 文件空间路径：
- 主体图片：media/outbound/{task_id}/subject.png
- 蒙版图片：media/outbound/{task_id}/mask.png
```

**批量图片抠图成功模板：**
```
✨ 批量智能抠图完成！

📊 处理结果：
- 总数：{total_count} 张
- 成功：{success_count} 张
- 失败：{failed_count} 张

{success_results}

{failed_results}
```

**批量抠图成功结果列表（每条）：**
```
✅ 图片 {index}：
   🎯 主体：[点击预览]({subject_url})
   🎭 蒙版：[点击预览]({mask_url})
   📂 文件路径：media/outbound/{task_id}/
```

**批量抠图失败结果列表（每条）：**
```
❌ 图片 {index}：{error_code} - {error_message}
💡 处理建议：{suggestion}
```

> **失败结果处理说明**：失败的图片需要根据错误码匹配「错误处理规范」中的对应错误码，展示完整的错误描述和用户处理建议。示例：
> - 错误码 `1402`：显示「创点不足」，处理建议「请前往 [创点充值页面](https://console.volcengine.com/kickart/fusion/setting/combobuy?tab=additionalCombo) 充值创点或升级套餐」
> - 错误码 `1501`：显示「用户套餐过期」，处理建议「请前往 [套餐开通页面](https://console.volcengine.com/kickart/fusion/setting/combobuy?tab=combo) 开通套餐」
> - 错误码 `1411`：显示「输入分辨率错误」，处理建议「请检查素材分辨率是否符合规格要求（如≥480p）」
> - 其他错误：显示原始错误信息，处理建议「稍后重试，如问题持续请联系火山技术支持」

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