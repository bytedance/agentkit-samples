---
name: byted-las-vlm-video
version: "0.3.8"
description: "视频多模态理解：对视频生成描述/摘要/标签，并支持基于视频内容问答。当用户要理解视频内容、生成描述或对视频提问时触发。"
metadata:
  category: productivity
  lasCliVersion: "0.3.8"
  requires:
    bins:
      - las-cli
  cliHelp: "las-cli operators help las_vlm_video"
  operatorId: "las_vlm_video"
  openclaw:
    identity:
      - type: tip
        env:
          - VE_TIP_TOKEN
        required: true
---

# VLM 视频理解 (`las_vlm_video`)

当用户希望对视频内容进行理解、摘要、打标签或问答时使用本 Skill。

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

- **版本检查（必须）**：请执行 las-cli install 0.3.8。若 las-cli 命令不存在，则执行 npm i -g "@volcengine/las-cli@0.3.8"
- **新版本提醒**：请执行 `npm info @volcengine/las-cli version` 查看当前可用的最新 Skill 版本（`las-cli` 与 Skill 版本一一对应）。若返回版本高于本 Skill 标注版本，请先提示用户升级当前 Skill。升级方式：请用户发送自然语言指令 `帮我安装byted-las-vlm-video技能`，等待自动完成安装即可。
- **认证检查**：优先使用运行时自动注入的平台身份；若当前环境未自动注入，再运行 `las-cli config show` 确认旧版凭证 `las.apiKey` 和 `volcengine.region` 已配置。
- **资源检查**: `video_url` 需为可访问的 HTTP(S) 地址。若输入为 `tos://`，请先转成预签名 URL（`las-cli tos presign get ...`），或直接使用 `las-cli tos upload` 输出中的 `presigned_url`。

### Step 1: 初始化与准备

- **上传资源**: 若输入为本地视频，先上传到 TOS。
- **准备参数**: 创建 `params.json`。
  ```json
  {
    "video_url": "tos://my-bucket/inputs/xxx.mp4",
    "text": "视频里有什么？"
  }
  ```

### Step 2: 预估价格（⚠️ 必须获得用户确认）

`las-cli price` 命令的输出结果非常重要，不要做任何精简、修改或摘要处理。

- **算价**: 无论是否成功计算出价格，必须完整返回以下命令输出的结果（markdown 格式）
  ```bash
  las-cli price las_vlm_video \
    --params-file ./params.json \
    --format markdown
  ```
- **用户确认**: 输出预估价格后，**必须等待用户确认**。

### Step 3: 执行任务并呈现结果（⚠️ 直接输出命令执行结果，不要精简）

`las-cli operators call` 命令的输出结果非常重要，不要做任何精简、修改或摘要处理。

- **执行**: 必须完整返回以下命令输出的结果（markdown 格式）
  ```bash
  las-cli operators call las_vlm_video \
    --params-file ./params.json \
    --format markdown \
    --out ./result.md
  ```

### Step 4: 失败排查

- **检查输入**: 确认 `video_url` 可访问。
- **检查配置**: `las-cli config show`。
- **重试**: 直接重新执行 `operators call` 命令并观察错误。
