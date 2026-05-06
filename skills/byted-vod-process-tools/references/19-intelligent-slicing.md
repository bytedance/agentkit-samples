# 智能场景切分 `intelligent_slicing`

基于画面转场和镜头变化，智能将长视频切分为多个逻辑相关的短片段。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 输入类型：`Vid` 或 `DirectUrl` |
| `video` | string | ✅ | 当 type 为 `Vid` 时为视频 ID；当 type 为 `DirectUrl` 时为 FileName |
| `min_duration` | float | 可选 | 最小片段时长（秒），默认 `2.0` |
| `threshold` | float | 可选 | 场景切分灵敏度阈值，默认 `15.0`（值越小切分越多） |

## 返回值

任务自动轮询至终态，成功时返回片段列表（含各片段的起止时间和产物信息）：

```json
{
  "Status": "Success",
  "VideoUrls": [
    {
      "DirectUrl": "path/to/segment_001.mp4",
      "Url": "https://cdn.example.com/segment_001.mp4"
    }
  ]
}
```

## 示例

```bash
# 对视频进行智能场景切分
python <SKILL_DIR>/scripts/intelligent_slicing.py \
  '{"type":"Vid","video":"v0310abc"}'

# 自定义切分参数
python <SKILL_DIR>/scripts/intelligent_slicing.py \
  '{"type":"Vid","video":"v0310abc","min_duration":5.0,"threshold":10.0}'
```
