# 画中画/水印叠加 `add_sub_video`

在主视频上叠加子视频或动态水印，支持自定义位置、尺寸和出现时间段。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video` | dict | ✅ | 主视频：`{"type":"vid","source":"v0001"}` |
| `sub_video` | dict | ✅ | 子视频/水印：`{"type":"vid","source":"v0002"}` |
| `sub_options` | dict | 可选 | 叠加选项，见下方子字段 |

### sub_options 子字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `height` | string | 水印高度，支持百分比（如 `"30%"`）或像素（如 `"100"`） |
| `width` | string | 水印宽度，支持百分比或像素 |
| `pos_x` | string | 水印 X 轴位置（像素，以视频左上角为原点） |
| `pos_y` | string | 水印 Y 轴位置（像素，以视频左上角为原点） |
| `start_time` | float | 水印出现时间（秒） |
| `end_time` | float | 水印消失时间（秒） |

> **注意**：若 `end_time` 超过原视频时长，输出视频将以 `end_time` 为准，超出部分以黑屏延续。

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "success",
  "OutputJson": {
    "vid": "v0310xxx",
    "url": "https://cdn.example.com/output.mp4"
  }
}
```

## 示例

```bash
# 在视频右下角叠加 logo（宽20%，从第5秒到第15秒）
python <SKILL_DIR>/scripts/add_sub_video.py \
  '{"video":{"type":"vid","source":"v0001"},
    "sub_video":{"type":"http","source":"https://example.com/logo.mp4"},
    "sub_options":{"width":"20%","pos_x":"80%","pos_y":"80%","start_time":5,"end_time":15}}'

# 全程画中画（左上角，固定大小300px宽）
python <SKILL_DIR>/scripts/add_sub_video.py \
  '{"video":{"type":"vid","source":"v0001"},
    "sub_video":{"type":"vid","source":"v0002"},
    "sub_options":{"width":"300","pos_x":"20","pos_y":"20"}}'
```
