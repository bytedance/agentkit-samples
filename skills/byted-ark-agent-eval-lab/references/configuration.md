# 方案配置参考

创建或修改某个配置分区时读取对应章节；评测 MA 时同时读取 Target 中的 MA 专项和 Environment。
沿用 [主指南](../SKILL.md) 的凭据、授权、Project、幂等与结果边界。
这些是用户输入与回读说明，不在 Skill 中重新实现 Owner 的编译、默认值或可比性判断。

## 配置位置与冻结边界

| 对象 | 用户填写 / 查询入口 | 发布后回读 |
|---|---|---|
| Target（含 Model、MCP、Skill） | `spec.target.config`；`targets spec/validate`、`models list/spec/validate` | `content.target`，由 Target Owner 编译 |
| Dataset | `spec.dataset.config.dataset_version_refs`；精确版本、items 与 requirements | `content.dataset` 及 `content.items` 的题目闭包 |
| Benchmark Judge（按题目需要） | `spec.verifier_models`；精确 Dataset requirements 的 `items[].judge_requirements` | `content.items[].verifier_secrets[].model_binding` |
| Environment | `spec.environment.config`；本文件的模式形状、Plan Preview / Validate | `content.environment` 及逐题环境投影 |
| 私有 Skill（可选） | canonical `target.skills` 中的 `private_artifact` 引用 | `content.target.private_skill_artifacts` 的精确包身份、版本与摘要 |
| 执行准备（可选） | `spec.preparation.artifacts/auth`；[执行准备参考](execution-preparation.md) | `content.preparation` 中的产物身份、摘要与鉴权精确版本，不含密钥值 |
| RunPolicy | `spec.run_policy.config`；下文 v1 输入 | `content.run_policy` 的生效策略 |

Draft 可以是未完成的部分配置；不得为保存草稿而猜值补齐。按 Target → Dataset →
Environment → RunPolicy 的依赖顺序填写；发布要求完整且有效。
Snapshot 的 ID / `content_digest` 来自 Publish 后的精确回读；其冻结内容不是可直接写回
Draft 的请求模板。禁止编辑 Snapshot、用 `latest` 替换精确版本或从零重建 Owner 输出。
修改已有分区时保留未要求变更的字段，并按主指南的级联失效规则恢复原有下游配置。
冻结配置不等于锁定外部服务的全部状态：MA、远程 MCP 或可变 Git 引用的版本／内容无法确立时，
明确可复现性与控制变量结论的限制，不声称 Snapshot 已冻结这些外部变化。

## Target 配置模块

Target 是 Plan 中 `spec.target.config` 对象本身，负责描述“评测哪个 Agent、
使用哪个模型，以及是否附加 MCP/Skill”。Target 不是完整 Plan，也不要把
`dataset`、`environment`、`run_policy` 放进 Target。

### 1. 先读取当前 Agent 能力

不要根据历史 Plan、样例或 Agent 名称猜字段。先读取当前服务返回的协议：

```bash
agent-eval targets agent-types --format json
agent-eval targets spec <agent_type> --format json
```

不要在 Skill 中维护固定的 Agent 能力列表。`targets agent-types` 返回当前调用方
可选择的 `agent_type`；对拟使用的类型执行 `targets spec <agent_type>`，以该 Spec
返回的 `requires_model`、`supports_mcp` 和 `supports_skills` 判断关联关系：

- `requires_model=true`：Target 必须填写 `model`，并先查询可用 Model。
- `supports_mcp=true`：允许填写顶层 `mcp_servers`。
- `supports_skills=true`：允许填写顶层 `skills`。
- 对应能力为 `false` 时，字段可以省略或传空数组；不要为了“保留字段”填入内容。

如果服务返回的 Agent 类型或能力与下文示例不同，以本次 CLI 查询结果和服务端
校验结果为准，不根据历史 Plan 或 Agent 名称推断。

### 2. Target 字段怎么放

Target 的固定形状如下：

```json
{
  "agent_type": "<从 targets agent-types 返回的值>",
  "model": "<requires_model=true 时填写实际 ModelSpec>",
  "config": "<targets spec 返回的 param_schema 对应参数>",
  "mcp_servers": [],
  "skills": []
}
```

字段规则：

1. `agent_type` 必须使用当前 `targets agent-types` 返回的值。
2. `model` 是否必填由 `targets spec` 的 `requires_model` 决定；按下节“模型选择与确认”
   选择模型，用 `models spec/validate` 核对参数，不要猜测默认模型或 `config.max_turns`。
