# Kubernetes SelfHosted 工具执行环境

## 概述

在 Kubernetes 的一个 Pod 中运行 dispatcher 和多个 Worker 进程，为 AgentKit Managed Agent（MA）提供工具执行环境。MA 服务端负责模型调用和对话推进，本地 Worker 执行 Bash 等工具并回传结果。

使用流程：**创建 SelfHosted MA 资源 → 填写三个连接参数 → kubectl apply → 验证工具调用**。已有 MA 资源时可直接从填写参数开始。

## 核心功能

- 一份 YAML 创建 Namespace、MA 连接 Secret、PVC 和 Deployment。
- dispatcher 轮询指定 Environment 的 Work，按 Session 启动 Worker；默认最多并发 10 个 Worker。
- PVC 保存 Session 工作目录、HOME 和执行记录，同 Session 后续任务可复用文件。
- 单副本、Recreate 更新策略，提供进程健康和就绪探针。

## Agent 能力

后端负责执行 Harness 配置中的可用工具；模型、系统提示词、工具定义、Skills、Workspace 和 RuntimeTemplate 由 MA 资源配置管理。模型可直接回答，也可产生工具请求，由 Worker 执行并提交结果。

Worker 是同一容器里的进程，不为每个 Session 创建独立 Pod。该方案使用普通进程隔离，适用于可信会话；各 Worker 共享容器 CPU / 内存上限，不提供强多租户沙箱。

## 目录结构说明

| 文件 / 目录 | 用途 |
| --- | --- |
| [k8s_selfhost.example.yaml](k8s_selfhost.example.yaml) | 不含真实凭据的 Kubernetes 清单模板；当前默认 Linux/ARM64 |
| `k8s_selfhost.yaml` | 从模板复制、填入连接参数的本地部署文件，被本目录 Git 忽略 |
| [../../resource_to_chat_http/](../../resource_to_chat_http/README.md) | 创建 MA 资源、发送消息、查看工具事件及清理云资源 |
| [../../harness_console/](../../harness_console/README.md) | 通过本地网页管理 MA 资源和 Session 对话 |

## 本地运行

以下部署命令从本目录执行；资源创建和对话步骤会显式切换到 `../../resource_to_chat_http`。

### 1. 前置准备

- 安装 kubectl，并准备能连接目标 Kubernetes 集群的 kubeconfig 和部署权限。清单会创建 `harness-selfhost` Namespace，并在其中管理 Secret、PVC、Deployment。
- 集群有匹配镜像架构的 Linux 节点。模板当前选择 **ARM64**，需要 CPU 请求 1 核、内存请求 2Gi；容器上限为 CPU 4 核、内存 8Gi。
- 集群有默认 StorageClass，能提供可写、支持 POSIX `flock` 的持久化文件系统，并允许 UID/GID 1000 访问；默认 PVC 大小 20Gi。
- Pod 能访问 MA Endpoint、镜像仓库及业务工具需要的服务。清单没有镜像拉取 Secret，目标仓库需允许匿名拉取，或节点已有有效授权；节点缓存命中不证明匿名拉取成功。

确认部署目标及节点架构：

```bash
kubectl config current-context
kubectl get nodes -L kubernetes.io/os,kubernetes.io/arch
kubectl get storageclass
```

无需为该后端另建 context。kubectl 默认使用当前 context；清单显式指定 Namespace，Pod 运行时不读取 kubeconfig，也不调用 Kubernetes API。

### 2. 创建或复用 MA 资源

若你已有可用的 MA Endpoint、SelfHosted Environment、Environment Key，以及正确绑定的 Harness、模型 RuntimeTemplate 和 Session，直接跳到第 3 步。也可使用自己的脚本准备这些资源。

本仓库的配套资源创建步骤如下，完整配置要求见[资源到对话说明](../../resource_to_chat_http/README.md)：

```bash
cd ../../resource_to_chat_http
uv venv
uv pip install -r requirements.txt
source .venv/bin/activate
cp -n ../config.yaml.example ../config.yaml
```

填写 `../config.yaml` 中的账号 AK/SK、地域、模型及模型 API Key **Name**、资源规格等必填项；不要手填模板标明由脚本回写的 Session / Environment Key 字段。然后显式选择 SelfHosted：

```bash
python 01_create_resources.py --prefix selfhost-demo --env-mode selfhost
```

脚本创建或复用 Endpoint，创建 SelfHosted Environment、Harness、模型侧 SessionStore / RuntimeTemplate、Environment Key 和 Session。SelfHosted 模式不创建 Cloud 工具沙箱；模型执行器仍在 MA 服务端运行。

成功后脚本回写共享配置，并输出以下三项连接信息：

```text
ANTHROPIC_BASE_URL=<MA 数据面地址>
ANTHROPIC_ENVIRONMENT_ID=<SelfHosted Environment ID>
ANTHROPIC_ENVIRONMENT_KEY=<Environment Key 明文>
```

