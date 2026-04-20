---
name: voice-notify
description: 火山引擎语音通知发送。使用火山引擎语音服务API向指定手机号码发送语音通知。当用户需要发送语音通知时使用本技能。
license: Complete terms in LICENSE.txt
metadata: 
  openclaw:
    emoji: "📞 "
    requires:
      env:
        - VOLCENGINE_ACCESS_KEY 
        - VOLCENGINE_SECRET_KEY
    os: 
      - darwin
      - linux
    triggers:
      - 发送语音通知
      - 打语音电话
      - 语音提醒
      - 给.*发送语音
      - 语音通知

---

# 火山引擎语音通知发送技能

基于火山引擎语音服务API向指定手机号码发送语音通知。

## 适用场景

1. 用户提到「给{手机号}发送语音通知」「帮我给{手机号}打语音电话」
2. 用户提到「用{语言}给{手机号}发送语音通知」
3. 用户提到「给{手机号}发送{关键词}语音通知」
4. 用户需要通过语音方式通知重要信息

## 核心执行流程

**当你收到发送语音通知的请求时，请严格按照以下 4 个步骤依次执行：**

---

### 第 1 步：提取手机号码

从用户的指令中提取 11 位手机号码。如果用户没有提供手机号，请先询问用户。

---

### 第 2 步：查询可用号码池

执行以下命令查询号码池：

```bash
python3 scripts/voice_notify.py pool
```

从返回的 JSON 结果中：

- 查看 `Result.Records` 数组
- 选择一个 `NumberCount > 0`（有号码可用）的号码池
- 提取该号码池的 `NumberPoolNo` 字段值（例如：`NP165357678402826428`）

**注意：** 优先选择第一个有号码的号码池。

---

### 第 3 步：查询语音资源

执行以下命令查询语音资源：

```bash
python3 scripts/voice_notify.py resource
```

从返回的 JSON 结果中：

- 查看 `Result.Records` 数组
- 根据用户指令中的关键词，在资源的 `Name`、`Remark`、`TtsTemplateContent`、`Lang` 字
  段中匹配
- 选择最匹配的语音资源
- 提取该资源的 `ResourceKey` 字段值

**资源选择规则：**

1. 如果没有匹配的关键词，选择列表中的第一个资源

---

### 第 4 步：发送语音通知

执行以下命令发送语音通知：

```bash
python3 scripts/voice_notify.py send <手机号> <资源Key> <号码池编号>
```

将第 1 步提取的手机号、第 3 步提取的资源Key、第 2 步提取的号码池编号填入命令中。

---

### 第 5 步：返回结果

将 `send` 命令的返回结果直接告知用户。

---

## 脚本命令说明

| 命令       | 参数                              | 说明                   |
| ---------- | --------------------------------- | ---------------------- |
| `resource` | 无                                | 查询可用语音资源列表   |
| `pool`     | 无                                | 查询语音通知号码池列表 |
| `send`     | `<手机号> <资源Key> <号码池编号>` | 发送语音通知           |

## 完整使用示例

### 示例 1：简单发送

**用户输入：** 给13800138000发语音通知

**你的执行：**

1. 提取手机号：`13800138000`

2. 查询号码池：

```bash
python3 scripts/voice_notify.py pool
```

假设返回结果中第一个有号码的号码池的 `NumberPoolNo` 是 `NPabc`

3. 查询语音资源：

```bash
python3 scripts/voice_notify.py resource
```

假设返回结果中第一个资源的 `ResourceKey` 是 `312346368e676406285b8463931f090f4`

4. 发送语音通知：

```bash
python3 scripts/voice_notify.py send 13800138000 312346368e676406285b8463931f090f4 NPabc
```

5. 将发送结果告知用户

---

### 示例 2：指定语言

**用户输入：** 用日语给13800138000发送语音通知

**你的执行：**

1. 提取手机号：`13800138000`

2. 查询号码池：

```bash
python3 scripts/voice_notify.py pool
```
选择第一个有号码的号码池

3. 查询语音资源：
```bash
python3 scripts/voice_notify.py resource
```

在返回的资源列表中，查找 `Lang` 为 `jap` 或 `Name`/`Remark` 包含"日语"的资源，提取其 `ResourceKey`

4. 发送语音通知：

```bash
python3 scripts/voice_notify.py send 13800138000 <日语资源Key> <号码池编号>
```

5. 将发送结果告知用户

---

### 示例 3：指定关键词

**用户输入：** 给13800138000发送OCIC语音通知
**你的执行：**

1. 提取手机号：`13800138000`

2. 查询号码池：

```bash
python3 scripts/voice_notify.py pool
```

选择第一个有号码的号码池

3. 查询语音资源：

```bash
python3 scripts/voice_notify.py resource
```

在返回的资源列表中，查找 `Name` 或 `Remark` 包含"OCIC"的资源，提取其 `ResourceKey`

4. 发送语音通知：

```bash
python3 scripts/voice_notify.py send 13800138000 <OCIC资源Key> <号码池编号>
```

5. 将发送结果告知用户

---

## 环境变量

使用前需配置火山引擎访问密钥到系统环境变量或 OpenClaw 的 .env 文件：

- **VOLCENGINE_ACCESS_KEY**：火山引擎访问密钥ID
- **VOLCENGINE_SECRET_KEY**：火山引擎秘密访问密钥

获取方式：登录火山引擎控制台，在访问密钥管理中创建和获取。

## 错误处理

- 若报错 `请设置环境变量 VOLCENGINE_ACCESS_KEY 和 VOLCENGINE_SECRET_KEY`：提示用户配置火山引擎访问密钥。
- 若报错 `没有找到可用的号码池`：提示用户检查账户下是否有可用的语音通知号码池。
- 若报错 `没有找到可用的语音资源`：提示用户检查账户下是否有可用的语音资源文件。
- 遇到其他报错时直接告知用户具体错误信息。

## 参考文档

- `https://www.volcengine.com/docs/6358/166389?lang=zh` — 签名机制
- `https://www.volcengine.com/docs/6358/1722078?lang=zh` — 查询可用语音资源
- `https://www.volcengine.com/docs/6358/172952?lang=zh` — 单次发送语音通知
- `https://www.volcengine.com/docs/6358/173339?lang=zh` — 查询号码池列表