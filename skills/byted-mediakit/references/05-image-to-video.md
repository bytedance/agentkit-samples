# 图片转视频 `image_to_video`

将多张图片串联生成视频，支持每张图片设置独立时长、动画效果和转场。

## 参数

### 顶层参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `images` | list[dict] | ✅ | 图片列表，见下方子字段说明 |
| `transitions` | list[string] | 可选 | 转场效果 ID 列表（与图片数 -1 对应，不足时循环复用） |

### images 子字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `vid` / `directurl` / `http` |
| `source` | string | ✅ | 图片文件标识 |
| `duration` | float | 可选 | 该图片展示时长（秒），默认 3，支持 2 位小数 |
| `animation_type` | string | 可选 | 动画类型：`move_up` / `move_down` / `move_left` / `move_right` / `zoom_in` / `zoom_out` |
| `animation_in` | float | 可选 | 动画开始时间（秒），默认从图片开始 |
| `animation_out` | float | 可选 | 动画结束时间（秒），默认随图片结束 |

### 可用转场效果

参见 [01-stitching.md](./01-stitching.md) 中的转场效果列表。

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
# 3 张图片转视频，第 2 张放大动画，图片间加「泛开」转场
python <SKILL_DIR>/scripts/image_to_video.py \
  '{"images":[
    {"type":"http","source":"https://example.com/1.jpg","duration":3},
    {"type":"http","source":"https://example.com/2.jpg","duration":4,"animation_type":"zoom_in"},
    {"type":"http","source":"https://example.com/3.jpg","duration":3}
  ],"transitions":["1182358"]}'
```
