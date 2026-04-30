## AI 剧本还原（Drama Script Restoration）

基于大模型视频理解，将剧情类视频转化为结构化剧本文本。精准识别并提取视频中的场景、人物（角色）、对话、情节等核心元素，为内容创作者和数据分析师提供高价值的文本素材。

---

### 工作流程

#### 步骤 1：确认视频 ID

用户需提供一个或多个视频 ID（Vid）。如果用户只有本地文件或 URL，按 SKILL.md「公共前置步骤：媒资上传」完成上传后获取 Vid。

#### 步骤 2：提交剧本还原任务

```bash
python <SKILL_DIR>/scripts/drama_script.py '<json_args>' [space_name]
python <SKILL_DIR>/scripts/drama_script.py @params.json [space_name]
```

脚本提交任务后会**自动轮询**直到终态（成功/失败/超时），无需额外操作。

#### 步骤 3（可选）：恢复轮询

如果任务超时，可使用输出中的 `resume_hint.command` 恢复：

```bash
python <SKILL_DIR>/scripts/drama_script.py --poll <TaskId> [space_name]
```

#### 步骤 4：交付结果

任务成功后，返回的 `ResultUrl` 是一个 `.json.gz` 压缩文件的下载链接（有效期 **24 小时**），包含完整的结构化剧本信息（场景、人物、对话、情节等）。

**⚠️ 结果交付规则**：直接将 `ResultUrl` 下载链接提供给用户即可，**不需要下载或解压这个 JSON 文件**。向用户展示时说明：

> 剧本还原完成，以下是结构化剧本的下载链接（`.json.gz` 格式，有效期 24 小时）：
>
> 下载链接：`<ResultUrl>`
>
> 下载后使用 gzip 解压即可获得结构化剧本 JSON 文件。

---

### 限制

- 所有视频**总时长不超过 300 分钟**
- 视频分辨率需**保持一致**（不可混合不同分辨率的视频）
- 视频必须包含**硬字幕**（内嵌字幕），纯画面无字幕视频不支持
- **不支持 HLS / M3U8 格式**的视频
- ResultUrl 有效期 **24 小时**，过期需重新提交任务

---

### 参数说明（drama_script.py）

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| `Vids` | Array\<String\> | **是** | - | 视频 ID 列表，至少 1 个 |
| `ClientToken` | String | 否 | 自动生成 UUID | 幂等 token，相同 token 不会重复创建任务 |

---

### 示例

#### 单个视频

```json
{
    "Vids": ["v02399g10002d6tab1iljht5kim11hp0"]
}
```

#### 多个视频（同一部剧的多集）

```json
{
    "Vids": [
        "v02399g10002d6tab1iljht5kim11hp0",
        "v02399g10002qpj9aljht4nmunv9ng",
        "v02399g10002qpj9aljhta75lgba20"
    ]
}
```

#### 指定幂等 token

```json
{
    "Vids": ["v02399g10002d6tab1iljht5kim11hp0"],
    "ClientToken": "my-unique-request-id-001"
}
```

#### 命令行示例

```bash
# 单个视频剧本还原
python <SKILL_DIR>/scripts/drama_script.py '{"Vids":["v02399g10002d6tab1iljht5kim11hp0"]}'

# 多个视频
python <SKILL_DIR>/scripts/drama_script.py '{"Vids":["v023xxx","v024xxx","v025xxx"]}' my_space

# 使用文件传参
python <SKILL_DIR>/scripts/drama_script.py @params.json my_space

# 恢复超时任务的轮询
python <SKILL_DIR>/scripts/drama_script.py --poll 'task_abc123' my_space
```

---

### 输出

成功时返回：
```json
{
    "Status": "success",
    "TaskId": "task_abc123",
    "SpaceName": "my_space",
    "ResultUrl": "https://example.com/result.json.gz",
    "note": "ResultUrl 是一个 .json.gz 压缩文件的下载链接（有效期 24 小时）。直接将此链接提供给用户，不需要下载或解压。"
}
```

> **⚠️ 重要**：收到 `ResultUrl` 后，直接将链接交付给用户。**禁止**执行 `curl`、`wget` 等命令下载该文件，也**禁止**执行 `gunzip`、`zcat` 等命令解压该文件。

失败时返回：
```json
{
    "Status": "failed",
    "TaskId": "task_abc123",
    "SpaceName": "my_space",
    "detail": { "Status": "failed" },
    "note": "任务失败，请检查输入视频是否满足限制条件后重新提交。"
}
```

超时时的恢复指引：
```json
{
    "error": "轮询超时（360 次 × 5s），任务仍在处理中",
    "TaskId": "task_abc123",
    "resume_hint": {
        "description": "任务尚未完成，可用以下命令重启轮询",
        "command": "python <SKILL_DIR>/scripts/drama_script.py --poll 'task_abc123' my_space"
    }
}
```
