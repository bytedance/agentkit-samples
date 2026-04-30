# 提取音轨 `extract_audio`

从视频中分离并导出独立音频文件。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `vid` / `directurl` / `http` |
| `source` | string | ✅ | 视频文件标识 |
| `format` | string | 可选 | 输出音频格式：`m4a`（默认）/ `mp3` |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "success",
  "OutputJson": {
    "vid": "v0310xxx",
    "url": "https://cdn.example.com/output.m4a"
  }
}
```

## 示例

```bash
# 提取音轨为 mp3
python <SKILL_DIR>/scripts/extract_audio.py \
  '{"type":"vid","source":"v0001","format":"mp3"}'
```
