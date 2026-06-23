---
name: byted-arkclaw-jd-resume-match
version: "1.0.0"
description: "对 1 个 JD PDF 与多位候选人简历做批量文本抽取和人岗匹配评估，并可结合 ASR 转写更新画像后写入 CRM。适用于招聘初筛建档和通话后复评。"
---

# JD 与简历匹配评估（`byted-arkclaw-jd-resume-match`）

这个 skill 支持两个原子场景：
- **批量初筛**：`1 个 JD PDF + 多位候选人简历 PDF`
- **单候选人复评**：`1 个 JD PDF + 1 份简历 PDF + 1 份通话转写结果`

它先用本地脚本对 PDF 做文本抽取，再把 JD、简历、转写结果整理为统一 `bundle.json`。随后由 AI 对候选人与 JD 的匹配度、优劣势、是否建议进入下一步电话沟通进行总结，形成可审查的结构化 `assessment.json`，最后写入 `byted-arkclaw-local-hr-crm`。

## 全局唯一 Key

- 候选人必须以**电话号码**作为全局唯一 key
- 初筛建档和通话后补充录入都必须关联到同一个电话号码
- 初筛建档阶段，`prepare_match_bundle.py` 必须从**简历 PDF 转文本结果**中识别手机号
- `--phone-source`、ASR `source`、文件名只作为辅助线索，不是初筛建档的主来源
- 若任一候选人无法从简历文本中解析出手机号，分析包生成应直接失败，而不是生成无法入库的候选人记录

## 核心脚本

- `scripts/env_init.sh`：初始化 Python 环境并安装 PDF 文本抽取依赖
- `scripts/extract_pdf_text.py`：对单个 PDF 做文本抽取，优先直接提取，必要时走 OCR 回退
- `scripts/prepare_match_bundle.py`：整合 `1 个 JD + 多份简历 + 可选转写结果`，输出统一分析包
- `scripts/upsert_crm_profile.py`：把 AI 产出的单候选人或多候选人结构化画像写入 `byted-arkclaw-local-hr-crm`

## 输入与输出

### 输入

- 必填：`1 个 JD PDF`
- 初筛模式：`多位候选人简历 PDF`
- 复评模式：`单候选人简历 PDF + 通话录音 ASR 转写结果`

## 文件来源规则

- JD、简历、转写文件的位置由调用者提供
- 只需要向调用者索要文件路径，并直接使用这些路径
- 不要求调用者先把文件上传、复制或重命名到 skill 目录下
- 只有在调用者明确要求落地中间产物时，才在当前 skill 下写 `output/`

### 输出

- `bundle.json`：批量或单候选人的统一分析输入包
- `assessment.json`：AI 产出的结构化评估结果
- CRM 入库结果：候选人初筛结论或最终复评结果

## 在总流程中的位置

- 初筛阶段：负责把 `JD + 多份简历` 转为结构化候选人初筛结果，并写入 CRM 初步建档
- 通话后阶段：负责结合 `JD + 简历 + 录音转写` 更新同一候选人的匹配结论、优劣势和最终建议
- 两个阶段都必须复用同一个手机号，确保更新的是同一候选人档案

## 触发条件

在以下场景调用本 skill：
- 用户提供岗位 JD PDF 和候选人简历 PDF，希望评估匹配度
- 用户提供 `1 个 JD PDF + 多位候选人简历 PDF`，希望做批量初筛
- 用户希望结合通话录音识别结果，形成完整候选人画像
- 用户希望把评估结论、依据和转写原文写入 CRM 供后续审查

## 工作流

### Step 1: 初始化环境

```bash
cd byted-arkclaw-jd-resume-match
source ./scripts/env_init.sh
```

### Step 2: 生成分析输入包

批量初筛：

```bash
python ./scripts/prepare_match_bundle.py \
  --jd-pdf <caller_provided_jd_pdf> \
  --resume-dir <caller_provided_resume_dir> \
  --output ./output/resume_screen_bundle.json \
  --screening-stage resume_screened
```

单候选人复评：

```bash
python ./scripts/prepare_match_bundle.py \
  --jd-pdf <caller_provided_jd_pdf> \
  --resume-pdf <caller_provided_resume_pdf> \
  --transcript <caller_provided_transcript> \
  --phone-source 13999999999-刘女士.mp3 \
  --output ./output/call_review_bundle.json \
  --screening-stage call_completed
```

说明：
- `--resume-pdf` 可重复传入多次
- `--resume-dir` 会扫描目录中的 PDF
- `--resume-manifest` 支持从清单文件批量读取简历路径
- `--transcript` 支持 `txt`、`json`、`meta.json`、`summary.json`
- Agent 应先向调用者索要 JD、简历、转写文件路径，而不是要求文件先上传到 skill 目录
- 多候选人模式下，`--transcript` 和 `--phone-source` 可不传；如需传入，数量需与简历数量一致，或只传 1 个供所有候选人复用
- 每位候选人必须能解析出手机号，推荐方式是：
  - 保证简历正文中包含可识别的手机号
  - `--phone-source` 可用于补充姓名或在通话后复评时核对候选人身份
  - ASR `source` 可用于通话阶段回查原始录音

### Step 3: AI 生成评估结论

Agent 读取 `bundle.json` 后，必须输出一个 `assessment.json`，初筛模式与复评模式都至少包括：
- 候选人既往项目经验
- 技术能力总结
- 学历水平
- 工作年限是否符合 JD
- JD 匹配分
- 候选人优势与劣势
- 是否建议进入下一步电话沟通，或电话后是否建议推进
- AI 判断结论
- AI 判断依据
- 若存在通话录音，则附通话转写原文全文，不能只保留摘要

字段规范见：`references/assessment-schema.md`

### Step 4: 写入 CRM

单候选人：

```bash
python ./scripts/upsert_crm_profile.py \
  --profile-json ./output/assessment.json \
  --phone-source 13999999999-刘女士.mp3
```

多候选人：

```bash
python ./scripts/upsert_crm_profile.py \
  --profile-json ./output/assessment.json
```

批量模式下，脚本会优先从每位候选人的 `phone_source`、`candidate_hint.source_file`、`candidate_hint.phone` 中恢复候选人标识。

## 输出物

- `bundle.json`：原始抽取文本 + 候选人列表 + transcript + 候选人识别线索
- `assessment.json`：AI 结构化评估结果，可为单候选人对象或候选人列表
- CRM JSON：最终入库后的候选人画像

## 关键要求

- 结论必须区分“录音事实”和“AI 推断”
- `ai_match_evidence` 必须写明依据来自简历、JD、通话中的哪些信息
- `transcript_text` 必须以全量原始转写文本入库，供后续审查
- 初筛模式必须给出 `screening_decision`、`screening_reason`、`strengths_summary`、`weaknesses_summary`
- 通话后复评必须补充 `final_match_score`、`final_recommendation`
- `assessment.json` 中必须保留 `phone` 字段，保证后续 CRM 更新命中同一候选人
- 学历、工作年限、项目经验等关键信息不明确时，写“待确认”而不是编造
