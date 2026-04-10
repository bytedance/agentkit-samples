## AI 解说视频生成（Drama Recap）

基于大模型视频理解，根据原视频智能生成带有 AI 配音和解说字幕的"二创"解说视频。支持自定义解说词或 AI 自动生成，可配置音色、语速、解说风格、字幕样式以及短剧三要素模板。

---

### 工作流程

#### 步骤 1：确认视频 ID

用户需提供一个或多个视频 ID（Vid）。如果用户只有本地文件或 URL，按 SKILL.md「公共前置步骤：媒资上传」完成上传后获取 Vid。

也支持传入已完成的**剧本还原任务 ID**（`DramaScriptTaskId`），此时无需再提供 Vids。

#### 步骤 2：确认解说词来源（⚠️ 二选一）

| 模式 | 参数设置 | 说明 |
|------|----------|------|
| **用户提供解说词** | `RecapText` = "解说文案" | 默认模式，必须提供 `RecapText` |
| **AI 自动生成** | `AutoGenerateRecapText` = `true` | AI 根据视频内容自动创作，不可同时设置 `RecapText` |

如果用户没有明确提供解说词且未要求 AI 自动生成，**需向用户确认**选择哪种模式。

#### 步骤 3：提交解说视频生成任务

```bash
python <SKILL_DIR>/scripts/drama_recap.py '<json_args>' [space_name]
python <SKILL_DIR>/scripts/drama_recap.py @params.json [space_name]
```

脚本提交任务后会**自动轮询**直到终态（成功/失败/超时），无需额外操作。

#### 步骤 4（可选）：恢复轮询

如果任务超时，可使用输出中的 `resume_hint.command` 恢复：

```bash
python <SKILL_DIR>/scripts/drama_recap.py --poll <TaskId> [space_name]
```

---

### 限制

- 所有视频**总时长不超过 90 分钟**（约 45 集短剧）
- 视频分辨率需**保持一致**
- 视频必须包含**硬字幕**（内嵌字幕）
- **不支持 HLS / M3U8 格式**
- **不支持挂载在对象存储桶中的视频**
- 需白名单开通，使用前需联系火山引擎技术支持

---

### 参数说明（drama_recap.py）

#### 视频输入（二选一）

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `Vids` | Array\<String\> | 与 DramaScriptTaskId 二选一 | 视频 ID 列表 |
| `DramaScriptTaskId` | String | 与 Vids 二选一 | 已完成的剧本还原任务 ID |

#### 解说词

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| `RecapText` | String | 条件必选 | - | 自定义解说词（`AutoGenerateRecapText=false` 时必填） |
| `AutoGenerateRecapText` | Boolean | 否 | `false` | 是否 AI 自动生成解说词 |
| `RecapStyle` | String | 否 | - | AI 解说风格关键词，如"搞笑""悬疑"，≤500 字符 |
| `RecapTextSpeed` | Double | 否 | `1.0` | 解说语速 [0.5, 2.0]，推荐 1.2 |
| `RecapTextLength` | Integer | 否 | - | AI 生成解说词长度（字符数），≤5000 |
| `PauseTime` | Integer | 否 | `120` | 句间停顿（毫秒）[1, 1000] |
| `AllowRepeatMatch` | Boolean | 否 | `false` | 是否允许匹配重复画面 |

#### 音色

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| `VoiceType` | String | 否 | `"Yunxi"` | 音色名称（见下方预置音色列表） |
| `AppId` | String | 否 | - | 豆包语音 App ID（使用高级音色时） |

**预置音色**：`Yunxi`（默认）、`Yunjian`、`Yunfeng`、`Yunyi`、`Yunjie`、`Yunze`、`Yunye`、`Xiaoxiao`、`Xiaochen`、`Xiaohan`、`Xiaomo`

#### 其他

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| `IsEraseSubtitle` | Boolean | 否 | `false` | 是否擦除原视频字幕 |
| `BatchGenerateCount` | Integer | 否 | `1` | 批量生成数量，最大 100 |
| `FontConfig` | Object | 否 | - | 字幕样式配置（字体、位置、颜色等） |
| `MiniseriesEdit` | Object | 否 | - | 短剧三要素配置（见下方） |

#### 短剧三要素（MiniseriesEdit）

仅适用于**竖屏短剧**，一键添加剧名、角标、提示语。

