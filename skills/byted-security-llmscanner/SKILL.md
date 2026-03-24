---
name: byted-security-llmscanner
description: 大模型安全测评全流程管理工具。支持创建/更新模型和智能体测评资产、查询可用资源、发起合规测评任务、发起安全测评任务、分析测评结果等全流程操作。
---

# 大模型安全测评全流程管理技能使用指南

## 触发条件
当用户发送包含"创建资产"、"更新资产"、"发起测评"、"分析测评"、"查询资源"等关键词的指令时，触发本技能。

---

## 脚本位置说明

**脚本目录：** `~/.openclaw/workspace/skills/byted-security-llmscanner/scripts/`

**执行方式：**
```bash
cd ~/.openclaw/workspace/skills/byted-security-llmscanner/scripts
npx ts-node src/create_asset_model.ts <参数...>
```

**以下示例均需先进入脚本目录**

---

## ⚠️ 易错点说明

### 1. 资产ID vs 资产名称
- **`update_asset_model.ts`** 的第一个参数是 `Name`（资产名称），不是 `AssetID`。脚本会自动根据名称和ModelID查询资产ID。
- **`update_asset_agent.ts`** 的参数是 `<AgentID> <Name> <PlatformID>`，需要同时提供资产ID和名称。

### 2. 脚本代码问题
- 部分脚本可能存在重复属性问题（如 `proxy: false` 重复），导致 TypeScript 编译错误。如遇此类错误，需要检查并修复脚本代码。

### 3. 模态类型匹配
- 资产的模态类型必须包含测评集的模态类型，否则无法发起测评。
- 例如：测评集是 `text2text`，资产的模态类型可以是 `text2text` 或 `text2text,image2text`，但不能只有 `image2text`。

### 4. 智能体平台参数
- 不同智能体平台需要不同的参数，必须先用 `list_agent_platforms.ts vars <PlatformID>` 查询该平台需要的参数。

### 5. 安全测评剧本适用范围
- 部分安全测评剧本专门针对 OpenClaw，部分是通用的。查询剧本时会显示 `assetTypes`[] 字段，如果为空则表示通用。

---

## 通用枚举

### 模态类型
- `text2text`：文生文
- `image2text`：图文生文
- `text2image`：文生图

### 资产类型
- `model`：大模型
- `agent`：智能体
- `openclaw`：OpenClaw 资产

### 合规测评任务状态
| 状态码 | 状态名称 | 说明 |
| --- | --- | --- |
| 0 | 待测评 | 任务已创建，等待开始执行 |
| 1 | 测评中 | 任务正在执行 |
| 2 | 测评成功 | 任务执行完成（终态） |
| 3 | 测评异常 | 任务执行失败（终态） |
| 5 | 暂停测评 | 任务被暂停（终态） |
| 6 | 终止测评 | 任务被终止（终态） |

### 安全测评任务状态
| 状态码 | 状态名称 | 说明 |
| --- | --- | --- |
| 10 | 等待处理 | 任务已创建，等待开始执行 |
| 20 | 处理中 | 任务正在执行 |
| 30 | 异常 | 任务执行失败（终态） |
| 40 | 完成 | 任务执行完成（终态） |

---

## 资产管理

### 1. 创建大模型资产

**调用：**
```bash
npx ts-node src/create_asset_model.ts <Name> <ModelID> <BaseUrl> <ApiKey> [ModalTypes]
```

**参数：**
- `Name`：资产名称（如：deepseek-v3）
- `ModelID`：模型 ID（如：ep-20250325142301-ljxvm）
- `BaseUrl`：API 地址（如：https://ark-cn-beijing.bytedance.net/api/v3）
- `ApiKey`：API 密钥（如：sk-xxxxxxxxxxxx）
- `ModalTypes`：模态类型（可选，逗号分隔，默认：text2text）

**示例：**
```bash
npx ts-node src/create_asset_model.ts deepseek-v3 ep-20250325142301-ljxvm https://ark-cn-beijing.bytedance.net/api/v3 sk-xxxxxxxxxxxx text2text
```

---

### 2. 更新大模型资产

**调用：**
```bash
npx ts-node src/update_asset_asset_model.ts <Name> <ModelID> <BaseUrl> <ApiKey> [ModalTypes]
```

**参数：**
- `Name`：资产名称（⚠️ 注意：不是 AssetID，脚本会自动查询）
- `ModelID`：模型 ID
- `BaseUrl`：API 地址
- `ApiKey`：API 密钥
- `ModalTypes`：模态类型（可选，逗号分隔，默认：text2text）

**示例：**
```bash
npx ts-node src/update_asset_model.ts deepseek-v3 ep-new-model-id https://ark-cn-beijing.bytedance.net/api/v3 sk-new-api-key text2text
```

**⚠️ 注意：**
- 第一个参数是 `Name`（资产名称），不是 `AssetID`
- 脚本会根据 `Name` 和 `ModelID` 自动查询资产ID

---

### 3. 查询智能体平台

**调用：**
```bash
# 查询所有平台
npx ts-node src/list_agent_platforms.ts list

# 查询平台需要的变量
npx ts-node src/list_agent_platforms.ts vars <PlatformID>
```

**⚠️ 注意：**
- 创建智能体资产前，必须先查询该平台需要的参数
- 不同平台需要的参数不同，例如 dify 平台需要 `api_key`，hiagent 平台可能需要其他参数

---

### 4. 创建智能体资产

**调用：**
```bash
npx ts-node src/create_asset_agent.ts <Name> <PlatformID> [options]
```

