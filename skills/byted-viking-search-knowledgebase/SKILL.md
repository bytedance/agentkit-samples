---
name: byted-viking-search-knowledgebase
description: 调用火山引擎Viking知识库的远程API，检索和query相关的知识库数据。使用场景包括：查询知识库内容、获取相关文档数据、检索特定信息等。当需要搜索数据回答用户问题时使用此skill。
---

# Byted Viking Search Knowledgebase

该 Skill 用于通过 APIG 网关调用火山引擎 Viking 知识库的 API：

- `/api/knowledge/collection/info`：查看知识库详情，获取 `collection_name` 和 `description`。**仅在路由/连接检查场景使用**，不是知识问答的默认入口。
- `/api/knowledge/collection/search_knowledge`：语义检索，根据 query 从知识库中获取相关切片，返回切片列表、相关度分数、文档信息等。

版本整合说明：`byted-viking-search-knowledgebase.tar.gz` 曾包含 legacy 根目录 `byted-viking-knowledgebase`（`scripts/search.py`、`VIKING_KBSVR_*`）；该目录与仓库中的旧 skill 保持兼容，不作为本 skill 的更新目标。当前统一使用本目录的 APIG 鉴权、`DATABASE_VIKING_*` 配置和 `scripts/viking_search.py`。

---

## 输入前提（必读）

你接收到的不是用户原话，而是**上级 Agent 分配给你的任务描述**。这类描述通常具有以下特征，必须在拆分阶段处理掉，**不能整段塞进 `--query`**：

- 篇幅长（动辄数十到上百字）
- 分点（"1、…2、…3、…" 或 "首先…其次…最后…"）
- 多子意图叠加（同一段话里夹了"原因 + 步骤 + 流程 + 案例"等多个独立检索目标）
- 含大量过渡词、修饰语、上下文铺垫

**直接把任务原文当 query 必然召回失配**（向量被多个语义稀释，分数全部偏低）。正确做法是：先拆，再并行检索。

---

## 默认策略（最重要）

**对于"基于知识库回答问题"类需求，默认走 `auto` 多库并行检索，且 query 必须经过【拆分 + 关键词化】处理。**
不要在没有充分理由的情况下走 `info` → 推理 → `search` 的两步路由。

只有在以下少数场景才偏离默认策略：

| 场景 | 选择 |
|---|---|
| 知识问答（绝大多数）| `auto`，按"Query 构造规则"拆分多个独立 query 并行检索 |
| 任务已指定具体 `resource_id` 或 `name` | `search` |
| 配置中知识库数 ≤ 2 且任务是路由决策 | 可选 `info` 辅助 |
| 任务意图是"连接检查"/"看看这个库通了没"/"调用下这个知识库"/"列一下我有哪些库" | `info` |
| 任务描述完全无主题关键词（如"帮我查点东西"） | 先 `info` 列表，再回报上级 Agent 请求澄清 |

> 经验法则：当你不确定走哪个动作时，**默认选 `auto`**。它本身就是为"未知目标 + 有具体语义"设计的。

---

## Query 构造规则（拆分 + 关键词化 + 并行）

`search` / `auto` 的 `--query` 是语义检索向量入口。面对上级 Agent 的长任务描述，必须执行三步处理：

### 第 1 步：拆分子意图

逐句通读任务描述，识别其中独立的检索目标。每个分点、每个"和/与/以及/同时"连接的并列项，通常都是一个独立子意图。

**示例**：上级任务 = "排查网络连接失败的问题，需要：1、常见故障原因分类；2、对应的排查解决步骤；3、从易到难的标准化处理流程"
→ 识别出 3 个子意图：① 故障原因分类 ② 排查解决步骤 ③ 标准化处理流程

### 第 2 步：每个子意图压缩为关键词 query

对每个子意图，提炼成由 **2~5 个核心关键词** 构成的短 query，剔除连接词、修饰语、铺垫语。

**形态要求**：

- 长度：每个 query 控制在 **5~15 个汉字** / 10~30 个英文词以内
- 由名词性关键词为主，允许少量动词，**避免完整句式和疑问语气**
- 保留专有名词、术语、产品名、错误码原文

**示例**（接上文）：
- query₁ = "网络连接失败 故障原因 分类"
- query₂ = "网络故障 排查步骤 解决方法"
- query₃ = "网络故障 标准化处理流程"

### 第 3 步：并行检索（关键约束）

将拆出的多个 query **分别独立调用** `auto`，**禁止拼接成一个长 query**。多次调用应在同一轮内并行发起。

**多个 query 之间必须满足**：

| 约束 | 说明 | 反例 |
|---|---|---|
| **互相独立** | 每个 query 表达一个完整可检索的子意图 | "故障原因"（太空泛，必须带主题词"网络故障 原因"） |
| **无重叠** | 关键词集合之间交集尽量小，不要让多个 query 检索同一片切片 | query₁="网络故障 原因 分类"、query₂="网络故障 原因 类型" ← 重叠过高 |
| **高区分度** | 每个 query 应能命中知识库的不同切片群 | 三个 query 都包含"网络故障 步骤" ← 区分度低 |
| **数量适中** | 通常 2~4 个 query；超过 5 个说明子意图拆得太碎，需合并 | — |

