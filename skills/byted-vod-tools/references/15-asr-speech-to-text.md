# 语音转字幕 (ASR) `asr_speech_to_text`

使用 ASR 技术将视频中的语音内容转换为带时间戳的字幕信息。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 输入类型：`Vid` 或 `DirectUrl` |
| `video` | string | ✅ | 当 type 为 `Vid` 时为视频 ID；当 type 为 `DirectUrl` 时为 FileName |
| `language` | string | 可选 | 识别提示语言，不传则自动探测。支持取值见下方 |

### language 可选值

| 取值 | 语言 |
|------|------|
| `cmn-Hans-CN` | 简体中文 |
| `cmn-Hant-CN` | 繁体中文 |
| `eng-US` | 英语 |
| `jpn-JP` | 日语 |
| `kor-KR` | 韩语 |
| `rus-RU` | 俄语 |
| `fra-FR` | 法语 |
| `por-PT` | 葡萄牙语 |
| `spa-ES` | 西班牙语 |
| `vie-VN` | 越南语 |
| `mya-MM` | 缅甸语 |
| `nld-NL` | 荷兰语 |
| `deu-DE` | 德语 |
| `ind-ID` | 印尼语 |
| `ita-IT` | 意大利语 |
| `pol-PL` | 波兰语 |
| `tha-TH` | 泰语 |
| `tur-TR` | 土耳其语 |
| `ara-SA` | 阿拉伯语 |
| `msa-MY` | 马来语 |
| `ron-RO` | 罗马尼亚语 |
| `fil-PH` | 菲律宾语 |
| `hin-IN` | 印地语 |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "Success",
  "Texts": [
    {
      "Start": 0.5,
      "End": 3.2,
      "Text": "大家好，欢迎收看",
      "Speaker": "speaker_0"
    }
  ]
}
```

## 示例

```bash
# 对视频进行中文语音识别
python <SKILL_DIR>/scripts/asr_speech_to_text.py \
  '{"type":"Vid","video":"v0310abc","language":"cmn-Hans-CN"}'

# 自动检测语言
python <SKILL_DIR>/scripts/asr_speech_to_text.py \
  '{"type":"Vid","video":"v0310abc"}'

# DirectUrl 模式
python <SKILL_DIR>/scripts/asr_speech_to_text.py \
  '{"type":"DirectUrl","video":"path/to/file.mp4"}'
```
