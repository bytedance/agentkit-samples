# SKILL: seederive-task

> Seederive 任务管理 SKILL —— 教会 Agent 创建、管理和预览打标任务

## 触发条件

当用户提到以下意图时触发：
- 创建打标/标注/分析任务（如"帮我对这批评论做情感分析"）
- 查看/管理已有任务（如"看看我有哪些任务"）
- 预览数据或查看任务结果（如"预览一下这个任务的输出"）
- 删除任务
- 任务回填

## 前置条件

确保已完成 `SKILL.md` 中的前置步骤（设置 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY`）。

## 脚本命令速查

| 操作 | 命令 |
|------|------|
| 创建任务 | `python ${SKILL_DIR}/scripts/seederive.py task create --name "名称" --flow-config-file flow.json` |
| 更新任务 | `python ${SKILL_DIR}/scripts/seederive.py task update --id 123 --name "新名称"` |
| 删除任务 | `python ${SKILL_DIR}/scripts/seederive.py task delete --id 123` |
| 获取详情 | `python ${SKILL_DIR}/scripts/seederive.py task get --id 123` |
| 任务列表 | `python ${SKILL_DIR}/scripts/seederive.py task list --keyword "情感"` |
| 任务回填 | `python ${SKILL_DIR}/scripts/seederive.py task backfill --bdb-task-id 456 --start-time "2025-01-01" --end-time "2025-01-07"` |
| 数据预览 | `python ${SKILL_DIR}/scripts/seederive.py task preview --input-dataset-file ds.json --limit 10` |
| 结果预览 | `python ${SKILL_DIR}/scripts/seederive.py task result --task-id 123 --page-size 10` |
| 轻量预览 | `python ${SKILL_DIR}/scripts/seederive.py task quick-preview --file data.csv --node-type EMOTION_DETECTION --input-column "评论内容"` |

## 核心概念：taskFlowConfig

任务的核心是 `taskFlowConfig`，它定义了数据处理的 DAG 流程图。创建任务时通过 `--flow-config-file` 传入 JSON 文件，或 `--flow-config` 传入 JSON 字符串。

```json
{
  "nodes": [ ... ],      // 节点列表
  "edges": [ ... ],      // 连接关系（sourceNodeId → targetNodeId）
  "finalSchema": null,   // 系统自动生成，创建时无需填写
  "llmConfig": null      // 可选，LLM 模型配置
}
```

### 节点类型总览

| 节点类型 | 名称 | 优先级 | 说明 | 需要标签库 |
|---------|------|--------|------|-----------|
| `DS_INPUT` | 数据输入 | 0 | 数据源入口，必须有 | 否 |
| `ASR` | 语音转文字 | 1 | 提取语音中的文字 | 否 |
| `OCR` | 图片文字提取 | 1 | 从图片中提取文字 | 否 |
| `TRANSLATION` | 多语言翻译 | 2 | 翻译成目标语言 | 否 |
| `SHILL_DETECTION` | 营销水军识别 | 3 | 识别营销水军内容 | 否 |
| `SUBJECT_DETECTION` | 主体识别 | 3 | 识别文本中提及的主体 | **是** |
| `TAG_DETECTION` | 标签识别 | 3 | 按标签体系分类 | **是** |
| `CONTENT_SCORING` | 内容评分 | 4 | 质量/原创/有用性/合规评分 | 否 |
| `OPINION_SUMMARY` | 观点总结 | 5 | 提取核心观点和理由 | 否 |
| `EMOTION_DETECTION` | 情感识别 | 6 | 正面/负面/中性情感分析 | 否 |
| `CUSTOM_APPLICATION` | 自定义应用 | 7 | 用户自定义提示词处理 | 否 |
| `DS_OUTPUT` | 数据输出 | 99 | 输出结果到目标表，必须有 | 否 |

### 节点连接规则

节点通过 `edges` 连接，必须遵循优先级顺序（低→高）。每个节点的 `inputAvailableNodeTypes` 定义了它可以接收哪些上游节点的数据。

### 节点详细配置

#### DS_INPUT（数据输入节点）

每个任务必须有且仅有一个 DS_INPUT 节点，定义输入数据源：

```json
{
  "nodeId": "ds_input_1",
  "nodeType": "DS_INPUT",
  "nodeName": "数据输入",
  "config": {
    "inputDataSet": {
      "type": "AEOLUS_DATASET",
      "aeolusDatasetId": "数据集ID",
      "database": "数据库名",
      "table": "表名",
      "cluster": "集群名"
    }
  }
}
```

#### EMOTION_DETECTION（情感识别节点）

```json
{
  "nodeId": "emotion_1",
  "nodeType": "EMOTION_DETECTION",
  "nodeName": "情感识别",
  "inputFields": [
    { "fieldName": "content", "fieldType": "ColumnReference", "value": ["评论内容"] }
  ],
  "outputFields": [
    { "fieldName": "emo", "fieldType": "Enum", "description": "情感分类（正面/负面/中性）" },
    { "fieldName": "emo_reason", "fieldType": "String", "description": "情感分析说明" }
  ]
}
```

#### TAG_DETECTION（标签识别节点）

> 需要先创建标签库获得 `tagBaseId`，详见 `${SKILL_DIR}/references/tag-base.md`

```json
{
  "nodeId": "tag_1",
  "nodeType": "TAG_DETECTION",
  "nodeName": "标签识别",
  "inputFields": [
    { "fieldName": "content", "fieldType": "ColumnReference", "value": ["评论内容"] },
    { "fieldName": "tag_base_id", "fieldType": "TagBase", "value": "标签库ID" }
  ],
  "outputFields": [
    { "fieldName": "l1_tag", "fieldType": "String" }, { "fieldName": "l1_reason", "fieldType": "String" },
    { "fieldName": "l2_tag", "fieldType": "String" }, { "fieldName": "l2_reason", "fieldType": "String" },
    { "fieldName": "l3_tag", "fieldType": "String" }, { "fieldName": "l3_reason", "fieldType": "String" },
    { "fieldName": "l4_tag", "fieldType": "String" }, { "fieldName": "l4_reason", "fieldType": "String" }
  ]
}
```

#### SUBJECT_DETECTION（主体识别节点）

> 需要先创建标签库（subject 类型）获得 `tagBaseId`，详见 `${SKILL_DIR}/references/tag-base.md`

```json
{
  "nodeId": "subject_1",
  "nodeType": "SUBJECT_DETECTION",
  "nodeName": "主体识别",
  "inputFields": [
    { "fieldName": "content", "fieldType": "ColumnReference", "value": ["评论内容"] },
    { "fieldName": "tag_base_id", "fieldType": "TagBase", "value": "标签库ID" }
  ],
  "outputFields": [
    { "fieldName": "l1_subject", "fieldType": "String" }, { "fieldName": "l1_reason", "fieldType": "String" },
    { "fieldName": "l2_subject", "fieldType": "String" }, { "fieldName": "l2_reason", "fieldType": "String" },
    { "fieldName": "l3_subject", "fieldType": "String" }, { "fieldName": "l3_reason", "fieldType": "String" }
  ]
}
```

#### SHILL_DETECTION（营销水军识别节点）

```json
{
  "nodeId": "shill_1",
  "nodeType": "SHILL_DETECTION",
  "nodeName": "营销水军识别",
  "inputFields": [
    { "fieldName": "content", "fieldType": "ColumnReference", "value": ["评论内容"] }
  ],
  "outputFields": [
    { "fieldName": "is_shill", "fieldType": "String", "description": "是否营销水军" },
    { "fieldName": "is_shill_reason", "fieldType": "String", "description": "识别理由" }
  ]
}
```

#### OPINION_SUMMARY（观点总结节点）

```json
{
  "nodeId": "opinion_1",
  "nodeType": "OPINION_SUMMARY",
  "nodeName": "观点总结",
  "inputFields": [
    { "fieldName": "content", "fieldType": "ColumnReference", "value": ["评论内容"] }
  ],
  "outputFields": [
    { "fieldName": "opinion", "fieldType": "String" },
    { "fieldName": "opinion_reason", "fieldType": "String" }
  ]
}
```

#### CUSTOM_APPLICATION（自定义应用节点）

```json
{
  "nodeId": "custom_1",
  "nodeType": "CUSTOM_APPLICATION",
  "nodeName": "自定义分析",
  "inputFields": [
    { "fieldName": "content", "fieldType": "ColumnReference", "value": ["评论内容"] },
    { "fieldName": "prompt", "fieldType": "Prompt", "value": "请分析以下内容..." },
    { "fieldName": "outputSchema", "fieldType": "OutputSchema", "value": [
        { "fieldName": "summary", "fieldType": "String", "description": "摘要" },
        { "fieldName": "keywords", "fieldType": "String", "description": "关键词" }
    ]}
  ],
  "outputFields": [
    { "fieldName": "summary", "fieldType": "String" },
    { "fieldName": "keywords", "fieldType": "String" }
  ]
}
```

#### TRANSLATION（翻译节点）

```json
{
  "nodeId": "trans_1",
  "nodeType": "TRANSLATION",
  "nodeName": "多语言翻译",
  "inputFields": [
    { "fieldName": "content", "fieldType": "ColumnReference", "value": ["评论内容"] },
    { "fieldName": "target_language", "fieldType": "String", "value": "中文" }
  ],
  "outputFields": [
    { "fieldName": "translation", "fieldType": "String" }
  ]
}
```

#### ASR（语音转文字节点）

```json
{
  "nodeId": "asr_1",
  "nodeType": "ASR",
  "nodeName": "语音转文字",
  "inputFields": [
    { "fieldName": "content", "fieldType": "ColumnReference", "value": ["音频URL"] },
    { "fieldName": "enable_speaker_diarization", "fieldType": "Boolean", "value": true }
  ],
  "outputFields": [
    { "fieldName": "asr", "fieldType": "String" }
  ]
}
```

#### DS_OUTPUT（数据输出节点）

每个任务必须有且仅有一个 DS_OUTPUT 节点：

```json
{
  "nodeId": "ds_output_1",
  "nodeType": "DS_OUTPUT",
  "nodeName": "数据输出",
  "inputFields": [
    { "fieldName": "target_dataset", "fieldType": "String", "value": "输出表名" },
    { "fieldName": "columns", "fieldType": "List", "value": ["emo", "emo_reason"] }
  ]
}
```

## 执行步骤

### 场景一：创建情感分析任务

用户说："帮我对这批评论数据做情感分析"

**步骤一**（Agent 模型能力）：分析用户需求，确定需要使用 EMOTION_DETECTION 节点

**步骤二**：执行脚本，查询现有任务，避免重复创建

```bash
python ${SKILL_DIR}/scripts/seederive.py task list --keyword "情感"
```

**步骤三**（Agent 模型能力）：如果已存在同名任务，询问用户是否要新建或复用

**步骤四**（Agent 模型能力）：根据用户需求构造 taskFlowConfig JSON，保存为临时文件 `flow.json`

**步骤五**：执行脚本，创建任务

```bash
python ${SKILL_DIR}/scripts/seederive.py task create --name "评论情感分析" --description "对评论数据进行情感分析" --flow-config-file flow.json
```

> `flow.json` 示例内容见本文档「核心概念：taskFlowConfig」部分，Agent 需根据节点配置参考构造完整 JSON。

**步骤六**：执行脚本，查询任务状态

```bash
python ${SKILL_DIR}/scripts/seederive.py task get --id 456
```

**步骤七**（Agent 模型能力）：分析任务状态，向用户报告

### 场景二：翻译后再做情感分析（多节点串联）

用户说："帮我把英文评论翻译成中文，然后做情感分析"

**步骤一**（Agent 模型能力）：构造包含 TRANSLATION → EMOTION_DETECTION 的串联 taskFlowConfig，注意 emotion 节点的 inputFields 中 content 引用 `translation` 字段（翻译节点的输出）

**步骤二**：执行脚本，创建任务

```bash
python ${SKILL_DIR}/scripts/seederive.py task create --name "翻译+情感分析" --flow-config-file flow.json
```

### 场景三：预览数据和查看结果

**预览输入数据**（Agent 先构造 inputDataSet JSON 文件 `ds.json`）：

```bash
python ${SKILL_DIR}/scripts/seederive.py task preview --input-dataset-file ds.json --limit 10
```

**查看任务输出结果**：

```bash
python ${SKILL_DIR}/scripts/seederive.py task result --task-id 123 --page-size 10
```

如需指定分区：

```bash
python ${SKILL_DIR}/scripts/seederive.py task result --task-id 123 --partition '{"p_date":"2025-01-01"}'
```

### 场景四：任务回填

```bash
python ${SKILL_DIR}/scripts/seederive.py task backfill --bdb-task-id 456 --start-time "2025-01-01 00:00:00" --end-time "2025-01-07 23:59:59"
```

### 场景五：轻量预览

用户说："帮我用这个 CSV 文件试一下情感分析的效果"

轻量预览无需创建完整任务，直接上传文件 + 指定节点类型即可预览结果。

**情感分析预览**：

```bash
python ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --file comments.csv --node-type EMOTION_DETECTION --input-column "评论内容"
```

**标签识别预览**（需要标签库 ID）：

```bash
python ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --file data.csv --node-type TAG_DETECTION --input-column "文本" --tag-base-id 42
```

**自定义分析预览**（需要提示词和输出字段定义）：

```bash
python ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --file data.csv --node-type CUSTOM_APPLICATION --input-column "内容" \
  --prompt "提取关键词和摘要" \
  --output-fields '[{"fieldName":"keywords","fieldType":"String"},{"fieldName":"summary","fieldType":"String"}]'
