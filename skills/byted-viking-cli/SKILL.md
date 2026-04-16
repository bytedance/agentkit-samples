---
name: byted-viking-cli
description: 官方Viking CLI 命令行助手：本CLI覆盖火山引擎 VikingDB(向量库)/Knowledge(知识库)/Memory(记忆库)的数据集管理和数据的读写及检索，
  可用于扩展Agent的知识检索边界 提升Agent的记忆能力；
  当用户对知识库/向量库提问时，使用本Skill;
  当用要操作向量库/知识库 或 从向量库/知识库检索信息时使用本Skill；
  当用户要记忆检索和记忆存储时，使用本Skill。
version: 1.0.0
license: Apache-2.0
---

## 目标
把用户的需求转换为可直接执行的`viking-cli`命令并执行，如果覆盖不了则提示用户。
`viking-cli`命令位于skill安装目录下的`scripts/viking-cli`, 直接执行这里的，不要从系统路径中查找。


## 工作原则
- 涉及复杂 JSON、中文、嵌套数组时，优先推荐文件输入方式；如果当前命令不支持文件输入，再给命令行 JSON 示例。
- 如果用户没有指定collection，则可省略 `--collection` 的参数，默认使用配置文件中的 collection 。
- 如果用户需求超出当前 CLI 能力边界，要明确说“当前 CLI 未实现该子命令”。

## 命令树
- `viking-cli version`
- `viking-cli auth`
- `viking-cli vikingdb`
  - `setup`
  - `collection {create|get|list|update|delete}`
  - `index {create|get|list|update|delete|enable|disable}`
  - `upsert`
  - `fetch`
  - `delete`
  - `search-by-id`
  - `search-by-keywords`
- `viking-cli memory`
  - `setup`
  - `collection {create|get|list|update|delete}`
  - `add-session`
  - `search`
- `viking-cli knowledge`
  - `setup`
  - `collection {create|get|list|delete}`
  - `add-doc`
  - `add-file`
  - `add-dir`
  - `get-doc`
  - `list-docs`
  - `update-doc`
  - `delete-doc`
  - `search-knowledge`
  - `service-chat`

## 全局配置
CLI 通过 `viking-cli auth` 交互式写入 `~/.viking/config`，后续命令默认从配置文件读取 AK / SK / Region / Project，
如无特殊情况，命令行无需指定--region和--project参数。
用户执行过对应产品的 `setup`，创建的collection name会写入配置文件，后续很多数据面命令可以不再显式传 `--collection`。

### 交互式配置（推荐）
```bash
viking-cli auth
```
执行后，根据提示依次输入：
- AccessKey (AK)
- SecretKey (SK)
- Region (如 `cn-beijing`)
- Project (如 `default`)

### 全局 Flags（命令行参数）
当前实际支持的全局 flags 只有：
- `--format`：输出格式，`json` 或 `text`
- `--timeout`：请求超时，例如 `120s`


## JSON 输入策略
部分 control plane 命令支持：
- `--input-json '<JSON_OBJECT>'`
- `--input-file /path/to/payload.json`

这类命令会先用结构化 flags 组装 payload，再 merge `--input-json/--input-file` 的内容。

建议：
- 结构简单时，用显式 flags
- JSON 结构复杂时，用 `--input-file`
- `memory add-session` 复杂内容优先推荐 `--messages-file`；`metadata` 可选，传文件用 `--metadata-file`

## 输出约定
默认输出为格式化 JSON；若用户需要纯文本，使用 `--format text`。


### 版本与鉴权配置
```bash
viking-cli version
viking-cli auth
```

### VikingDB / Setup
通过本地数据样本自动推断 schema，并一键创建 collection、index，并 upsert 数据 【推荐】。

`vikingdb setup` 支持默认命名（允许不传 `--collection` / `--index`）：
- 默认 collection：`viking_cli_{userid}`
- 默认 index：`viking_cli_{userid}_index`（即 `<collection>_index`）

```bash
viking-cli --region <region> vikingdb setup   --collection <collection_name>   --index <index_name>   --file data.csv   --id-field item_id

viking-cli --region <region> vikingdb setup   --collection <collection_name>   --index <index_name>   --file data.csv   --fields '[{"FieldName":"avatar","FieldType":"image"},{"FieldName":"content","FieldType":"text"}]'

viking-cli --region <region> vikingdb setup   --collection <collection_name>   --index <index_name>   --file data.jsonl   --vectorize-field content
```