3. `config` 只填写当前 Agent Spec 的 `param_schema` 声明字段；不要把
   `mcp_servers` 或 `skills` 塞进 `config`。
4. `mcp_servers` 和 `skills` 是 Target 顶层字段。不使用时可以省略，也可以显式
   传空数组；两者都会按空列表处理。
5. 新建 Plan 时省略用户没有明确要求的可选 Target 参数；如采用模板，必须先
   替换全部占位值并按当前 Spec 复核。

#### 模型选择与确认

对需要 Model 的 Target，先用 `models list --agent-type <agent_type>` 查询当前兼容候选，
按实际返回的 `access`、`provider`、`name` 选择，并用 `models spec/validate` 核对配置。
MA 不额外填写或覆盖模型，沿用下文 MA 专项规则。

| 用户意图 | 选择与确认 |
|---|---|
| 明确指定模型 | 核对当前兼容范围；不可用时说明限制并请求替代选择，不静默换模型 |
| 新建但未指定模型 | 给出候选与简短推荐理由；可先形成待确认 Draft，在发布前通过中文 Preview 统一确认，不必单独多问一轮 |
| 明确授权“帮我选模型” | 在当前兼容候选中按任务要求选择，说明理由并在 Preview 展示；选择在授权范围内时不再单独追问 |
| 修改或明确复用已有方案 | 未要求换模型就保留原配置；原配置不再兼容时说明阻断，不因目录更新自动换模型 |

候选不明、查询失败或没有足够依据推荐时，说明缺项并让用户选择；可保存部分 Draft，
不为补齐配置而默认取列表第一项、演示值或历史成功模型。推荐只依据当前兼容性、用户约束和可核实证据，
没有可靠依据就不评价价格、效果或稳定性。区分“目录支持”“历史运行成功”“本次实际运行已验证”；
静态校验或发布成功不能作为最后一项的证据，也不为选模型擅自触发试跑。

对比不同 Agent 时，优先推荐各 Target 共同支持的同一模型及兼容的相同关键参数；
无共同模型时说明差异并确认取舍，不擅自更换用户指定模型或声称已控制变量。
对比模型本身时，按意图配置不同模型，不强制统一；MA 配置不可确认时，不假定它与另一侧模型一致。
中文 Preview 同时说明各成员模型、选择来源（用户指定／本次推荐／沿用原配置）及已知可比性限制；
未经用户确认或明确选型授权的推荐不能直接发布，原有发布／运行授权边界不变。

### 3. MCP 怎么填

MCP 每项使用 Harbor 的 `MCPServerConfig` 结构。下面分别给出
`stdio`、`sse` 和 `streamable-http` 三种 transport 的真实配置。

以下都是形状示例，不是应自动加入的组件；包版本和远程地址须按用户需求确认并替换占位值。
`stdio` 以 npm 包 `@modelcontextprotocol/server-filesystem` 为例，允许 MCP
Server 访问 Agent 容器内的 `/tmp`：

```json
{
  "name": "filesystem",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem@<confirmed-version>", "/tmp"]
}
```

`sse` 使用已确认的服务端点：

```json
{
  "name": "example-sse",
  "transport": "sse",
  "url": "https://<confirmed-mcp-host>/sse"
}
```

`streamable-http` 使用该服务实际支持的 HTTP 端点，不从 SSE 地址猜路径：

```json
{
  "name": "example-http",
  "transport": "streamable-http",
  "url": "https://<confirmed-mcp-host>/mcp"
}
```

`transport` 只能是 `stdio`、`sse` 或 `streamable-http`；远程形式需要 `url`，
`stdio` 需要 `command`。这些单项结构由 Harbor 校验。上面的 stdio 示例要求运行
环境已提供 Node.js/npm，并会在运行时通过 npm 获取对应官方包；不要把包下载凭据
写入 Target。远程服务是否需要鉴权按实际服务和当前支持的配置确定，不写入明文凭据；远程服务不可用
时应按服务依赖失败处理，不要自行替换成其他地址。MCP 是否对当前 Agent 生效由
`targets spec` 的 `supports_mcp` 决定；不要在不支持的 Agent 上填写。

### 4. Skill 怎么填

