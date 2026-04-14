---
name: byted-las-image-resample
version: "1.0.1"
description: "Downsamples, resizes, and compresses images using Volcengine LAS with multiple interpolation methods (lanczos, bilinear, nearest). Image resizing, image scaling, and image compression — reduces image resolution, dimensions, and file size. Changes and adjusts DPI settings. Converts between image formats including JPEG, PNG, TIFF. Generates thumbnails and optimizes images for web or print. Supports batch resize for photos and images up to 100MB and 225 megapixels. Note: downscale only, does not upscale. Use this skill when the user wants to resize or downscale images, compress images to reduce file size, change image format (JPEG/PNG/TIFF), adjust image DPI, generate image thumbnails, optimize images for web/print, or batch process multiple images."
---

# LAS 图像重采样（`las_image_resample`）

对图像进行降采样缩放（**仅缩小，不支持放大**），支持修改 DPI、JPG/PNG 互转。

## 设计模式

本 skill 主要采用：
- **Tool Wrapper**：封装 `lasutil` CLI 调用
- **Pipeline**：包含 Step 0 → Step N 的顺序工作流

## 核心 API 与配置

- **算子 ID**: `las_image_resample`
- **API**: 同步（`process`）
- **环境变量**: `LAS_API_KEY` (必填)

> 详细参数与接口定义见 [references/api.md](references/api.md)。

## Gotchas

- **仅支持降采样**：`target_size` 不得超过原图尺寸，本算子不支持放大。
- **输入限制**：仅支持 JPEG/PNG/TIFF，≤100MB，像素总数 ≤225,000,000。
- **密钥安全**：若聊天框屏蔽密钥，让用户在当前目录创建 `env.sh` 并写入 `export LAS_API_KEY="..."`，SDK 会自动读取。
- **免责声明**：最终回复结果时必须包含："本方式的计费均为预估计费，与实际费用有差距，实际费用以运行后火山产生的账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。"，且禁止使用"实际费用"字眼描述预估价。


## 工作流（严格按步骤执行）

复制此清单并跟踪进度：

```text
执行进度：
- [ ] Step 0: 前置检查
- [ ] Step 1: 初始化与准备
- [ ] Step 2: 预估价格
- [ ] Step 3: 执行/提交任务
- [ ] Step 4: 结果呈现
```

### Step 0: 前置检查（⚠️ 必须在第一轮对话中完成）

在接受用户的任务后，**不要立即开始执行**，必须首先进行以下环境检查：
1. **检查 `LAS_API_KEY` 与 `LAS_REGION`**：确认环境变量或 `.env` 中是否已配置。
   - 若无，必须立即向用户索要（提示：`LAS_REGION` 常见为 `cn-beijing`）。
   - **注意**：`LAS_REGION` 必须与您的 API Key 及 TOS Bucket 所在的地域完全一致。如果用户中途切换了 Region，必须提醒用户其 TOS Bucket 也需对应更换，否则会导致权限异常或上传失败。
2. **检查输入路径**：
   - 如果用户要求处理的是**本地文件**，则需要先通过 File API 上传至 TOS（只需 `LAS_API_KEY`，无需额外 TOS 凭证）。
   - 如果算子的**输出结果**存放在 TOS 上，且用户需要下载回本地，则需要 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY`。对于**仅需要上传输入文件**的场景，TOS 凭证**不再必须**。
3. **确认无误后**：才能进入下一步。

### Step 1: 初始化与准备

**环境初始化（Agent 必做）**：

```bash
# 执行统一的环境初始化与更新脚本（会自动创建/激活虚拟环境，并检查更新）
source "$(dirname "$0")/scripts/env_init.sh" las_image_resample
workdir=$LAS_WORKDIR
```

> 如果网络问题导致更新失败，脚本会跳过检查，使用本地已安装的 SDK 继续执行。

- **处理本地文件时**：先本地检查格式和尺寸，预估价格，用户确认后再上传：
  ```bash
  # 提前检查图片格式（避免参数错误）
  ./scripts/check_format.sh <local_path>
  # 本地使用 identify 获取尺寸（无需上传即可预估价格）
  identify -format "%wx%h" <local_path>
  ```
  计算预估价格并等待用户确认后，再执行上传：
  ```bash
  # 用户确认后，上传到 TOS
  lasutil file-upload <local_path>
  ```
  上传成功后返回 JSON，取其中的 `presigned_url`（HTTPS 预签名下载链接，24 小时有效）传给算子作为输入 URL。

### Step 2: 预估价格（⚠️ 必须获得用户确认）

1. 读取 [references/prices.md](references/prices.md) 获取最新计费标准。
2. **优先本地获取尺寸**（避免不必要上传）：
   ```bash
   # 使用 ImageMagick identify 本地获取
   identify -format "%wx%h" <local_path>
   ```
   如果 identify 失败，再使用 lasutil 远程获取：
   ```bash
   lasutil image-info <input_image_url>
   ```
3. 根据分辨率档位和单价计算总价，**将计费单价与预估总价一并告知用户并强制暂停执行**，明确等待用户回复确认。在用户明确回复"继续"、"确认"等同意指令前，**绝对禁止**进入下一步（执行/提交任务）。提示：预估仅供参考，实际以火山账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。

### Step 3: 执行重采样 (Process)

构造基础 `data.json`：
```json
{
  "image_src_type": "image_url",
  "image": "<presigned_url>",
  "tos_dir": "tos://bucket/output/",
  "target_size": [1024, 1024],
  "method": "lanczos"
}
```
*注：本地文件通过 `lasutil file-upload` 上传后，使用 `presigned_url` 作为 `image` 字段值，`image_src_type` 设为 `"image_url"`。若直接使用 TOS 路径，设置 `"image_src_type": "image_tos"`。*

执行命令：
```bash
data=$(cat "$workdir/data.json")
lasutil process las_image_resample "$data" > "$workdir/result.json"
```

### 结果呈现

使用脚本自动生成结果展示（自动包含计费声明）：
```bash
./scripts/generate_result.md.sh $workdir/result.json <estimated_price>
```

生成内容包含：
- 任务信息卡片
- 输入/输出尺寸统计
- **自动包含计费声明** ✅

手动提取方式：
```bash
jq -r '"输出路径：" + .data.image_path' $workdir/result.json
```
## 审查标准

执行完成后，Agent 应自检：
1. 环境变量是否正确配置
2. 输入文件是否成功上传
3. 输出结果是否正确呈现给用户
4. 计费声明是否包含
