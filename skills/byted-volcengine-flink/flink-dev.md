---
name: flink-dev
description: Flink SQL development and deployment tool for creating, developing, deploying, and debugging Flink SQL jobs. Use this skill when the user asks to create, develop, deploy, debug, write SQL, or work on Flink SQL jobs/tasks/applications. Always trigger when the user mentions terms like "create SQL", "develop SQL", "deploy SQL", "debug SQL", "write SQL", "Flink SQL", or equivalent Chinese phrases.
---

# Flink SQL Development and Deployment Skill

自动化创建、开发、部署和调试 Flink SQL 任务。

## 核心流程

### 1. 信息提取
从用户提问中提取关键信息：
- **Flink 项目名** (project_name)
- **任务名** (job_name)
- **SQL 逻辑描述**：用户想要实现的业务逻辑
- **数据源**：Kafka、Paimon、MySQL 等
- **数据目标**：输出到哪里

如果用户没有明确提供，主动询问缺失的关键信息。

### 2. SQL 代码生成
根据用户的逻辑描述，生成 Flink SQL 代码。

**生成 SQL 时需要考虑：
- 数据源的连接配置（Kafka、Paimon、MySQL 等）
- 数据表的 schema 定义
- 业务逻辑的实现
- 水位线（Watermark）设置
- 窗口函数（如需要）
- 输出目标的配置

**向用户展示生成的 SQL 代码，并询问是否需要调整和优化。

### 3. SQL 逻辑确认
在用户确认 SQL 逻辑后，再继续后续步骤。

**在执行任何变更操作前，必须向用户确认！**

### 4. 创建和部署流程

#### 步骤 1：创建应用草稿
使用 `mcporter call volceapi.create_flink_application_draft` 创建应用草稿。

**命令格式**：
```bash
mcporter call volceapi.create_flink_application_draft project_name="xxx" job_name="xxx" ...
```

#### 步骤 2：获取应用草稿
使用 `mcporter call volceapi.get_flink_application_draft` 获取应用草稿，检查 SQL 代码。

**命令格式**：
```bash
mcporter call volceapi.get_flink_application_draft project_name="xxx" job_name="xxx"
```

#### 步骤 3：更新应用草稿
如果需要修改 SQL 代码或配置，使用 `mcporter call volceapi.update_flink_application_draft` 更新应用草稿。

**命令格式**：
```bash
mcporter call volceapi.update_flink_application_draft project_name="xxx" job_name="xxx" ...
```

#### 步骤 4：部署应用草稿
使用 `mcporter call volceapi.deploy_flink_application_draft` 部署应用草稿。

**命令格式**：
```bash
mcporter call volceapi.deploy_flink_application_draft project_name="xxx" job_name="xxx"
```

#### 步骤 5：启动应用
使用 `mcporter call volceapi.start_flink_application` 启动已部署的应用。

**重要**：开发期间从全新启动，不要从 savepoint 恢复。

**命令格式**：
```bash
mcporter call volceapi.start_flink_application project_name="xxx" job_name="xxx"
```

### 5. 调试流程

#### 步骤 1：检查任务状态
使用 `mcporter call volceapi.list_flink_application` 检查任务状态。

#### 步骤 2：获取应用日志
使用 `mcporter call volceapi.list_flink_application_log` 获取应用日志。

**日志查询策略**：
- 如果用户提供了故障时间，使用该时间范围
- 如果没有提供，查询最近 1 小时的日志
- 查询 ERROR 级别日志，同时查看 WARNING 级别
- 查询 JOBMANAGER 和 TASKMANAGER 组件的日志

**命令格式**：
```bash
mcporter call volceapi.list_flink_application_log \
  project_name="xxx" \
  job_name="xxx" \
  start_time="YYYY-MM-DDTHH:MM:SS" \
  end_time="YYYY-MM-DDTHH:MM:SS" \
  level="ERROR"
```

#### 步骤 3：分析错误
如果发现异常报错：

1. **停止任务**（仅停止当前正在调试的任务！）
   ```bash
   mcporter call volceapi.stop_flink_application project_name="xxx" job_name="xxx"
   ```
   ⚠️ **重要**：只能停止用户明确要求调试的任务，绝对不能停止其他任务！

2. **根据报错信息更新应用草稿**
   ```bash
   mcporter call volceapi.update_flink_application_draft project_name="xxx" job_name="xxx" ...
   ```

3. **重新部署应用草稿**
   ```bash
   mcporter call volceapi.deploy_flink_application_draft project_name="xxx" job_name="xxx"
   ```

4. **重新启动应用**
   ```bash
   mcporter call volceapi.start_flink_application project_name="xxx" job_name="xxx"
   ```

5. **重新检查日志，确认是否还有错误**

#### 步骤 4：重复调试循环
重复上述步骤，直到任务启动后没有报错。

### 6. 验证正常运行
当任务启动后没有报错，才算正常运行。

向用户提供以下信息：
- 任务状态
- 任务配置信息
- 运行时信息
- Flink UI 地址
- 后续使用建议

## 重要安全规则

### ⚠️ 绝对不能做的事情

1. **绝对不能停止不相关的任务**
    - 只能停止用户明确要求调试的任务
    - 在停止任务前，必须明确确认是当前正在调试的任务
    - 如果有任何疑问，先询问用户，不要擅自停止

