---
name: flink-sre
description: Flink SRE automation tool for managing operations such as start, stop, restart, scale-out, scale-in, and configuration updates for Flink jobs. Use this skill when the user asks to start, stop, restart, scale, resize, update configs, modify parameters, or perform any SRE operations on Flink applications/jobs/tasks. Always trigger when the user mentions terms like "start", "stop", "restart", "scale", "resize", "update config", "SRE", or equivalent Chinese phrases.
---

# Flink SRE Automation Operations Skill

自动化管理 Serverless Flink 应用的启动、停止、重启、扩容、缩容、配置修改等运维操作。

## 核心流程

### 1. 信息提取
从用户提问中提取关键信息：
- **Flink 项目名** (project_name)
- **任务名** (job_name)
- **操作类型**：启动、停止、重启、扩容、缩容、修改配置等
- **具体参数**：新的并行度、新的配置参数等

如果用户没有明确提供，主动询问缺失的关键信息。

### 2. 获取应用信息
使用 `mcporter call volceapi.list_flink_application` 获取应用列表，验证应用是否存在。

如果找到应用，使用以下工具获取详细信息：
- `get_flink_application_detail` - 获取应用详情
- `get_flink_runtime_application_info` - 获取运行时信息

### 3. 风险确认
**在执行任何变更操作前，必须向用户确认风险！**

使用以下格式向用户确认：
```
⚠️ **操作风险确认**

您将要执行以下操作：
- **操作类型**：[启动/停止/重启/扩容/缩容/修改配置]
- **目标任务**：[项目名] / [任务名]
- **当前状态**：[当前状态]
- **变更内容**：[具体变更内容]

**潜在风险**：
- [列出可能的风险，如任务中断、数据丢失、性能影响等]

请确认是否继续执行此操作？(yes/no)
```

只有当用户明确确认（回复 yes、确认、继续等）后，才继续执行操作。

### 4. 执行操作

#### 启动任务
使用 `mcporter call volceapi.start_flink_application` 启动任务。

**命令格式**：
```bash
mcporter call volceapi.start_flink_application project_name="xxx" job_name="xxx"
```

#### 停止任务
使用 `mcporter call volceapi.stop_flink_application` 停止任务。

**命令格式**：
```bash
mcporter call volceapi.stop_flink_application project_name="xxx" job_name="xxx"
```

#### 重启任务
使用 `mcporter call volceapi.restart_flink_application` 重启任务。

**命令格式**：
```bash
mcporter call volceapi.restart_flink_application project_name="xxx" job_name="xxx"
```

#### 扩容/缩容任务
扩容/缩容需要以下步骤：

**⚠️ 重要原则**：
1. **必须首先获取原先的任务配置** - 使用 `get_flink_application_draft` 获取完整的当前配置
2. **只修改并行度这一个参数** - 绝对不能修改其他任何配置参数
3. **保持其他所有配置不变** - 确保只更新 `parallelism.default` 这一个参数
4. **使用完整配置更新** - 更新时传入完整的配置，只修改并行度字段

**详细步骤**：
1. **获取当前应用草稿** - 使用 `get_flink_application_draft` 获取完整的当前配置
2. **展示当前配置给用户确认** - 向用户展示当前的并行度和其他配置
3. **只修改并行度配置** - 只修改 `parallelism.default` 这一个参数，其他所有配置保持原样
4. **更新应用草稿** - 使用 `update_flink_application_draft`，传入完整的配置（只修改并行度）
5. **部署应用草稿** - `deploy_flink_application_draft`
6. **重启任务** - `restart_flink_application`

**关键验证点**：
- 更新前必须向用户确认："我们只会修改并行度这一个参数，其他配置保持不变，确认吗？"
- 更新后必须验证：并行度是否正确变更，其他配置是否保持不变

#### 修改配置参数
修改配置参数需要以下步骤：
1. 获取应用草稿：`get_flink_application_draft`
2. 更新应用草稿：`update_flink_application_draft`（修改配置参数）
3. 部署应用草稿：`deploy_flink_application_draft`
4. 重启任务：`restart_flink_application`

**详细步骤**：
1. 首先获取当前应用草稿
2. 修改指定的配置参数
3. 部署新的草稿版本
4. 重启任务使配置生效

### 5. 验证操作结果
操作执行完成后，使用以下工具验证结果：
- `list_flink_application` - 查看任务状态是否变更
- `get_flink_application_detail` - 查看最新的应用详情
- `get_flink_runtime_application_info` - 查看运行时信息

向用户报告操作结果。

## 操作类型说明

| 操作类型 | 描述 | 需要确认 |
|---------|------|---------|
| **启动任务** | 启动已停止的 Flink 任务 | ✅ 是 |
| **停止任务** | 停止正在运行的 Flink 任务 | ✅ 是 |
| **重启任务** | 重启 Flink 任务（先停止再启动） | ✅ 是 |
| **扩容任务** | 增加任务的并行度 | ✅ 是 |
| **缩容任务** | 减少任务的并行度 | ✅ 是 |
| **修改配置** | 修改 Flink 任务的配置参数 | ✅ 是 |