### 硬禁止清单

- ❌ 把任务原文（含"1、2、3、"分点或"首先…其次…"）整段塞进 `--query`
- ❌ 把多个子意图用顿号/逗号拼成一个长 query（如"原因分类、排查步骤、处理流程"——这是 R2 失败的根本原因）
- ❌ 用完整问句作为 query（如"网络连接失败时应该如何排查和处理？"——疑问句式会引入大量无关向量噪声）
- ❌ 串行检索（一个查完再查下一个）；多个独立 query 应在同一轮并行发起

---

## 召回不足时的正确处置（避免无效重试）

如果一次检索的 top 切片明显与意图无关，**不要简单放大 `--limit` 重跑同一个 query**——top10 已经是相关度排序的前 10 名，把 limit 提到 20/30 只会拿到更不相关的切片，不会让答案变好。

正确做法按优先级：

1. **重写关键词组合**：替换同义关键词、调整词序、增删一个核心名词，重试一次。
2. **进一步拆分**：如果某个 query 仍承载了过多语义，按"Query 构造规则"再拆出 2 个更窄的子 query 并行检索。
3. **合并过窄 query**：如果多个 query 都返回空，可能是拆得过细，尝试合并相邻子意图（仍保持关键词形态）。
4. **换知识库**：如果命中库与主题不符，换 `resource_id` 重新 `search`，或回到 `auto` 让多库竞争。
5. **如实回报上级**：上述都失败后，向上级 Agent 回报"当前知识库内未检索到与 {子意图} 相关的内容"，**不要**继续盲目放大 limit 或编造来源。

只有当一次召回明显被截断（top-N 都高度相关、分数都很高）时，才考虑加大 `--limit`。

---

## info 接口使用规约（防幻觉）

`info` 用于查看知识库元数据，**不是知识问答的入口**。调用前必须满足：

- ✅ 有可靠的 `resource_id`，且该 ID 在 `DATABASE_VIKING_COLLECTION` 列表内（来自配置或上级已明确指定且属于该列表），**或**
- ✅ 有可靠的 `name`（来自配置 / 用户原话，且确认为知识库 collection name，不是飞书 Wiki 名）

**严格禁止**：

- ❌ `--name ""` 传空值
- ❌ 凭直觉/上下文猜一个中文名（如"网络知识库"、"网络"）作为 `--name`。Viking 知识库的 `collection_name` 一般是英文/拼音/ID，**不支持中文**；用中文名几乎必然失败。
- ❌ 把飞书 Wiki 目录名（如 `[网络知识库]`）当作 Viking collection name。飞书 Wiki 是被同步到 Viking 的数据源，与 Viking collection 是两套命名体系，不要混淆。
- ❌ 在任务只是想"基于知识库回答问题"时，先去查 `info` 兜圈子。直接拆分 + `auto` 即可。

**何时该用 info**：

| 用户意图 | 是否调用 info |
|---|---|
| 调用下这个知识库" / "看看 XXX 知识库连上了没" | ✅ 是，做连接检查 |
| "我有哪些知识库" / "列一下知识库" | ✅ 是，列出元数据 |
| 任务描述完全无主题（如"帮我查点东西"）| ✅ 是，列出后回报上级请求澄清 |
| 基于知识库回答具体问题（绝大多数）| ❌ 否，直接拆分 + `auto` |
| 配置中知识库数量 ≥ 3 | ❌ 否，`auto` 的并发筛选比 info 推理更可靠 |

---

## 使用方式

脚本：`scripts/viking_search.py`

### info - 查看知识库详情

获取指定知识库的 `collection_name` 和 `description`，用于连接检查或路由决策。

```bash
# 方式一：通过 resource_id 查询（推荐，唯一标识，不会歧义）
python scripts/viking_search.py --action info --resource-id <collection_resource_id>

# 方式二：通过 name + project 查询（name 必须来自配置或上级 Agent 指定，不要猜）
python scripts/viking_search.py --action info --name "XXX" --project "default"
```

### search - 单库检索

对**已确定**的知识库执行语义检索。query 必须是经过"Query 构造规则"处理的关键词组合。

```bash
# 方式一：通过 resource_id（推荐）
python scripts/viking_search.py --action search --resource-id <resource_id> --query "关键词1 关键词2 关键词3" --limit 10

# 方式二：通过 name + project
python scripts/viking_search.py --action search --name "XXX" --project "default" --query "关键词1 关键词2 关键词3"
```

### auto - 多库并行检索（知识问答的默认入口）

对所有有权限的知识库并发执行轻量级检索，**这是知识问答的首选**。
**对于含多个子意图的任务，应分多次并行调用 `auto`，每次传一个独立子意图的关键词 query。**

