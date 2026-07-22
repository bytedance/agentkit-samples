# 认证与凭据

## 常用命令

```bash
vefaas login --check
vefaas login --sso
vefaas login --accessKey <AK> --secretKey <SK>
vefaas login --accessKey <AK> --secretKey <SK> --sessionToken <STS>
vefaas login --token <OIDC-or-OAuth-token>
vefaas whoami
vefaas logout
vefaas doctor
```

也支持环境变量：

```bash
export VOLC_ACCESS_KEY_ID="<AK>"
export VOLC_SECRET_ACCESS_KEY="<SK>"
export VOLC_SESSION_TOKEN="<optional STS>"
```

AK/SK 可在火山引擎 IAM Access Key 管理页创建或查看：https://console.volcengine.com/iam/keymanage

## Agent 规则

- 执行需要访问云端资源的命令前，优先用 `vefaas login --check` 或 `vefaas whoami` 检查凭据。
- 用户没有 AK/SK 时，优先引导 `vefaas login --sso`。
- 因权限不足建议切换 AK/SK 时，同时给出 IAM Access Key 管理页，说明可在那里创建或查看 AK/SK。
- `vefaas login --sso` 会返回浏览器登录链接，同时 CLI 会在本地启动监听服务并等待浏览器回调；不要把它当成一次性 token 输入流程。
- 不要在回复中展示 AK、SK、session token、OAuth/OIDC token。
- 鉴权状态不明确、账号/项目/连通性异常时，执行 `vefaas doctor`。
- 默认使用系统 Keychain；只有当前环境不能使用 Keychain 时才加 `--no-keychain`。
- 切换 SSO、AK/SK 或环境变量凭据后，重新确认资源可见性。

## SSO 授权边界

当前 SSO 登录主要按 veFaaS 权限域授权，并包含部分其它服务的部分动作，不等价于完整 AK/SK 权限。

如果用户通过 SSO 登录后，调用某些接口时出现类似“veFaaS 无法操作 APIG / 无权限操作 APIG / 无权访问 CR / 关联服务权限不足”的报错，通常不是 CLI 参数错误，而是 SSO 授权范围不足。典型 CR 报错形如 `Target:"cr"`、`Action:"ListRegistries"` 或 `API access denied`。

遇到这类情况：

1. 告知用户当前 SSO 授权可能不足以完成该 APIG、CR 或关联服务操作。
2. 建议用户改用 AK/SK 登录后重试：
   ```bash
   vefaas login --accessKey <AK> --secretKey <SK>
   ```
3. 告知 AK/SK 可在 IAM Access Key 管理页获取：https://console.volcengine.com/iam/keymanage
4. 如果使用 AK/SK 仍然报 CR 权限不足，提示用户联系管理员补充 Container Registry（CR）OpenAPI 权限，例如 `ListRegistries`、`ListNamespaces`、`ListRepositories`、`ListTags`。
5. 如果用户不希望切换 AK/SK，建议用户自行前往 Web 控制台完成对应 APIG、CR 或关联服务操作。

## 常见恢复

| 现象 | 处理 |
|---|---|
| 没有凭据 | `vefaas login --sso` 或 AK/SK 登录 |
| AK/SK 无效、签名错误 | 让用户确认凭据后重新 `vefaas login` |
| SSO 登录后提示无权操作 APIG、CR 或关联服务 | 提示 SSO 授权范围可能不足，建议切换 AK/SK 登录，并给出 https://console.volcengine.com/iam/keymanage |
| AK/SK 调 CR 仍提示 `Target:"cr"` / `ListRegistries` 等权限不足 | 提示联系管理员补充 Container Registry（CR）OpenAPI 权限 |
| 切换凭据后资源 not found | 重新 `vefaas fn list/info`、`vefaas gateway list` 定位资源，确认 region |
| 不确定当前登录身份 | `vefaas whoami` 或 `vefaas login --check` |
| 不确定是凭据、网络还是项目问题 | `vefaas doctor` |