Skill 是对象引用，不是裸字符串，也不是本地目录或已下载的路径。每一项都用
`type` 字段区分来源。当前云端 Target 支持两种 `type`：

- `github`：公开 GitHub 来源，`url` 承载来源字符串；
- `private_artifact`：引用同项目已启用的私有 Skill 包，`artifact_id` 指向该包。

```json
{
  "skills": [
    { "type": "github", "url": "anthropics/skills@main" },
    { "type": "github", "url": "https://github.com/anthropics/skills/tree/main/skills/docx" }
  ]
}
```

`github` 的 `url` 允许以下形式：

- `anthropics/skills`
- `anthropics/skills@main`
- `https://github.com/anthropics/skills`
- `https://github.com/anthropics/skills/tree/main/skills/docx`

不允许本地路径、`http://`、非 GitHub 地址、URL 查询参数或片段。Skill
仓库是否可访问、内容是否可用由后续服务阶段判断；`targets validate` 只做
静态格式校验，不执行 Git 下载。

私有 Skill 在同一 `skills` 列表中用
`{"type":"private_artifact","artifact_id":"<skill-artifact-id>"}` 引用同项目的
已启用 Skill 包，与 `github` 对象并存。不填 TOS 地址、临时路径或编译输出。
CLI 使用 `spec.preparation.artifacts`，业务登录独立按需绑定，见[执行准备参考](execution-preparation.md)。

### 5. 完整 Target 示例

下面是 Codex 的完整 Target 模板。`<...>` 占位符必须替换为当前 CLI 查询到的
真实值，不能原样提交：

```json
{
  "agent_type": "codex",
  "model": {
    "access": "ark_router",
    "provider": "volcengine_ark",
    "name": "<models list 返回的模型>",
    "parameters": {}
  },
  "config": {},
  "mcp_servers": [],
  "skills": []
}
```

需要同时配置 MCP 和 Skill 时，仍然是同一个完整 Target：

```json
{
  "agent_type": "claude-code",
  "model": {
    "access": "ark_router",
    "provider": "volcengine_ark",
    "name": "<models list 返回的模型>",
    "parameters": {}
  },
  "config": {},
  "mcp_servers": [
    {
      "name": "example-sse",
      "transport": "sse",
      "url": "https://<confirmed-mcp-host>/sse"
    }
  ],
  "skills": [
    { "type": "github", "url": "https://github.com/anthropics/skills/tree/main/skills/docx" }
  ]
}
```

只增加 Skill 时也不能只提交 `{"skills": [...]}`。应保留完整 Target：
保留原有 `agent_type`、`model`、`config` 和 `mcp_servers`，只替换 `skills`
分区；新建 Target 则按上面的完整模板填写。

### 6. 校验并放入 Plan

先将 Target 对象单独保存为 JSON，并执行：

```bash
agent-eval targets validate --input <target.json> --format json
```

这个命令的输入是 Target 对象本身，不是完整 Plan。校验通过后，将同一份
Target 原样放入 Plan：

```json
{
  "spec": {
    "target": {
      "config": {
        "agent_type": "codex",
        "model": {
          "access": "ark_router",
          "provider": "volcengine_ark",
          "name": "<models list 返回的模型>",
          "parameters": {}
        },
        "config": {},
        "mcp_servers": [],
        "skills": []
      }
    }
  }
}
```

不要在 Plan 中复制一份经过本地改写的 Target；Target 分区以当前服务返回的
Owner 规范 JSON 为准。随后按用户授权停在 Draft，或继续 Preview / Validate → Publish；
校验 Target 不授权发布或运行。

### 7. MA Target 特殊引导

MA（Managed Agent）不是安装型 Agent。安装型 Agent 通常需要 `model`，由
Harbor 在题目沙箱内安装并启动 CLI；MA 的被测 Agent 已经存在于调用方的方舟
账号中，Target 只需要引用它的 `agent_id`。

#### 获取被测 Agent ID

有两种方式：

