# Mobile Use Agent

Mobile Use 是基于火山引擎云手机与豆包视觉识别大模型能力，通过自然语言指令完成面向移动端场景自动化任务的 AI Agent 解决方案。

它可以在云手机上执行端到端任务，例如：

- 启动与切换 App
- UI 导航与页面跳转
- 表单填写与点击/滑动等交互
- 基于屏幕视觉理解进行下一步操作决策

## Python 依赖

最低运行环境：

- Python 3.9+

依赖包：

- volcengine-python-sdk（提供 `volcenginesdkcore`）

安装方式（使用仓库统一依赖）：

```bash
pip install -r "Quick Start/MobileUse/requirements.txt"
```

## 鉴权方式

本 Skill 默认通过命令行参数传入 AK/SK：

- `--access-key`
- `--secret-key`

## 执行入口（OpenAPI）

本 Skill 使用 `RunAgentTaskOneStep` 作为“执行入口”，一键启动一次新的 Agent 执行。

Request:

- Method: `POST`
- Action: `RunAgentTaskOneStep`
- Service: `ipaas`
- Version: `2023-08-01`

Required fields:

- `RunName` (String)
- `PodId` (String)
- `ProductId` (String)
- `UserPrompt` (String)

Optional fields (commonly used):

- `MaxStep` (Integer, 1 \~ 500)
- `Timeout` (Integer, seconds, 1 \~ 86400)

Notes:

- 调用 Mobile Use Agent OpenAPI 前，需要先完成跨服务访问授权。
- 若 `IsScreenRecord=true`，需要提前在云手机控制台配置对象存储，否则可能调用失败。
