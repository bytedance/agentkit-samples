
---
更新时间: 2026-03-24
版本号: v1.0
来源文档: Mobile_Use_Agent_控制台使用指南.md
---

# Mobile Use Agent (MUA) Skills 执行任务指南

本指南提供了一套确定性的指令，用于 Mobile Use Agent Skills 执行并完成认为的前置准备工作。使用前，需要让用户先阅读本指南，了解所有操作的详细步骤和注意事项。

## 1. 核心目标

MUA 火山引擎控制台提供以下核心功能，需要执行以下操作：
- **首次使用前授权**: 为火山引擎账号授予执行 MUA 操作所需的全部依赖服务权限。
- **开通 MUA Token服务**：为指定业务开通 MUA Token 服务，用于Mobile Use Agent 执行任务。
- **业务创建**: 创建一个逻辑隔离的业务单元，后续所有资源和配置都将归属于该业务。
- **资源订购**: 为指定业务订购并开通云手机实例及相关服务。用于Mobile Use Agent 执行任务。
- **工具配置**: 管理和部署 Agent 在云手机环境中执行任务所需的工具，包括“操作应用指南”和“技能”。
- **记录 AccessKey ID、SecretAccessKey(https://console.volcengine.com/iam/keymanage)、product_id、pod_id**: 用于后续操作。


## 2. 全局约束与规则

在执行任何操作前，必须遵循以下全局约束：

- **授权约束**:
  - 账号**必须**拥有 `ServiceRoleForIPaaS` 角色权限。
  - 账号**必须**拥有 `PaasServiceRole` 角色权限。
- **资源就绪约束**:
  - 订购云手机资源后，必须等待约 2–3 分钟，直至实例状态变为“已就绪”，方可执行后续操作。
- **工具配置约束**:
  - **应用指南升级**: 升级“操作应用指南”时，提供的文件包名**必须**与旧版本完全一致，否则升级将失败。
  - **技能存储路径**: 在“技能配置”中，“技能存储位置”字段**必须**填写到技能文件所在的**文件夹**级别，而不是文件本身。
- **环境约束**:
  - MUA 云手机镜像内预置的应用（App）数量有限。若任务需要与特定 App 交互，**必须**首先通过“上架应用”功能（[操作说明](https://www.volcengine.com/docs/6394/1223958?lang=zh)）将其安装至环境中。

## 3. 操作流程与决策树


### 流程 1: 创建 AccessKey ID 和 SecretAccessKey

此流程确保账号具备执行后续 Mobile Use Agent Skills 执行任务的基础权限。
- **输入**:
  - 火山引擎账号主体。
- **决策分支与步骤**:
  1.  **访问** [API 访问密钥](https://console.volcengine.com/iam/keymanage)。
  2.  **点击** “新建密钥”按钮。
  3.  **记录** 创建的 AccessKey ID 和 SecretAccessKey。
  4.  **期望输出**: AccessKey ID 和 SecretAccessKey 已成功创建。



### 流程 2: 首次使用授权

此流程确保账号具备执行后续所有操作的基础权限。

- **前置条件**:
  - 已登录火山引擎账号。
- **输入**:
  - 火山引擎账号主体。
- **决策分支与步骤**:
  1.  **检查 `ServiceRoleForIPaaS` 权限**:
      - **IF** 权限已存在 (例如，访问授权页提示“已授权”):
        - **THEN** 步骤 1 成功，继续检查下一项。
      - **ELSE** 权限不存在:
        - **THEN** 访问 [ServiceRoleForIPaaS 配置地址](https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas) 并执行授权操作。
        - **GOTO** 重新检查 `ServiceRoleForIPaaS` 权限。
  2.  **检查 `PaasServiceRole` 权限**:
      - **IF** 权限已存在:
        - **THEN** 步骤 2 成功。
      - **ELSE** 权限不存在:
        - **THEN** 访问 [PaasServiceRole 配置地址](https://console.volcengine.com/iam/identitymanage/role) 并执行创建角色和授权操作。
        - **GOTO** 重新检查 `PaasServiceRole` 权限。
- **期望输出/状态**:
  - 账号同时具备 `ServiceRoleForIPaaS` 和 `PaasServiceRole` 两种角色的授权。


### 流程 3: 开通 MUA Token 服务

- **前置条件**:
  - 已完成“流程 1: 首次使用授权”。
**输入**:
  - 火山引擎账号主体。
**决策分支与步骤**:
  1.  **访问** [Mobile Use Agent 业务管理页面](https://console.volcengine.com/ACEP/Business/6)。
  2.  **阅读**并**同意**[产品服务条款]（https://www.volcengine.com/docs/6394/2275424?lang=zh）和[服务等级协议]（https://www.volcengine.com/docs/6394/69987?lang=zh）
  3. **点击** “立即开通”按钮。
**期望输出**: 页面上出现“创建业务”按钮。


### 流程 4: 创建业务

- **前置条件**:
  - 已完成“流程 2: 开通 MUA 服务”。
- **输入**:
  - 业务名称 (自定义)。
- **步骤**:
  1.  **访问** [Mobile Use Agent 业务管理页面](https://console.volcengine.com/ACEP/Business/6)。
  2.  **点击** “创建业务”按钮。
  3.  **填写** “业务名称”。
  4.  **提交** 创建请求。
- **期望输出/状态**:
  - 在业务管理列表中，出现一个新创建的业务条目。
  - 记录“业务id”（product_id），后续后续操作将需要使用该ID。

### 流程 5: 订购资源

- **前置条件**:
  - 已完成“流程 3: 创建业务”。
- **输入**:
  - 已创建的业务。
- **步骤**:
  1.  在业务管理页面，找到目标业务，点击“订购资源”按钮。
  2.  在订购页面，完成资源选择与支付流程。
  3.  **等待** 2-3 分钟。
  4.  刷新页面或返回业务列表，检查资源状态。
- **期望输出/状态**:
  - 实例ID/名称，不为空。
  - “体验 Mobile Use Agent”按钮，可点击。
  - 记录“实例ID/名称”（pod_id），后续后续操作将需要使用该ID。
- **失败与处理**:
  - **IF** 等待超过 3 分钟后资源仍未就绪:
    - **THEN** 判定为异常状态，需要人工介入检查。

### 流程 6: 上传/升级操作应用指南

- **前置条件**:
  - 已创建业务。
- **入口**: `业务管理 -> (左侧边栏)工具配置 -> 操作应用指南`
- **输入**:
  - Markdown 格式的应用指南文件（可参考 [应用操作指南模板.md](https://lf3-static.bytednsdoc.com/obj/eden-cn/uhmlnbs/%E5%BA%94%E7%94%A8%E6%93%8D%E4%BD%9C%E6%8C%87%E5%8D%97%E6%A8%A1%E7%89%88.md)）。
- **决策分支与步骤**:
  - **场景 A: 新建指南**
    1.  执行“上传文件”操作。
    2.  选择输入的 Markdown 文件。
    3.  完成上传。
    - **期望输出**: 文件上传成功，列表中出现新的指南条目。
  - **场景 B: 升级指南**
    1.  **约束检查**: 确认待上传文件的包名与待升级的现有指南的包名**完全一致**。
    2.  **IF** 包名不一致:
        - **THEN** **终止操作**。升级将失败。
    3.  **ELSE** 包名一致:
        - **THEN** 执行“升级”操作，选择新版本文件。
    - **期望输出**: 升级成功，指南版本更新。

### 流程 7: 配置技能

- **前置条件**:
  - 已创建业务。
  - 技能相关文件（如 .py, .md）已准备就绪并上传至某个对象存储桶的文件夹中。
- **入口**: `业务管理 -> (左侧边栏)工具配置 -> 技能配置`
- **输入**:
  - 技能文件所在的对象存储桶文件夹路径 (例如: `tos://bucket-name/folder/`)。
- **步骤**:
  1.  进入“技能配置”页面。
  2.  在“技能存储位置”输入框中，**必须**填写到技能文件所在的**文件夹**路径。
  3.  保存配置。
- **期望输出/状态**:
  - 技能配置保存成功。

### 流程 7： 上架应用

- **前置条件**:
  - 已创建业务。
  - 应用相关文件（如 .apk）已准备就绪。
- **入口**: `云手机业务 -> 进入业务 -> 应用管理 -> 新增应用`
- **输入**:
  - 应用文件（如 .apk）。
- **步骤**:
  1.  点击“新增应用”按钮。
  2. 在“新增应用页面”，
    - 输入“应用名称”。
    - 通过“URL 上传”或者“本地上传”上传应用文件。
  3.  点击“确定”按钮。
- **期望输出/状态**:
  - 页面显示“应用上架成功”。

## 4. 示例文件说明

源文档提供了以下示例文件，仅用于演示技能配置的组成，不可直接用于生产。

- `file_get_time_utc8.py`: 一个 Python 脚本文件，作为技能的实现代码示例。
- `file_SKILL.md`: 一个 Markdown 文件，作为技能的描述和定义文件示例。

## 5. 参考链接

以下是操作中涉及的控制台页面和资源模板的静态链接列表，供参考。

- **控制台入口**:
  - [Mobile Use Agent 控制台](https://console.volcengine.com/ACEP/Business/6)
  - [业务管理页面](https://console.volcengine.com/ACEP/Business/6)
  - [对象存储桶列表](https://console.volcengine.com/tos/bucket?projectName=default)
- **授权地址**:
  - [ServiceRoleForIPaaS 配置地址](https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas)
  - [PaasServiceRole 配置地址](https://console.volcengine.com/iam/identitymanage/role)
- **资源与模板**:
  - [应用操作指南模板.md](https://lf3-static.bytednsdoc.com/obj/eden-cn/uhmlnbs/%E5%BA%94%E7%94%A8%E6%93%8D%E4%BD%9C%E6%8C%87%E5%8D%97%E6%A8%A1%E7%89%88.md)
  - [应用上架操作说明](https://www.volcengine.com/docs/6394/1223958?lang=zh)
