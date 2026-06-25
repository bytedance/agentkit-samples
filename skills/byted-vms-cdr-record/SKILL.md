---
name: byted-vms-cdr-record
version: 2.0.0
description: 火山云通信话单 / 录音查询 Skill. 用户问「查一下 callId xxx 的话单」「下载 xxx 的录音」时调用. 注意TOP 接口仅支持按 CallId 精确查询, 不支持按 SingleOpenId/手机号/时间区间反查.
license: Apache-2.0
metadata:
  author: leixin.alex@bytedance.com
  homepage: https://www.volcengine.com/docs/6358/166398?lang=zh
  knowledge_base: references/vms-fundamentals.md
  openclaw:
    emoji: "📋"
    requires:
      env:
        - VOLC_ACCESS_KEY
        - VOLC_SECRET_KEY
    os:
      - darwin
      - linux
    triggers:
      - 查话单
      - 查询话单
      - 通话记录
      - 下载录音
      - 录音文件
      - 录音下载链接
      - callId.*话单
---

# byted-vms-cdr-record · 火山云通信话单/录音查询

## 环境变量

按以下优先级解析鉴权 (与其他 vms-* skill 一致):

1. `ARK_SKILL_API_KEY` + `ARK_SKILL_API_BASE` → 火山引擎 arkclaw 企业版. 请先在火山后台页面配置好 AK/SK, 由 arkclaw 注入这两个环境变量 (`ARK_SKILL_API_KEY` 为 API 密钥, `ARK_SKILL_API_BASE` 为 API 基础地址), 脚本以 `Bearer` 鉴权直连该网关, 无需本地签名;
2. `VOLC_ACCESS_KEY` + `VOLC_SECRET_KEY` (兼容 `VOLCENGINE_ACCESS_KEY`/`VOLCENGINE_SECRET_KEY`) → 个人版 arkclaw / openclaw / coco / aime / claudecode 等普通 agent, 用户直接把 AK/SK 告诉 agent, 脚本本地做 HMAC-SHA256 (Volc V4) 签名;
3. 否则报错并提示用户填入 AK/SK.

## 重要前置说明 (TOP 限制)

`QueryCallRecordMsg` / `QueryAudioRecordFileUrl` 这两个接口在 TOP 网关上有以下硬约束 (实测):

- **必须传 `CallIdList` (form-urlencoded)**, 服务端校验直接报 `Required List parameter 'CallIdList' is not present`;
- **不接受按手机号 / 时间区间 / SingleOpenId 反查**;
- `SingleBatchAppend` 返回的是 `SingleOpenId` 而**不是 `CallId`**, 这两者是不同字段, 无法相互转换.

因此, 想拿到 `CallId` 必须依赖以下两条之一:

1. **平台异步回调**: 火山通信会在通话结束时把含 `CallId` 的话单 push 到业务方配置的回调地址;
2. **业务侧持久化**: 业务后端在收到回调时把 `single_open_id ↔ call_id` 映射存到自己的存储中, 后续按 SingleOpenId 反查 CallId.

如果用户只有 `SingleOpenId` 或被叫号码, 没有 `CallId`, **不要尝试调用本 skill 的 `query_cdr`**, 应明确告知用户该限制并引导其去控制台 https://console.volcengine.com/cloud_vms/cdrList 查看, 或在业务侧用 SingleOpenId 反查 CallId, 又或者改用 `query_sip_record` (按被叫/主叫 + 时间窗) 查列表.

## 命令

```bash
# 1. 按 callId 精确查话单 (V1, CallIdList 必填, 实际走 form-urlencoded)
python3 scripts/cdr_record.py query_cdr --call-id <CallId> \
    [--business-type voiceNotify|privacyNumber|aicall] \
    [--limit 20] [--offset 0]

# 1.1. 按 callId 批量查话单 (V2, JSON body, 单次最多 100 条)
python3 scripts/cdr_record.py query_cdr_v2 --call-id <CallId1,CallId2,...>

# 2. 按被叫/主叫 + 时间窗列表查话单 (QuerySipRecord, 不需要 CallId)
python3 scripts/cdr_record.py query_sip_record \
    [--callee <CalleePhone>] [--caller <CallerPhone>] \
    [--begin-time-lower "2026-05-22 00:00:00"] \
    [--begin-time-upper "2026-05-28 23:59:59"] \
    [--sub-service-type 102] [--number-pool-no <NumberPoolNo>] \
    [--call-status ANSWERED] [--limit 20] [--offset 0]

# 3. 获取录音文件下载 URL (顶层返回 DownloadUrl, 可直接复制下载)
python3 scripts/cdr_record.py query_record_url --call-id <CallId> \
    [--business-type privacyNumber] [--expire-time 3600] \
    [--save-to ~/Downloads/<CallId>.wav]   # 可选: 直接落到本地

# 4. 获取录音 ASR 转文本下载 URL (V2, 单次最多 100 条)
python3 scripts/cdr_record.py query_asr_url --call-id <CallId1,CallId2,...>
```

## 标准流程

1. 用户给 `callId` → 直接 `query_cdr` 单条精查 + 必要时 `query_record_url` 拉录音.
2. 用户**只**给 `SingleOpenId` / 手机号 / 时间区间 → 走「兜底」一节, 不要盲目调本 skill.
3. URL 有过期时间, 默认遵循平台值, 可用 `--expire-time` 覆盖.

## 关键字段

返回字段一般包含: `CallId / StartTime / RingTime / AnswerTime / EndTime / Duration / BillSec / CallStatus / Direction / PhoneA / PhoneX / PhoneB / SubsId`. 录音字段包含 `RecordFileUrl / RecordDuration / FileSize`.

判断接通: `AnswerTime` 非空 / `BillSec > 0` / `CallStatus == ANSWERED`.

## 错误兜底

- `Required List parameter 'CallIdList' is not present` → 你忘了传 `--call-id` 或 SingleOpenId 当 CallId 用了, 见上方限制.
- `Result: []` → CallId 不存在 / 不属于本账号 / 在话单回调入库前就被查 (有秒级延迟).
- 录音不存在 → 该次通话未开启录音, 检查绑定关系的 `RecordFlag`.
- 控制台兜底: https://console.volcengine.com/cloud_vms/cdrList .
- 鉴权失败: 提示检查 AK/SK. 普通 agent (个人版 arkclaw / openclaw / coco / aime / claudecode) 检查 `VOLC_ACCESS_KEY`/`VOLC_SECRET_KEY`; 火山引擎 arkclaw 企业版需先在火山后台页面配置好 AK/SK, 再确认 `ARK_SKILL_API_KEY`/`ARK_SKILL_API_BASE` 已注入.

## 📚 基础知识 / 参数传递参考

构造 `CallIdList` / `BusinessType` / 时间区间 / 加密字段前, 请先阅读本 skill
内置的本地基础知识文档:

> `references/vms-fundamentals.md`

该文档覆盖 SubServiceType 枚举 (101/102/103/104/201~206) / 号码状态映射 /
CallId 各业务前缀 / 录音 CDN host / 出口 IP 白名单等通用规范.
所有 vms-* skill 共用同一份内容, 本地加载无外网依赖. 飞书原文 (可选):
https://bytedance.sg.larkoffice.com/docx/Mv32dc0yooBn7txDxW8lsDdDgYb
