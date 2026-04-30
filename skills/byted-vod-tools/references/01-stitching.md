# 视频/音频拼接 `stitching`

将多段视频或音频按顺序拼接为一个文件，视频支持转场特效。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `video` 或 `audio` |
| `videos` | list[string] | 视频时必填 | 视频列表，每项格式见下方「文件引用格式」 |
| `audios` | list[string] | 音频时必填 | 音频列表 |
| `transitions` | list[string] | 可选 | 转场效果 ID 列表（仅 video 支持，audio 忽略） |

### 文件引用格式

- `vid://v0310xxx` — VOD 空间 Vid
- `directurl://test.mp4` — VOD 存储 FileName
- `https://example.com/a.mp4` — 公网 URL（直接传字符串）

转场数量少于视频段数 -1 时，自动循环复用。

## 可用转场效果

| 效果名 | ID |
|--------|-----|
| 交替出场 | 1182359 |
| 旋转放大 | 1182360 |
| 泛开 | 1182358 |
| 六角形 | 1182365 |
| 故障转换 | 1182367 |
| 飞眼 | 1182368 |
| 梦幻放大 | 1182369 |
| 开门展现 | 1182370 |
| 立方转换 | 1182373 |
| 透镜变换 | 1182374 |
| 晚霞转场 | 1182375 |
| 圆形交替 | 1182378 |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "success",
  "OutputJson": {
    "vid": "v0310xxx",
    "url": "https://cdn.example.com/output.mp4",
    "resolution": "1920x1080",
    "duration": 12.5
  }
}
```

失败时返回 `"Status": "failed_run"`；轮询超时返回 `error` + `resume_hint`。

## 示例

```bash
# 拼接两段视频，加「交替出场」转场
python <SKILL_DIR>/scripts/stitching.py \
  '{"type":"video","videos":["vid://v0001","vid://v0002"],"transitions":["1182359"]}'

# 拼接音频（不支持转场）
python <SKILL_DIR>/scripts/stitching.py \
  '{"type":"audio","audios":["vid://v0003","vid://v0004"]}'
```
