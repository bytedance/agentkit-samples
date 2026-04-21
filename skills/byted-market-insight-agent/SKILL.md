---
name: byted-market-insight-agent
description: 火山引擎市场洞察助手。帮助用户获取品牌在各大社交平台和媒体渠道上的公开内容数据，通过 AI 筛选出真正值得关注的信息，并发现潜在商机线索。当用户提到以下任何场景时使用此技能：想知道最近网上有没有人在讨论自己的品牌或产品、想看看竞品最近在社交媒体上有什么动态、想了解某个话题或事件在网上的讨论热度和趋势、想定期获取和自己业务相关的行业资讯和热点内容、想把筛选后的内容数据接入自己的系统做进一步分析、想查看自己账号下有哪些监测任务或拉取某个任务的数据、想了解最新的中东局势关税贸易战AI大模型等热点话题的网络讨论、想查询商机线索信息获取 ACOR 评估竞争分析公司画像、提到火山引擎市场洞察 Volcengine Insight PullPost ListCustomSubsTask QueryClueInfo。即使用户没有直接提到"市场洞察"，只要涉及品牌声量追踪、行业动态了解、热点事件网络讨论、公开内容数据获取、商机查询与分析等需求，都应触发此技能。
version: 1.0.1
---

# Market Insight Agent — 火山引擎市场洞察助手


## 用途与设计目标

本 Skill 旨在为 Agent 提供一个统一、稳定且无感的市场洞察服务调用入口。它整合了 `market-insight-agent-v2-optimized`（零依赖 Gateway 版本）和 `market-insight-agent-portable-sdk`（官方 SDK 版本）的优点，实现了以下目标：

1.  **统一调用路径**：无论底层采用 API Gateway 还是官方 SDK，对 Agent 而言，始终通过 `scripts/client.py` 中 `list_custom_subs_task`、`pull_post`、`query_clue_info` 三个函数以相同的方式调用。
2.  **动态 Provider 选择**：默认优先使用 API Gateway 方式。同时，Skill 能够根据当前环境（如环境变量配置）和运行时状态（如某条链路连续失败）动态地、智能地选择最佳调用路径。
3.  **SDK 自动安装**：当需要使用 SDK 路径但环境中未安装 `volcengine-python-sdk` 时，Skill 会自动尝试安装，实现真正的“开箱即用”。
4.  **状态与凭证持久化**：Skill 会将其运行状态（如上次成功的 Provider）和用户提供的凭证（若通过“最小化询问”获得）持久化到 Skill 私有的 `persist/` 目录中，实现会话间的状态保持和凭证复用。
5.  **最小化询问**：仅在完全没有可用凭证或所有链路均认证失败时，才向 Agent 层发出明确的“最小化询问”请求，由 Agent 决定何时以及如何向用户获取凭证，避免了不必要的打扰。

## 触发场景

当需要与火山引擎市场洞察服务交互时，应使用本 Skill。具体场景包括但不限于：

- **品牌声量监测**：获取关于特定品牌或产品的社交媒体讨论。
- **竞品动态追踪**：监控竞争对手的市场活动、用户反馈。
- **行业趋势分析**：通过分析公开数据发现行业热点与变化。
- **热点话题总结**：对特定事件或话题进行深入的内容挖掘与分析。
- **监控任务管理**：查询、管理在市场洞察平台创建的订阅/监控任务。
- **商机线索查询**：拉取由 AI 生成的、包含 ACOR 评估、公司画像等的结构化商机线索。

## Provider 选择策略

Skill 内部通过 `scripts/auth_resolver.py` 实现了一套智能的 Provider 选择策略，其决策顺序如下：