## 风险提示模板

### 启动任务风险
- 任务启动可能需要较长时间
- 如果任务有积压数据，启动后可能需要时间追赶
- 启动失败可能需要手动干预

### 停止任务风险
- 任务停止后，数据处理将中断
- 可能导致数据延迟
- 停止失败可能需要手动干预

### 重启任务风险
- 任务会短暂中断
- 可能导致数据延迟
- 重启失败可能需要手动干预
- Checkpoint 可能需要重新开始

### 扩容/缩容风险
- 任务会重启，导致短暂中断
- 可能导致数据延迟
- 扩容后可能需要更多资源
- 缩容可能影响处理性能
- 重新部署可能失败

### 修改配置风险
- 任务会重启，导致短暂中断
- 可能导致数据延迟
- 配置错误可能导致任务启动失败
- 需要验证新配置的正确性

## 输出格式

**ALWAYS 使用以下格式输出操作结果：**

```
# ⚙️ Flink SRE 操作执行结果

## 📋 操作信息
- **操作类型**: [操作类型]
- **项目名**: [项目名]
- **任务名**: [任务名]
- **执行时间**: [时间]

## ✅ 操作结果
[描述操作是否成功]

## 📊 当前状态
- **任务状态**: [当前状态]
- **并行度**: [当前并行度]
- **其他关键信息**: [其他信息]

## 💡 后续建议
[给出后续操作建议]
```

## 注意事项

### 重要：扩容/缩容的特殊要求

⚠️ **扩容/缩容时必须遵守以下规则**：

1. **必须首先获取原先的任务配置** - 使用 `get_flink_application_draft` 获取完整的当前配置
2. **绝对不能修改其他参数** - 只能修改 `parallelism.default` 这一个参数
3. **保持其他所有配置不变** - 所有其他配置必须与原配置完全一致
4. **使用完整配置更新** - 更新时传入完整的配置，只修改并行度字段
5. **向用户明确说明** - 在操作前向用户说明："我们只会修改并行度这一个参数，其他配置保持不变"
6. **操作后验证** - 验证并行度是否正确变更，其他配置是否保持不变

### 通用注意事项

1. **始终先确认风险**：在执行任何变更操作前，必须向用户确认风险
2. **先获取应用信息**：在执行操作前，先获取应用的详细信息
3. **验证操作结果**：操作执行完成后，必须验证结果
4. **提供清晰的反馈**：向用户提供清晰的操作结果和后续建议
5. **使用友好的语言**：用用户能理解的语言解释操作和风险
6. **避免过度技术化**：除非用户要求，否则避免过度技术化的解释
7. **错误处理**：如果操作失败，向用户说明失败原因，并提供解决方案

## 常用配置参数

以下是一些常用的 Flink 配置参数，可以通过修改配置来调整：

- `parallelism.default` - 默认并行度
- `taskmanager.memory.process.size` - TaskManager 内存大小
- `jobmanager.memory.process.size` - JobManager 内存大小
- `taskmanager.numberOfTaskSlots` - TaskManager slot 数量
- `execution.checkpointing.interval` - Checkpoint 间隔
- `execution.checkpointing.timeout` - Checkpoint 超时时间
- `restart-strategy` - 重启策略
- `state.backend.type` - 状态后端类型

## 工具调用顺序

### 启动任务
1. `list_flink_application` - 验证应用存在
2. **风险确认** - 向用户确认风险
3. `start_flink_application` - 启动任务
4. `list_flink_application` - 验证操作结果

### 停止任务
1. `list_flink_application` - 验证应用存在
2. **风险确认** - 向用户确认风险
3. `stop_flink_application` - 停止任务
4. `list_flink_application` - 验证操作结果

### 重启任务
1. `list_flink_application` - 验证应用存在
2. **风险确认** - 向用户确认风险
3. `restart_flink_application` - 重启任务
4. `list_flink_application` - 验证操作结果

### 扩容/缩容任务
1. `list_flink_application` - 验证应用存在
2. `get_flink_application_draft` - **获取完整的当前配置**
3. **展示当前配置** - 向用户展示当前的并行度和其他配置
4. **参数修改确认** - 向用户确认："我们只会修改并行度这一个参数，其他配置保持不变，确认吗？"
5. **风险确认** - 向用户确认风险
6. `update_flink_application_draft` - **只修改并行度这一个参数**，保持其他所有配置不变
7. `deploy_flink_application_draft` - 部署新草稿
8. `restart_flink_application` - 重启任务
9. `list_flink_application` - 验证操作结果
10. **验证配置变更** - 验证并行度是否正确变更，其他配置是否保持不变

### 修改配置
1. `list_flink_application` - 验证应用存在
2. `get_flink_application_draft` - 获取应用草稿
3. **风险确认** - 向用户确认风险
4. `update_flink_application_draft` - 更新配置参数
5. `deploy_flink_application_draft` - 部署新草稿
6. `restart_flink_application` - 重启任务
7. `list_flink_application` - 验证操作结果