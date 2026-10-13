---
name: byted-arkclaw-call-records-simulate
version: "1.0.0"
description: "通话记录模拟与语音合成技能。根据自然语言需求或结构化场景生成对话 JSON，并调用 edge-tts 合成为 MP3。适用于需要构造招聘邀约、电话销售、面试邀约等模拟通话录音，或为 ASR 测试和演示准备语音样本时。"
---

# 通话记录模拟（`byted-arkclaw-call-records-simulate`）

根据调用者的自然语言提示，构建结构化的**通话记录 JSON**，再调用 `edge-tts` 将对话渲染为单个合成的 MP3 音频文件，用于 Demo、ASR 测试、语音数据集构造等场景。

## 输入与输出

### 输入

- 业务场景
- 主叫 / 被叫角色设定
- 预期通话结果
- 轮次、时长、语气等补充要求
- 若需复用已有候选人信息，只向调用者索要必要字段或文件路径，不要求先把资料复制到当前 skill 目录

### 输出

- `materials/*.json`：结构化通话脚本
- `output/*.mp3`：合成后的模拟录音
- 若已知候选人邮箱，可在 `materials/*.json` 中保留 `candidate_email` 字段，供后续复试邮件邀约链路使用

## 在总流程中的位置

- 测试与演示阶段：用于模拟招聘电话、验证 ASR 与 CRM 链路
- 不负责候选人正式评估与 CRM 决策，只负责生成可控的模拟通话样本

## 设计模式

本 skill 主要采用：
- **Prompt → Structured Data**：将自然语言提示转换为标准化的 `materials/*.json` 通话记录
- **Tool Wrapper**：封装 `edge-tts` Python SDK 的异步流式接口
- **Pipeline**：`构建 JSON` → `校验` → `TTS 合成` → `输出 MP3`

## 核心脚本与配置

所有功能脚本位于 `scripts/` 目录：
- `scripts/env_init.sh`：环境初始化（创建虚拟环境、安装 `edge-tts`）
- `scripts/generate_record.py`：根据用户提示生成通话记录 JSON 骨架（支持交互式/命令行两种模式）
- `scripts/tts_processor.py`：读取 JSON 素材，按角色逐句调用 `edge-tts` 合成，并拼接为单个 MP3

### 目录约定

```
byted-arkclaw-call-records-simulate/
├── SKILL.md
├── checklist.md
├── evals/
│   └── evals.json
├── references/
│   └── voices.md                  # 可用语音模型清单
├── scripts/
│   ├── env_init.sh
│   ├── generate_record.py
│   └── tts_processor.py
├── materials/                     # 通话记录 JSON 素材
│   ├── interview_accept.json
│   └── interview_rejection.json
└── output/                        # 合成后的 MP3 输出目录
```

## Gotchas

- **网络依赖**：`edge-tts` 需访问 Microsoft Edge 在线 TTS 服务，离线或代理受限环境会失败（表现为 `WebSocket 403/无法连接`）。
- **声音区分**：同一段对话中，**不同角色务必使用不同的 voice**，否则 ASR 的 speaker diarization 无法区分说话人。推荐男女声组合（如 `zh-CN-YunxiNeural` + `zh-CN-XiaoxiaoNeural`）。
- **文本合规**：不得在合成音频中编造真实姓名、真实电话号码、真实公司内部信息；应使用化名 + 脱敏号码（如 `138****1234`）。
- **拼接方式**：本 skill 采用**逐句追加二进制流**的方式拼接 MP3（`edge-tts` 输出为单一 codec 的 MP3 片段，直接 `bytes` 拼接即可被播放器解码）。若需严格的无缝编辑，请改用 `ffmpeg concat`。

## 工作流（严格按步骤执行）

复制此清单并跟踪进度：

```text
执行进度：
- [ ] Step 0: 前置检查
- [ ] Step 1: 环境初始化
- [ ] Step 2: 解析用户提示 → 生成通话记录 JSON
- [ ] Step 3: 用户确认 JSON
- [ ] Step 4: 调用 edge-tts 合成音频
- [ ] Step 5: 结果呈现
```

### Step 0: 前置检查（⚠️ 必须在第一轮对话中完成）