Environment Key 与账号 AK/SK、模型 API Key 是不同凭据，不能互换。Harness、Environment、RuntimeTemplate 和 Session 需满足同一 Workspace 的绑定要求。

回到部署目录：

```bash
cd ../self_host/k8s_mode
```

### 3. 填写连接参数

复制模板，并限制含 Key 文件的访问权限：

```bash
cp -n k8s_selfhost.example.yaml k8s_selfhost.yaml
chmod 600 k8s_selfhost.yaml
```

编辑 `k8s_selfhost.yaml`，只替换顶部 `selfhost-connection` Secret 中的三个值：

```yaml
stringData:
  ANTHROPIC_BASE_URL: "https://your-ma-endpoint.example.com"
  ANTHROPIC_ENVIRONMENT_ID: "your-selfhost-environment-id"
  ANTHROPIC_ENVIRONMENT_KEY: "your-environment-key"
```

**kubectl apply 不会自动读取或替换终端环境变量。** 即使执行了 `export ANTHROPIC_ENVIRONMENT_ID=...`，仍需将实际值填写到 YAML。apply 将这些值写入 Kubernetes Secret，Pod 启动时再从 Secret 注入环境变量。

### 4. 确认 AMD64 / ARM64 配置

当前模板的实际 `nodeSelector` 和镜像均为 **ARM64**。若目标节点为 AMD64，需同时替换以下两处：

```yaml
nodeSelector:
  kubernetes.io/os: linux
  kubernetes.io/arch: amd64
```

```yaml
image: agentkit-platform-2116711330-cn-beijing.cr.volces.com/agentkit/harness-selfhosted-process@sha256:6c7f13e39ce0e638a38da808704a4da451be7accda721571a9ae1c6c736a8528
```

恢复 ARM64 时，架构为 `arm64`，镜像为模板中的：

```text
agentkit-platform-2116711330-cn-beijing.cr.volces.com/agentkit/harness-selfhosted-process@sha256:4a1b575aa0842c98e26c9647c3483bb0e8ddc053ecc4c29548feb4cc26d0234e
```

这两个 digest 各自仅支持一种架构，不能只删除架构限制期待自动匹配。之后若发布了同时包含两种架构的镜像索引，可改用同一多架构镜像地址，并只保留 Linux 节点限制。

### 5. 部署及检查

首次部署只需提交一份清单：

```bash
kubectl apply -f k8s_selfhost.yaml
```

apply 成功表示资源已提交。另行等待并确认运行状态：

```bash
kubectl -n harness-selfhost rollout status deployment/selfhost-backend --timeout=180s
kubectl -n harness-selfhost get pods,pvc -o wide
kubectl -n harness-selfhost logs -f deployment/selfhost-backend --timestamps
```

期望 Pod 为 `1/1 Running`、PVC 为 `Bound`。运行时只有一个 Pod：dispatcher 领取并 ACK Work 后，经 supervisor 启动对应 Session 的 Worker。基本工具链路无需 Service、Ingress 或公网入站端口。

## AgentKit 部署

本目录部署的是 Kubernetes 工具执行侧，MA 模型侧资源由配套创建脚本或已有流程管理。更新镜像或 Pod 配置后重新 apply 会触发 Deployment 更新；只修改 `selfhost-connection` Secret 不会更新已运行进程的环境变量，需要在工具任务空闲时重启：

```bash
kubectl apply -f k8s_selfhost.yaml
kubectl -n harness-selfhost rollout restart deployment/selfhost-backend
kubectl -n harness-selfhost rollout status deployment/selfhost-backend --timeout=180s
```

保留单副本和 Recreate 策略，避免共享数据目录的 dispatcher 独占锁冲突。PVC 保留 Session 文件，不保留进程内存或后台服务。

## 效果展示

正常情况下，容器日志会出现 dispatcher 启动记录；领取任务后出现 `worker process started`，包含 Work ID、Session ID 和 supervisor PID。它说明 Worker 启动了，不能单独证明某个工具已成功执行。

当前进程后端丢弃 Worker 子进程的 stdout / stderr，因此 `kubectl logs` 主要展示 dispatcher 生命周期日志。实际工具名称、参数和结果通过 MA Session 的 `agent.tool_use` / `user.tool_result` 事件查看；配套 HTTP 对话脚本会关联调用 ID 并显示结果。

完整验收应看到两轮成功的 Bash 工具结果、同文件复用及最终回复，并收到 `session.status_idle` 且 `stop_reason.type=end_turn`。Pod 探针就绪、消息提交 HTTP 200 或模型返回普通文字，都不足以证明工具链路完成。

## 资源清理

清理前结束正在运行的工具任务，并确认 kubectl 当前 context 是要清理的集群。Kubernetes 后端、MA 云资源和本地凭据文件分别管理，删除其中一项不会自动清理其他两项。

