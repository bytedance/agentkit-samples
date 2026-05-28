---
name: "byted-ind-ecom-prompt-to-video"
description: "使用 Seedance 2.0 根据提示词与参考素材生成视频。用户要把文本/参考图/参考视频变成视频时使用。"
---

# Seedance 2.0 文生视频/参考生成视频（byted-ind-ecom-prompt-to-video）

本 skill 用于调用火山方舟上的 Seedance 2.0 视频生成能力，支持：

- 文生视频（仅 prompt）
- 图生视频（首帧/首尾帧）
- 多参考生成（参考图片最多 9 张、参考视频最多 3 个）

## 使用方式

在 skill 目录下执行 `scripts/generate.py`。

### 参数

- `--prompt`：视频文本提示词
- `--first_frame`：首帧图片（URL 或本地路径）
- `--last_frame`：尾帧图片（URL 或本地路径）
- `--reference_images`：参考图片（URL 或本地路径，最多 9 张）
- `--reference_videos`：参考视频（URL 或本地路径，最多 3 个）
- `--resolution`：分辨率（如 `720p`、`1080p`）
- `--ratio`：画幅（如 `16:9`、`9:16`、`1:1`、`adaptive`）
- `--duration`：时长（秒）

### 示例

**文生视频：**

```bash
python3 scripts/generate.py --prompt "A cute cat playing with a ball of yarn in a sunny room" --ratio 16:9 --duration 5
```

**图生视频（首帧）：**

```bash
python3 scripts/generate.py --prompt "The cat jumps" --first_frame "/path/to/cat.jpg" --ratio 16:9 --duration 5
```

**多参考图片：**

```bash
python3 scripts/generate.py --prompt "A scenic landscape" --reference_images "/path/to/img1.jpg" "/path/to/img2.jpg" --ratio 16:9
```

## 本地素材处理逻辑（重要）

- **本地图片**：
  - 在“可用 TOS”时会先上传到 TOS，再使用公网 URL 参与生成。
  - 若无可用 TOS，则自动转为 `data:<mime>;base64,...` 形式提交。
- **本地参考视频**：建议直接提供公网 URL；如提供本地视频，需要可用 TOS 才能先上传转为公网 URL。
- **视频输出**：
  - 若可用 TOS，会尝试将生成视频转存到 TOS 并输出 TOS URL。
  - 否则直接返回模型原始视频 URL（通常有时效，建议尽快下载或转存）。

## 环境变量

最低必需：

- `ARK_API_KEY`
- `SEEDANCE_EP_ID`
- `ARK_BASE_URL`（可选，默认 `https://ark.cn-beijing.volces.com/api/v3`）

如需启用 TOS 上传/转存：

- `VOLC_ACCESS_KEY`
- `VOLC_SECRET_KEY`
- `TOS_ENDPOINT`
- `TOS_REGION`
- `TOS_BUCKET`
- `TOS_UPLOAD_ENABLED`（可选，默认 `true`）

## 输出

脚本会轮询任务直到结束，并在终端输出：

- `Final Video URL: <url>`