**参数：**
- `Name`：智能体资产名称
- `PlatformID`：平台 ID（通过 `list_agent_platforms.ts list` 查询）
- `--key=value`：智能体对话变量（可多个，支持 JSON 格式）

**示例：**
```bash
npx ts-node src/create_asset_agent.ts 客服助手 b0226c4550aa4791a8c19a118a5f8ef5 --api_key=app-xxxxxxxxxxxx
```

**⚠️ 注意：**
- 必须先用 `list_agent_platforms.ts vars <PlatformID>` 查询该平台需要的参数
- 参数格式为 `--key=value`，例如 `--api_key=app-xxx`、`--user_id=admin`

---

### 5. 更新智能体资产

**调用：**
```bash
npx ts-node src/update_asset_agent.ts <AgentID> <Name> <PlatformID> [options]
```

**参数：**
- `AgentID`：资产 ID
- `Name`：智能体资产名称
- `PlatformID`：平台 ID
- `--key=value`：智能体对话变量（可多个，支持 JSON 格式）

**示例：**
```bash
npx ts-node src/update_asset_agent.ts asset_9876543210 客服助手 b0226c4550aa4791a8c19a118a5f8ef5 --api_key=app-zzzzzzzzzzzz
```

**⚠️ 注意：**
- 参数顺序是 `<AgentID> <Name> <PlatformID>`，与创建智能体不同
- 需要同时提供资产ID和名称

---

## 资源查询

### 6. 查询可用资源

**调用：**
```bash
# 查询合规测评资源（测评集、资产）
npx ts-node src/list_resources.ts [ModalTypes]

# 查询安全测评资源（资产、剧本）
npx ts-node src/fetch_lists.ts [ModalTypes]

# 查询安全测评剧本
npx ts-node src/list_rt_scenarios.ts [AssetType]
```

**参数：**
- `ModalTypes`：模态类型（可选，逗号分隔，如：text2text,image2text）
- `AssetType`：资产类型（可选，用于筛选剧本）

**输出示例：**
```
=== 可用测评集 ===
ID: suite_001, 名称: 安全合规测评集, 模态: 文生文

=== 可用大模型资产 ===
ID: asset_001, 名称: deepseek-v3, 模态: 文生文

=== 可用智能体资产 ===
ID: asset_003, 名称: 客服助手, 模态: 文生文
```

**⚠️ 注意：**
- 查询资源时会显示资产的模态类型，确保资产的模态类型包含测评集的模态类型
- 例如：测评集是 `text2text`，资产的模态类型可以是 `text2text` 或 `text2text,image2text`

---

## 合规测评

### 7. 发起合规测评任务

**调用：**
```bash
npx ts-node src/create_task.ts <测评集ID> <资产ID> [AssetType]
```

**参数：**
- `测评集ID`：测评集的唯一标识符
- `资产ID`：测评对象的唯一标识符（模型、智能体或 OpenClaw）
- `AssetType`：资产类型（可选，默认：model）

**⚠️ 注意：**
- 资产的模态类型必须包含测评集的模态类型，否则无法发起测评
- 如果资产模态类型不匹配，会返回错误

---

### 8. 分析合规测评任务

**调用：：**
```bash
npx ts-node src/run_analysis.ts <TaskID>
```

**参数：**
- `TaskID`：任务 ID（格式如：019ce0495b68758ea00fda8fc63b2ba0）

**功能：**
- 查询任务状态
- 如果任务成功完成，自动拉取数据并分析
- 如果任务未完成，显示执行进度和预估时间
- 如果任务异常/暂停/终止，显示状态并提示无法分析

**输出（任务已完成）：**
```
任务状态：测评成功（状态码：2）
数据总量：76 条
安全通过：45 (59.2%)
发现风险：31 (40.8%)
```

**输出（任务未完成）：**
```
任务状态：测评中（状态码：1）
执行进度：30/76 (39.5%)
预计剩余时间：1分钟
```

---

## 安全测评

### 9. 发起安全测评任务

**调用：**
```bash
npx ts-node src/create_rt_task.ts <TaskName> <AssetID> <AssetType> <ScenarioID>
```

**参数：**
- `TaskName`：任务名称（如：提示词注入测试）
- `AssetID`：测评对象 ID（模型、智能体或 OpenClaw）
- `AssetType`：资产类型（model/agent/openclaw）
- `ScenarioID`：安全测评剧本 ID（通过 `list_rt_scenarios.ts` 查询）

**⚠️ 注意：**
- 部分剧本专门针对 OpenClaw，部分是通用的
- 查询剧本时会显示 `assetTypes`[] 字段，如果为空则表示通用
- 如果是 OpenClaw 专用剧本，资产类型必须是 `openclaw`

---

### 10. 分析安全测评任务

**调用：**
```bash
npx ts-node src/analyze_rt_task.ts <TaskID>
```

**参数：**
- `TaskID`：任务 ID

**功能：**
- 查询安全测评任务报告
- 自动拉取报告数据并分析

**输出：**
```
任务状态：完成
资产名称：deepseek-v3
资产类型：model

【按测评结果分】
  失陷（Fall）：5 个
  风险（Risk）：10 个
  总计：15 个

【按严重度分】
  🔴 高：3 个
  🟡 中：7 个
  🟢 低：5 个

【风险详情】
  风险名称：提示词注入成功
  严重程度：🔴 HIGH
  评分：8/10

通过率：80.0% (60/75)
失败率：20.0% (15/75)
```

**⚠️ 注意：**
- 如果任务状态是 `20`（处理中），需要等待任务完成后再分析
- 可以多次运行此命令查询任务进度
