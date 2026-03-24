---
name: byted-las-pdf-parse-doubao
description: |
  Parse PDF documents to extract Markdown or structured content.
  Use this skill when user needs to:
  - Parse/extract content from PDF files
  - Convert PDF to Markdown format
  - Extract structured data from PDF documents
  Requires LAS_API_KEY for authentication.
---

# LAS-AI PDF 解析（las_pdf_parse_doubao）

## 快速开始

在本 skill 目录执行：

```bash
python3 scripts/skill.py --help
```

### 提交并等待

```bash
python3 scripts/skill.py submit \
  --url "https://las-ai-cn-beijing-baseline.tos-cn-beijing.volces.com/operator_cards_serving/public/baseline/las_pdf_parse_doubao/v1/pdf-sample.pdf" \
  --parse-mode normal \
  --format markdown
```

`parse_mode` 说明：

- `normal`：默认开启，不进行深度思考；速度更快，适用于绝大多数文档场景。
- `detail`：开启深度思考；分析更细致，但耗时更长。

### 仅提交（返回 task_id）

```bash
python3 scripts/skill.py submit --url "<pdf_url>" --no-wait
```

### 轮询 / 等待

```bash
python3 scripts/skill.py poll <task_id>
python3 scripts/skill.py wait <task_id> --timeout 1800 --format markdown
```

## 配置

- 鉴权：环境变量 `LAS_API_KEY`（推荐）或在当前目录提供 `env.sh`
  - 默认使用 `Authorization: Bearer <LAS_API_KEY>`
  - 若控制台示例为 `X-Api-Key`，可用 `--auth x-api-key` 或设置 `LAS_API_KEY_AUTH=x-api-key`
- Region：`--region cn-beijing|cn-shanghai` 或环境变量 `LAS_REGION`

## 参数与返回字段

详见 `references/api.md`。
