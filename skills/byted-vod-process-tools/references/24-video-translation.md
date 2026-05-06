## AI 视频翻译（声影智译）

将视频从一种语言翻译为另一种语言，支持文本翻译、语音翻译和面容翻译。

---

### 工作流程

#### 步骤 1：确认视频 ID

用户需提供视频 ID（Vid）。如果用户只有本地文件或 URL，按 SKILL.md「公共前置步骤：媒资上传」完成上传后获取 Vid。

#### 步骤 2：确认源语言和目标语言（⚠️ 必选，无默认值）

**`SourceLanguage` 和 `TargetLanguage` 是必选参数，没有默认值。**

如果用户没有明确提供，**必须先向用户确认**后再调用脚本，不可自行假设或填入默认值。

确认时可向用户展示支持的语言列表：

**源语言**（SourceLanguage）仅支持：

| 代码 | 语言 |
|------|------|
| `zh` | 中文 |
| `en` | 英文 |

**目标语言**（TargetLanguage）支持：

| 代码 | 语言 | 代码 | 语言 |
|------|------|------|------|
| `zh` | 中文 | `en` | 英文 |
| `ja` | 日语 | `ko` | 韩语 |
| `de` | 德语 | `fr` | 法语 |
| `ru` | 俄语 | `es` | 西班牙语 |
| `pt` | 葡萄牙语 | `it` | 意大利语 |
| `id` | 印尼语 | `vi` | 越南语 |
| `th` | 泰语 | `ar` | 阿拉伯语 |
| `tr` | 土耳其语 | | |

#### 步骤 3：询问翻译内容类型（文本/语音/面容，可多类型自由组合）（⚠️ 必须执行）

每次翻译任务都需要**先询问用户**要翻译哪些内容类型，并将结果映射到 `TranslationTypeList`。

可选类型：

| 类型 | TranslationTypeList 中包含的项 | 说明 |
|------|---------------------------------|------|
| 文本翻译 | `SubtitleTranslation` | 仅文本翻译 |
| 语音翻译 | `VoiceTranslation` | 文本 + 语音翻译 |
| 面容翻译 | `FacialTranslation` | 文本 + 语音 + 面容翻译 |

允许多类型组合（例如：文本 + 语音、文本 + 语音 + 面容等）。

注：在当前实现中，只要选择了 `VoiceTranslation` 或 `FacialTranslation`，`SubtitleTranslation` 将会一并开启。

> 说明：脚本参数中的 `TranslationTypeList` 支持以下常见组合：
>
> - `["SubtitleTranslation"]`：仅文本翻译
> - `["SubtitleTranslation","VoiceTranslation"]`：文本 + 语音翻译
> - `["SubtitleTranslation","VoiceTranslation","FacialTranslation"]`：文本 + 语音 + 面容翻译（默认）

用户明确选择后，将 `TranslationTypeList` 设置为对应的组合。

#### 步骤 4：确认是否擦除原字幕（⚠️ 必须询问）

每次翻译任务都**必须询问用户**是否需要擦除原视频中的字幕，不得跳过此步骤或自行假设。

询问时**必须附带以下收费提示**：