1.  **会话粘性优先**：如果上一次调用成功，则优先复用该 Provider（Gateway 或 SDK），以保证链路稳定性。
2.  **默认优先级**：在没有历史成功记录的情况下，默认按以下顺序尝试：
    -   **API Gateway**：检查是否存在 `ARK_SKILL_API_BASE` 和 `ARK_SKILL_API_KEY` 环境变量。此路径无任何第三方 Python 库依赖，是首选。
    -   **官方 SDK**：检查是否存在 `VOLCSTACK_ACCESS_KEY_ID` 和 `VOLCSTACK_SECRET_ACCESS_KEY` 环境变量。
3.  **动态降级**：如果某个 Provider 连续出现鉴权失败（401/403）或网络不可达，它将被临时标记为“降级”状态，在一段时间内自动切换到备用 Provider。
4.  **最小化询问触发**：当上述所有路径均因缺少凭证而无法使用时，Skill 会抛出 `MissingCredentialsError`，并附带清晰的提示，告知 Agent 层应如何向用户请求凭证。

更多细节请参考 `references/usage.md`。

## 危险操作限制

为了确保安全与合规，本 Skill 严格遵守以下限制：

-   **不执行 `aime skill upload` 或 `aime skill enable`**：Skill 的打包和部署应由用户或上层 CICD 流程明确发起，Skill 本身不包含任何自动上传或启用的逻辑。
-   **不硬编码凭证**：所有 API Key、AK/SK 等敏感信息均通过环境变量或持久化的 `persist/auth.json` 文件读取，代码中不包含任何硬编码的凭证。
-   **日志脱敏**：在打印 Debug 日志时，会自动对 API Gateway 地址、API Key 等敏感信息进行脱敏处理，仅打印非敏感的调用摘要。
-   **持久化目录隔离**：所有持久化文件（状态、凭证）均存储在 Skill 根目录下的 `persist/` 目录中，确保与工作空间的其他部分隔离。

## 环境变量在哪里找

本 Skill 在启动时会主动去帮你“找环境变量”，并按固定顺序决定实际生效的凭证来源：

- 首先**必须扫描常见 shell 配置文件中的 `export` 行**（`~/.bashrc`、`~/.bash_profile`、`~/.zshrc`、`~/.profile`），只读解析其中形如 `export ARK_*/VOLCSTACK_*` 的简单常量定义，用于收集 Gateway 与 SDK 的候选凭证；
- 然后默认假设用户已经在环境变量中配置了凭证：如果当前进程的环境变量（`os.environ`）中已经有对应的 `ARK_*` / `VOLCSTACK_*`，则认为这些值“已经生效”，**会覆盖前面从 rc 文件中收集到的候选值**；
- 若在环境变量中仍然缺少成对凭证，则再回退到 Skill 私有的持久化文件 `persist/auth.json`（由 Agent 层在最小化询问后写入），尝试补全缺失的 Gateway 或 SDK 凭证；
- 当上述三处都无法提供可用凭证时，才会抛出 `MissingCredentialsError`，由 Agent 层触发“最小化询问”，向用户要必要的少量信息。

顺序：**先扫描 rc → 再读取 os.environ（若已生效覆盖候选）→ 再读 persist/auth.json → 最后触发最小化询问**。

整个过程中，rc 文件的解析始终是只读的：
- 只解析简单常量形式的 `export VAR=VALUE` 行，不会执行 `source`，不会展开 `$VAR`、`$()` 等表达式；
- 日志中也只会输出脱敏后的摘要，而不会打印明文凭证；
- 不会自动写回 rc 或修改用户环境。

典型自查方式包括：

- 在终端中查看当前进程环境：`echo $ARK_SKILL_API_BASE` 或 `env | grep ARK_SKILL_API_BASE`
- 在 rc 文件中搜索 export 语句：`grep -n "^export ARK_SKILL_API_BASE" ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile 2>/dev/null`

## 快速验证

你可以通过运行 `scripts/quick_validate.py` 来进行一次静态自检，它会检查关键文件是否存在、Python 版本是否满足要求，以及环境变量的配置情况，但不会发起任何网络请求。

```bash
python3 scripts/quick_validate.py
```
