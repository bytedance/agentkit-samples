---
name: byted-kickart-ai-beauty
description: 分析用户输入的图片，对画面中的人智能美颜，输出美颜后的图片，支持单张JPG、PNG格式，也支持多张图片URL或批量处理压缩包中的图片文件。当用户提及美颜、美化、美白、磨皮、瘦脸、人像美化、照片美颜、自动美颜、AI美颜时触发使用
version: 1.2.1
---

# 智能美颜SKILL

## 📋 工具说明

### 核心功能
分析用户输入的图片，对画面中的人智能美颜，输出美颜后的图片。

### 可用命令
| 命令 | 功能 | 说明 |
|------|------|------|
| `python scripts/plan.py` | 套餐查询 | 查询用户当前的 Ark Claw 套餐 |
| `python scripts/beauty.py --file <图片路径> --output <输出文件>` | 智能美颜处理 | 对图片进行智能美颜处理 |

### 📥 图片获取方式
支持以下四种方式获取图片：
1. **本地文件**：直接提供本地图片文件的绝对路径
2. **网络图片URL**：直接提供网络图片URL地址，无需先下载，工具自动处理
3. **多张图片URL**：提供多个图片URL，用逗号分隔，工具依次处理并打包为zip返回
4. **图片压缩包**：用户可以上传一个包含多张图片的压缩包，**直接将压缩包路径传给beauty.py**，工具会自动解压并处理其中的所有图片，无需手动解压。

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
   > 直接在此处发送您的Access Key ID和Secret Access Key，我会帮您完成临时环境变量配置
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
  python scripts/plan.py
  ```
- **步骤4：结果处理逻辑**
  - ✅ **套餐有效**：返回结果中的 `message` 字段为有效截止时间（北京时间），校验通过
  - ❌ **套餐已过期**：`message` 小于等于当前时间，引导用户开通套餐，终止流程
  - ❌ **接口调用错误**：参考「错误处理规范」匹配错误码，向用户明确告知错误原因和解决方案，并且终止流程

---

## 🛠️ 智能美颜处理执行流程

### 前置准备
1. 确保输出目录存在：`mkdir -p /tmp/openclaw/ai-beauty/output`
2. 生成唯一输出文件名：`ai_beauty_<timestamp>_<random>.json`
3. 准备本地图片文件：支持JPG、PNG格式，也支持批量图片压缩后的压缩包。

### 输入类型自动识别
- **图片压缩包**：路径以 `.zip`, `tar`, `tar.gz` 等压缩包格式结尾 → 自动解压并批量处理，**直接传入压缩包路径即可，无需手动解压**
- **多张URL**：包含逗号且包含 `http://` 或 `https://` → 依次处理每张URL并打包为zip
- **单张图片/URL**：其他情况 → 单张图片处理

### 执行步骤
1. **输入**：用户提供的本地图片文件路径、图片URL、多个图片URL（逗号分隔）、或图片压缩包路径
2. **工具调用**：执行 `python scripts/beauty.py --file <输入路径/URL> --output <输出文件>` 命令
3. **输出**：JSON格式的处理结果


### 输出JSON格式说明
#### 单张图片
**处理成功：**
```json
{
  "image_name": "原图片文件名",
  "result_url": "美颜后的图片URL"
}
```

**处理失败：**
```json
{
  "image_name": "原图片文件名",
  "error_code": "错误码",
  "error_msg": "错误原因"
}
```

#### 批量URL或图片压缩包
```json
{
  "success_count": 3,
  "failed_count": 1,
  "total_count": 4,
  "results": [
    {
      "image_name": "原图片文件名1",
      "result_url": "美颜后的图片URL",
      "success": true
    },
    {
      "image_name": "原图片文件名2",
      "error_code": "错误码",
      "error_msg": "错误原因",
      "success": false
    }
  ],
  "zip_path": "/path/to/beauty_images.zip"
}
```
| 字段 | 类型 | 说明 |
|:---:|:---:|:---|
| `success_count` | int | 成功处理的图片数量 |
| `failed_count` | int | 处理失败的图片数量 |
| `total_count` | int | 总图片数量 |
| `results` | array | 所有图片的处理结果列表 |
| `zip_path` | string | 打包好的所有美颜后图片的本地zip路径 |

**results数组中每个元素的字段说明：**
| 字段 | 类型 | 说明 |
|:---:|:---:|:---|
| `image_name` | string | 原始图片文件名 |
| `result_url` | string | 成功时返回美颜后的图片URL |
| `success` | bool | 处理是否成功 |
| `error_code` | string | 失败时返回错误码（0表示成功，其他为错误码） |
| `error_msg` | string | 失败时返回错误原因 |

### 返回格式说明

