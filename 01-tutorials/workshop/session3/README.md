# 火山智能体身份和权限管理平台

## 概述

火山智能体身份和权限管理平台（a.k.a. Agent Identity）产品，是一款面向智能体全新设计的身份与权限管理系统，可以为智能体提供与人类用户同等的、可治理的身份与安全能力，使代理系统能够安全、可控、可审计地在企业级环境中运行，其工作原理如下图所示：

![智能体身份和权限管理工作原理](assets/images/identity_image.png)

## 核心功能

- **身份认证**：支持 OAuth2.0/OIDC/SAML 协议，可集成飞书、Coze 等身份源。
- **权限控制**：基于策略的访问控制（PBAC），支持细粒度权限配置。
- **凭证托管**：智能体运行时可自动托管，获取和刷新凭据，无需手动管理。

## Agent 能力

- Identity

## 目录结构说明

```text
session3
├──E3_lark_doc                   # 实验3：学习如何使用Agent Identity产品来安全的托管外部服务（本实验以飞书文档为例）的访问凭证，以允许智能体安全无感的访问下游资源。
├──E4_volc_ops                   # 实验4：学习如何使用Agent Identity产品来安全的托管火山资源（本实验以MCP市场的ECS运维工具为例）的访问凭证，以允许智能体安全无感的访问下游资源。
├──E5_ops_knowledgebase          # 实验5：学习如何使用Agent Identity产品来为整个智能体调用的委托链配置静态策略，为智能体访问下游资源提供细化的权限管控能力。
├──E6a_mail_ast_with_guard       # 实验6：这是一项预览功能，可以体验使用Agent Identity产品在智能体运行时根据智能体的运行上下文，动态为智能体赋予运行时最小权限，为用户提供更强化的智能体权限管控能力。
├──E6b_mail_ast_without_guard    # 实验6：同上，但该实验不开启guard的智能体
├──.env.template                 # 配置文件示例，您可以根据需要修改
├──.pre-commit-config.yaml       # 代码提交前的校验配置文件
├──LICENSE                       # 项目开源协议
├──pyproject.toml                # 项目依赖管理文件
├──README.md                     # 项目说明文档
```

## 本地运行

### 前置准备

| 项目 | 说明 | 操作 |
| ------ | ------ | ------ |
| **火山控制台账号** | 必须拥有 **IDFullAccess**，**STSAssumeRoleAccess** 的子账号，并且该子账号需要提供对应的 **AK/SK**进行**复制并记录**（后续 `.env` 或代码中需要使用） | 用于登录 IAM 子用户 |
| **飞书账号** | 需要能够查看或配置 **飞书开放平台**（<https://open.feishu.cn/app>），以便创建/授权应用（参考下文配置） | 加入 `火山 AgentKit Identity（内部测试）` 组织：<code>https://identity.feishu.cn/invite/member/_oF71wu7U3w</code> |
| **本地环境** | Git、PowerShell / Bash、`uv`（Python 环境管理） | 参考下文安装步骤 |

### 依赖安装

#### 拉取代码

```bash
git clone https://github.com/volcengine/agentkit-samples.git
cd agentkit-samples/01-tutorials/workshop/session3
```

#### 安装 `uv`（推荐国内镜像）

```bash

# Linux/macOS
curl -LsSf https://force-workshop.tos-cn-beijing.volces.com/uv-latest/uv-installer.sh | sh

# Windows PowerShell
irm https://force-workshop.tos-cn-beijing.volces.com/uv-latest/uv-installer.ps1 | iex

```

#### 创建并同步 Python 3.12 虚拟环境

```bash
export UV_PYTHON_INSTALL_MIRROR=https://force-workshop.tos-cn-beijing.volces.com/python-build-standalone
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/
uv venv --python 3.12
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple --force-reinstall
```

### 环境准备

#### 增加火山角色

1. **打开角色管理页面**

   <https://console.volcengine.com/iam/identitymanage/role>

2. **新建角色**

   - 在「角色管理」页面，点击 **「新建角色」** 按钮。

3. **设置信任身份**

   - **信任身份**：`账号`
   - **身份**：`当前账号`（即你登录的主账号）
   - 点击 **「下一步」**。

