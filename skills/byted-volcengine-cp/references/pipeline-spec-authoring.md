# 流水线 Spec 编写参考

## 目录

- [顶层与任务结构](#顶层与任务结构)
- [Step 编写](#step-编写)
- [组件索引](#组件索引)
- [原子模板](#原子模板)
- [回归验证](#回归验证)

## 顶层与任务结构

当 `examples/` 中的模板不能覆盖需求时，按本参考从零拼 spec，再用
`create_pipeline.py` 落库。

```yaml
version: 1.0.0
agentPool: public/prod-v2-public
parameters: {}
sources: []
stages:
  - stage: stage-build
    displayName: 构建阶段
    tasks:
      - task: task-compile
        displayName: 编译
        timeout: 2h
        dependsOn: [task-prev]
        resourcesPolicy: all
        resources:
          limits: {cpu: 1C, memory: 2Gi}
          storage: {sizeLimit: ""}
        workspace:
          resources:
            - ref: source1
              directory: $(CP_WORKSPACE)/repo
          caches:
            - cacheKey: m2
              directory: $(CP_WORKSPACE)/.m2
              cachePolicy: pull-push
        steps: []
final: []
```

- `agentPool` 必须以 `public/` 或 `private/` 开头。北京和柔佛生产公共池均为
  `public/prod-v2-public`；`--auto-agent-pool` 只改公共池。
- `stages` 与顶层 `tasks` 二选一。多阶段按声明顺序串行；`final` 是可选收尾任务。
- Agent task 配置一个或多个 `steps`。Agentless task 不写 `steps`，直接写 task 级
  `component` + `inputs`，例如 `manualApproval@1.0.0/manual-approval`。
- `dependsOn` 只能引用同一 stage 内已存在的 task，且不能有环。
- 需要代码源时配置 `resourcesPolicy: all` 和引用 `sources[].name` 的 workspace resource。

## Step 编写

手写 spec 时 step 统一使用 `component` + `inputs`。不要直接写组件渲染后的内部
`image` + `script` 字段；自定义镜像命令也使用 `execCmd@1.0.0/custom-image`。

```yaml
steps:
  - step: build-image
    displayName: 镜像构建
    component: build@2.0.0/buildkit-cr@4.0.0
    inputs:
      region: cn-beijing

  - step: custom-image-cmd
    displayName: 自定义镜像命令
    component: execCmd@1.0.0/custom-image
    inputs:
      image: alpine:3.20
      cmd: echo hello
```

常用组件：

| 用途 | component identifier |
|---|---|
| Shell 命令 | `execCmd@1.0.0/shell` |
| 自定义镜像命令 | `execCmd@1.0.0/custom-image` |
| 主机执行 / scp | `execCmd@1.0.0/run-host-task` / `run-scp-task` |
| Go/Python/Java/NodeJS 编译 | `build@2.0.0/golang` / `python` / `java` / `nodejs` |
| 单元测试 | `unittest@1.0.0/golang` / `python` / `java` |
| Sonar | `scan@1.0.0/sonar` |
| 构建并推送 CR | `build@2.0.0/buildkit-cr@4.0.0` |
| 自定义仓库镜像 | `build@2.0.0/buildkit-custom` |
| 制品 | `artifact@1.0.0/upload-tos` / `upload-artifact` / `download-artifact` |
| kubectl | `cp-steps@2.0.0/kubectl-deploy-yaml` / `kubectl-exec` |
| Git | `repository@0.0.1/gitTag` / `cloneRepo` / `gitBranchManager` |
| 人工卡点 | `manualApproval@1.0.0/manual-approval` |

常用变量：`$(CP_WORKSPACE)`、`$(CP_ROOT_WORKSPACE)`、`$(parameters.<key>)`、
`$(stages.<stage>.tasks.<task>.outputs.<name>)`、环境变量和 `$(DATETIME)`。

## 组件元数据

不要把从内部数据库或服务端源码生成的组件快照随对外 Skill 分发。通过生产 OpenAPI 查询当前账号
实际可见的系统步骤，并以返回的 identifier、版本和 YAML 契约为准：

```bash
python3 scripts/component_step.py list --region cn-beijing --builtin --all --json
```

`kind=step` 用于 `task.steps[].component`；`kind=task` 用于 agentless `task.component`。

## 原子模板

| 模板 | 文件 | 关键 component |
|---|---|---|
| 命令执行 | `examples/exec-cmd.yaml` | `execCmd@1.0.0/shell` |
| 人工卡点 | `examples/manual-approval.yaml` | `manualApproval@1.0.0/manual-approval` |
| 镜像构建 | `examples/image-build.yaml` | `build@2.0.0/buildkit-cr@4.0.0` |
| Java 编译 smoke | `examples/java-compile-smoke.yaml` | `build@2.0.0/java` |

模板默认使用北京公共池。跨地域创建时加 `--auto-agent-pool`。

## 回归验证

落库前确认 agentPool、stages/tasks 二选一、task 执行形态、component inputs、dependsOn 和 timeout。
禁止在 YAML 写明文 AK/SK/token/password，改用变量或服务连接。

- 成功：输出 `START`、关键日志、`END` 并 exit 0。
- 失败：显式 exit 非零，确保日志能定位原因。
- 取消：长循环输出日志，进入 Running 后取消并检查 run/task 状态。
- 超时：短 timeout 配合持续输出和 sleep，检查终态。
- 证据记录 workspace、pipeline、runId、stage/task/taskRun/step 状态及脱敏日志。
- 长时间 `Queued` 且无日志通常是调度/资源等待，不应当作成功证据。
