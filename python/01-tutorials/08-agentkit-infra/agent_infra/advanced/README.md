# 进阶案例

[03 Queue Cloud（进阶模式）](03_queue_cloud_mode/README.md) 通过 APIG 创建会话并接收事件，工具 Work 由 AgentKit 会话与编排服务中的托管 Dispatcher 消费。它和 [01 Direct](../01_direct_mode/README.md) 都使用 Cloud Environment，但会话入口和工具调度路径不同。

## 本地预览

从仓库根目录进入案例，创建虚拟环境并查看调用计划：

```bash
cd python/01-tutorials/08-agentkit-infra/agent_infra/advanced/03_queue_cloud_mode
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r ../../requirements.txt --default-index https://mirrors.aliyun.com/pypi/simple/
python run.py create-environment --dry-run
python run.py cleanup --dry-run
```

查看 [Queue Cloud 完整步骤](03_queue_cloud_mode/README.md#逐步创建资源)，按顺序创建 Route、Cloud Environment、Harness、SessionStore、Runtime 和 Environment API Key，再创建会话并流式对话。试跑结束后，在同一目录执行 `python run.py cleanup`。账号及模型配置见[进入项目并配置 uv](03_queue_cloud_mode/README.md#进入项目并配置-uv)。