4. **填写角色名称**

   - 在弹出的表单中输入角色名称，例如 `identity_agentkit_workshop`（自行命名，后续便于辨识）。
   - 再次点击 **「下一步」**。

5. **绑定策略**

   - 在策略搜索框中输入 **`IDReadOnlyAccess`**，勾选对应的策略名称。
   - 点击 **「完成」**，角色即创建成功。

6. **记录角色 TRN**

   - 创建成功后，点击新建好的角色进入 **角色详情页**。
   - 在页面顶部可以看到 **「角色TRN」**，形如：

     ```text
     trn:iam::2114543432:role/identity_agentkit_workshop
     ```

   - 将该 TRN **复制并记录**（后续 `.env` 或代码中需要使用）。

#### 配置用户池和客户端

1. **打开用户池列表**
   访问 <https://console.volcengine.com/identity/region:identity+cn-beijing/user-pools?projectName=default>。

2. **新建用户池**
   - 点击 **「新建用户池」**。
   - 填写 **用户池名称**（如 `workshop_user_pool`）。
   - 选择登录属性（推荐 **用户名 + 手机号**）。
   - 点击 **「确认」** 完成创建。

3. **进入用户池详情**
   在用户池列表中点击刚创建的 `workshop_user_pool`，进入详情页。

4. **新建客户端**
   - 在用户池详情页点击 **「新建客户端」**。
   - 输入 **客户端名称**（如 `workshop_web_client`）。
   - 选择 **客户端类型** 为 **Web 应用**。
   - 在 **允许回调 URIs** 中填入本地回调地址，例如：

     ```text
     http://127.0.0.1:8000/api/v1/oauth2callback
     ```

   - 点击 **「确认」** 完成创建。

5. **记录关键信息**
   - 创建成功后页面会展示 **Client ID**、**Client Secret**、**Redirect URI** 等信息。
   - 记录用户池详情中的外部身份提供商回调 URL **OAuth 注册回调地址**、**OAuth 登录回调地址**，后续将填写**飞书开放平台应用**中。
   - **注意**：`Client Secret` 仅用于本地开发，请勿提交到代码仓库。

#### 配置飞书应用

1. **创建飞书应用**
   - 访问 <https://open.feishu.cn/app/>，点击 **「创建应用」**，填写名称、描述等信息后提交。

2. **开通所需权限**
   - 进入 **「权限管理」 → 「开通权限」**，勾选以下权限并保存：
     - `user_access_token`（用户身份权限）
     - `contact:contact.base:readonly`
     - `contact:user.base:readonly`
     - `contact:user.employee_id:readonly`
     - `drive:drive`
     - `docx:document:readonly`
     - `docs:document.content:read`

3. **配置安全设置（回调 URL）**
   - 在左侧菜单选择 **「安全设置」 → 「回调 URL」**，依次添加：

     ```text
     # 火山 Identity 回调，例如
     https://auth.id.cn-beijing.volces.com/api/v1/oauth2callback

     # UserPool 登录回调，例如
     https://userpool-dc3db63c-093f-42b5-aa58-8b0ad57424c7.userpool.auth.id.cn-beijing.volces.com/login/generic_oauth/callback

     # UserPool 注册回调，例如
     https://userpool-dc3db63c-093f-42b5-aa58-8b0ad57424c7.userpool.auth.id.cn-beijing.volces.com/signup/generic_oauth/callback
     ```

   - 对应字段分别为 **「OAuth 注册回调地址」**、**「OAuth 登录回调地址」**，确保 URL 完全匹配（包括协议、域名、路径），否则会出现 `redirect_uri mismatch` 错误。

4. **保存并获取凭证**
   - 完成上述配置后，点击 **「保存」**。
   - 前往 **「凭证与基础信息」** 页面，记录下 **`App ID`** 与 **`App Secret`**。

#### 配置外部身份供应商

1. **打开身份管理控制台**
   访问 <https://console.volcengine.com/identity/region:identity+cn-beijing> 并登录。

2. **进入目标用户池**
   - 在左侧列表中找到并点击本次实验使用的 **用户池**。

3. **新建外部身份供应商**
   - 在用户池详情页左侧选择 **「外部身份供应商」**。
   - 点击 **「新建供应商」**。