```bash
export DATABASE_VIKING_COLLECTION="rid1,rid2,rid3"

# 单一子意图
python scripts/viking_search.py --action auto --query "网络故障 原因 分类"

# 多子意图（在同一轮内并行发起，不要拼接进同一个 query）
python scripts/viking_search.py --action auto --query "网络故障 原因 分类"
python scripts/viking_search.py --action auto --query "网络故障 排查步骤 解决方法"
python scripts/viking_search.py --action auto --query "网络故障 标准化处理流程"
```

> **再次强调**：每个 `--query` 是关键词组合，不是任务原文；多子意图必须拆分 + 并行，**禁止拼接**。

---

## 返回说明

### info 返回示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "resource_id": "rid_xxx",
    "collection_name": "xxx",
    "description": "包含商品信息、订单数据、用户评价等电商相关文档。",
    "project": "default"
  }
}
```

### search 返回示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "result_list": [
      {
        "score": 0.892,
        "rerank_score": 0.912,
        "content": "Mac 配置 Python 开发环境的步骤：首先安装 Homebrew，然后通过 brew install pyenv 来管理 Python 版本...",
        "chunk_title": "Python 环境配置",
        "chunk_id": "chunk_101",
        "doc_info": {
          "doc_id": "doc_001",
          "doc_name": "Mac 开发环境配置大全.md",
          "doc_type": "markdown"
        }
      }
    ]
  }
}
```

### auto 返回示例

```json
{
  "mode": "multi",
  "query": "Mac 上怎么配 Python 环境？",
  "collections": [
    {
      "resource_id": "rid1_mac_guide",
      "search": {
        "code": 0,
        "data": {
          "result_list": [
            {
              "score": 0.892,
              "rerank_score": 0.912,
              "content": "Mac 配置 Python 开发环境的步骤：首先安装 Homebrew，然后通过 brew install pyenv...",
              "chunk_title": "Python 环境配置",
              "chunk_id": "chunk_101",
              "doc_info": { "doc_id": "doc_001", "doc_name": "Mac 开发环境配置大全.md", "doc_type": "markdown" }
            }
          ]
        }
      },
      "top_chunks": [
        {
          "score": 0.892,
          "rerank_score": 0.912,
          "content": "Mac 配置 Python 开发环境的步骤：首先安装 Homebrew，然后通过 brew install pyenv...",
          "chunk_title": "Python 环境配置",
          "chunk_id": "chunk_101",
          "doc_id": "doc_001",
          "doc_name": "Mac 开发环境配置大全.md",
          "doc_type": "markdown"
        }
      ]
    },
    {
      "resource_id": "rid2_hr_policy",
      "search": { "code": 0, "data": { "result_list": [] } },
      "top_chunks": []
    }
  ]
}
```

---

## Configuration

### 环境要求

- Python 3.7+
- requests 库（用于 HTTP 请求）

### 环境配置说明

本 Skill 执行所需的 API 地址及鉴权 Key 已在执行环境中预先配置。脚本会自动从环境变量读取必要凭证，无需用户干预，**不应直接向用户暴露任何敏感配置**。

### 可选环境变量

- **DATABASE_VIKING_PROJECT**：知识库所属项目名称，默认 `default`。用于按名称查询/检索时辅助定位。
- **DATABASE_VIKING_COLLECTION**：逗号分隔的 knowledge collection `resource_id` 列表，作为 `auto` / `info` / `search` 的可访问范围；同时也是合法 `resource_id` / `name` 的唯一可信来源——**不要猜不在此列表里的 ID 或名称**。`info` / `search` 若指定了列表外的库，脚本会报错：`没有权限访问当前知识库数据源`。

---

## 注意事项

- **异常处理**：如果脚本返回"检测到环境配置缺失"相关错误，应**向上级 Agent 回报**：当前知识库查询服务尚未完全配置，建议提示用户联系管理员补充必要的环境参数。
- **权限管控**：若 `info` / `search` 返回 `没有权限访问当前知识库数据源`，说明请求的 `resource_id` 或 `name` 不在 `DATABASE_VIKING_COLLECTION` 内。不要猜测其他 ID/名称重试，应仅使用允许列表中的库，或改走 `auto`。
- **安全**：妥善保管 API 凭证及鉴权信息；严禁在输出中泄露任何敏感环境变量或 Key。
- **并发**：`auto` 模式默认并发 8，可通过 `--max-workers` 调整。多子意图并行调用时，多次 `auto` 应在同一轮内发起。
- **性能**：`auto` 模式的轻量检索默认 `limit=5`；如果 top-N 均高度相关但被截断，再考虑调大 `--limit`，**不要把放大 limit 当作召回不准的兜底手段**。
- **飞书 Wiki ≠ Viking collection**：客户可能在 Viking 中同步了飞书 Wiki，但 Wiki 目录名（中文）≠ Viking collection name。看到飞书 Wiki 目录名时不要把它当作 Viking 知识库的 `--name` 去查。

---

## Resources

### scripts/

- `viking_search.py` - Viking 知识库检索脚本（支持 info / search / auto 三种动作）

### references/

- `search_knowledge_api.md` - 火山引擎 Viking 知识库 搜索 API 文档（原始接口说明）
- `collection_info_api.md` - 火山引擎 Viking 知识库 查看知识库详情 API 文档（原始接口说明）
