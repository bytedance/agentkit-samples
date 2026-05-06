# 视频理解能力

## 功能命名

- `understand_video_content`

## 作用

- 使用大模型进行视频理解，生成视频内容解析与自然语言描述。

## 参数

| 参数名     | 类型   | 必填 | 说明                                            |
| ---------- | ------ | ---- | ----------------------------------------------- |
| video_url  | string | ✅   | 视频文件 URL，支持 `http://` 或 `https://`      |
| prompt     | string | ✅   | 用户提示词，描述对视频理解的具体要求            |
| fps        | float  | ✅   | 抽帧帧率，须大于 0，支持整数或浮点数            |
| max_frames | int    | ❌   | 最大抽帧数，须大于 0；不传则由服务端默认策略处理 |

## 环境变量

- ARK_MODEL_ID(str): **必选**，方舟模型 ID，用于请求体 `model` 字段
- 未设置、为空或 `null` 时会抛出配置异常

## 返回数据

- choices(List[message]): 仅返回模型 `choices` 中的 `message` 列表
  - message.role(str): 角色（通常为 `assistant`）
  - message.content(str): 主回答内容
  - message.reasoning_content(str): 推理内容（模型支持时返回）

## 说明

- 方法会在内部自动构造 `chat.completions` 请求体，不需要外部传递 `messages` / `model` / `stream`
- 内部另有默认上限等行为，与网关/模型版本有关；`max_frames` 见上表
- 返回不会包含 `usage` / `id` / `model` 等元信息，仅保留 `choices[].message`
