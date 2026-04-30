# 任务查询能力

## 功能命名

- `query_task`

## 作用

- 查询异步任务状态，支持轮询直到任务完成。

## 参数

| 参数名      | 类型   | 必填 | 说明                    |
| ----------- | ------ | ---- | ----------------------- |
| task_id     | string | ✅   | 任务查询 ID             |
| interval    | int    | ❌   | 轮询间隔，默认 5 秒     |
| max_retries | int    | ❌   | 最大轮询次数，默认 6 次 |

## 返回数据

- duration(float): **非必选**，时长（秒）
- play_url(str): **非必选**，播放地址（根据任务类型解析为音频或视频地址）
- request_id(str): 日志 id
- status(str): 任务状态（`running` \| `completed` \| `queued` \| `failed` \| `canceled`）
- task_id(str): 任务查询 ID
