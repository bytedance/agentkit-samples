---
name: flink-resource
description: Intelligent diagnostic tool for Serverless Flink applications. Use this skill whenever the user asks about Flink job resources, task errors, failures, exceptions, performance issues, OOM, checkpoint issues, connectivity problems, or any Flink-related troubleshooting. Always trigger when the user mentions terms like "Flink", "troubleshoot", "diagnose", "OOM", "checkpoint", "timeout", or equivalent Chinese phrases.
---

# Flink Job Resource Analysis Skill

分析资源池水位与任务 CU 消耗，识别僵尸任务并生成降本建议。

## 核心流程

### 1. 信息提取
从用户提问中提取关键信息：
- **Flink 项目名** (project_name)
- **任务名** (job_name)
- **故障问题描述**
- **故障发生时间** (用于日志查询)
- **区域** (region，可选)

如果用户没有明确提供，主动询问缺失的关键信息。

### 2. 获取应用列表
使用 `mcporter call volceapi.list_flink_application` 获取应用列表，支持按以下条件过滤：
- project_name（项目名）
- job_name（任务名）
- job_state（任务状态：ALL/CREATED/STARTING/RUNNING/FAILED/CANCELLING/SUCCEEDED/STOPPED）
- job_type（任务类型）
- resource_pool（资源池）
- region（区域）

### 3. 获取详细信息
对于找到的应用，获取以下详细信息：

**应用详情：**
```bash
mcporter call volceapi.get_flink_application_detail project_name="xxx" job_name="xxx"
```

**运行时信息：**
```bash
mcporter call volceapi.get_flink_runtime_application_info project_name="xxx" job_name="xxx"
```

### 4. 获取诊断信息
**应用日志：**
- 如果用户提供了故障时间，使用该时间范围
- 如果没有提供，查询最近 1 小时的日志
- 默认查询 ERROR 级别日志，同时查看 WARNING 级别
- 查询 JOBMANAGER 和 TASKMANAGER 组件的日志

```bash
mcporter call volceapi.list_flink_application_log \
  project_name="xxx" \
  job_name="xxx" \
  start_time="YYYY-MM-DDTHH:MM:SS" \
  end_time="YYYY-MM-DDTHH:MM:SS" \
  level="ERROR"
```

**应用事件：**
```bash
mcporter call volceapi.get_flink_application_event project_name="xxx" job_name="xxx" limit=50
```

### 5. 资源池检查
当发现以下情况时，检查资源池：
- OOM（内存溢出）
- TaskManager 丢失
- 容器被杀
- 任务启动失败
- 性能下降

```bash
mcporter call volceapi.list_flink_resource_pool project_name="xxx"
```

## 异常分类系统

根据收集到的信息，将根异常分类为以下类别之一：

| 类别 | 典型信号 |
|------|-----------|
| **Resource** | OOM、TaskManager 丢失、容器被杀、堆空间不足、内存溢出、GC 频繁、资源耗尽 |
| **Data** | 反序列化错误、模式不匹配、NullPointerException、数据格式错误、类型转换异常 |
| **Checkpoint** | Checkpoint 超时/过期、状态后端错误、Checkpoint 失败、状态大小异常 |
| **Connectivity** | Kafka 不可达、连接拒绝/超时、网络异常、数据库连接失败、外部服务不可用 |
| **Code/Logic** | SQL 语法错误、UDF 异常、ClassCastException、业务逻辑错误、代码异常 |
| **Configuration** | 无效的并行度、参数缺失、资源配置过小、配置错误、环境变量缺失 |
| **Infrastructure** | 节点故障、网络分区、存储不可用、底层基础设施问题 |
| **Snapshot** | 文件未找到、快照过期太快、消费速度太慢、状态恢复失败 |

## 优先级区分

根据问题严重程度，标记优先级：

🔴 **Critical** — 任务宕机或数据丢失风险，需要立即采取行动。
- 任务已失败（FAILED）
- 任务已停止（STOPPED）
- 数据丢失风险
- 严重的资源耗尽

🟡 **Warning** — 性能下降或间歇性错误，建议采取行动。
- 任务运行但性能下降
- Checkpoint 超时但未失败
- 频繁的 GC 但未 OOM
- 间歇性连接问题
- 警告级别日志增多

🟢 **Info** — 健康或轻微的优化建议。
- 任务正常运行
- 轻微的性能优化空间
- 配置可以优化但不影响运行

## 诊断报告结构

**ALWAYS 使用以下格式输出诊断报告：**

```
# 🚨 Flink 任务智能诊断报告

## 📋 基本信息
- **项目名**: [项目名]
- **任务名**: [任务名]
- **当前状态**: [状态]
- **诊断时间**: [时间]

## 🔍 问题分析

### 异常类别
[类别 emoji] **[类别名称]**

### 优先级
[优先级 emoji] **[优先级名称]**

### 根本原因
[用通俗语言解释根本原因]

### 关键证据
- [证据 1]
- [证据 2]
- [证据 3]

## 💡 修复建议

### 1. 立即修复
[具体的修复步骤]

### 2. 预防措施
[如何避免问题再次发生]

### 3. 优化建议
[可选的性能优化建议]

## 📊 相关信息
[附上关键的日志片段、事件信息或运行时数据]
```

## 修复建议模板

提供编号的、可操作的修复步骤：

1. **用通俗语言解释根本原因**
   - 技术细节，但用易懂的方式

2. **具体的修复方法**
   - 参数修改（如并行度、内存配置）
   - SQL 修复
   - 资源调整
   - 代码修改建议

3. **预防措施**
   - 如何避免问题再次发生
   - 监控建议
   - 最佳实践

## 工具调用顺序

1. 先调用 `list_flink_application` 找到目标应用
2. 调用 `get_flink_application_detail` 获取应用详情
3. 调用 `get_flink_runtime_application_info` 获取运行时信息
4. 调用 `list_flink_application_log` 获取日志（ERROR + WARNING）
5. 调用 `get_flink_application_event` 获取事件
6. 如需要，调用 `list_flink_resource_pool` 检查资源池
7. 综合分析，分类异常，给出诊断报告

## 注意事项

- 始终先确认项目名和任务名
- 如果有多个应用匹配，让用户选择
- 日志查询时，如果没有明确时间，查询最近 1 小时
- 同时查看 ERROR 和 WARNING 级别的日志
- 检查 JOBMANAGER 和 TASKMANAGER 两个组件
- 遇到资源相关问题时，务必检查资源池
- 用用户能理解的语言解释，避免过度技术化
- 给出具体、可操作的建议，而不是模糊的指导