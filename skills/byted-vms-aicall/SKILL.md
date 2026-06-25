---
name: byted-vms-aicall
version: 2.0.0
description: 火山云通信智能外呼 Skill. 当用户希望「让 AI 机器人帮忙打电话办事」(如订餐厅、催收、回访、问卷) 时调用. 内部依次走话术查询 → 任务创建 → 任务结果查询.
license: Apache-2.0
metadata:
  author: leixin.alex@bytedance.com
  homepage: https://www.volcengine.com/docs/6358
  knowledge_base: references/vms-fundamentals.md
  openclaw:
    emoji: "🤖"
    requires:
      env:
        - VOLC_ACCESS_KEY
        - VOLC_SECRET_KEY
    os:
      - darwin
      - linux
    triggers:
      - 智能外呼
      - AI外呼
      - 机器人打电话
      - 帮我打电话
      - 自动外呼
      - 帮忙预订.*
      - 给.*打电话
---

# byted-vms-aicall · 火山云通信智能外呼

## 何时使用

当用户希望 AI 机器人代为外呼办事时:
- 「帮我打给 1XXXXXXXXXX 预订餐厅, 餐厅 xx, 时间 xx, 几人 xx」
- 「让机器人催一下这批欠费用户」
- 「帮我做一次满意度回访」
- 「查一下昨天那批外呼任务的结果」

## 环境变量

按以下优先级解析鉴权 (与其他 vms-* skill 一致):

1. `ARK_SKILL_API_KEY` + `ARK_SKILL_API_BASE` → 火山引擎 arkclaw 企业版. 请先在火山后台页面配置好 AK/SK, 由 arkclaw 注入这两个环境变量 (`ARK_SKILL_API_KEY` 为 API 密钥, `ARK_SKILL_API_BASE` 为 API 基础地址), 脚本以 `Bearer` 鉴权直连该网关, 无需本地签名;
2. `VOLC_ACCESS_KEY` + `VOLC_SECRET_KEY` (兼容 `VOLCENGINE_ACCESS_KEY`/`VOLCENGINE_SECRET_KEY`) → 个人版 arkclaw / openclaw / coco / aime / claudecode 等普通 agent, 用户直接把 AK/SK 告诉 agent, 脚本本地做 HMAC-SHA256 (Volc V4) 签名;
3. 否则报错并提示用户填入 AK/SK.

## 命令

```bash
# 1. 查询可用话术 (GET, 无参或可选 --scene)
python3 scripts/aicall.py list_scripts [--scene restaurant_booking]

# 2. 创建外呼任务 (POST, PhoneList 是对象数组, 由脚本根据 --phone-list + --variable-values 构造)
python3 scripts/aicall.py create_task \
    --script-id <ScriptId> \
    --phone-list "<PhoneA>,<PhoneB>" \
    --variable-values '{"餐厅":"必胜客","时间":"2026-05-29 18:00","人数":"3","备注":"靠窗"}'

# 3. 查询任务进度 / 通话结果 (GET)
python3 scripts/aicall.py query_task --task-id <TaskId>
```

## 标准执行流程

1. 从用户语义里抽取「目标号码 + 任务意图 + 关键变量」.
2. `list_scripts` 找匹配话术. 如果无, 给出已有话术列表让用户选, 或提示去控制台创建话术: https://console.volcengine.com/cloud_vms/aicall .
3. 直接调用 `create_task` 创建任务, 返回 `TaskId`. **无需选号码池**: 平台按话术绑定的默认号码池自动选号.
4. 用户后续问进度时, 用 `query_task` 拉结果, 返回任务进度、通话明细 (含 ASR、意图标签、通话时长等).

## 错误兜底

- `RESOURCE_NOT_FOUND` (话术不存在) → 返回当前可用话术列表.
- 鉴权失败 → 提示检查 AK/SK. 普通 agent (个人版 arkclaw / openclaw / coco / aime / claudecode) 检查 `VOLC_ACCESS_KEY`/`VOLC_SECRET_KEY`; 火山引擎 arkclaw 企业版需先在火山后台页面配置好 AK/SK, 再确认 `ARK_SKILL_API_KEY`/`ARK_SKILL_API_BASE` 已注入.

## 参考

- 火山云通信智能外呼官方文档: https://www.volcengine.com/docs/6358

## 📚 基础知识 / 参数传递参考

调用任何 action 前 (尤其是 `create_task` 的 `PhoneList` / `VariableValues` 字段构造),
请先阅读本 skill 内置的本地基础知识文档:

> `references/vms-fundamentals.md`

该文档覆盖 SubServiceType 枚举 / 号码状态映射 / CallId 格式 / 录音 CDN /
出口 IP 白名单等通用规范, 所有 vms-* skill 共用同一份内容. 本地文件在外网受限
环境也能用, 性能优于远程拉取. 若需对照原始版本, 可回看飞书原文:
https://bytedance.sg.larkoffice.com/docx/Mv32dc0yooBn7txDxW8lsDdDgYb
