# 视频翻转 `flip`

对视频做上下（flip_x）或左右（flip_y）镜像翻转，支持同时开启两个方向。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `vid` / `directurl` / `http` |
| `source` | string | ✅ | 视频文件标识 |
| `flip_x` | bool | 可选 | `true` = 上下翻转，默认 `false` |
| `flip_y` | bool | 可选 | `true` = 左右翻转，默认 `false` |

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
# 左右翻转（镜像）
python <SKILL_DIR>/scripts/flip.py \
  '{"type":"vid","source":"v0001","flip_y":true}'

# 同时上下+左右翻转（旋转 180°）
python <SKILL_DIR>/scripts/flip.py \
  '{"type":"vid","source":"v0001","flip_x":true,"flip_y":true}'
```