> 是否需要擦除原视频中的字幕？
>
> ⚠️ **字幕擦除为收费功能**，按实际输出视频时长计费，具体价格请参考 [视频 AI 应用计费](https://www.volcengine.com/docs/4/1941013#%E8%A7%86%E9%A2%91-ai-%E5%BA%94%E7%94%A8)。
>
> - **是**：擦除原字幕（`IsEraseSource: true`）
> - **否**：保留原字幕（`IsEraseSource: false`，默认）

用户明确回复后，将 `IsEraseSource` 设置为对应值。

#### 步骤 5：提交翻译任务

```bash
python <SKILL_DIR>/scripts/video_translation.py '<json_args>' [space_name]
python <SKILL_DIR>/scripts/video_translation.py @params.json [space_name]
```

脚本提交任务后会**自动轮询**直到终态（成功/失败/暂停），无需额外操作。

#### 步骤 6（可选）：管理翻译任务

翻译任务可能耗时较长，以下场景可使用对应脚本：

| 场景 | 命令 |
|------|------|
| 查看翻译任务列表 | `python <SKILL_DIR>/scripts/list_translation.py [space_name] ['<options_json>']` |
| 查看指定项目详情 / 重启轮询 | `python <SKILL_DIR>/scripts/poll_translation.py <ProjectId> [space_name]` |
| 超时后恢复 | 直接复制输出中 `resume_hint.command` 的命令执行 |

---

### 限制

- **视频时长**：不超过 **10 分钟**（600 秒），超限将被自动拒绝
- **`SourceLanguage` 和 `TargetLanguage`**：必选，无默认值，必须由用户明确指定
- **`TranslationTypeList`**：必须询问用户翻译类型组合（文本/语音/面容，可多选）
- **`IsEraseSource`**：必须每次询问用户确认，并提示字幕擦除为收费功能

---

### 参数说明（video_translation.py）

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| `Vid` | String | **是** | - | 视频 ID |
| `SourceLanguage` | String | **是** | - | 源语言，**必须由用户明确指定** |
| `TargetLanguage` | String | **是** | - | 目标语言，**必须由用户明确指定** |
| `SpaceName` | String | 否 | 环境变量/命令行 | 点播空间名 |
| `TranslationTypeList` | Array | **询问** | 全部三种 | 翻译类型组合（见下表） |
| `RecognitionType` | String | 否 | `"OCR"` | 字幕识别方式（见下表） |
| `IsVision` | Boolean | 否 | `false` | 是否开启视频理解 |
| `IsHardSubtitle` | Boolean | 否 | `true` | 是否硬字幕 |
| `FontSize` | Integer | 否 | `30` | 硬字幕字体大小（1-80） |
| `IsEraseSource` | Boolean | **询问** | `false` | 是否擦除原字幕，**必须询问用户确认**（收费功能） |
| `MarginL` | Double | 否 | `0.1` | 左边距比例（0-1） |
| `MarginR` | Double | 否 | `0.09` | 右边距比例（0-1） |
| `MarginV` | Double | 否 | `0.12` | 底部边距比例（0-1） |
| `ShowLines` | Integer | 否 | `0` | 最多显示行数，0 不限 |
| `TermbaseConfig` | Object | 否 | - | 术语库配置 |
| `ProcessConfig` | Object | 否 | - | 流程控制配置（如暂停阶段） |
| `VoiceCloneConfig` | Object | 否 | - | 声音克隆配置 |

### 翻译类型组合（TranslationTypeList）

| 组合 | 说明 |
|------|------|
| `["SubtitleTranslation"]` | 仅文本翻译 |
| `["SubtitleTranslation","VoiceTranslation"]` | 文本 + 语音翻译 |
| `["SubtitleTranslation","VoiceTranslation","FacialTranslation"]` | 文本 + 语音 + 面容翻译（默认） |

### 字幕识别方式（RecognitionType）

| 值 | 说明 |
|----|------|
| `OCR` | 从视频画面识别字幕（默认） |
| `ASR` | 从音轨识别字幕 |
| `SourceSubtitleFile` | 使用用户提供的源语言字幕文件 |
| `SourceAndTargetSubtitleFile` | 使用用户提供的源/目标语言字幕文件 |
| `BilingualSubtitleFile` | 使用用户提供的双语字幕文件 |

---

### 参数说明（list_translation.py）

```bash
python <SKILL_DIR>/scripts/list_translation.py [space_name] ['<options_json>']
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `PageNumber` | Integer | `1` | 页码 |
| `PageSize` | Integer | `10` | 每页数量 |
| `StatusFilter` | String | - | 状态过滤（逗号分隔），如 `"InProcessing,ProcessSucceed"` |
| `ProjectIdOrTitleFilter` | String | - | 按项目 ID 或名称过滤 |

### 翻译项目状态

| 状态 | 说明 |
|------|------|
| `InProcessing` | 处理中 |
| `ProcessSuspended` | 处理暂停（等待人工干预） |
| `ProcessSucceed` | 处理完成 |
| `ProcessFailed` | 处理失败 |
| `InExporting` | 导出中 |
| `ExportSucceed` | 导出完成 |
| `ExportFailed` | 导出失败 |

---

### 示例

#### 最简调用（必须包含 Vid + 源语言 + 目标语言）

```json
{
    "Vid": "v0d225g10002d6tab1iljhtf5buiu8v0",
    "SourceLanguage": "zh",
    "TargetLanguage": "es"
}
```

#### 指定翻译类型 + 擦除原字幕

```json
{
    "Vid": "v0d225g10002d6tab1iljhtf5buiu8v0",
    "SourceLanguage": "zh",
    "TargetLanguage": "ja",
    "TranslationTypeList": ["SubtitleTranslation", "VoiceTranslation"],
    "IsEraseSource": true
}
```

#### 完整配置

```json
{
    "SpaceName": "my_space",
    "Vid": "v0d225g10002d6tab1iljhtf5buiu8v0",
    "SourceLanguage": "zh",
    "TargetLanguage": "es",
    "TranslationTypeList": [
        "SubtitleTranslation",
        "VoiceTranslation",
        "FacialTranslation"
    ],
    "RecognitionType": "OCR",
    "IsVision": false,
    "IsHardSubtitle": true,
    "FontSize": 30,
    "IsEraseSource": false,
    "MarginL": 0.1,
    "MarginR": 0.09,
    "MarginV": 0.12,
    "ShowLines": 0
}
```

#### 命令行完整示例

```bash
# 提交翻译任务
python <SKILL_DIR>/scripts/video_translation.py '{"Vid":"v0d225g10002d6tab1iljhtf5buiu8v0","SourceLanguage":"zh","TargetLanguage":"es"}'

# 使用文件传参
python <SKILL_DIR>/scripts/video_translation.py @params.json my_space

# 查看所有翻译任务
python <SKILL_DIR>/scripts/list_translation.py my_space

# 过滤已完成的任务
python <SKILL_DIR>/scripts/list_translation.py my_space '{"StatusFilter":"ProcessSucceed"}'

# 查看项目详情 / 恢复轮询
python <SKILL_DIR>/scripts/poll_translation.py 684038d6b71c9005b266fefe my_space
```

---

### 输出

成功时返回：
```json
{
    "Status": "ProcessSucceed",
    "ProjectId": "684038d6b71c9005b266fefe",
    "ProjectVersion": "01c4fa5da48a588a46f81e282b100",
    "InputVideo": {
        "Title": "example.mp4",
        "Vid": "v0d225g10002d6tab1iljhtf5buiu8v0",
        "Url": "https://...",
        "Duration": 120.5
    },
    "OutputVideo": {
        "Vid": "v0299fg4d103gsqljht10tatbreg",
        "Url": "https://...",
        "FileName": "video.mp4",
        "Duration": 120.5
    }
}
```

语言缺失时的错误：
```json
{"error": "必须提供 SourceLanguage（源语言）。支持的源语言: en(英文), zh(中文)。请让用户明确指定源语言后重试。"}
```

超时时的恢复指引：
```json
{
    "error": "轮询超时（360 次 × 5s），翻译任务仍在处理中",
    "ProjectId": "684038d6b71c9005b266fefe",
    "resume_hint": {
        "description": "任务尚未完成，可用以下命令重启轮询",
        "command": "python <SKILL_DIR>/scripts/poll_translation.py '684038d6b71c9005b266fefe' my_space"
    }
}
```
