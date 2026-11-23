# 本地 SelfHosted 工具执行

使用 Anthropic `ant beta:worker poll` 领取指定 Environment 的工具 Work，
在本机工作目录执行工具并回写结果。模型 Runtime 仍由资源教程创建。

## 准备资源

从本目录进入资源教程，安装 Python 3.12 环境：

```bash
cd ../../resource_to_chat_http
uv venv --python 3.12
uv pip install -r requirements.txt
source .venv/bin/activate
cp -n ../config.yaml.example ../config.yaml
```

填写共享配置的账号 AK/SK、方舟 API Key Name，并核对模型、地域和角色，然后执行：

```bash
python 01_create_resources.py --env-mode selfhost
```

完整配置与资源清理说明见 [资源到对话教程](../../resource_to_chat_http/README.md)。

## 启动本地 Worker

按 [ant CLI 安装说明](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
安装客户端。macOS 可使用：

```bash
brew install anthropics/tap/ant
```

在另一个终端，将资源创建输出的三项值设置为同名环境变量，启动 Worker：

```bash
export ANTHROPIC_BASE_URL="<输出的数据面地址>"
export ANTHROPIC_ENVIRONMENT_ID="<输出的 EnvironmentId>"
export ANTHROPIC_ENVIRONMENT_KEY="<输出的 Environment Key>"
export APP_MODE="demo"
mkdir -p ~/workspace
ant beta:worker poll \
  --workdir ~/workspace \
  --environment-id "$ANTHROPIC_ENVIRONMENT_ID" \
  --environment-key "$ANTHROPIC_ENVIRONMENT_KEY" \
  --base-url "$ANTHROPIC_BASE_URL"
```

本地工具以启动 Worker 的用户权限执行。`APP_MODE` 是普通业务变量示例；
修改后需重新启动 Worker，运行中的进程不会继承另一个终端后续的 `export`。
控制面的 `Config.EnvVars` 不会自动修改本地进程环境，详见
[环境变量](../README.md#环境变量)。

## 调用与验证

回到已经激活虚拟环境的资源教程终端：

```bash
python 02_invoke_session_http.py \
  --prompt '请用 bash 执行 printenv APP_MODE，然后只回复实际输出。' \
  --expected-substring demo
```

确认真实工具调用、关联的成功结果和本轮 `end_turn`；模型回复包含 `demo`
不能单独证明变量已注入。连续工具与续聊场景需另行验收。

结束后先用 Ctrl+C 停止本地 Worker，再按资源教程清理云资源。
云端资源清理不会删除本地 `~/workspace` 文件。
