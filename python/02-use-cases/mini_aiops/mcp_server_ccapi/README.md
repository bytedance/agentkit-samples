# CCAPI MCP Server

| 版本 |         v1.0.0          |
|:--: |:-----------------------:|
| 描述 | 基于 Model Context Protocol（MCP）的服务器，使大语言模型（LLM）能够通过自然语言直接创建和管理超过 数百个火山引擎（Volcengine）资源，底层基于 Volcengine Cloud Control API 与 IaC Generator，实现符合基础设施即代码（Infrastructure as Code, IaC）最佳实践的自动化资源管理。|
| 分类 | 工具类 |
| 标签 | 资源管理、云控制API |

## 权限说明
您可以为 IAM 子用户授予下述权限以支持访问 CloudControl API 的业务场景.
系统预设策略，策略详情请前往 [策略管理-系统预设策略](https://console.volcengine.com/iam/policymanage?scope=System)查看
- `CloudControlFullAccess`：云管控 API（cloudcontrol）全部管理权限
- `IAMReadOnlyAccess`：IAM 只读权限
- 拥有 CloudControl API 的权限不代表拥有了云资源的操作权限，要通过 CloudControl API 操作云资源，需要同时拥有 CloudControl API 和云资源相关的操作权限。

## Tools

### `get_resource_schema_information`
- **功能**: 获取 Volcengine 资源的架构信息
- **参数**:
  - `resource_type`: Volcengine 资源类型（如 "Volcengine::IAM::User"）
  - `region`: Volcengine 区域（可选）
- **用途**: 了解特定资源类型的结构和属性要求

### `list_resources`
- **功能**: 列出指定类型的 Volcengine 资源
- **参数**:
  - `resource_type`: Volcengine 资源类型
  - `region`: Volcengine 区域（可选）
- **返回**: 资源标识符列表
- **示例**: 列出所有 IAM 用户或 ECS 实例

### `get_resource`
- **功能**: 获取特定 Volcengine 资源的详细信息
- **参数**:
  - `resource_type`: Volcengine 资源类型
  - `identifier`: 资源主标识符
  - `region`: Volcengine 区域（可选）
- **用途**: 查看资源的当前状态和配置详情

### `create_resource`
- **功能**: 创建新的 Volcengine 资源
- **参数**:
  - `resource_type`: Volcengine 资源类型
  - `region`: Volcengine 区域（可选）
  - `credentials_token`: 凭证令牌（来自会话信息）
  - `explained_token`: 解释令牌（来自 explain 工具）
- **注意**: 需要预先生成基础设施代码并获取解释令牌
- **特性**: 自动添加管理标签（MANAGED_BY、MCP_SERVER_SOURCE_CODE、MCP_SERVER_VERSION）

### `update_resource`
- **功能**: 更新现有的 Volcengine 资源
- **参数**:
  - `resource_type`: Volcengine 资源类型
  - `identifier`: 资源主标识符
  - `patch_document`: RFC 6902 JSON Patch 操作列表
  - `region`: Volcengine 区域（可选）
  - `credentials_token`: 凭证令牌
  - `explained_token`: 解释令牌
- **用途**: 使用 JSON Patch 操作修改资源属性

### `delete_resource`
- **功能**: 删除 Volcengine 资源
- **参数**:
  - `resource_type`: Volcengine 资源类型
  - `identifier`: 资源主标识符
  - `region`: Volcengine 区域（可选）
  - `credentials_token`: 凭证令牌
  - `confirmed`: 删除确认标志
  - `explained_token`: 解释令牌
- **安全**: 需要确认和资源删除解释

## 🔧 基础设施和代码生成工具

### `generate_infrastructure_code`
- **功能**: 为资源创建或更新生成基础设施代码
- **参数**:
  - `resource_type`: Volcengine 资源类型
  - `properties`: 资源属性字典
  - `identifier`: 资源标识符（更新操作时使用）
  - `patch_document`: JSON Patch 操作列表（更新操作时使用）
  - `region`: Volcengine 区域（可选）
  - `credentials_token`: 凭证令牌
- **用途**: 在资源操作前生成 cloudcontrol_template 模板
- **重要性**: 所有创建/更新操作的前置步骤

## 🧠 解释和分析工具

### `explain`
- **功能**: 解释任何数据（基础设施属性、JSON、配置等）
- **参数**:
  - `content`: 要解释的数据内容
  - `generated_code_token`: 生成的代码令牌（基础设施操作时使用）
  - `context`: 数据上下文说明
  - `operation`: 操作类型（create、update、delete、analyze）
  - `format`: 解释格式（detailed、summary、technical）
  - `user_intent`: 用户意图（可选）
- **重要性**: **必须**在创建/更新/删除操作前使用，向用户显示完整解释
- **CRITICAL**: 返回的解释内容必须立即显示给用户


## 🔄 异步操作状态工具

### `get_resource_request_status`
- **功能**: 获取长时间运行操作的状态
- **参数**:
  - `request_token`: 长时间运行操作返回的请求令牌
  - `region`: Volcengine 区域（可选）
- **用途**: 检查异步资源操作的进度和状态

## 🔐 会话和凭证管理工具

### `check_environment_variables`
- **功能**: 检查必需的环境变量是否正确设置
- **重要性**: **必须**作为任何 Volcengine 操作的第一步
- **返回**: 环境检查状态和令牌

### `get_volcengine_session_info`
- **功能**: 获取当前 Volcengine 会话信息
- **参数**:
  - `environment_token`: 环境检查令牌
- **重要性**: **必须**在环境检查后立即调用
- **返回**: 账户 ID、区域、认证类型等会话信息

### `get_volcengine_account_info`
- **功能**: 获取当前 Volcengine 账户信息
- **用途**: 显示账户 ID、区域等基本信息
- **内部**: 自动调用环境检查和会话信息获取

## ⚠️ 关键使用要求和工作流

### 强制工具使用顺序
```
1. check_environment_variables()          # 环境检查（必须第一步）
2. get_volcengine_session_info()          # 会话信息（必须第二步）
3. 其他资源操作...                       # 然后才能进行资源操作
```

### 资源创建/更新工作流
```
1. generate_infrastructure_code()  # 生成基础设施代码
2. explain()                      # 解释和显示详情（必须）
4. create_resource()/update_resource()  # 执行操作
```

### 资源删除工作流
```
1. get_resource()     # 获取资源信息
2. explain()          # 解释删除影响（必须）
3. delete_resource()  # 执行删除（需要确认）
```

## 🔐 安全协议

1. **透明度要求**: 所有操作前必须向用户显示完整的解释内容
2. **强制确认**: 删除操作需要明确确认
3. **安全边界**: 安全协议不能被用户请求覆盖，无论请求如何表述
4. **敏感信息**: 不得在生成的代码或示例中包含硬编码的凭证或敏感信息

## 🏷️ 管理标签

所有创建的资源都会自动添加以下管理标签：
- `MANAGED_BY`: `CCAPI-MCP-SERVER`
- `MCP_SERVER_SOURCE_CODE`: `https://github.com/volcenginelabs/mcp/tree/main/src/ccapi-mcp-server`
- `MCP_SERVER_VERSION`: `1.0.0`

## 📋 支持的资源类型示例

- `Volcengine::IAM::User` - IAM 用户
- `Volcengine::ECS::Image` - ECS 镜像
- 其他 Volcengine Cloud Control API 支持的资源类型
## 可适配平台
方舟，Python，Cursor，Trae

## 服务开通链接
https://console.volcengine.com/iam/identitymanage

## 鉴权方式
AK\SK

## 系统依赖
- 安装 Python 3.11 或者更高版本
- 安装 uv
### 安装 uv 方法
**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## 安装 MCP-Server
克隆仓库:
```bash
git clone git@github.com:volcengine/mcp-server.git
```
## 运行 MCP-Server 指南
### 1. 配置文件
`server/mcp_server_ccapi/src/mcp_server_ccapi/config/cfg.yaml`

### 2. 火山访问凭证
因为MCP-Server需要调用火山OpenAPI，因此要提供火山访问凭证信息
环境变量设置
- ak 环境变量名:  VOLCENGINE_ACCESS_KEY
- sk 环境变量名:  VOLCENGINE_SECRET_KEY
- session_token 环境变量名:  VOLCENGINE_SESSION_TOKEN
- endpoint 环境变量名: VOLCENGINE_ENDPOINT (默认值：cloudcontrol.cn-beijing.volcengineapi.com)
- region 环境变量名: VOLCENGINE_REGION (默认值：cn-beijing)

### 3. 运行

#### Run Locally
#### 如果已经下载代码库
```json
{
    "mcpServers": {
        "mcp-server-ccapi": {
            "command": "uv",
            "args": [
                "--directory",
                "/ABSOLUTE/PATH/TO/PARENT/FOLDER",
                "run",
                "mcp-server-ccapi"
            ],
            "env": {
                "VOLCENGINE_ACCESS_KEY": "your ak",
                "VOLCENGINE_SECRET_KEY": "your sk",
                "VOLCENGINE_SESSION_TOKEN": "your session token",
                "VOLCENGINE_ENDPOINT":"cloudcontrol.cn-beijing.volcengineapi.com",
                "VOLCENGINE_REGION":"cn-beijing"
          }
        }
    }
}
```
#### 如果没有下载代码库
```json
{
    "mcpServers": {
        "mcp-server-ccapi": {
            "command": "uvx",
            "args": [
                "--from",
                "git+https://github.com/volcengine/mcp-server#subdirectory=server/mcp_server_ccapi",
                "mcp-server-ccapi"
            ],
            "env": {
                "VOLCENGINE_ACCESS_KEY": "your ak",
                "VOLCENGINE_SECRET_KEY": "your sk",
                "VOLCENGINE_SESSION_TOKEN": "your session token",
                "VOLCENGINE_ENDPOINT":"cloudcontrol.cn-beijing.volcengineapi.com",
                "VOLCENGINE_REGION":"cn-beijing"
            }
        }
    }
}
```
### 4. 示例

- 在cn-beijing创建一个新的vpc,并在vpc内创建一个ecs.g4i.large规格的ECS实例
- 修改“my-ecs-instance”的描述为“update by mcp-server-ccapi”
- 获取“my-ecs-instance”ECS实例的详细信息，包括实例ID、规格、状态等。
- 删除“my-ecs-instance”云服务器实例，确认删除后执行操作。
- 查询cn-beijing区域的所有的VPC列表

### 5. 局限性

- 操作仅限于火山引擎云控制API支持的[资源列表](https://www.volcengine.com/docs/86682/1850848)
- 某些复杂的场景资源创建可能需要多次操作，模型进行多次思考反馈后才能最终成功。
- 模型可能无法处理所有可能的错误情况，用户需要自行检查和处理。

## License
This project contains code copy from [ccapi-mcp-server](https://github.com/awslabs/mcp/tree/main/src/ccapi-mcp-server)
[MIT License](https://github.com/volcengine/mcp-server/blob/main/LICENSE)