❌ 禁止自由发挥，补充其他内容，如文字描述、图片描述等
❌ 禁止返回美颜的优化细节，只返回美颜后的图片URL或ZIP包下载链接
❌ 禁止返回脚本执行的中间细节，比如任务ID、处理时间等，只返回美颜后的图片URL或ZIP包下载链接

***严格按照以下格式返回给用户***

#### 单张图片输入场景

1. ✅ 处理完成状态
2. 🔗 带完整签名的火山链接URL（可点击）

***正向示例1***
✅ AI美颜处理成功！请点击链接预览或下载图片（有效期24小时，请及时下载）：
https://example.com/beauty.jpg

***正向示例2***
❌ AI美颜处理失败！未检测到人脸，请上传包含清晰人脸的图片重试

#### 批量URL输入场景

1. ✅ 处理完成状态
2. 🔗 每张图对应的完整签名的火山链接URL（可点击）
3. 📚 压缩包本地路径

***正向示例3***
✅ AI美颜处理成功！请点击链接预览或下载图片（有效期24小时，请及时下载）：
image1：https://example.com/beauty1.jpg
image2：https://example.com/beauty2.jpg
打包下载路径：/path/to/beauty_results.zip

***正向示例4***
✅ AI美颜处理成功！请点击链接预览或下载图片（有效期24小时，请及时下载）：
image1：https://example.com/beauty1.jpg
image4：https://example.com/beauty3.jpg
image2,image3：[脚本返回的具体失败原因]
打包下载路径：/path/to/beauty_results.zip


#### 图片压缩包输入场景
1. ✅ 处理完成状态
2. 🔗 压缩包本地路径

***正向示例5***
✅ AI美颜处理成功！请及时下载美颜后的图片压缩包：
打包下载路径：/path/to/beauty_results.zip

***正向示例6***
✅ AI美颜处理成功！
- 成功处理4/6张图片
- 失败2张图片，sample1.jpg: [失败原因1], sample2.jpg: [失败原因2]
打包下载路径：/path/to/beauty_results.zip

***正向示例7***
❌ AI美颜处理失败！所有的图片都未检测到人脸，请上传包含清晰人脸的图片重试


### Agent执行特殊要求
1. **超时设置**：调用exec工具启动脚本时，设置≥180000ms（3分钟）的yieldMs
2. **友好提示**：若脚本未立即返回结果，先回复用户："正在为您进行美颜处理，任务执行时间可能较长，请您稍候~"
3. **异常处理**：若脚本因超时/异常退出，立即使用持久化的Task ID调用任务查询接口确认后端状态，禁止直接判定任务失败
4. **返回结果**：单张图直接返回图片URL；批量图片处理返回zip包下载链接，如果zip文件太大无法直接发送，返回zip包路径
5. **批量处理**：若用户上传的是图片压缩包，工具会自动解压并处理其中的所有图片，**自动下载所有美颜后的图片并打包为zip包**，无需额外手动下载打包。

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
| 1416 | 输入媒体数量错误 | 用户输入的素材数量超过限制 | 提供的媒体素材数量超出限制，多出的素材可能不会使用 |
| 1417 | 大模型调用错误 | 模型调用出错，通常是输入参数错误 | 媒体素材处理存在问题，请重新尝试，如问题持续请联系火山技术支持 |
| 1501 | 用户套餐过期 | 调用接口时，用户套餐已过期 | 请前往 [套餐开通页面](https://console.volcengine.com/kickart/fusion/setting/combobuy?tab=combo) 开通套餐 |
| 100010 | 签名验证失败 | AK/SK签名验证失败 | 请检查您提供的火山鉴权AK/SK是否正确，可访问[火山引擎控制台](https://console.volcengine.com/iam/keymanage)确认 |
| 100013 | 缺少服务权限 | 缺少iccloud\_muse服务的RegisterArkClawCombo权限 | 您的企业账号未开通Kickart权限，请联系火山主账号管理员为您开通，或详询火山技术支持 |
| x01001 | AK/SK未配置 | 用户未配置AK/SK | 请输入火山鉴权的AK/SK，可访问[火山引擎控制台](https://console.volcengine.com/iam/keymanage)获取 |
| x01010 | 有效套餐缺失 | 素材上传出现错误，通常是套餐原因 | 请前往 [套餐开通页面](https://console.volcengine.com/kickart/fusion/setting/combobuy?tab=combo) 开通套餐 |
| 2000 | URL不合法或未检测到人脸 | 提交的URL格式错误或未检测到人脸 | 请检查URL是否正确，仅支持人脸图进行美颜处理 |
| 其他 | \- | 未明确列出的其他错误情况 | 稍后重试，如问题持续请联系火山技术支持 |
---