### VikingDB / Collection
创建：
```bash
viking-cli --region <region> vikingdb collection create   --name <collection_name>   --desc '<description>'   --fields-json '<json_array>'   --fulltext-json '<json_object>'   --tags-json '<json_value>'   --vectorize-json '<json_object>'
```
完整 payload：
```bash
viking-cli --region <region> vikingdb collection create --input-file /path/to/create_collection.json
```
查询：
```bash
viking-cli --region <region> vikingdb collection get --name <collection_name>
```
列表：
```bash
viking-cli --region <region> vikingdb collection list  --page-number 1   --page-size 10   --filter-json '<json_value>'
```
更新：
```bash
viking-cli --region <region> vikingdb collection update --name <collection_name>   --desc '<description>'   --fields-json '<json_value>'
```
删除：
```bash
viking-cli --region <region> vikingdb collection delete --name <collection_name>
```

### VikingDB / Index
创建：
```bash
viking-cli --region <region> vikingdb index create  --name <index_name>   --collection <collection_name>   --desc '<description>'   --cpu-quota 2   --shard-count 1   --shard-policy '<policy>'   --vector-index-json '<json_object>'   --scalar-index-json '<json_value>'
```
查询：
```bash
viking-cli --region <region> vikingdb index get --name <index_name>   --collection <collection_name>
```
列表：
```bash
viking-cli --region <region> vikingdb index list --page-number 1 --page-size 10
```
更新：
```bash
viking-cli --region <region> vikingdb index update --name <index_name>   --collection <collection_name>   --desc '<description>'   --cpu-quota 4   --scalar-index-json '<json_value>'
```
启用 / 禁用：
```bash
viking-cli --region <region> vikingdb index enable --name <index_name> --collection <collection_name>
viking-cli --region <region> vikingdb index disable --name <index_name> --collection <collection_name>
```
删除：
```bash
viking-cli --region <region> vikingdb index delete --name <index_name> --collection <collection_name>
```

### VikingDB / Data
导入 / 更新数据：
```bash
viking-cli --region <region> vikingdb upsert   --collection <collection_name>   --file data.csv   --id-field id   --batch-size 200

viking-cli --region <region> vikingdb upsert   --collection <collection_name>   --file data.jsonl   --batch-size 200

```
获取数据：
```bash
viking-cli --region <region> vikingdb fetch --collection <collection_name> --ids-json '["id1","id2"]'
```
删除数据：
```bash
viking-cli --region <region> vikingdb delete --collection <collection_name> --ids-json '["id1","id2"]'
viking-cli --region <region> vikingdb delete --collection <collection_name> --del-all
```
相似搜索：
```bash
viking-cli --region <region> vikingdb search-by-id   --collection <collection_name>   --index <index_name>   --id '<document_id>'   --limit 10
```
Query或关键词搜索：
```bash
viking-cli --region <region> vikingdb search-by-keywords   --collection <collection_name>   --index <index_name>   --query '<search_text>'   --limit 10
```

### Memory / Setup 与 Collection
一键创建个人记忆库，默认命名为 `viking_cli_{userid}`：
```bash
viking-cli --region <region> memory setup

viking-cli --region <region> memory setup --name <collection_name>
```
创建：
```bash
viking-cli --region <region> memory collection create --name <collection_name>  --desc '<description>'   --cpu-quota 2
```
列表：
```bash
viking-cli --region <region> memory collection list
```
查询 / 更新：
```bash
viking-cli --region <region> memory collection get --name <collection_name>
viking-cli --region <region> memory collection update --name <collection_name> --desc '<description>' --cpu-quota 4
```
删除：
```bash
viking-cli --region <region> memory collection delete --name <collection_name>
```

### Memory / Session 与搜索
记录会话内容：
```bash
viking-cli --region <region> memory add-session   --collection <collection_name>   --session-id '<session_id>'   --messages-file ./messages.json   [--metadata-file ./metadata.json]
```
`messages.json` 示例：
```json
[
  {"role": "user", "content": "我喜欢打篮球"},
  {"role": "assistant", "content": "好的，记下了"}
]
```
`metadata.json` 结构（可选，未传时 CLI 会自动生成）：
```json
{
  "default_user_id": "user_id",
  "default_user_name": "user_name",
  "default_assistant_id": "assistant_id",
  "default_assistant_name": "assistant_name"
}
```
`filter-json` 结构（可选，未传时 CLI 会自动生成）：
```json
{
  "memory_type": ["sys_event_v1", "sys_profile_v1"],
  "user_id": "user_id",
  "assistant_id": "assistant_id"
}
```
记忆搜索:
```bash
viking-cli --region <region> memory search --collection <collection_name> --query '打篮球' --filter-json '<json_object>' --limit 10
```

