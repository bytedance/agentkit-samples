# 文档检索与 doc-first

本页指导如何用 `vefaas doc` 检索 veFaaS 官方文档，以及 **landing / 答疑 / SDK 接入** 三类知识场景的工作流。`vefaas doc` 全家桶**免登录、只读、不计费**，可自由多次调用。

涉及 veFaaS 概念、能力、选型、计费、限额、SDK 用法、OpenAPI 参数时，MUST 先用 `vefaas doc` 检索官方文档再作答或写代码，**禁止凭记忆直接回答这些具体事实**。

## doc 是什么

`vefaas doc` 是 veFaaS 官方文档的终端检索器，直连官网文档接口。把它当作本 skill 内置的轻量 RAG 检索工具：拉取权威文档原文，agent 在其上做问答或抽取代码示例，而不是凭记忆编造。

## 子命令与读取字段

agent 自用时**一律加 `-o json`**，按下表读取字段（字段路径已与 CLI 实现对齐）：

| 命令 | 用途 | agent 读取字段 |
| --- | --- | --- |
| `vefaas doc` | 列出内置主题 | `data.topics[].{topic,title,documentId}` |
| `vefaas doc <topic> -o json` | 取主题正文 | `data.markdown`（正文）、`data.title`、`data.url`、`data.updatedTime` |
| `vefaas doc search <关键词> -o json` | 按标题搜索 | `data.results[].{documentId,title,path,url}` |
| `vefaas doc tree -o json` | 官网完整目录树 | `data.tree`（嵌套）、`data.total` |
| `vefaas doc --id <DocumentID> -o json` | 按 ID 取任意文档正文 | `data.markdown`（同 detail） |

**内置主题别名（直达高频文档）：** `intro`（产品介绍）、`quickstart`（函数部署快速入门）、`cli`、`sdk`（SDK 概览）、`api`（API 列表）。

**SDK 子命令组：** `vefaas doc sdk` 概览；`vefaas doc sdk go|python|node` 各语言使用案例；`vefaas doc sdk methods [Action]` 从 SDK 解析出的方法/字段（详见工作流三）。

## 检索范式

1. **高频主题** → 用别名直达：`vefaas doc <topic> -o json`，读 `data.markdown`。
2. **长尾问题**（计费、限额、触发器、网关、某具体功能/接口）→ 两步：
   - `vefaas doc search <关键词> -o json` 定位：从 `data.results[]` 按 `title` + `path`（面包屑路径）挑最匹配的**叶子文档**，取其 `documentId`。**注意 search 只返回定位信息，不含正文。**
   - `vefaas doc --id <documentId> -o json` 取正文，读 `data.markdown`。
3. **不知道关键词** → `vefaas doc tree -o json` 浏览整棵目录定位。

## 坑位

- **目录节点无正文**：`vefaas doc --id` 打到纯目录（menu）节点会报 not-found。回到 search 结果换一条 `path` 更深的叶子文档。
- **别名只有有限个**：其余主题（计费/触发器/网关等）必须走 `search` 或 `tree`，不要硬猜别名。
- **markdown 可能较长**：`data.markdown` 是完整原文，agent 自行截取与问题相关的段落用于推理。

---

## 工作流一：新用户 landing

**触发**：用户第一次接触 veFaaS、不清楚它是什么 / 怎么开始 / 想跑起来第一个函数。

**步骤**：

1. **不要一上来让用户登录。** 先 `vefaas --version` 确认 CLI 已装且版本达标；未装给安装指引（可 `vefaas doc cli -o json` 取最新安装文档，避免给过时命令）。
2. 概念锚点：`vefaas doc intro -o json` → 用 `data.markdown` 给用户一段简短的「veFaaS 是什么、能干什么」。
3. 上手路径：`vefaas doc quickstart -o json` → 基于 `data.markdown` 把官方快速入门**结合用户当前项目类型裁剪成具体步骤**（不是照搬）。
4. 分流到执行：
   - 已有本地项目 → 走应用工作流（`vefaas deploy` 路径），此时才需要鉴权（环境变量 AK/SK 或 `vefaas login`）。
   - 没有项目 → 引导 `vefaas init` 选模板。
