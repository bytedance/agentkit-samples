# 添加内嵌字幕 `add_subtitle`

将外部字幕文件（如 SRT 格式）或字幕文本列表烧录到视频画面中，生成带有内嵌字幕的新视频。支持自定义字体、字幕样式和字幕位置。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video` | dict | ✅ | 视频信息，见下方子字段 |
| `subtitle_url` | string | 二选一 | 字幕文件 URL / FileName，支持 SRT、VTT、ASS 等格式。优先级高于 `text_list` |
| `text_list` | list | 二选一 | 字幕文本列表，见下方子字段 |
| `subtitle_config` | dict | 可选 | 字幕样式配置，见下方子字段 |

### video 子字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | `vid` / `directurl` / `http` |
| `source` | string | 视频文件信息 |

### text_list 子字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 字幕文本 |
| `start_time` | float | 文本开始时间（秒） |
| `end_time` | float | 文本结束时间（秒） |

### subtitle_config 子字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `font_size` | int | 字体大小（像素），默认 200 |
| `font_type` | string | 字体 ID，默认 `SY_Black`（思源黑体） |
| `font_color` | string | 字体颜色，RGBA 格式，默认 `#FFFFFFFF`（白色） |
| `background_color` | string | 背景颜色，RGBA 格式，默认 `#00000000`（透明） |
| `background_border_width` | number | 背景边框宽度（像素） |
| `border_color` | string | 描边颜色，RGBA 格式，默认 `#00000000` |
| `border_width` | int | 描边宽度（像素），默认 0 |
| `font_pos_config` | dict | 位置配置：`width`、`height`、`pos_x`、`pos_y`（支持百分比或像素） |

### 可用字体 ID

| 字体名称 | 字体 ID |
|----------|---------|
| 思源黑体 | `SY_Black` |
| 阿里巴巴普惠体 | `ALi_PuHui` |
| 庞门正道标题体 | `PM_ZhengDao` |
| 站酷高端黑 | `1187221` |
| 站酷酷黑体 | `1187219` |
| 站酷快乐体 | `1187217` |
| 站酷文艺体 | `1187213` |
| 站酷小薇 LOGO 体 | `1187211` |
| 站酷仓耳渔阳体 | `1187223` |
| 站酷意大利体 | `1187225`（不支持中文） |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "success",
  "OutputJson": {
    "vid": "v0310xxx",
    "url": "https://cdn.example.com/output.mp4",
    "duration": 60.0
  }
}
```

## 示例

```bash
# 通过字幕文件添加字幕
python <SKILL_DIR>/scripts/add_subtitle.py \
  '{"video":{"type":"vid","source":"v0001"},"subtitle_url":"directurl://subtitles.srt"}'

# 通过文本列表添加字幕
python <SKILL_DIR>/scripts/add_subtitle.py \
  '{"video":{"type":"vid","source":"v0001"},"text_list":[{"text":"你好世界","start_time":0,"end_time":3},{"text":"欢迎观看","start_time":3,"end_time":6}]}'

# 自定义字幕样式
python <SKILL_DIR>/scripts/add_subtitle.py @params.json
```