### Knowledge / Setup 与 Collection
一键创建个人知识库，默认命名为 `viking_cli_{userid}`：
```bash
viking-cli --region <region> knowledge setup

viking-cli --region <region> knowledge setup --name <collection_name>
```
创建：
```bash
viking-cli --region <region> knowledge collection create   --name <collection_name>   --desc '<description>'   --version 4   --data-type unstructured_data
```
列表 / 查询：
```bash
viking-cli --region <region> knowledge collection list
viking-cli --region <region> knowledge collection get --name <collection_name>
```
删除：
```bash
viking-cli --region <region> knowledge collection delete --name <collection_name>
```

### Knowledge / 文档与搜索
新增文档（直接传 URI）：
```bash
viking-cli --region <region> knowledge add-doc   --collection <collection_name>   --uri <uri>   --doc-id <doc_id>   --doc-name '<doc_name>'   --doc-type '<doc_type>'   --desc '<description>'   --tag-list-json '<json_value>'
```
上传本地文件：
```bash
viking-cli --region <region> knowledge add-file   --collection <collection_name>   --file /path/to/local_file.pdf
```
上传目录：
```bash
viking-cli --region <region> knowledge add-dir   --collection <collection_name>   --dir /path/to/local_directory
```
获取 / 列表 / 更新 / 删除文档：
```bash
viking-cli --region <region> knowledge get-doc --collection <collection_name> --doc-id <doc_id>
viking-cli --region <region> knowledge list-docs --collection <collection_name> --offset 0 --limit 10
viking-cli --region <region> knowledge update-doc --collection <collection_name> --doc-id <doc_id> --doc-name '<new_name>'
viking-cli --region <region> knowledge delete-doc --collection <collection_name> --doc-id <doc_id>
```
知识搜索：
```bash
viking-cli --region <region> knowledge search-knowledge   --collection <collection_name>   --query '<text_query>'   --limit 10
```

### Knowledge / 知识服务的检索与问答
对知识服务进行检索或问答。支持非流式和流式输出。鉴权使用 APIKey：优先 `--api-key`，否则从 `~/.viking/config` 读取；首次调用成功后会写入配置文件，后续可直接复用。`service-rid` 同理：优先 `--service-rid`，否则从配置文件读取。
```bash
viking-cli --region <region> knowledge service-chat --api-key <api_key> --service-rid <service_rid> --content '列举 2025 Q1 财报里的三项亮点'

viking-cli --region <region> knowledge service-chat --service-rid <service_rid> --messages-file ./messages.json

viking-cli --region <region> --format text knowledge service-chat --service-rid <service_rid> --content '列举 2025 Q1 财报里的三项亮点' --stream true

viking-cli --format text knowledge service-chat --content "列举 2025 Q1 财报里的三项亮点" --stream true

```
`messages.json` 示例：
```json
[
  {"role": "user", "content": "列举 2025 Q1 财报里的三项亮点"}
]
```

## 常见问题定位
- `unknown command`：用户输入了当前 CLI 未实现的子命令；引导其回到本 skill 的命令树。
- `missing --name` / `missing --query` 等：这些都是实现里的硬校验；修复方式是补齐对应 flag。
- `missing --collection`：先确认是否已执行过对应产品的 `setup`。如果执行过，CLI 会自动从配置文件读取默认 collection；如果没执行过，则需要显式补 `--collection` 或 提示用户执行`setup`命令。
- JSON 解析报错：优先检查 shell 引号；复杂 JSON 优先改成 `--input-file`、`--messages-file`、`--metadata-file` 等文件输入。
- `client not initialized` 或请求初始化失败：通常是还没执行 `viking-cli auth`，或者配置文件里缺少 region / AK / SK。
- region 相关请求错误：优先显式补 `--region <region>`，然后用 `collection list` 之类的轻量命令验证配置是否生效。
