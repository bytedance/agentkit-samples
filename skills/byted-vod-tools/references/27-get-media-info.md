# 27 - 获取媒资信息

## 功能

通过 Vid（视频 ID）获取媒资信息，包含基础信息、片源信息及播放地址。支持批量查询，超过 20 个 Vid 时自动分批请求。

## 脚本

```bash
python <SKILL_DIR>/scripts/get_media_info.py '{"vids":"v001,v002,v003"}'
python <SKILL_DIR>/scripts/get_media_info.py @params.json
```

## 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `vids` | string 或 array | 是 | Vid 列表。字符串时用逗号分隔；数组时直接传入。无数量上限，超过 20 个自动分批请求 |

## 返回示例

```json
{
  "MediaInfoList": [
    {
      "Vid": "v02b69g10000xxxxx",
      "Title": "示例视频",
      "SpaceName": "my_space",
      "PublishStatus": "Published",
      "CreateTime": "2025-12-28T08:57:58Z",
      "Source": {
        "Format": "MP4",
        "Duration": 120.5,
        "Width": 1920,
        "Height": 1080,
        "Size": 52428800,
        "Codec": "h264",
        "Fps": 30.0,
        "FileName": "088ecee226xxx.mp4"
      },
      "PlayUrl": "https://cdn.example.com/xxx/video.mp4?auth=xxx"
    }
  ],
  "NotExistVids": ["v_not_found"]
}
```

## 说明

- 底层调用 `GetMediaInfos` 接口，单次最多查询 20 个 Vid。当传入 Vid 超过 20 个时，脚本自动分批发送请求并合并结果。
- 播放地址获取优先使用 CDN 域名 + URL 鉴权，若视频未发布会自动执行发布操作后获取 Origin 地址。
- `NotExistVids` 字段仅在存在无效 Vid 时返回。
