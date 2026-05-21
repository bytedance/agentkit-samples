---
name: byted-las-pdf-parse-doubao
version: "0.3.8"
description: "PDF 解析（Doubao）：将 PDF/扫描件转成结构化 Markdown/文本，支持表格与多栏版式。当用户要从 PDF 提取文字/表格或做 OCR 时触发。"
metadata:
  category: productivity
  lasCliVersion: "0.3.8"
  requires:
    bins:
      - las-cli
  cliHelp: "las-cli operators help las_pdf_parse_doubao"
  operatorId: "las_pdf_parse_doubao"
  openclaw:
    identity:
      - type: tip
        env:
          - VE_TIP_TOKEN
        required: true
---

# PDF 解析 (`las_pdf_parse_doubao`)

当用户希望从 PDF/图片中提取文本、表格、段落等结构化内容时使用本 Skill。

## 注意事项（⚠️ 必须遵守）
- 千万不要让用户输入 AccessKey 和 SecretKey。
- 下载文件只能使用 `las-cli tos download` 命令（兼容 tos 和非 tos 资源）。
- `las-cli operators call` 和 `las-cli price` 命令的输出结果非常重要，必须完整返回给用户。

## 工作流（严格按步骤执行）

复制此清单并跟踪进度：

```text
执行进度：
- [ ] Step 0: 前置检查
- [ ] Step 1: 初始化与准备
- [ ] Step 2: 预估价格
- [ ] Step 3: 执行任务并呈现结果
- [ ] Step 4: 失败排查
```

### Step 0: 前置检查

版本检查（必须）：请执行 las-cli install 0.3.8。若 las-cli 命令不存在，则执行 npm i -g "@volcengine/las-cli@0.3.8"
- **新版本提醒**：请执行 `npm info @volcengine/las-cli version` 查看当前可用的最新 Skill 版本（`las-cli` 与 Skill 版本一一对应）。若返回版本高于本 Skill 标注版本，请先提示用户升级当前 Skill。升级方式：请用户发送自然语言指令 `帮我安装byted-las-pdf-parse-doubao技能`，等待自动完成安装即可。
- **认证检查**：优先使用运行时自动注入的平台身份；若当前环境未自动注入，再运行 `las-cli config show` 确认旧版凭证 `las.apiKey` 和 `volcengine.region` 已配置。

### Step 1: 初始化与准备

- **上传资源**: 若输入为本地文件，先上传到 TOS。
  ```bash
  las-cli tos upload ./document.pdf
  # 假设返回 "tos_url": "tos://my-bucket/inputs/xxx.pdf"
  ```

- **准备参数**: 创建 `params.json`。
  ```json
  {
    "url": "tos://my-bucket/inputs/xxx.pdf",
    "output_tos_path": "tos://my-bucket/outputs/pdf_parse/",
    "parse_mode": "normal",
    "start_page": 1,
    "num_pages": 200,
    "full_result": true,
    "aspect_ratio_threshold": 0.334
  }
  ```

说明：
- `output_tos_path`：可选。填写后会把解析结果产物写到该目录（推荐），典型结构：`{output_tos_path}/{task_id}/result.md`、`result_preview.md`、`images/`、`detail.json`。
- `parse_mode`：`normal`（默认）/ `detail`（更细，通常更贵）。
- `start_page` / `num_pages`：仅 PDF 有效；`num_pages` 默认 200，最大 400。
- `full_result`：`true` 返回完整解析结果；`false` 仅返回产物信息（结果较大时建议关掉，并配合 `output_tos_path`）。

### Step 2: 预估价格（⚠️ 必须获得用户确认）

`las-cli price` 命令的输出结果非常重要，不要做任何精简、修改或摘要处理。

- **算价**: 必须完整返回以下命令输出的结果（markdown 格式）
  ```bash
  las-cli price las_pdf_parse_doubao \
    --params-file ./params.json \
    --format markdown
  ```
- **用户确认**: 输出预估价格后，**必须等待用户确认**。

### Step 3: 执行任务并呈现结果（⚠️ 直接输出命令执行结果，不要精简）

`las-cli operators call` 命令的输出结果非常重要，不要做任何精简、修改或摘要处理。

- **执行**: 必须完整返回以下命令输出的结果（markdown 格式）
  ```bash
  las-cli operators call las_pdf_parse_doubao \
    --params-file ./params.json \
    --format markdown \
    --out ./result.md
  ```

### Step 4: 失败排查

- **检查任务状态**: `las-cli task status <task_id>`。
- **检查输入**: 确认 `url` 可访问；若是 `tos://`，先用 `las-cli tos check "<tos_url>"` 验证。
- **检查输出目录**: 若设置了 `output_tos_path`，确保是 `tos://bucket/prefix/` 目录形式。
- **检查配置**: `las-cli config show`。
