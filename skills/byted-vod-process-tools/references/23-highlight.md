## 短剧高光剪辑（Highlight）

基于大模型的多模态高光提取算法，智能地从短剧正片视频中提取出最精彩的高光片段。可生成单集摘要、剧集集锦、剧集宣传片等不同形式的视频素材，用于广告投放、短剧宣传等各种场景。

---

### 工作流程

#### 步骤 1：确认视频 ID

用户需提供一个或多个视频 ID（Vid）。如果用户只有本地文件或 URL，按 SKILL.md「公共前置步骤：媒资上传」完成上传后获取 Vid。

#### 步骤 2：提交高光剪辑任务

```bash
python <SKILL_DIR>/scripts/highlight.py '<json_args>' [space_name]
python <SKILL_DIR>/scripts/highlight.py @params.json [space_name]
```

脚本提交任务后会**自动轮询**直到终态（成功/失败），无需额外操作。

#### 步骤 3（可选）：恢复轮询

如果任务超时，可使用输出中的 `resume_hint.command` 恢复：

```bash
python <SKILL_DIR>/scripts/poll_media.py highlight <RunId> [space_name]
```

---

### 限制

- 输入视频至少 **1 个**，支持多个视频同时提交（如多集短剧）,最多不超过30个
- 当前仅支持 **Miniseries**（短剧）模型

---

### 参数说明（highlight.py）

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| `Vids` | Array\<String\> | **是** | - | 视频 ID 列表，至少 1 个 |
| `Model` | String | 否 | `"Miniseries"` | 模型类型（当前仅支持短剧） |
| `Mode` | String | 否 | `"StorylineCuts"` | 剪辑模式（剧情高光剪辑） |
| `WithStoryboard` | Boolean | 否 | `true` | 是否生成分镜脚本 |
| `WithOpeningHook` | Boolean | 否 | `true` | 是否生成开头钩子片段 |

### 模型（Model）

| 值 | 说明 |
|----|------|
| `Miniseries` | 短剧模型（默认） |

### 模式（Mode）

| 值 | 说明 |
|----|------|
| `StorylineCuts` | 剧情高光剪辑（默认），按故事线提取高光片段 |

---

### 示例

#### 单个视频

```json
{
    "Vids": ["v02399g10002d6tab1iljht5kim11hp0"]
}
```

#### 多集视频（批量提交）

```json
{
    "Vids": [
        "v02399g10002d6tab1iljht5kim11hp0",
        "v02399g10002qpj9aljht4nmunv9ng",
        "v02399g10002qpj9aljhta75lgba20"
    ]
}
```

#### 完整配置

```json
{
    "Vids": [
        "v02399g10002d6tab1iljht5kim11hp0",
        "v02399g10002qpj9aljht4nmunv9ng"
    ],
    "Model": "Miniseries",
    "Mode": "StorylineCuts",
    "WithStoryboard": true,
    "WithOpeningHook": true
}
```

#### 命令行示例

```bash
# 单个视频高光剪辑
python <SKILL_DIR>/scripts/highlight.py '{"Vids":["v02399g10002d6tab1iljht5kim11hp0"]}'

# 多集视频
python <SKILL_DIR>/scripts/highlight.py '{"Vids":["v023xxx","v024xxx","v025xxx"]}' my_space

# 使用文件传参
python <SKILL_DIR>/scripts/highlight.py @params.json my_space

# 恢复超时任务的轮询
python <SKILL_DIR>/scripts/poll_media.py highlight 'lb:5c320217a2b335641293cb39beeb' my_space
```

---

### 输出

成功时返回：
```json
{
    "Status": "Success",
    "Code": "",
    "SpaceName": "test-doc",
    "VideoUrls": [],
    "AudioUrls": [],
    "Texts": []
}
```

> **说明**：高光剪辑任务的产物通常需要通过视频点播控制台或后续剪辑 API 获取具体的高光片段视频。任务成功表示高光提取已完成。

超时时的恢复指引：
```json
{
    "error": "轮询超时（360 次 × 5s），任务仍在处理中",
    "resume_hint": {
        "description": "任务尚未完成，可用以下命令重启轮询",
        "command": "python <SKILL_DIR>/scripts/poll_media.py 'highlight' 'lb:xxx' my_space"
    }
}
```
