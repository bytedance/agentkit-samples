---
name: byted-arkclaw-local-batch-asr
version: "1.0.0"
description: "基于 FunASR 的本地批量语音转写技能。可对单个文件、整个目录或 manifest 中的音视频文件进行本地转文字，并导出多种文本格式。适用于需要隐私友好的本地 ASR、批量转写或替代远程语音识别流程时。"
---

# 本地批量语音转写（`byted-arkclaw-local-batch-asr`）

基于本地 `FunASR + PyTorch` 运行批量音频/视频转文字流程，支持单文件、整个目录、或 manifest 文件列表输入，适合在 `arkclaw-hiring-workflow` 工作流中替代远程 `byted-las-asr-pro`。

## 输入与输出

### 输入

- 本地音频或视频文件
- 或包含多文件路径的目录 / manifest
- 输入文件路径由调用者提供，支持绝对路径或相对路径；不要求先上传到当前 skill 的固定目录

### 输出

- 每个文件的 `transcript.<format>`
- 每个文件的 `meta.json`
- 批次级 `summary.json`、`summary.csv`、`result.md`

## 在总流程中的位置

- 通话后阶段：负责把真实电话录音转换为可审查的转写结果
- 不负责做人岗匹配、优劣势判断或 CRM 决策，只负责稳定地产出转写文本与批处理结果

## 设计模式

本 skill 主要采用：
- **Tool Wrapper**：封装本地 Python 脚本调用
- **Pipeline**：前置检查 -> 环境初始化 -> 本地批量转写 -> 汇总结果
- **Local-first**：不依赖外部 ASR API，优先保护录音隐私

## 核心脚本与配置

- `scripts/env_init.sh`：初始化或复用本地 Python 虚拟环境，安装依赖并补齐 `ffmpeg` 入口
- `scripts/check_format.sh`：本地容器格式预检查
- `scripts/transcribe_batch.py`：批量转写主脚本
- `scripts/generate_result.md.sh`：根据批处理结果目录生成 Markdown 摘要
- `scripts/local_batch_asr_runtime/`：本地 ASR 运行时模块，包含模型加载、设备检测、格式输出

## 能力范围

- 支持输入：单文件、目录递归扫描、manifest 文本文件
- 支持格式：`wav/mp3/m4a/flac/aac/mp4/avi/mkv/mov`
- 支持输出：`txt/json/srt/ass/md`
- 支持生成汇总：`summary.json`、`summary.csv`、`result.md`
- 支持最佳努力说话人分离：若当前模型/结果不支持，将自动回退为单说话人文本
- 支持断点式批量处理：失败文件记录在汇总中，不阻断整体任务

## 工作流（严格按步骤执行）

复制此清单并跟踪进度：

```text
执行进度：
- [ ] Step 0: 前置检查
- [ ] Step 1: 初始化环境
- [ ] Step 2: 输入准备
- [ ] Step 3: 本地批量转写
- [ ] Step 4: 结果汇总
- [ ] Step 5: 结果呈现
```

### Step 0: 前置检查

1. 确认输入是本地可访问路径：单文件、目录、或 manifest 文件。
2. 优先用 `scripts/check_format.sh` 检查文件扩展名。
3. 若输入是目录，确认是否需要递归扫描，以及是否需要限制文件数。
4. 若后续要导入 CRM，建议保留源文件名，方便从文件名提取手机号与姓名。

### Step 1: 初始化环境

```bash
source "$(dirname "$0")/scripts/env_init.sh"
workdir="$LOCAL_BATCH_ASR_WORKDIR"
```

脚本会：
- 在当前 skill 下创建并使用 `.venv`
- 安装 `funasr`、`modelscope`、`torch`、`torchaudio`、`imageio-ffmpeg`、`librosa`
- 自动创建 `ffmpeg` 可执行入口

### Step 2: 输入准备

#### 单文件

```bash
./scripts/check_format.sh <caller_provided_audio_path>
```

#### 目录批量

```bash
find <caller_provided_audio_dir> -type f | sed 's#^#- #'
```

#### manifest 列表

`manifest.txt` 每行一个由调用者提供的绝对路径或相对路径：

```text
./calls/a.wav
./calls/b.mp3
./calls/call.mp4
```

### Step 3: 本地批量转写

#### 单文件

```bash
source ./scripts/env_init.sh
python ./scripts/transcribe_batch.py <caller_provided_audio_path> -f txt
```

#### 整个目录

```bash
source ./scripts/env_init.sh
python ./scripts/transcribe_batch.py <caller_provided_audio_dir> --recursive -f txt -o ./output/run_001
```

#### manifest 批量

```bash
source ./scripts/env_init.sh
python ./scripts/transcribe_batch.py --manifest <caller_provided_manifest> -f json -o ./output/run_manifest
```

### Step 4: 结果汇总

```bash
./scripts/generate_result.md.sh ./output/run_001 > ./output/run_001/result.md
```

输出目录结构：

```text
./output/run_001/
├── summary.json
├── summary.csv
├── result.md
└── files/
    ├── <stem>/
    │   ├── transcript.txt
    │   └── meta.json
```

### Step 5: 结果呈现

向用户展示：
1. 成功/失败文件数
2. 输出目录路径
3. `summary.csv` 和 `summary.json` 路径
4. 一段文本预览
5. 如果需要，可继续把结果导入 `byted-arkclaw-local-hr-crm`

## Gotchas

- 首次运行会下载模型，耗时较长且占用较大磁盘空间。
- 本地 `FunASR` 的说话人分离能力依赖模型与时间戳支持，当前实现采用“最佳努力 + 自动回退”。
- 如果只需要稳定文本，建议默认输出 `txt` 或 `json`。
- 若没有系统 `ffmpeg`，脚本会通过 `imageio-ffmpeg` 提供本地二进制入口。

## 参考资料

- `references/output-formats.md`：输出结构与汇总文件说明

## 审查标准

执行完成后，Agent 应自检：
1. `scripts/env_init.sh` 能正常初始化环境
2. `scripts/transcribe_batch.py` 能处理单文件和目录输入
3. 结果目录包含 `summary.json` / `summary.csv`
4. skill 目录中不提交 `.venv`、`output`、`__pycache__` 等生成物
