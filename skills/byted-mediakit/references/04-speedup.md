# 视频变速 / 音频变速 `speedup`

调整视频或音频的播放速度倍数。

## 用法

```bash
python <SKILL_DIR>/scripts/speedup.py <video|audio> '<json_args>'
```

第一个参数指定媒体类型（`video` 或 `audio`），决定使用哪个工作流。

## 参数（json_args）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `vid` / `directurl` / `http` |
| `source` | string | ✅ | 文件标识 |
| `speed` | float | 可选 | 速度倍数，范围 **0.1～4**，默认 `1.0` |

### speed 参考值

| speed | 效果 |
|-------|------|
| 0.25 | 四分之一慢放 |
| 0.5 | 慢放 |
| 1.0 | 原速（默认） |
| 2.0 | 两倍速 |
| 4.0 | 最高四倍速 |

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
# 视频两倍速
python <SKILL_DIR>/scripts/speedup.py video \
  '{"type":"vid","source":"v0001","speed":2.0}'

# 音频 0.5 倍慢放
python <SKILL_DIR>/scripts/speedup.py audio \
  '{"type":"vid","source":"v0002","speed":0.5}'
```
