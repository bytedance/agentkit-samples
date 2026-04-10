# 画面文字提取 (OCR) `ocr_text_extract`

使用 OCR 技术智能提取视频画面中嵌入的文字信息。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 输入类型：`Vid` 或 `DirectUrl` |
| `video` | string | ✅ | 当 type 为 `Vid` 时为视频 ID；当 type 为 `DirectUrl` 时为 FileName |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "Success",
  "Texts": [
    {
      "Start": 1.0,
      "End": 5.5,
      "Text": "画面中的文字内容"
    }
  ]
}
```

## 示例

```bash
# 提取视频画面中的文字
python <SKILL_DIR>/scripts/ocr_text_extract.py \
  '{"type":"Vid","video":"v0310abc"}'

# DirectUrl 模式
python <SKILL_DIR>/scripts/ocr_text_extract.py \
  '{"type":"DirectUrl","video":"path/to/file.mp4"}'
```