1. **网络**：确认当前环境能访问 `speech.platform.bing.com`（edge-tts 后端），否则立即提醒用户需联网/切代理。
2. **Python**：要求 `python3 ≥ 3.9`。
3. **明确关键信息**：若用户提示缺少以下任一项，必须追问：
   - 业务场景（猎头邀约 / 催收 / 售后回访 / 客服咨询 / 面试初筛 …）
   - 主叫 / 被叫角色设定（性别、身份、姓氏）
   - 预期结果（接受 / 拒绝 / 待定 / 投诉 …）
   - 预计时长或对话轮次（默认 8–12 轮，约 1 分钟）
4. **输出文件名**：最终音频统一使用 `虚拟手机号-被叫人标识.mp3` 命名，如 `13111111111-陈先生.mp3`、`13999999999-刘女士.mp3`；若没有明确名字，则按性别退化为 `女士` / `先生`。

### Step 1: 环境初始化

```bash
source "$(dirname "$0")/scripts/env_init.sh"
```

该脚本会：
- 在 skill 根目录创建/复用 `tts_env/` 虚拟环境
- 安装 / 校验 `edge-tts` 依赖
- 导出 `CALL_SIM_WORKDIR` 指向 skill 根目录

### Step 2: 解析用户提示 → 生成通话记录 JSON

调用 `generate_record.py` 将结构化参数落盘为 `materials/<name>.json`：

```bash
python scripts/generate_record.py \
  --name "FDE 工程师面试邀约（接受版）" \
  --scenario interview_invite \
  --outcome accept \
  --caller "猎头（张）:zh-CN-XiaoxiaoNeural" \
  --callee "候选人（陈）:zh-CN-YunxiNeural" \
  --candidate-email "chen@example.com" \
  --duration "约1分钟" \
  --out materials/fde_interview_accept.json
```

**Agent 责任**：根据用户自然语言提示，构造符合以下 schema 的对话内容并写入 `conversations` 字段。允许 Agent 在 `generate_record.py` 产出的骨架基础上，通过编辑 JSON 注入具体台词（推荐：先跑一次脚本生成骨架，再用文本编辑写入台词）。

**通话记录 JSON Schema**：
```json
{
  "name": "对话名称",
  "duration": "预计时长",
  "output_file": "虚拟手机号-被叫人标识.mp3（如 13111111111-陈先生.mp3）",
  "scenario": "场景标签（可选）",
  "outcome": "accept | reject | pending | complaint | ...（可选）",
  "candidate_email": "候选人邮箱（可选，用于后续邮件邀约）",
  "conversations": [
    {
      "role": "角色名（如 猎头（张））",
      "text": "具体台词",
      "voice": "zh-CN-XiaoxiaoNeural"
    }
  ]
}
```

### Step 3: 用户确认 JSON（⚠️ 必须获得用户确认）

在生成 JSON 之后、合成音频之前，**必须**将 JSON 主要内容（至少 name / duration / conversations 轮次与台词摘要）回显给用户，并明确暂停等待确认。得到"继续 / 确认 / OK"类指令后才能进入合成步骤。

### Step 4: 调用 edge-tts 合成音频

```bash
python scripts/tts_processor.py \
  --material materials/fde_interview_accept.json \
  --output ./output
```

脚本将：
1. 读取 JSON
2. 对每个 `conversations[i]` 调用 `edge_tts.Communicate(text, voice).stream()`
3. 逐句追加拼接为完整 MP3，写入 `output/<虚拟手机号>-<被叫人标识>.mp3`

### Step 5: 结果呈现

向用户输出：
- 通话记录 JSON 的路径（`materials/<name>.json`）
- 合成音频路径（`output/<虚拟手机号>-<被叫人标识>.mp3`）
- 总对话轮次、预计时长、使用的 voice 列表
- 提醒下游可配合 `byted-arkclaw-local-batch-asr` 等 ASR skill 做回环测试

## 审查标准

执行完成后，Agent 应自检：
1. `materials/<name>.json` 是否符合 schema，`conversations` 非空且每轮都有 `role / text / voice`
2. 是否已让用户确认 JSON 内容后再发起合成
3. `output/<虚拟手机号>-<被叫人标识>.mp3` 是否成功生成且可用播放器播放
4. 文案是否避免真实姓名、真实电话、敏感信息
5. 不同角色是否使用了不同的 voice
