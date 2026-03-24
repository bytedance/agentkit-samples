---
name: byted-las-image-resample
description: |
  Image resampling operator for downsampling images.
  Use this skill when user needs to:
  - Resize/downsample images to target size
  - Change image DPI settings
  - Convert between JPG/PNG formats
  Supports 4 interpolation methods: nearest, bilinear, bicubic, lanczos.
  Supports input from URL, TOS, base64, or binary.
  Requires LAS_API_KEY for authentication.
---

# LAS-IMAGE-RESAMPLE (las_image_resample)

本 Skill 用于调用 LAS 图像重采样算子，对输入图像进行尺寸重采样（仅支持降采样），并将结果保存到用户指定的 TOS 目录。

- `POST https://operator.las.cn-beijing.volces.com/api/v1/process` 同步处理

## 快速开始

在本 skill 目录执行：

```bash
python3 scripts/skill.py --help
```

### 执行图像重采样

```bash
# 从 URL 输入
python3 scripts/skill.py process \
  --image "https://example.com/sample.jpg" \
  --tos-dir "tos://bucket/output/" \
  --target-size 1024 1024 \
  --method lanczos

# 从 TOS 输入
python3 scripts/skill.py process \
  --image "tos://bucket/input/sample.jpg" \
  --tos-dir "tos://bucket/output/" \
  --target-size 800 600
```

## 参数说明

- `--image`: 输入图像（URL 或 TOS 路径）
- `--tos-dir`: 输出 TOS 目录
- `--target-size`: 目标尺寸 [width, height]，默认 [200, 200]
- `--target-dpi`: 目标 DPI [x, y]，默认 [72, 72]
- `--method`: 插值方法，支持 nearest/bilinear/bicubic/lanczos，默认 lanczos
- `--image-suffix`: 输出格式，.jpg 或 .png，默认 .jpg

## 插值方法说明

- `nearest`: 速度最快，适合像素风格图像
- `bilinear`: 速度与质量平衡
- `bicubic`: 更平滑的高质量缩放
- `lanczos`: 抗锯齿效果更好，适合照片（推荐）

## 常见问题

- 仅支持降采样：target_size 的宽高不得超过原图
- 输入图像格式支持：JPEG/PNG/TIFF
- 输入图像大小限制：文件大小不超过 100MB，像素总数不超过 225,000,000
- 确保 TOS 路径有读写权限
- API Key 需通过环境变量 `LAS_API_KEY` 或 `env.sh` 配置