4. **填写供应商信息**
   - **供应商名称**：自行取名，例如 `feishu_identity_provider`。
   - **提供商类型**：选择 **「内置身份供应商」**。
   - **客户端 ID**：填写 **飞书应用的 App ID**。
   - **客户端密码**：填写 **飞书应用的 App Secret**。

5. **配置授权范围（Scope）**
   - 在 **「授权作用域」** 输入以下权限（英文逗号分隔）：

     ```text
     contact:user.base:readonly,contact:contact.base:readonly
     ```

6. **设置用户唯一标识属性**
   - 在 **「用户唯一标识属性」** 填写：

     ```json
     ["data","user_id"]
     ```

7. **保存并记录**
   - 点击 **「确认」** 完成创建。
   - 记录下 **供应商 ID**（后续在代码或配置文件中可能需要使用）。

#### 配置凭据管理（Outbound Credentials）

1. **打开凭据管理页面**
   访问 <https://console.volcengine.com/identity/region:identity+cn-beijing/outbound-credentials>。

2. **新建凭据**

   - 点击 **「新建凭据」**，在弹窗中选择 **「OAuthClient」** 类型。

3. **填写 OAuth 客户端信息**
   - **客户端 ID**：填写 **飞书应用的 App ID**（与 3.7 中保持一致）。
   - **客户端密码**：填写 **飞书应用的 App Secret**。
   - **权限范围（Scope）**：同样填入

     ```text
     contact:user.base:readonly,contact:contact.base:readonly
     ```

4. **完成创建**

   - 确认信息无误后点击 **「确认」**。

### 调试方法

#### 配置 `.env`

在项目根目录新建（或编辑）**`.env`** 文件，将以下变量填入对应的值。每个变量的获取来源已在前面的章节标注，确保在填写前已完成相应的配置步骤。

```dotenv
# ==================== 认证相关 ====================
ADK_OAUTH2_USERPOOL_UID=            # ① 用户池 UID（用户池详情页可见）
ADK_OAUTH2_CLIENT_ID=               # ② OAuth2 客户端 ID（用户池 → 客户端 → Client ID）
ADK_OAUTH2_CLIENT_SECRET=           # ③ OAuth2 客户端 Secret（同上）
ADK_OAUTH2_CALLBACK_URL=            # ④ OAuth2 回调地址，示例：
                                    #    http://127.0.0.1:8000/api/v1/oauth2callback
ADK_OAUTH2_SCOPE="openid profile"   # ⑤ 授权范围，保持默认即可

# ==================== 角色/凭证 ====================
RUNTIME_IAM_ROLE_TRN=               # ⑥ 运行时 IAM 角色 TRN（3.4 创建角色后记录）

# ==================== 火山云凭证 ====================
VOLCENGINE_ACCESS_KEY=              # ⑦ 子账号 AK（火山控制台 → 子账号 → Access Key）
VOLCENGINE_SECRET_KEY=              # ⑧ 子账号 SK（同上）

# ==================== 业务服务 ====================
DATABASE_VIKING_BASE_URL=           # ⑨ Viking 数据库访问地址（实验提供或自行部署）
ADAPTIVE_PERMISSION_SERVICE_KEY=    # ⑩ 细粒度权限服务 Key（平台分配）

# ==================== 其他可选 ====================
# 如有额外的环境变量，可在此处继续添加
```

##### 填写要点

1. **`ADK_OAUTH2_USERPOOL_UID`**
   - 进入 **火山 Identity 控制台 → 用户池**，在用户池列表中点击目标池，URL 中的 `uid` 即为该值。

2. **`ADK_OAUTH2_CLIENT_ID / SECRET`**
   - 在同一用户池的 **客户端** 页面创建的 **Web 应用**，页面会展示 `Client ID` 与 `Client Secret`。

3. **`RUNTIME_IAM_ROLE_TRN`**
   - 参见 **3.4 增加火山角色**，创建成功后进入角色详情页即可看到形如
     `trn:iam::2114543432:role/identity_agentkit_workshop` 的 TRN。

4. **`VOLCENGINE_ACCESS_KEY / SECRET_KEY`**
   - 使用拥有 **IDFullAccess** 与 **STSAssumeRoleAccess** 权限的子账号登录 **火山控制台 → AccessKey**，生成并复制。