2. **绝对不能修改不相关的任务**
    - 只能修改用户明确要求开发/调试的任务
    - 在修改任务前，必须明确确认

3. **绝对不能部署不相关的任务**
    - 只能部署用户明确要求开发/调试的任务

### ✅ 必须做的事情

1. **明确任务范围**
    - 在执行任何操作前，明确确认是哪个任务
    - 向用户重复确认任务名和项目名

2. **风险确认**
    - 在执行任何变更操作前，向用户确认风险
    - 明确说明可能的影响

3. **操作后验证**
    - 执行操作后，验证操作结果
    - 确认没有影响其他任务

## 输出格式

### SQL 代码生成反馈

```
# 📝 Flink SQL 代码生成

## 📋 任务信息
- **项目名**: [项目名]
- **任务名**: [任务名]
- **业务逻辑**: [业务逻辑描述]

## 💻 生成的 SQL 代码
```sql
[生成的 SQL 代码]
```

## ❓ 确认问题
1. SQL 逻辑是否正确？
2. 是否需要调整或优化？
3. 确认后继续部署？(yes/no)
```

### 操作风险确认

```
⚠️ **操作风险确认**

您将要执行以下操作：
- **操作类型**: [创建/部署/启动/停止/调试]
- **目标任务**: [项目名] / [任务名]
- **当前状态**: [当前状态]
- **变更内容**: [具体变更内容]

**潜在风险**：
- [列出可能的风险]

**重要**：此操作只会影响 [任务名]，不会影响其他任务。

请确认是否继续执行此操作？(yes/no)
```

### 调试流程反馈

```
# 🔍 Flink SQL 任务调试

## 📋 任务信息
- **项目名**: [项目名]
- **任务名**: [任务名]
- **当前状态**: [当前状态]

## 🐛 错误信息
[发现的错误信息]

## 🔧 修复方案
[修复方案描述]

## ❓ 确认问题
是否按照此方案修复？(yes/no)
```

### 成功完成反馈

```
# ✅ Flink SQL 任务开发完成

## 📋 任务信息
- **项目名**: [项目名]
- **任务名**: [任务名]
- **当前状态**: [当前状态]
- **完成时间**: [时间]

## 📊 任务配置
[关键配置信息]

## 🌐 Flink UI
[Flink UI 地址]

## 💡 后续建议
[后续使用建议]
```

## 常用 Flink SQL 模板

### Kafka 源表模板

```sql
CREATE TABLE source_table (
  -- 字段定义
) WITH (
  'connector' = 'kafka',
  'topic' = 'topic-name',
  'properties.bootstrap.servers' = 'kafka-server:9092',
  'properties.group.id' = 'group-id',
  'scan.startup.mode' = 'latest-offset',
  'format' = 'json'
);
```

### Paimon 目标表模板

```sql
CREATE TABLE sink_table (
  -- 字段定义
) WITH (
  'connector' = 'paimon',
  'path' = 'tos://bucket/path',
  'warehouse' = 'tos://bucket/path',
  'auto-create' = 'true'
);
```

### 带 Watermark 的流处理

```sql
CREATE TABLE source_table (
  -- 字段定义
  event_time TIMESTAMP(3),
  WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH (
  -- 连接器配置
);
```

## 工具调用顺序

### 创建 SQL 任务开发完整流程

1. **信息提取** - 从用户提问中提取信息
2. **SQL 代码生成** - 根据逻辑描述生成 SQL
3. **用户确认 SQL** - 向用户展示 SQL，等待确认
4. **风险确认** - 向用户确认风险
5. **创建应用草稿** - `create_flink_application_draft`
6. **获取应用草稿** - `get_flink_application_draft`
7. **更新应用草稿** - `update_flink_application_draft`（如需要）
8. **部署应用草稿** - `deploy_flink_application_draft`
9. **启动应用** - `start_flink_application`
10. **检查任务状态** - `list_flink_application`
11. **获取日志** - `list_flink_application_log`
12. **分析错误** - 如果有错误，停止任务 → 更新 → 重新部署 → 重新启动
13. **重复调试循环** - 直到没有错误
14. **验证正常运行** - 提供最终结果

### 调试循环（发现错误时）

1. **获取日志** - `list_flink_application_log`
2. **分析错误**
3. **停止任务** - `stop_flink_application`（⚠️ 仅停止当前调试的任务！）
4. **更新应用草稿** - `update_flink_application_draft`
5. **部署应用草稿** - `deploy_flink_application_draft`
6. **启动应用** - `start_flink_application`
7. **检查日志** - 确认是否还有错误
8. **重复** - 直到没有错误

## 注意事项

1. **任务范围确认**：在执行任何操作前，明确确认是哪个任务
2. **绝不影响其他任务**：绝对不能停止、修改、部署不相关的任务
3. **风险确认**：在执行任何变更操作前，必须向用户确认风险
4. **先获取信息**：在执行操作前，先获取应用的详细信息
5. **验证操作结果**：操作执行完成后，必须验证结果
6. **提供清晰反馈**：向用户提供清晰的操作结果和后续建议
7. **使用友好语言**：用用户能理解的语言解释操作和风险
8. **避免过度技术化**：除非用户要求，否则避免过度技术化的解释
9. **错误处理**：如果操作失败，向用户说明失败原因，并提供解决方案
10. **调试循环**：调试时，要有耐心，重复直到成功