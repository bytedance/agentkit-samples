---
name: byted-arkclaw-local-hr-crm
displayName: 候选人CRM数据库
description: 基于 JSON 文件的候选人 CRM 工具，支持初筛建档、通话后更新、查询和导出。适用于保存简历画像、ASR 转写原文、匹配结论及其依据。
version: "1.0.0"
category: 数据管理/CRM
author: 系统
icon: 📋
parameters:
  - name: action
    type: string
    required: true
    description: "操作类型：upsert（新增或更新候选人）/query（查询候选人）/list（列出全部候选人）/export（导出Markdown报表）"
  - name: phone
    type: string
    required: false
    description: "候选人电话号码（upsert和query时必填），兼容 `13812341234`、`13812341234-刘`、`13812341234-刘.mp3`"
  - name: candidate_name
    type: string
    required: false
    description: "候选人姓名，未显式传入时可从文件名中解析"
  - name: email
    type: string
    required: false
    description: "候选人邮箱，优先从简历文本中抽取，用于后续邮件邀约"
  - name: is_qualified
    type: bool
    required: false
    description: "是否为有效候选人"
  - name: gender
    type: string
    required: false
    description: "候选人性别：男/女/未知"
  - name: industry
    type: string
    required: false
    description: "所在行业，如：互联网、金融、制造业、教育"
  - name: current_position
    type: string
    required: false
    description: "当前职位，如：高级Java工程师、产品总监"
  - name: years_of_exp
    type: int
    required: false
    description: "工作年限"
  - name: job_switch_intent
    type: string
    required: false
    description: "跳槽意向：高/中/低"
  - name: candidate_focus
    type: string
    required: false
    description: "候选人关注重点，如：薪资涨幅、晋升空间、工作地点、远程办公"
  - name: notes
    type: string
    required: false
    description: "备注信息"
  - name: transcript_text
    type: string
    required: false
    description: "音频转写原文，入库后用于后续审查与复核"
  - name: project_experience
    type: string
    required: false
    description: "候选人既往项目经验总结"
  - name: technical_capability
    type: string
    required: false
    description: "候选人技术能力总结"
  - name: education_level
    type: string
    required: false
    description: "学历水平，如本科/硕士/博士"
  - name: jd_years_match
    type: string
    required: false
    description: "工作年限是否符合JD要求，如符合/部分符合/不符合/待确认"
  - name: jd_match_score
    type: int
    required: false
    description: "JD匹配分，范围0-100"
  - name: ai_match_conclusion
    type: string
    required: false
    description: "AI 对候选人与 JD 匹配度的结论"
  - name: ai_match_evidence
    type: string
    required: false
    description: "AI 判断依据，需写明来自简历、JD、录音的哪些信息"
---
# 候选人CRM数据库 Skill

## 功能说明
基于本地 JSON 文件实现轻量级候选人关系管理，支持候选人档案的增删改查与报表导出。以电话号码为唯一 key，适用于招聘猎头场景下的候选人画像存储与检索；支持保存邮箱，供后续邮件邀约复试使用，并可把音频转写原文、项目经验、技术能力、学历、初筛结论、最终结论与依据一并写入数据库供后续审查。

## 输入与输出

### 输入

- 初筛建档阶段：
  - 候选人标识：`phone`，且它是全局唯一 key
  - 简历侧字段：`email`、`project_experience`、`technical_capability`、`education_level`、`years_of_exp`
  - 初筛判断字段：`screening_stage`、`screening_decision`、`screening_reason`、`strengths_summary`、`weaknesses_summary`、`jd_match_score`
- 通话后更新阶段：
  - 必须复用同一个 `phone`
  - 录音转写字段：`transcript_text`
  - 通话补充字段：`job_switch_intent`、`candidate_focus`、`notes`
  - 最终判断字段：`final_match_score`、`final_recommendation`、`ai_match_conclusion`、`ai_match_evidence`

### 输出

- `upsert`：返回单个候选人的最新画像摘要
- `query`：返回候选人的完整画像与转写原文
- `list`：返回候选人列表概览
- `export`：返回招聘者可读的 Markdown 报表

## 在总流程中的位置

- 初筛阶段：接收 `byted-arkclaw-jd-resume-match` 产出的结构化画像，完成候选人初步建档
- 通话后阶段：接收 `byted-arkclaw-local-batch-asr` 与 AI 复评结果，对同一候选人做增量更新
- 无论是初步建档还是后续补录，CRM 都只以电话号码为唯一 key，不允许用文件名或姓名替代唯一标识

## 设计模式
本 skill 主要采用：
- **Tool Wrapper**：封装 Python 脚本调用
- **数据持久化**：本地 JSON 文件存储

## 核心脚本
所有功能脚本位于 `scripts/` 目录：
- `scripts/main.py`: 主脚本，提供 `upsert`/`query`/`list`/`export` 四种操作

## 配置说明
CRM 数据文件路径及字段默认值，详见 `config.yaml`

## 触发条件
- 通话录音分析完成后，需要录入候选人数据
- JD 与简历批量初筛完成后，需要对候选人做初步建档
- 用户查询某候选人信息：「查一下 13812341234 的候选人画像」
- 需要导出候选人列表或生成汇总报表

## 使用方法

### 前置准备
确保 Python 3 环境可用，无需额外依赖（使用标准库）。

### 调用示例