```

**翻译预览**：

```bash
python ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --file data.csv --node-type TRANSLATION --input-column "content" --target-language "中文"
```

**结果导出为 CSV 文件**：

```bash
python ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --file comments.csv --node-type EMOTION_DETECTION --input-column "评论内容" \
  --response-format csv --output result.csv
```

**直接传原始数据**（无需文件，适合 Agent 调用）：

```bash
# 字符串数组模式：每个元素作为 inputColumn 的值
python ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --raw-data '["这个产品太好了", "质量一般", "很差劲"]' \
  --node-type EMOTION_DETECTION --input-column "评论内容"

# 对象数组模式：支持多列
python ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --raw-data '[{"评论内容":"太好了","用户":"A"},{"评论内容":"一般","用户":"B"}]' \
  --node-type EMOTION_DETECTION --input-column "评论内容"

# 从 JSON 文件读取原始数据
python ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --raw-data-file data.json --node-type EMOTION_DETECTION --input-column "评论内容"
```

支持的参数：

| 参数 | 说明 |
|------|------|
| `--file` | CSV / Excel 文件路径（与 `--raw-data` 二选一） |
| `--raw-data` | 原始数据 JSON 数组（与 `--file` 二选一） |
| `--raw-data-file` | 原始数据 JSON 文件路径（与 `--file` 二选一） |
| `--node-type` | 节点类型（必填） |
| `--input-column` | 作为待处理文本的列名（必填） |
| `--max-rows` | 最大处理行数（默认 10，上限 50） |
| `--tag-base-id` | 标签库 ID（TAG_DETECTION / SUBJECT_DETECTION 需要） |
| `--prompt` | 自定义提示词（CUSTOM_APPLICATION 需要） |
| `--output-fields` | 输出字段 JSON 数组（CUSTOM_APPLICATION 需要） |
| `--target-language` | 翻译目标语言（TRANSLATION 用，默认"中文"） |
| `--response-format` | 响应格式：`json`（默认）或 `csv`（返回文件下载） |
| `--output` | CSV 输出文件路径（默认 `quick_preview_result.csv`） |

## 错误处理

脚本会自动解析返回的 JSON 并输出。如果 HTTP 状态码 >= 400，脚本以非零退出码退出。

| 错误关键词 | 含义 | 处理建议 |
|-----------|------|---------|
| "认证失败" | AK/SK 无效 | 检查 VOLCENGINE_ACCESS_KEY/VOLCENGINE_SECRET_KEY |
| "任务不存在或无权限" | 无权限 | 确认任务 ID 和账号权限 |
| 400 参数错误 | taskFlowConfig 格式不对 | 检查 JSON 中的节点配置 |

## 与其他 SKILL 的关系

- 当需要使用 `TAG_DETECTION` 或 `SUBJECT_DETECTION` 节点时，需先读取 `${SKILL_DIR}/references/tag-base.md` 创建标签库获取 `tagBaseId`
- 当任务效果不佳需要优化时，读取 `${SKILL_DIR}/references/optimize.md` 进行提示词优化