5. **`DATABASE_VIKING_BASE_URL`** 与 **`ADAPTIVE_PERMISSION_SERVICE_KEY`**
   - 这两项通常由实验组织者提供，若自行部署请填入对应服务的访问地址与密钥。

---

### 调试方法

> **⚡️ 所有实验均在同一目录下运行，若已启动应用可直接跳到对应实验步骤。**

#### 实验 1 – 用户池登录智能体

1. 启动服务

   ```bash
   uv run veadk web
   ```

2. 浏览器访问 `http://127.0.0.1:8000` → 登录页。

3. 使用 **实验前创建的本地用户**（用户名/临时密码）登录。

4. 首次登录需修改密码并完成短信验证码。

5. 授权后即可进入 Agent 应用页面。

#### 实验 2 – 飞书 IdP 联合登录

1. 同实验 1 启动服务（若已运行可跳过）。

2. 在登录页点击 **“使用飞书登录”** → 跳转飞书授权页面 → **授权** → 返回 Agent 并 **允许访问**。

3. 成功后即可使用飞书身份访问智能体。

#### 实验 3 – 安全托管飞书文档凭证

1. 登录 **Agent Identity 控制台 → 凭证托管**，查看已预置的 `feishu` Provider（无需手动创建）。

2. 启动服务并打开 Agent。

3. 选择 **E3_lark_doc** Agent，输入

   ```text
   为我总结文档内容：https://icncjgc0bh0b.feishu.cn/docx/WmlQdfqiNoB1CqxHtKMcdJfonBd
   ```

4. 按提示完成飞书授权，即可得到文档摘要。

#### 实验 4 – 安全托管火山资源（ECS）凭证

1. 登录 **凭证托管**，查看 `ecs‑oauth‑provider`（已预置）。

2. 启动服务 → 选择 **E4_volc_ops** Agent，输入查询指令（如 “我有哪些 ECS？”）。

3. 完成火山登录与授权后，Agent 将返回 ECS 列表。

#### 实验 5 – 静态细粒度权限策略

1. 登录 **Agent Identity 控制台 → 用户池**，记录当前登录用户的 **User ID**。

2. 在 **权限策略** 页面，新建策略：

   - **效果**：允许
   - **主体**：`user::<UserID>`
   - **Agent**：`identity_agentkit_workshop`
   - **资源**：`knowledgebase document` → `production_credential.md`

3. 保存后，在 **E5_ops_knowledgebase** Agent 中查询 “生产服务器如何登录？” 即可看到授权成功的结果。

#### 实验 6 – 动态权限围栏（预览功能）

1. 启动服务 → 选择 **E6a_mail_ast_with_guard**（开启动态围栏）或 **E6b_mail_ast_without_guard**（未开启）。

2. 按提示输入邮件地址、关键词、转发目标。

3. 观察 **Event 窗口** 中 `customMetaData.permissions`，验证是否 **阻断** 攻击邮件（`user2@example.com`）或 **放行** 正常邮件（`user1@example.com`）。

#### 清理资源

```bash
# 删除本地虚拟环境
rm -rf .venv

# 删除克隆的代码仓库
cd .. && rm -rf agentkit-samples
```

> 如在火山控制台创建了 **用户、策略、凭证 Provider**，请在对应页面手动删除，避免产生额外费用。

## AgentKit 部署

暂无

## 示例提示词

暂无

## 效果展示

待补充

## 常见问题

| 场景 | 可能原因 | 解决办法 |
| ------ | ---------- | ---------- |
| **启动后无日志输出** | `uv` 环境未激活或依赖未安装 | 确认 `uv sync` 成功，重新执行 `uv run veadk web` |
| **登录页面一直跳转** | 浏览器缓存或未正确创建用户 | 清除浏览器缓存或重新创建用户（实验 1） |
| **飞书授权失败** | 组织邀请未生效或账号未绑定 | 重新加入组织链接，确认飞书账号已绑定组织 |
| **凭证托管页面 404** | IAM 子账号权限不足 | 使用组委会提供的子账号登录控制台 |
| **动态权限未生效** | 使用了 **E6b**（未开启）或浏览器阻止弹窗 | 切换到 **E6a**，确保浏览器允许弹窗 |

## 代码许可

本工程遵循 Apache 2.0 License