#### 1. 新增或更新候选人 (upsert)
```bash
# 完整字段示例
python scripts/main.py --action upsert --phone 13812341234 --candidate_name 刘女士 --email liu@example.com --is_qualified true --gender 男 --industry 互联网 --current_position 高级Java工程师 --years_of_exp 8 --job_switch_intent 高 --candidate_focus 薪资涨幅、技术栈匹配 --notes "目前在职，期望薪资涨幅30%" --transcript_text "您好，请问是刘女士吗？..." --project_experience "负责支付平台和风控平台建设" --technical_capability "Java、Spring Cloud、MySQL、Kafka" --education_level 本科 --jd_years_match 符合 --jd_match_score 82 --ai_match_conclusion "技术和项目背景较贴合 JD" --ai_match_evidence "简历中有 8 年后端经验，录音中确认做过云原生部署"

# 部分字段示例（仅更新特定字段）
python scripts/main.py --action upsert --phone 13812341234 --job_switch_intent 中

# 从音频文件名解析电话号码与姓名
python scripts/main.py --action upsert --phone 13999999999-刘女士.mp3 --gender 女 --industry 金融 --current_position 风控经理
```

#### 2. 查询候选人 (query)
```bash
python scripts/main.py --action query --phone 13812341234
python scripts/main.py --action query --phone 13999999999-刘女士.mp3
```

#### 3. 列出全部候选人 (list)
```bash
python scripts/main.py --action list
```

#### 4. 导出 Markdown 报表 (export)
```bash
python scripts/main.py --action export
```

## 参数说明
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| action | string | 是 | 操作类型：`upsert`/`query`/`list`/`export` |
| phone | string | 条件必填 | 候选人电话号码，兼容 `手机号` / `手机号-姓名` / `手机号-姓名.mp3` |
| candidate_name | string | 否 | 候选人姓名；若未提供，可从文件名解析 |
| email | string | 否 | 候选人邮箱，通常来自简历文本抽取 |
| is_qualified | bool | 否 | 是否为有效候选人 |
| gender | string | 否 | 候选人性别：`男`/`女`/`未知` |
| industry | string | 否 | 所在行业 |
| current_position | string | 否 | 当前职位 |
| years_of_exp | int | 否 | 工作年限 |
| job_switch_intent | string | 否 | 跳槽意向：`高`/`中`/`低` |
| candidate_focus | string | 否 | 关注重点 |
| notes | string | 否 | 备注信息 |
| transcript_text | string | 否 | 音频转写原文，保存到数据库供后续审查 |
| project_experience | string | 否 | 候选人既往项目经验总结 |
| technical_capability | string | 否 | 候选人技术能力总结 |
| education_level | string | 否 | 学历水平 |
| jd_years_match | string | 否 | 工作年限是否符合 JD |
| jd_match_score | int | 否 | JD 匹配分，范围 `0-100` |
| ai_match_conclusion | string | 否 | AI 对候选人与 JD 匹配度的结论 |
| ai_match_evidence | string | 否 | AI 判断依据 |

## 返回示例

### upsert
```
✅ 候选人 138****1234 数据已更新
  姓名: 刘女士 | 邮箱: liu@example.com | 有效候选人: 是
  性别: 男 | 行业: 互联网 | 职位: 高级Java工程师
  工作年限: 8年
  跳槽意向: 高
  关注重点: 薪资涨幅、技术栈匹配
  项目经验: 负责支付平台和风控平台建设
  技术能力: Java、Spring Cloud、MySQL、Kafka
  学历水平: 本科 | 年限匹配: 符合 | 匹配分: 82分
  AI结论: 技术和项目背景较贴合 JD
  AI依据: 简历中有 8 年后端经验，录音中确认做过云原生部署
  转写原文: 已保存
  更新时间: 2026-04-19 10:00
```

### query
```
📋 候选人 138****1234 档案
  姓名: 刘女士 | 邮箱: liu@example.com | 有效候选人: 是 | 性别: 男
  行业: 互联网 | 职位: 高级Java工程师 | 工作年限: 8年
  跳槽意向: 高
  关注重点: 薪资涨幅、技术栈匹配
  项目经验: 负责支付平台和风控平台建设
  技术能力: Java、Spring Cloud、MySQL、Kafka
  学历水平: 本科
  JD年限匹配: 符合 | JD匹配分: 82分
  AI结论: 技术和项目背景较贴合 JD
  AI依据: 简历中有 8 年后端经验，录音中确认做过云原生部署
  最近通话: 2026-04-19
  备注: 目前在职，期望薪资涨幅30%，可接受北京上海
  转写原文:
    您好，请问是刘女士吗？我是猎头顾问...
```

### list
```
📊 全部候选人列表 (2人)
  [1] 138****1234 - 刘女士 - 男 - 互联网 - 高级Java工程师 - 8年 - 高意向
  [2] 139****5678 - 王女士 - 女 - 金融 - 风控经理 - 5年 - 低意向
```

### export
```markdown
| 电话号码 | 姓名 | 邮箱 | 有效候选人 | 性别 | 行业 | 职位 | 工作年限 | 学历 | JD年限匹配 | JD匹配分 | AI结论 | 最近通话 |
|----------|------|------|-----------|------|------|------|---------|------|------------|----------|--------|----------|
| 138****1234 | 刘女士 | liu@example.com | 是 | 男 | 互联网 | 高级Java工程师 | 8 | 本科 | 符合 | 82 | 技术和项目背景较贴合 JD | 2026-04-19 |
| 139****5678 | 王女士 | wang@example.com | 否 | 女 | 金融 | 风控经理 | 5 | 本科 | 部分符合 | 64 | 经验方向相关但技术栈有偏差 | 2026-04-18 |
```
