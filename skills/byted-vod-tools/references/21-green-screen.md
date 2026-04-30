# 绿幕抠图 `green_screen`

对绿幕背景视频进行专业级抠图，常用于后期制作与特效合成。

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
# 绿幕抠图，输出 WEBM 格式
python <SKILL_DIR>/scripts/green_screen.py \
  '{"type":"Vid","video":"v0310abc"}'

# 绿幕抠图，输出 MOV 格式
python <SKILL_DIR>/scripts/green_screen.py \
  '{"type":"Vid","video":"v0310abc","output_format":"MOV"}'
```
