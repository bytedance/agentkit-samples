# byted-arkclaw-local-batch-asr 输出说明

## 单文件输出

每个输入文件都会生成一个独立目录：

```text
output/<run_name>/files/<file_stem>/
├── transcript.<format>
└── meta.json
```

## `meta.json` 字段

```json
{
  "source": "/abs/path/to/audio.mp3",
  "status": "completed",
  "format": "txt",
  "output_path": "/abs/path/to/transcript.txt",
  "speaker_count": 1,
  "segments": 1,
  "error": null
}
```

## 批量汇总输出

### `summary.json`

- 包含本次运行的配置、成功/失败数、每个文件的处理结果

### `summary.csv`

字段：
- `source`
- `status`
- `format`
- `output_path`
- `speaker_count`
- `segments`
- `error`

## 推荐格式

- `txt`：最适合 CRM 入库前人工查看
- `json`：最适合后续结构化处理
- `srt`：适合视频字幕
- `md`：适合形成面试/通话纪要
