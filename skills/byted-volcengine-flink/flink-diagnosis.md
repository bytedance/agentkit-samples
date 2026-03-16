---
name: flink-diagnosis
description: Comprehensive diagnostic skill for Volcengine Serverless Flink jobs. It uses read-only MCP interfaces to monitor status, troubleshoot failures, and analyze performance. **Read-only tools only; no stop, restart, deployment, or other automated operations are allowed.**
---

# Flink Job Diagnostic Skill

自动采集日志与指标，诊断任务故障、OOM、Checkpoint 及反压问题，输出根因报告与修复建议。

## 适用场景
1.  **任务状态监控**：查看 Flink 任务的运行状态、延迟指标、资源使用情况
2.  **异常问题排查**：当任务出现失败、延迟过高、性能瓶颈等问题时，进行根因分析
3.  **运行日志查询**：获取 JobManager、TaskManager 的运行日志，排查错误信息
4.  **事件信息查询**：查看任务运行过程中的事件记录，了解任务生命周期变化
5.  **资源使用分析**：查询资源池配置、项目列表、目录结构等基础信息

## 工具列表（仅包含只读工具）
### 1. 项目与资源查询类
| 工具名称 | 功能描述 |
|---------|---------|
| `list_flink_project` | 查询 Flink 项目列表，支持关键词搜索 |
| `list_flink_directory` | 查询 Flink 目录列表，可按项目过滤 |
| `list_flink_resource_pool` | 查询资源池信息，包含计费模式、资源配置等 |

### 2. 任务基础信息查询类
| 工具名称 | 功能描述 |
|---------|---------|
| `list_flink_application` | 查询 Flink 任务列表，支持按项目、名称、状态、类型等多维度过滤 |
| `get_flink_application_detail` | 查询单个任务的详细配置信息 |
| `get_flink_runtime_application_info` | 查询任务的运行时信息，包含 JobManager、TaskManager 的 Pod 列表和资源指标 |

### 3. 诊断排查类
| 工具名称 | 功能描述 |
|---------|---------|
| `list_flink_application_log` | 查询任务运行日志，支持按时间范围、日志级别、组件类型过滤，支持分页 |
| `get_flink_application_event` | 查询任务的事件记录，了解任务运行过程中的状态变化 |

## 诊断流程指南
### 第一步：基础信息收集
1.  查询项目列表：`list_flink_project(search_key="项目关键词")`
2.  查询任务列表：`list_flink_application(project_name="项目名", job_state="RUNNING")`
3.  定位到异常任务后，获取任务详情：`get_flink_application_detail(project_name="项目名", job_name="任务名")`

### 第二步：运行状态分析
1.  获取运行时信息：`get_flink_runtime_application_info(project_name="项目名", job_name="任务名")`
2.  查看延迟指标：从运行时信息中查看 `currentEmitEventTimeLag` 业务延迟指标
3.  检查资源使用：查看 JobManager、TaskManager 的资源分配和使用情况

### 第三步：异常问题排查
1.  查看事件记录：`get_flink_application_event(project_name="项目名", job_name="任务名", limit=100)`
2.  查询错误日志：
    ```
    list_flink_application_log(
        project_name="项目名",
        job_name="任务名",
        start_time="2025-10-30T19:00:00",
        end_time="2025-10-30T20:00:00",
        level="ERROR",
        component="jobmanager"
    )
    ```
3.  如果是 TaskManager 报错，修改 `component="taskmanager"` 进一步排查

### 第四步：性能瓶颈分析
1.  查看日志中的慢查询、背压等相关警告信息
2.  检查资源池配置是否满足任务需求：`list_flink_resource_pool(project_name="项目名", name="资源池名")`

## 使用示例
### 示例1：查询所有运行中的任务
```python
list_flink_application(job_state="RUNNING")
```

### 示例2：查询指定任务最近1小时的错误日志
```python
list_flink_application_log(
    project_name="my_project",
    job_name="my_flink_job",
    start_time="2025-10-30T19:00:00",
    end_time="2025-10-30T20:00:00",
    level="ERROR"
)
```

### 示例3：查询任务的运行时信息
```python
get_flink_runtime_application_info(
    project_name="my_project",
    job_name="my_flink_job"
)
```

## 注意事项
1.  **只读原则**：本技能仅使用上述列出的只读工具，禁止使用 `start_flink_application`、`stop_flink_application`、`restart_flink_application`、`deploy_flink_application_draft` 等运维类工具
2.  **日志查询限制**：单次日志查询的时间范围建议不超过24小时，避免返回数据量过大
3.  **分页处理**：当日志量较大时，使用 `cursor` 参数进行分页查询
4.  **数据安全**：查询结果中可能包含敏感信息，请注意数据保密