| 参数 | 类型 | 说明 |
|------|------|------|
| `Template` | String | 模板名称：`热门短剧1` \~ `热门短剧5` |
| `Title` | String | 短剧名称（≤15 字） |
| `Hint` | String | 提示语（≤20 字），如"影视效果 请勿模仿" |

#### 字幕样式（FontConfig）

| 参数 | 类型 | 说明 |
|------|------|------|
| `NoSubtitle` | Boolean | 是否不添加字幕，默认 `false` |
| `FontSize` | Integer | 字体大小（pixel） |
| `FontColor` | String | 字体颜色（RGBA），如 `"#FFCC66FF"` |
| `BorderColor` | String | 描边颜色（RGBA） |
| `BorderWidth` | Integer | 描边宽度（pixel） |
| `BackgroundColor` | String | 字幕背景色（RGBA） |
| `PosX` / `PosY` | Integer | 字幕区域左上角坐标 |
| `Width` / `Height` | Integer | 字幕区域尺寸 |
| `Alpha` | Double | 透明度 [0,1] |
| `AlignType` | Integer | 对齐方式（0=左, 1=居中, 2=右） |
| `Typesetting` | Integer | 排列方向（0=横排, 1=竖排） |

---

### 示例

#### 最简调用（用户提供解说词）

```json
{
    "Vids": ["v02b69g10000example"],
    "RecapText": "这是一部关于都市爱情的短剧，讲述了两位年轻人相遇相知相爱的故事。"
}
```

#### AI 自动生成解说词

```json
{
    "Vids": ["v02b69g10000example1", "v02b69g10000example2"],
    "AutoGenerateRecapText": true,
    "RecapStyle": "搞笑",
    "RecapTextSpeed": 1.2,
    "RecapTextLength": 800
}
```

#### 基于已有剧本还原结果

```json
{
    "DramaScriptTaskId": "v02bbbg1006xxx",
    "AutoGenerateRecapText": true,
    "RecapStyle": "悬疑"
}
```

#### 完整配置

```json
{
    "Vids": ["v02b69g10000example"],
    "RecapText": "自定义解说词文本...",
    "VoiceType": "Xiaoxiao",
    "IsEraseSubtitle": true,
    "RecapTextSpeed": 1.3,
    "PauseTime": 200,
    "BatchGenerateCount": 3,
    "FontConfig": {
        "FontSize": 60,
        "FontColor": "#FFFFFFFF",
        "BorderColor": "#000000FF",
        "BorderWidth": 2
    },
    "MiniseriesEdit": {
        "Template": "热门短剧1",
        "Title": "《都市爱情》",
        "Hint": "影视效果 请勿模仿"
    }
}
```

#### 命令行示例

```bash
# 用户提供解说词
python <SKILL_DIR>/scripts/drama_recap.py '{"Vids":["v02b69g10000example"],"RecapText":"解说文案..."}'

# AI 自动生成
python <SKILL_DIR>/scripts/drama_recap.py '{"Vids":["v023xxx"],"AutoGenerateRecapText":true,"RecapStyle":"搞笑"}' my_space

# 使用文件传参
python <SKILL_DIR>/scripts/drama_recap.py @params.json my_space

# 恢复超时任务的轮询
python <SKILL_DIR>/scripts/drama_recap.py --poll 'v02bbbg1006xxx' my_space
```

---

### 输出

成功时（单个视频）：
```json
{
    "Status": "success",
    "TaskId": "v02bbbg10064d3kbdminbj659kvikr10",
    "SpaceName": "my_space",
    "Vid": "v02b69g10000example"
}
```

成功时（批量生成）：
```json
{
    "Status": "success",
    "TaskId": "v02bbbg10064d3kbdminbj659kvikr10",
    "SpaceName": "my_space",
    "MultipleResult": {
        "TotalCount": 3,
        "SuccessItems": [
            {"Vid": "v02b69g10000out1", "Index": 1},
            {"Vid": "v02b69g10000out2", "Index": 2}
        ],
        "FailedItems": [
            {"Index": 3, "BizCode": 500130}
        ]
    }
}
```

超时时的恢复指引：
```json
{
    "error": "轮询超时（360 次 × 5s），任务仍在处理中",
    "TaskId": "v02bbbg1006xxx",
    "resume_hint": {
        "description": "任务尚未完成，可用以下命令重启轮询",
        "command": "python <SKILL_DIR>/scripts/drama_recap.py --poll 'v02bbbg1006xxx' my_space"
    }
}
```
