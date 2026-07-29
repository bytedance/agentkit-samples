# 故障排查

优先从这三步开始：

```bash
vefaas --version
vefaas doctor
vefaas --debug <command>
```

debug 运行可能在 `~/.vefaas/logs/` 写入详细日志。日志可能包含请求/响应信息，按敏感信息处理。

```bash
ls -lt ~/.vefaas/logs/ | head -5
```

## 常见问题

| 问题 | 恢复动作 |
|---|---|
| CLI 不存在或版本太旧 | `npm i -g @volcengine/vefaas-cli@latest`；要求 0.2.7+，并推荐 `vefaas update --check` |
| 鉴权失败 | `vefaas login --check`，再 `vefaas login --sso` 或 AK/SK 登录；AK/SK 可在 https://console.volcengine.com/iam/keymanage 获取 |
| SSO 登录后提示无权操作 APIG、CR 或关联服务 | SSO 授权范围可能不足，建议切换 AK/SK 登录并给出 https://console.volcengine.com/iam/keymanage，或让用户前往 Web 控制台完成相关操作 |
| 调用 `vefaas cr registries` 等命令提示 `Target:"cr"` / `ListRegistries` 权限不足 | 不要反复重试同一凭据；SSO 用户先切 AK/SK，AK/SK 仍失败时联系管理员补充 Container Registry（CR）OpenAPI 权限 |
| 不确定是账号、网络还是项目问题 | `vefaas doctor` |
| 框架检测错误 | `vefaas --debug inspect`，再覆盖 build/start/port |
| 本地构建失败 | 先本地复现构建命令，安装依赖，确认 Node >= 18 |
| 新应用部署找不到 gateway | `vefaas gateway list --first`；为空则让用户提供或创建网关 |
| 当前目录 link 到错误资源 | `vefaas config list`，再 `vefaas config pull ...` 或重新 link |
| 高阶命令不覆盖目标操作 | 查看 `vefaas api <Action> --help`，再读 [OpenAPI 调用](vefaas-openapi.md) |
