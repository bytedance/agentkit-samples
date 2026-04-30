# 图片转视频能力

## 功能命名

- `image_to_video`

## 作用

- 将图片序列合成为视频，支持单图动画及转场效果。

## 参数

| 参数名      | 类型  | 必填 | 说明                                                                                       |
| ----------- | ----- | ---- | ------------------------------------------------------------------------------------------ |
| images      | array | ✅   | 待合成图片列表；CLI 可用 `image_url=xxx,duration=3,animation_type=zoom_in`，多图空格分隔   |
| transitions | array | ❌   | 视频转场 ID 列表，同 [`concat_media_segments.md`](concat_media_segments.md) 中的转场 ID 表 |

### `images` 单项字段

| 字段           | 类型   | 必填 | 说明                               |
| -------------- | ------ | ---- | ---------------------------------- |
| image_url      | string | ✅   | 图片 URL                           |
| duration       | float  | ❌   | 播放时长，默认 3 秒，最多 2 位小数 |
| animation_type | string | ❌   |

              图片的动画类型，选填，不填时无动画效果。
              move_up：向上移动
              move_down：向下移动
              move_left：向左移动
              move_right：向右移动
              zoom_in：缩小
              zoom_out：放大|

| animation_in | float | ❌ | 动画开始时间，支持2位小数。默认为图片展示时长，表示动画随图片播放同时结束，单位：秒" |
| animation_out | float | ❌ | "动画结束时间，，支持2位小数。默认为图片展示时长，表示动画随图片播放同时结束，单位：秒" |

## 返回数据

- task_id(str): 任务查询 id
- request_id(str): 日志 id