### 仅停止后端，保留 Session 文件

从本目录执行，只删除 Deployment 及其 Pod，保留 PVC、连接 Secret 和 Namespace：

```bash
kubectl -n harness-selfhost delete deployment selfhost-backend --ignore-not-found=true
```

之后可用原 YAML 重新 apply，复用 PVC 上的文件。不需要清理 MA 资源时，到此即可。

### 完整删除 Kubernetes 资源及 Session 文件

确认 PVC 数据不再需要，并确认 `harness-selfhost` Namespace 没有其他需要保留的资源后，从本目录执行：

```bash
kubectl delete -f k8s_selfhost.yaml --ignore-not-found=true
```

这会删除清单里的 Deployment、连接 Secret、PVC 和整个 Namespace；Namespace 删除也会删除其中其他资源。底层 PV 是否删除取决于回收策略：`Delete` 可能直接删除卷及数据，`Retain` 会留下卷供管理员另行处理。此命令不能作为保留文件的停止方式，也不会删除 MA 云资源。

检查 Namespace 是否已删除；命令无输出表示查询时已不存在，若仍显示 `Terminating`，说明还在清理：

```bash
kubectl get namespace harness-selfhost --ignore-not-found=true
```

完全清理后，如不再复用本地连接配置，可删除仍包含 Environment Key 的本地文件，保留模板：

```bash
rm -f k8s_selfhost.yaml
```

MA 云资源使用创建时相同的配置和状态文件，通过配套 [03_cleanup_resources.py](../../resource_to_chat_http/03_cleanup_resources.py) 清理；该脚本保留共享 Endpoint，不管理 Kubernetes 资源。

## 示例提示词

部署就绪后，从配套对话目录对已有 Session 发起两轮工具测试：

```bash
cd ../../resource_to_chat_http
python 02_invoke_session_http.py \
  --prompt '请调用 Bash，在当前工作目录创建 selfhost-check.txt，写入 SELFHOST_TOOL_OK，然后输出 pwd 和该文件内容。' \
  --expected-substring SELFHOST_TOOL_OK
python 02_invoke_session_http.py \
  --prompt '请再次调用 Bash，读取上一轮的 selfhost-check.txt，输出其绝对路径和内容，保持文件原样。' \
  --expected-substring SELFHOST_TOOL_OK
```

两次调用复用共享配置中同一个 Session。需要 Harness 提供 Bash 工具，并确认实际出现工具调用与成功结果；最终回复包含标记只能验证文本，不能单独证明工具执行。若基础配置另外设置了回复断言，请先确认它与自定义提示词兼容。

也可在 [Harness Console](../../harness_console/README.md) 选择绑定同一 Environment 的 Session，依次发送上述提示词。

## 常见问题

| 现象 | 检查与处理 |
| --- | --- |
| Pod Pending，事件提示 `node affinity/selector` 不匹配 | 用 `kubectl get nodes -L kubernetes.io/arch` 确认节点架构，同时匹配 `nodeSelector` 和镜像 |
| PVC Pending | 检查默认 StorageClass、容量 / 配额和 provisioner；无默认存储时在 PVC 设置 `storageClassName` |
| `ImagePullBackOff` | 检查镜像地址、节点网络及匿名拉取权限；私有仓库需要有效拉取授权 |
| 日志持续 `work poll failed` | 检查 YAML 中的地址、SelfHosted Environment ID、Key 及其绑定；修改 Secret 后重启 |
| Worker 已启动但没有工具日志 | 当前 Worker 输出被丢弃，查看 Session 工具事件；设置 `LOG_LEVEL=DEBUG` 无法绕过输出丢弃 |
| 有文字回复但工具不执行 | 检查 Harness 工具配置、模型是否产生 `agent.tool_use`、Session Environment 绑定，以及模型与工具 Work 队列 |
| apply 后时间、Worker ID 和 PID 变了 | Pod 配置变化可能重建 Pod，`logs deployment/...` 会选择当前 Pod；日志的 `Z` 表示 UTC，北京时间加 8 小时 |
| Shell 中 export 了连接变量，但部署值没变 | kubectl 不替换 YAML 环境变量，编辑本地清单并 apply；连接 Secret 更新后重启 |

从本目录排查调度、存储和启动事件：

```bash
kubectl -n harness-selfhost describe pods -l app=selfhost-backend
kubectl -n harness-selfhost describe pvc selfhost-data
kubectl -n harness-selfhost get events --sort-by=.lastTimestamp
```

临时测试若接受 Pod 删除后丢失全部 Session 文件，可删除 PVC 对象，并将 Deployment 的数据卷替换为 `emptyDir: {}`，保留挂载路径。同一 Pod 的容器重启通常保留该卷，Pod 替换后丢失，不作为本示例默认持久化方案。

## 代码许可

本工程遵循仓库的 [Apache 2.0 License](../../../../../LICENSE)。
