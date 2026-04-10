# 人像抠图 `portrait_matting`

自动识别视频中的主要人像并进行高精度抠图，生成带有透明通道的视频素材。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 输入类型：`Vid` 或 `DirectUrl` |
| `video` | string | ✅ | 当 type 为 `Vid` 时为视频 ID；当 type 为 `DirectUrl` 时为 FileName |
| `output_format` | string | 可选 | 输出视频封装格式，默认 `WEBM`，支持 `MOV` / `WEBM` |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "Success",
  "VideoUrls": [
    {
      "FileId": "xxx",
      "DirectUrl": "path/to/output.webm",
      "Url": "https://cdn.example.com/output.webm"
    }
  ]
}
```

## 示例

```bash
# 人像抠图，输出 WEBM 格式
python <SKILL_DIR>/scripts/portrait_matting.py \
  '{"type":"Vid","video":"v0310abc"}'

# 人像抠图，输出 MOV 格式
python <SKILL_DIR>/scripts/portrait_matting.py \
  '{"type":"Vid","video":"v0310abc","output_format":"MOV"}'
```