5. 收尾：告诉用户后续可用 `vefaas doc` / `vefaas doc tree` 自助查文档。

**要点**：全程「先用免登录 doc 把人引导明白，真正要部署时再触发登录」，避免新用户在第一步被鉴权劝退。

## 工作流二：veFaaS 答疑（doc-first 防瞎编）

**触发**：用户问 veFaaS 概念、能力边界、资源选型（函数 vs 应用 vs 沙箱）、计费、限额、触发器、某功能怎么配。

**步骤（强制 doc-first）**：

1. **意图归类**到主题或关键词：命中内置别名 → `vefaas doc <topic> -o json`；长尾 → `vefaas doc search <关键词> -o json` 取 `data.results[]`，挑叶子文档拿 `documentId`。
2. **取原文**：`vefaas doc --id <documentId> -o json`，以 `data.markdown` 为唯一事实来源。命中目录节点报 not-found 时换下一条更深的结果。
3. **基于原文回答**，不超出文档外推。**计费 / 限额 / 配额绝不能凭记忆**，必须引用文档原文数值。
4. **附出处**：回答末尾给 `data.url` 与 `data.updatedTime`（让用户知道文档时效）。
5. search 无结果 → `vefaas doc tree -o json` 浏览目录；仍找不到则**如实说明官方文档未覆盖**，不要编造。

**要点**：answer ⊂ `data.markdown`，出处必附。

## 工作流三：SDK / OpenAPI 代码集成

**触发**：用户要在自己的代码里调 veFaaS SDK（Go/Python/Node），或用 OpenAPI 创建/管理资源。

**步骤**：

1. **识别语言**：Go/Python/Node；不确定先 `vefaas doc sdk -o json` 看支持矩阵。
2. **取官方示例**：`vefaas doc sdk go|python|node -o json` → `data.markdown` 通常含安装方式 + 鉴权初始化 + 调用示例。**以官方示例为骨架改写**成用户的具体调用（替换函数名/参数/region），不要凭记忆写 client 初始化、包名、方法签名——这些最容易记错。
3. **查方法与字段（SDK）**：`vefaas doc sdk methods` 列出从 SDK 解析出的所有方法；`vefaas doc sdk methods <Action> -o json` 读 `data.fields[]`（每项 `name/type/required/describe`，含嵌套 `subFields`）确认请求参数；加 `--lang go|python|node|java|php` 还能拿到该语言的请求示例骨架（`data.example`）。字段说明与 `vefaas api <Action> --help` 同源。
4. **OpenAPI 场景（官网文档优先）**：`vefaas doc api` 列出官网有文档页的 Action（按官网分类）；某接口 → `vefaas doc api <Action> -o json` 读 `data.markdown` 拿**官网接口文档**（参数表 / 示例 / 返回值 / 错误码）按文档写代码。官网未收录的接口（如 apig/cr）→ `vefaas api <Action> --help` 看本地 catalog 字段；`vefaas doc sdk methods <Action>` 则提供结构化字段，二者互补。
5. **鉴权代码**：SDK/OpenAPI 都需要 AK/SK，提醒用户从环境变量 `VOLC_ACCESS_KEY_ID` / `VOLC_SECRET_ACCESS_KEY` 读取，不要硬编码密钥。
6. **交叉提示**：很多管理操作 CLI 已封装（见对应执行工作流），若用户其实更适合用 CLI 而非手写 OpenAPI，先提示这条更省事的路径。

**要点**：写任何 veFaaS SDK/API 代码前，必须先 doc 取到官方示例 / 参数表；禁止不查文档直接生成 SDK 调用代码。

## 何时不必查 doc

纯执行操作（部署、发布、回滚、调用、管理资源）走对应执行工作流，参数以 `vefaas <command> --help` 为准，不必为每个命令查官方文档。doc-first 只约束「知识类」请求，不要让它拖慢执行类任务。
