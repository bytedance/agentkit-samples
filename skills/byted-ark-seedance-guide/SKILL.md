---
name: byted-ark-seedance-guide
description: "火山方舟 Seedance 模型使用指导技能。用户询问 Seedance/seedance2.0/doubao-seedance-2-0/doubao-seedance-2-0-fast/seedance2.0-mini等seedance系列模型的火山方舟接入、API 调用、参数、任务创建、任务查询、结果获取、计费开通、报错排查、SDK、最佳实践时优先调用本技能；当用户提供火山引擎官网文档链接（形如 https://www.volcengine.com/docs/*）并要求解读、总结、提炼、查询其中规则或基于文档回答时，也应调用本技能并通过 fetch 获取文档全文；普通提问使用 ServiceCodes: ark 检索火山方舟官方文档。"
metadata:
  author: volcengine/support
  version: "1.1"
---

# seedance-guide 火山方舟 Seedance 使用指导技能

## 功能描述
火山方舟 Seedance 模型使用指导技能，支持**按 ServiceCodes=ark 检索官方文档**和**根据火山引擎官网文档链接获取文档全文**。适用于 Seedance 相关的方舟接入、API 调用、参数解释、任务创建、任务查询、生成结果获取、计费开通、报错排查、SDK、最佳实践问题；也适用于用户直接提供 `https://www.volcengine.com/docs/...` 官方文档链接并要求总结、解读、提炼规则、定位参数或基于该文档回答的场景。

## 决策逻辑（必看）
### 触发判断规则
1. **Seedance 相关使用问题**：当用户提到 Seedance、seedance2.0、Seedance 2.0、doubao-seedance-2-0、doubao-seedance-2-0-fast、doubao-seedance-2-0-mini、视频生成、文生视频、图生视频、首尾帧、多模态参考生视频、创建视频任务、查询视频任务等火山方舟使用问题时，优先调用本技能。
2. **用户提供火山引擎官网文档链接**：当用户消息中包含 `volcengine.com/docs/` 或 `www.volcengine.com/docs/` 形式的官方文档链接，例如 `https://www.volcengine.com/docs/82379/2222480`、`https://www.volcengine.com/docs/82379/1520757?lang=zh`，并要求“总结/解读/提炼/查询/根据文档回答/看这个文档”等操作时，直接调用 `fetch` 接口获取完整内容，无需先检索。
3. **非 Seedance 或非方舟问题**：除非用户明确要求查方舟 Seedance 文档，否则不要把本技能作为通用火山引擎文档检索工具使用。

### search 和 fetch 配合规则
1. **用户提问类需求**：优先调用 `search` 接口，并且必须携带产品编码 `ark`，即 `ServiceCodes: ["ark"]`；返回5条结果，优先使用返回的Content内容回答。
2. **关键词补全**：如果用户只说“seedance 怎么用”等泛问题，检索词应补充“火山方舟 Seedance 2.0 doubao-seedance-2-0 创建视频生成任务 查询视频生成任务 API”等关键信息。
3. **二次检索优化**：如果第一次搜索结果匹配度不高，仍然保持 `ServiceCodes: ["ark"]`，改写关键词后再次检索。
4. **全产品兜底检索**：如果改写关键词并保持 `ServiceCodes: ["ark"]` 的第二次检索结果匹配度仍然不高，则第三次检索不携带 `ServiceCodes` 参数，进行全产品检索，再从结果中选择最相关的官方文档；不要切到 LAS 或其他产品文档，除非全产品兜底检索命中且内容确实相关，或用户明确要求对比。
5. **需要完整文档内容**：先调用 `search` 找到对应文档链接，再调用 `fetch` 获取全文内容。
6. **用户已给出官方文档 URL**：不要再用搜索绕路；先清理 URL query 参数，直接调用 `fetch` 获取全文，再围绕该文档内容回答。

## 功能说明
### 1. 文档检索 (search)
根据用户问题检索火山方舟 Seedance 相关官方文档，固定按产品编码 `ark` 过滤。
- 请求地址：`https://docs-api.cn-beijing.volces.com/api/v1/doc/search`

#### 请求参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| Query | string | 是 | 用户的具体问题描述 |
| Limit | number | 否 | 检索返回的文档数量，默认返回5篇 |
| ServiceCodes | array<string> | 否 | 产品过滤条件，指定仅查询某几个产品的文档，可通过返回结果中的ServiceCodes字段获取产品编码 |

#### 返回参数
核心有效数据在 `Result.DocList` 字段中，每个文档项包含：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| Title | string | 官方文档标题 |
| Url | string | 文档官方访问链接 |
| Content | string | 文档完整内容 |
| ServiceCodes | array<string> | 文档所属产品编码列表 |

---

### 2. 内容获取 (fetch)
根据火山引擎官方文档链接，获取对应的完整文档内容，支持结构化解析文档标题、正文内容。
- 请求地址：`https://docs-api.cn-beijing.volces.com/api/v1/doc/fetch`

#### 请求参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| Url | string | 是 | 火山引擎官方文档链接，格式如 `https://www.volcengine.com/docs/6349/162514` |

⚠️ **重要处理规则**：
如果Url包含query参数（例如 `https://www.volcengine.com/docs/6396/624853?lang=zh`），需要在请求前去掉所有query参数，只保留 `https://www.volcengine.com/docs/6396/624853` 部分进行请求。

#### 返回参数
核心有效数据在 `Result` 字段中：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| Title | string | 文档的完整标题 |
| Content | string | 文档的完整正文内容，结构化解析后的文本 |

## 结果处理规则
### 通用强制规则
1. 所有回答末尾**必须**附上对应的官方文档链接作为参考来源，使用 `[文档标题](纯净URL)` 格式，每条结果都要标注来源地址
2. 如果返回多个结果，按相关性排序展示，最多展示3条最相关的结果，每条结果都附带对应的文档链接
3. 链接必须使用脚本返回的`CleanUrl`（已剥离所有query参数），禁止使用带`?lang=zh`等参数的URL

### 检索结果处理
1. 优先使用返回的Content内容回答用户问题，信息更准确
2. 接口直接返回文档完整内容，无需做额外摘要提炼

### 内容获取结果处理
1. 接口直接返回文档完整内容，可直接使用无需额外处理

## 工具使用方法
### 检索文档
```bash
python {skill_dir}/scripts/seedance-docs.py search "查询关键词" 5 ark
```
示例：
```bash
python {skill_dir}/scripts/seedance-docs.py search "火山方舟 Seedance 2.0 创建视频生成任务 API" 5 ark
```

推荐检索关键词：
```bash
python {skill_dir}/scripts/seedance-docs.py search "火山方舟 doubao-seedance-2-0 文生视频 图生视频 创建任务 查询任务 API" 5 ark
python {skill_dir}/scripts/seedance-docs.py search "Seedance 2.0 fast doubao-seedance-2-0-fast 参数 计费 开通 报错" 5 ark
python {skill_dir}/scripts/seedance-docs.py search "方舟 Seedance 多模态参考生视频 首帧 首尾帧 视频生成教程" 5 ark
```

### 获取文档完整内容
```bash
python {skill_dir}/scripts/seedance-docs.py fetch "火山引擎文档链接"
```
示例：
```bash
python {skill_dir}/scripts/seedance-docs.py fetch "https://www.volcengine.com/docs/82379/1520757?lang=zh"
```
