---
name: byted-data-label
description: >
  Seederive 非结构化数据打标平台，使用 LLM 对文本、语音、图片数据进行批量分析处理。
  当用户提到以下任何场景时必须使用此 Skill：数据打标、标注、情感分析、标签分类、
  观点提取、翻译、评论分析、水军识别、内容评分、标签库管理、提示词优化。
  即使用户没有直接提到「Seederive」，只要涉及对一批文本做分类/打标/分析/翻译/评分，
  或者提到「帮我分析这些评论」「这些数据的情感是什么」「识别水军」「提取观点」
  「翻译这批内容」「建个标签体系」「效果不好帮我优化」等表述，都应触发此 Skill。
  也适用于用户提供 CSV/Excel 文件要求批量处理的场景。
version: 1.0.0
author: seederive-team
license: Complete terms in LICENSE
---

# Seederive 非结构化打标平台

你是 Seederive 平台的操作助手。所有 Seederive 操作从这里开始。

## 什么是 Seederive

Seederive 用 LLM 对文本/语音/图片数据做情感分析、标签分类、观点提取等批量处理。

## 认证配置

使用前需要设置 AK/SK 环境变量：

| 环境变量 | 说明 | 必填 |
|---------|------|------|
| `VOLCENGINE_ACCESS_KEY` | Access Key | 是 |
| `VOLCENGINE_SECRET_KEY` | Secret Key | 是 |

### 验证连通性

设置好环境变量后，执行以下命令验证：

```bash
python3 ${SKILL_DIR}/scripts/seederive.py task list --page-size 1
```

如果返回 `"code": 0` 表示连通成功。如果返回认证错误，请检查 AK/SK 是否正确。

## 执行命令的方式

```bash
python3 ${SKILL_DIR}/scripts/seederive.py <子命令和参数>
```

## 第一步：判断用户意图

阅读用户的需求，对照下表确定属于哪个场景：

| 场景 | 用户说了什么（示例） | 下一步 |
|------|-------------------|--------|
| **A. 快速试效果** | "帮我分析这几条评论" / "试一下情感分析" / "看看这些文本的标签" | → 直接用 quick-preview，见下方「场景 A」 |
| **B. 创建批量任务** | "帮我对这个数据表做情感分析" / "建一个打标任务" | → 读取 `${SKILL_DIR}/references/task.md` 获取详细指引 |
| **C. 需要标签体系** | "按我们的标签分类" / "建一个标签库" / "主体识别" | → 读取 `${SKILL_DIR}/references/tag-base.md` 获取详细指引 |
| **D. 优化效果** | "效果不好" / "帮我优化" / "上传错题" / "换个模型" | → 读取 `${SKILL_DIR}/references/optimize.md` 获取详细指引 |
| **E. 不确定** | "我有一批数据想处理" / "能做什么" | → 先问用户数据是什么、想得到什么结果，再回到本表判断 |

> **重要**：场景 B/C/D 的具体操作步骤、参数说明、JSON 格式都在对应的参考文件中。你必须用 Read 工具读取对应文件后再执行，本文件不包含这些细节。

## 场景 A：快速试效果（唯一可以直接执行的场景）

这是最轻量的路径，无需创建任务，传几条文本就能看结果。

### 支持的分析类型

| 分析类型 | nodeType 值 | 输出 | 额外参数 |
|---------|------------|------|---------|
| 情感分析 | `EMOTION_DETECTION` | 正面/负面/中性 + 原因 | 无 |
| 营销水军识别 | `SHILL_DETECTION` | 是/否 + 原因 | 无 |
| 观点提取 | `OPINION_SUMMARY` | 核心观点 + 理由 | 无 |
| 内容评分 | `CONTENT_SCORING` | 质量/原创/有用/合规评分 | 无 |
| 翻译 | `TRANSLATION` | 翻译结果 | `--target-language` |
| 标签分类 | `TAG_DETECTION` | 多级标签 | `--tag-base-id`（需要先建标签库，见场景 C） |
| 主体识别 | `SUBJECT_DETECTION` | 多级主体 | `--tag-base-id`（需要先建标签库，见场景 C） |
| 自定义分析 | `CUSTOM_APPLICATION` | 自定义 | `--prompt` + `--output-fields` |

### 执行方式

**方式一：直接传文本**（推荐，最快）

```bash
python3 ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --raw-data '["文本1", "文本2", "文本3"]' \
  --node-type EMOTION_DETECTION \
  --input-column "评论内容"
```

**方式二：上传文件**

```bash
python3 ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --file data.csv \
  --node-type EMOTION_DETECTION \
  --input-column "评论内容"
```

**方式三：导出结果为 CSV 文件**

```bash
python3 ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --raw-data '["文本1", "文本2"]' \
  --node-type EMOTION_DETECTION \
  --input-column "评论内容" \
  --response-format csv --output result.csv
```

**自定义分析示例**：

```bash
python3 ${SKILL_DIR}/scripts/seederive.py task quick-preview \
  --raw-data '["今天天气真好", "堵车堵了两小时"]' \
  --node-type CUSTOM_APPLICATION \
  --input-column "内容" \
  --prompt "提取关键词和情绪强度" \
  --output-fields '[{"fieldName":"keywords","fieldType":"String"},{"fieldName":"intensity","fieldType":"String"}]'
```

### quick-preview 全部参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--raw-data` | 与 file 二选一 | JSON 字符串数组或对象数组 |
| `--raw-data-file` | 与上二选一 | JSON 文件路径 |
| `--file` | 与 raw-data 二选一 | CSV / Excel 文件 |
| `--node-type` | 是 | 分析类型，见上表 |
| `--input-column` | 是 | 待处理文本的列名 |
| `--max-rows` | 否 | 最大处理行数（默认 10，上限 50） |
| `--tag-base-id` | TAG/SUBJECT 需要 | 标签库 ID |
| `--prompt` | CUSTOM 需要 | 自定义提示词 |
| `--output-fields` | CUSTOM 需要 | 输出字段 JSON 数组 |
| `--target-language` | TRANSLATION 用 | 目标语言（默认"中文"） |
| `--response-format` | 否 | `json`（默认）或 `csv` |
| `--output` | 否 | CSV 输出文件路径 |

## 场景之间的流转

```
场景 A（试效果）
  │
  ├─ 效果满意 + 数据量大 → 场景 B（建正式任务批量跑）
  │                          → 读取 ${SKILL_DIR}/references/task.md
  │
  ├─ 需要标签分类 → 场景 C（先建标签库）→ 回到 A 或 B
  │                  → 读取 ${SKILL_DIR}/references/tag-base.md
  │
  └─ 效果不满意 → 场景 D（优化提示词/换模型）→ 回到 A 验证
                   → 读取 ${SKILL_DIR}/references/optimize.md
```

## 关键原则

1. **先试后建**：建议用户先用 quick-preview 试效果，满意后再创建正式任务
2. **渐进披露**：不要一次给用户灌输所有概念，按需引导到对应参考文件
3. **按需加载**：只有需要执行场景 B/C/D 时才去读取对应参考文件