1. 在火山方舟 Managed Agents 控制台查看自己创建的 Agent：
   [Managed Agents](https://console.volcengine.com/ark/region:cn-beijing/managed-agents/agents)
2. 通过 CLI 查询当前调用方方舟账号下的 Agent：

   ```bash
   agent-eval targets ma-agent list --format json
   agent-eval targets ma-agent get <agent_id> --format json
   ```

   从 `list` 返回的 `data[].id` 中选择被测 Agent，再用 `get` 回读详情确认。
   这些命令需要调用方自己的 `ARK_API_KEY`，由执行 CLI 的进程环境安全注入；
   不要把 Key 写入命令、Target、Plan、Snapshot、日志或对话。

不要把“执行评测的 Agent”和“被测的 MA Agent”混为一谈。这里的
`agent_id` 必须是用户希望被评测的那个 Managed Agent。

#### 可选：获取 `vault_ids`

如果需要给 MA Session 绑定调用方账号下的凭据保管库，可以在火山方舟
[Credentials Vault 控制台](https://console.volcengine.com/ark/region:cn-beijing/managed-agents/credentials-vault)
查看，也可以通过 CLI 查询：

```bash
agent-eval targets ma-vault list --format json
agent-eval targets ma-vault get <vault_id> --format json
```

从列表返回的 `data[].id` 中选择保管库 ID，再用 `get` 回读详情确认。只把
保管库 ID 放进 Target，不要把保管库中的凭据内容放进配置。

```json
{
  "agent_type": "ma",
  "config": {
    "agent_id": "<被测 MA Agent ID>",
    "vault_ids": ["<ma-vault list 返回的 vault ID>"]
  }
}
```

`vault_ids` 是可选配置；不需要绑定保管库时可以省略。列表和详情查询都使用
调用方自己的 `ARK_API_KEY`，与查询 MA Agent 的凭据边界相同。

#### MA Target 怎么填

先执行 `targets spec ma --format json`，以当前返回的 `param_schema` 为准。
当前最小 Target 形状如下：

```json
{
  "agent_type": "ma",
  "config": {
    "agent_id": "<从方舟控制台或 ma-agent list 获取的真实 ID>"
  },
  "mcp_servers": [],
  "skills": []
}
```

MA Target 的规则：

- 不填写 `model`，MA 自带模型；
- `config.agent_id` 必填，不能填写显示名称代替 ID；
- 当前 MA 不支持 `mcp_servers` 和 `skills`，不要传入内容；省略或传空数组均可；
- `vault_ids` 等可选字段只有在 `targets spec ma` 返回且用户明确需要时才填写；
- `ARK_API_KEY` 是运行期调用凭据，不是 Target 参数。

将上面的完整对象原样放入 Plan 的 `spec.target.config`，不要把
`agent_id` 放到 `environment` 或 `run_policy`。MA 使用什么题目环境仍由
Plan 的 Environment 分区决定，不能在 Target 中填写 `vefaas`、`docker` 或
其他 Provider 字段。

## Dataset 输入与范围

Plan 使用精确引用，不把 Dataset 名称、推荐版本、题目正文或题数塞入 Target / RunPolicy：

```json
{
  "dataset": {
    "config": {
      "dataset_version_refs": [
        "dataset-version://projects/<dataset-owner-project-id>/datasets/<dataset-id>/versions/<dataset-version-id>"
      ]
    }
  }
}
```

引用中的 Project 是数据所有者，不一定等于本次评测 Project；使用真实查询返回的精确引用。
通过 `datasets versions get/items/requirements` 核对题目范围、声明的执行依赖和评分要求。
requirements 是声明，不证明依赖可访问、环境能运行或实际评分成功；没有正文时不编造正文。
准备新方案或固定子集资产时，使用范围正确的不可变 DatasetVersion，不在本地裁剪 Snapshot。
已有主动评测 Snapshot 仅需少量试跑时，按[主指南的选题流程](../SKILL.md#先验证少量题目)
使用 `runs start --snapshot-item-key` 限定本次 Run；保留原 Snapshot 和 RunPolicy，不必另建数据版本或重新发布。
新建文本草稿与归档包导入见 [数据与评分参考](data-and-scoring.md)。

## Benchmark Judge 模型

这里配置主动评测的 Benchmark Verifier，不是外部 Evidence 的独立 Grader。
Judge 与 Agent 模型分开；即使 MA 的 Target 不填模型，也必须检查题目的 Judge 要求。
只在新建／修改方案时完成此分区，不自动迁移历史 Draft 或 Snapshot。

### 发现要求，不猜模型

对 Plan 绑定的每个精确 DatasetVersion，读取 `datasets versions requirements`，检查所有
`items[].judge_requirements`。它来自已验证的 Task 元数据，只公开以下字段：

```json
{
  "judge_requirements": [
    {
      "env_key": "AEL_EXAMPLE_JUDGE_TOKEN",
      "model": "<题包原始模型名，不是替用户选定的模型>",
      "protocol": "openai-completions",
      "state": "configurable"
    }
  ]
}
```

| 返回情况 | 处理 |
|---|---|
| 所有题目均为 `[]` | 没有当前受管 Judge 要求，不新增 `verifier_models`；不代表已发现所有脚本依赖 |
| 非空数组且 `state=configurable` | 按实际 `env_key` 汇总，用户显式选择 Judge；不默认取题包、Agent、历史成功或目录第一项 |
| `state=fixed`，或旧响应中仅缺少 `state`、原三项声明完整有效 | 仅允许用户显式确认题包原模型；换模型需 Dataset 能力准备，不在客户端改声明 |
| 字段缺失、`null`、格式未知或查询失败 | 不能判定为“不需要 Judge”；可保留部分 Draft，停止发布并说明接口／元数据缺口 |

`env_key` 是凭据槽名，不是密钥值；`protocol` 是声明的 `openai-completions` 或 `responses`，
不从 Agent 类型推断，不把它当作可覆写的推理参数。`model` 始终表示题包原模型，实际选择写入
`spec.verifier_models`。同槽题目的原模型或协议不同，不直接等同于不可兼容：由 Plan Validate
按每题固定／可配置约束及原生协议校验共同选择，不能只取第一题的要求覆盖其余题。
校验确认无共同兼容模型时列出失败题目，供用户调整数据或拆方案；不自动删题、换模型、转换协议或重命名槽。

### 选择授权来源并保存

用 `models list --project-id <project_id> --format json` 查询当前目录；个人来源再按现有
`--access user_connection --connection-id <connection_id>` 精确查询。不要加 Agent 类型过滤
来筛 Judge，也不要伪造 `benchmark-judge` 调用 `models spec/validate`；Judge 兼容性由 Plan Validate 核验。
固定题匹配声明模型名，可配置题由用户显式选择；核对目录协议及当前身份的 `allowed_accesses`。
目录可见不证明所有题目兼容，不自动取目录第一项或新增连接。只确认一次模型及来源，不逐题问卷。
简短展示“Agent 用 A；Judge 用 B，走平台／当前个人连接”。已有明确来源选择且适用于 Judge
则复用；否则在 Preview 确认来源。无授权候选则说明阻断，不回退 Agent 模型、平台 Key 或其他连接。

用 `agent-eval examples plan-patch-verifier-models.json` 获取完整 Patch 形状。替换样例槽名、模型
及精确 CAS 绑定；每个值是 `TargetModelConfig` 形状，不套 `config`、不填 Token／API Key／base_url。
`access=user_connection` 时补当前 Project、当前用户有权使用的 `connection_id`；`ark_router`
不带该字段。`parameters` 默认 `{}`，不顺带修改题目的 Rubric、评分提示词或固定推理参数。
替换 `/spec/verifier_models` 时提交所需槽的完整映射，保留仍适用的原绑定；移除不再使用的槽需符合
本次数据变更授权，不改其他分区。Comparison 沿用原子 `batch-patch-members`，逐成员核对要求，
共同题目的评分模型必须由服务证明等价；不等价或无法证明时阻断发布，不接受“忽略差异”。
修改时保留未要求变更的 Judge 配置，Dataset 变化后重新 Validate。

### 校验、发布与历史边界

Preview 同时展示 Agent 和 Judge；`JUDGE_BINDINGS_UNVALIDATED` 不是已通过。
使用非原始 Judge 时说明评分解释限制：接口兼容不代表与官方 Judge 评分质量等价。
不把这项解释边界当作报告缺失或运行失败，不额外试调用模型。
执行精确 Plan／Comparison Validate，按结构化诊断处理缺绑定、多余绑定、模型／协议不匹配和权限错误；
不要通过删除报错字段绕过检查。只有校验有效且已获发布授权才 Publish。
回读精确 Snapshot 的逐题 `verifier_secrets[].model_binding`，核对模型、协议及来源／连接与确认配置一致；
不一致则停止，不启动试跑。发布只证明配置冻结，不证明实际 Judge 调用成功。
历史 Snapshot 继续按原冻结合同处理，不根据新目录、requirements 或 Skill 修改它；执行端明确拒绝兼容时，
按[旧 Snapshot 恢复说明](diagnosis-and-recovery.md#snapshot-不兼容时如何恢复)处理，不自动迁移或重发评测。
重评分不自动沿用新 Judge 投影。解读报告时从报告保留的 Snapshot 读取实际 Judge binding，
与 Agent 模型分开说明，不根据当前目录或题包原模型猜测历史评分配置。

## EvalPlan 的 environment 参数（`spec.environment.config`）

这一段回答"每道题在哪个世界里跑"。它是一份**策略**（policy），不是 Environment
spec：服务按 `resolution_mode` 校验，**每种模式只接受一组固定的键**，多一个键或少一个键
都会以 `ENVIRONMENT_POLICY_MALFORMED` 拒绝；不存在的模式返回
`ENVIRONMENT_RESOLUTION_UNSUPPORTED`。当前没有独立查询该策略 schema 的 CLI 命令，以下是本版本支持的输入形状，
最终以当前服务 Preview / Validate 的诊断为准；不要把 Environment 模块的 provider
字段（`vefaas.CreateFunction.*` 等）写进来，也不要因版本差异猜测其他字段。

| `resolution_mode` | 必填键 | 可选键 | 含义 |
|---|---|---|---|
| `benchmark_precache` | `target_execution_provider_type`、`dataset` | `resources` | **预缓存 benchmark 的标准模式。** 每道题运行在题目自带的预缓存镜像里；`dataset` 是 precache store 的标签（`livecodebench@6.0`、`aider-polyglot@1.0`、`gaia@1.0`），题目由 Dataset 闭包决定，服务逐题在 store 中解析并冻结镜像摘要 |
| `target_default` | `target_execution_provider_type` | — | 使用 Project 里**已发布**的默认 target-execution Environment。Project 没有时返回 `ENVIRONMENT_DEFAULT_MISSING`，Snapshot 会以 `readiness.status=pending` 发布且不可执行；benchmark 题目要求自带镜像时返回 `TASK_ENVIRONMENT_UNSUPPORTED` |
| `image` | `target_execution_provider_type`、`image {ref, digest}`、`resources` | — | 所有题目运行在同一个摘要固定的镜像里；`image.ref` 是 tag 引用（不带 `@sha256:`），`image.digest` 是 `sha256:` + 64 位十六进制 |
| `managed_agents_environment` | `ma_environment_id`、`ma_agent_id` | — | 直接使用用户已拥有的方舟 Managed Agents 云环境；**不**带 `target_execution_provider_type` |

- `target_execution_provider_type` 只有两个值：`vefaas`（Claude Code / Codex 等安装型
  Target 的沙箱）和 `ma`（被测 Target 是 Managed Agent 时）。`ma` 在
  `benchmark_precache` / `image` 下表示 **self-hosted**：Agent 在方舟运行，题目沙箱由
  Lab 承载。不要直接写 `managed_agents`、`local_docker` 或 `docker`。
- `resources` 的形状固定为 `{"cpu_milli": int, "memory_mb": int, "storage_mb": int}`，
  三项都是正整数，不接受别的键。`benchmark_precache` 下它是可选的：store 里的世界自带
  资源声明时省略；世界没有声明时（例如 `gaia@1.0`），按 provider 声明的默认规格运行
  （veFaaS / self-hosted MA：4000 mCPU / 8192 MB / 10240 MB），Plan 带
  `RESOURCE_SHAPE_DEFAULTED` 警告。用户要别的规格时按用户确认的数值补上 `resources`，不要猜。
- `dataset` 的标签必须与 `spec.dataset.config.dataset_version_refs` 指向的题目来自同一个
  benchmark；发布前用 `agent-eval worlds check --dataset <label> --item <task_name>`
  确认题目世界已构建（见 [高级操作参考](advanced-operations.md) 的"预缓存世界是否已构建并可运行"）。

内置样例 `agent-eval examples plan-create-precache.json` 是 `benchmark_precache` 的完整
Plan；`plan-create-claude-code.json` / `plan-create-codex.json` 是 `target_default`，只在
Project 已发布默认 Environment 时可用。评测 MA 时参考
`agent-eval examples plan-create-ma.json`（`agent_type: ma` + `target_execution_provider_type: ma`）。
MA 样例使用 `target_default`；题目需要 precache 时按本表改为 `benchmark_precache`，
使用与精确 DatasetVersion 相符的世界标签，不把示例当作环境已就绪的证明。

**MA 的两种题目环境形态，按用户的话选**（写错这里是 MA 配置最常见的卡点）：

1. **题目世界由 Lab 承载（self-hosted，默认选它）**：沿用上表的
   `benchmark_precache` / `image` / `target_default`，把
   `target_execution_provider_type` 写成 `ma`。含义是被测 Agent 在方舟侧运行，
   每道题的沙箱由 Lab 起，工具调用经 Bridge 回到该沙箱。
2. **用用户自己已有的 MA 云环境**：把 environment 分区整段换成
   `managed_agents_environment`，它**不带** `target_execution_provider_type`，
   并且自己带一份 `ma_agent_id`：

   ```json
   {
     "environment": {
       "config": {
         "resolution_mode": "managed_agents_environment",
         "ma_environment_id": "<用户提供>",
         "ma_agent_id": "<与 target.config.agent_id 同一个智能体>"
       }
     }
   }
   ```

   这种模式下 agent id 出现在两处（Target 与 Environment），必须指向同一个智能体；
   用户没有明确给出 `ma_environment_id` 时不要编，改用第 1 种。

**启动 Run 时用哪个 Ark 账号**：MA 会话用调用方的 Ark Key（`runs start` 从
`--ark-api-key` / `ARK_API_KEY` 读取，随请求头一次性传递，不入 Snapshot、不落盘）。
不提供时服务回退到部署级 Key，那个账号看不到用户的 Agent，表现为
`AGENT_SETUP_FAILED` / `InvalidAgent.NotFound <agent-id>`——遇到这个错先查 Key，
不要改 Plan、不要换 `agent_id`。

```json
{
  "environment": {
    "config": {
      "resolution_mode": "benchmark_precache",
      "target_execution_provider_type": "vefaas",
      "dataset": "livecodebench@6.0"
    }
  }
}
```

遇到以下拒绝码时按字面修正，不要换一种猜法重试：`ENVIRONMENT_POLICY_MALFORMED`
（键集合或取值形状不对，`field_path` 指向出错的键）、`ENVIRONMENT_RESOLUTION_UNSUPPORTED`
（模式名写错）、`ENVIRONMENT_PROVIDER_TYPE_UNSUPPORTED`（provider type 不是 `ma`/`vefaas`）、
`RESOURCE_SHAPE_UNRESOLVED`（provider 未声明默认规格，需要 `resources`）、`PRECACHE_ITEM_UNRESOLVED` /
`WORLD_INCOMPLETE`（题目世界未就绪，先 `worlds check`）、`ENVIRONMENT_DEFAULT_MISSING`
（`target_default` 无默认环境：按用户授权准备相容的默认环境；仅当题目确实有对应预缓存世界且用户同意时才改用 `benchmark_precache`，不能用换模式掩盖阻断）。

## RunPolicy：用户输入与生效策略

用户配置放在 `spec.run_policy.config`，不是 `content.run_policy`：

```json
{
  "run_policy": {
    "schema_version": "run-policy.config.v2",
    "config": {
      "repetitions_per_item": 1,
      "run_parallel_limit": 50,
      "item_timeout_seconds": 7200,
      "run_timeout_seconds": null,
      "item_failure_policy": "continue",
      "retry_policy": {
        "mode": "technical_failure_only",
        "max_attempts_per_item_run": 2
      }
    }
  }
}
```

新建主动评测方案默认填写上述配置，不让用户逐项选择技术参数；仅在用户主动要求时调整。
用户已经表达的时间、次数或费用限制不得被默认值覆盖。服务端负责强制校验与补齐缺省值；
新格式不填写 `preset` 或 `overrides`，不向不支持该格式的旧服务降级重试。

| 字段 | 可配置范围 |
|---|---|
| `repetitions_per_item` | 整数 1–10；计划重复执行，不是失败重试 |
| `run_parallel_limit` | 整数 1–50，默认 50；单 Run 并发上限，不保证获得对应容量 |
| `item_timeout_seconds` | 整数 1–86400，默认 7200；一次 Attempt 的整题预算 |
| `run_timeout_seconds` | `null` 自动计算；或整数 3600–604800，且不得小于单题预算 |
| `item_failure_policy` | `continue` 或 `fail_fast` |
| `retry_policy` | `mode` 为 `technical_failure_only` 或 `disabled`；`max_attempts_per_item_run` 为 1–3（含首次），`disabled` 必须为 1 |

超范围、字符串冒充数字、未知字段或枚举值会报错，不能自行截断或编造值。
历史 `active-default-v1` / `active-long-v1` 保留兼容；未获用户授权，不为统一格式改写已有 Draft 或 Snapshot。
默认 50 仅用于新建方案的缺省配置；修改已有方案时保留原并发值（如 5、20），不因新默认值而自动升级。
环境、项目、模型／个人连接额度及 Worker 空位仍独立生效，不能为达到 50 并发而自动调高它们。

### 将用户意图对应到操作

| 用户意图 | 含义与处理 |
|---|---|
| 每题独立评测 3 遍 | 将 `config.repetitions_per_item` 改为 3；不是自动重试 |
| 每题失败后自动重试 2 次 | 新格式设 `technical_failure_only` / 3；仅重试服务认定可重试的技术失败，不重试质量失败 |
| 每题最多跑 60 分钟 | 新格式设 `config.item_timeout_seconds=3600`；不是延长 CLI watch |
| 已结束的一轮中，只重新执行指定失败题 | 按主指南的限定 `runs rerun` 流程核对资格和授权；创建派生 Run，不改变源 Snapshot 策略 |

用户只说“重试几次”且上下文不能区分上述意图时才补问；意图明确时不重复确认。
修改前读取完整 Draft，新格式只调整 `config` 中用户指定的字段，旧格式沿用原预设允许的覆盖项。
Patch 仍提交完整 `/spec/run_policy` 分区，不把局部 config 当作局部合并；缺省字段会重新取默认值。
修改重复次数使用 `agent-eval examples plan-patch-run-policy.json`，按
`agent-eval examples README.md` 的“单 Plan：只修改每题重复次数”填写精确绑定并回读验证。
Comparison 的策略修改使用原子成员更新，保持各成员生效 RunPolicy 一致，不能只改一侧后仍声称条件相同。

### 冻结结果怎么读

Snapshot 的 `content.run_policy` 保存上述六个字段的最终值，不保留输入格式标识、preset 或 overrides。
`run_timeout_seconds=null` 按 `(唯一题数 × 每题重复次数 × 每次最大尝试数 + 1) × 单题预算`
计算，限制在 1 小时至 7 天，Snapshot 中一定为整数。超过 7 天会有封顶提示；这是预算，不是完成承诺。
显式填写 Run 期限时不按题数重算。历史预设仍按历史规则编译，不能套用新默认值解释旧 Snapshot。

Run 的截止时间从创建时起计算，排队也消耗整轮预算；选题 Run 沿用原 Snapshot 的预算，不按选中题数重算。
到期进入异步取消／收尾，不代表瞬时停止或立即释放资源。单题预算也不等于包含全部归档工作的端到端耗时承诺。
`max_attempts_per_item_run` 是执行预算，不是原始 Attempt 记录数硬上限：完全未被领取且满足安全回收条件的
派发过期最多可额外重派 2 次。技术尝试不是独立质量样本，不用“题数 × 最大尝试数”承诺记录数、模型请求数或费用上限。
没有可靠吞吐／计费依据时，不用超时、并发或计划执行量推算精确 ETA 与金额。

按 Preview / Validate / Publish 和精确 Snapshot 的实际结果核对，不根据 Skill 版本声称部署已支持新格式。
配置允许 24 小时不等于所有环境均可承载：发布期需要核对租期和执行合同，长时 Provider／凭证能力仍须验收。
新配置编译为 executor v3，环境启动等待最多 1 小时，且计入整题总预算；环境租期至少覆盖预算加 10 分钟收尾余量。
MA 与非 MA 使用相同的 RunPolicy 字段、默认值和范围，不因 Target 类型回退旧 preset。
新自托管 MA Run 必须使用调用方 `ARK_API_KEY`，按冻结 Run 期限有界缓存（最长7天），终态删除；
执行中缺失或读取失败明确报错，不换成平台身份。Bridge 绑定和服务循环按单题预算设置。
云端 MA 沿用其 Environment Provider 鉴权路径；统一配置不代表两种环境身份机制相同，也不代表真实长时验收通过。
已有 MA 方案保持原配置；所有 Target 仍以 Owner Preflight 实际结果为准。
不为绕过环境拒绝自动缩短用户预算。CLI `watch --timeout` 仅影响观察窗口。
技术失败保持未评分，不计为质量零分；诊断见[诊断与修正参考](diagnosis-and-recovery.md)。
