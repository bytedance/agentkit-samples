# 混音 `mix_audios`

将多轨音频混合叠加为一个文件（同时播放，非拼接）。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `audios` | list[dict] | ✅ | 音频列表，至少 1 项，每项含 `type` + `source` |

### audios 子字段

| 字段 | 说明 |
|------|------|
| `type` | `vid` / `directurl` / `http` |
| `source` | 音频文件标识 |

> 与 `stitching` 的区别：`mix_audios` 是多轨叠加（同时响），`stitching` 是顺序拼接（先后响）。

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
# 将人声和背景音乐混合
python <SKILL_DIR>/scripts/mix_audios.py \
  '{"audios":[
    {"type":"vid","source":"v0001"},
    {"type":"http","source":"https://example.com/bgm.mp3"}
  ]}'
```
