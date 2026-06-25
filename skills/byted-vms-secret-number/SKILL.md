---
name: byted-vms-secret-number
version: 2.0.0
description: 火山云通信隐私号 Skill. 管理 AXB / AXN / AXNE / AXG 等绑定关系生命周期, 不负责发起呼叫. 用户表达「绑定隐私号」「中间号」「号码保护」「解绑」「查绑定关系」时调用.
license: Apache-2.0
metadata:
  author: leixin.alex@bytedance.com
  homepage: https://www.volcengine.com/docs/6358/172141?lang=zh
  knowledge_base: references/vms-fundamentals.md
  openclaw:
    emoji: "🛡️"
    requires:
      env:
        - VOLC_ACCESS_KEY
        - VOLC_SECRET_KEY
    os:
      - darwin
      - linux
    triggers:
      - 隐私号
      - 中间号
      - 号码保护
      - AXB绑定
      - AXN绑定
      - AXNE绑定
      - 绑定隐私号
      - 解绑.*隐私号
      - 查.*绑定关系
---

# byted-vms-secret-number · 火山云通信隐私号

只处理「绑定关系生命周期」: 创建 / 解绑 / 查询. 真实通话由 A → X → B 触发, Skill 不发起呼叫.

## 环境变量

按以下优先级解析鉴权 (与其他 vms-* skill 一致):

1. `ARK_SKILL_API_KEY` + `ARK_SKILL_API_BASE` → 火山引擎 arkclaw 企业版. 请先在火山后台页面配置好 AK/SK, 由 arkclaw 注入这两个环境变量 (`ARK_SKILL_API_KEY` 为 API 密钥, `ARK_SKILL_API_BASE` 为 API 基础地址), 脚本以 `Bearer` 鉴权直连该网关, 无需本地签名;
2. `VOLC_ACCESS_KEY` + `VOLC_SECRET_KEY` (兼容 `VOLCENGINE_ACCESS_KEY`/`VOLCENGINE_SECRET_KEY`) → 个人版 arkclaw / openclaw / coco / aime / claudecode 等普通 agent, 用户直接把 AK/SK 告诉 agent, 脚本本地做 HMAC-SHA256 (Volc V4) 签名;
3. 否则报错并提示用户填入 AK/SK.

## 命令

```bash
# AXB 指定 X 号绑定
python3 scripts/secret_number.py bind_axb \
    --phone-a <PhoneA> --phone-b <PhoneB> --phone-x <PhoneX> \
    --number-pool-no <NumberPoolNo> [--expire-time 2592000] \
    [--record-flag 1] [--asr-flag 0]

# 平台选号 + AXB 绑定 (推荐, 不用预先指定 X)
python3 scripts/secret_number.py select_and_bind_axb \
    --phone-a <PhoneA> --phone-b <PhoneB> \
    --number-pool-no <NumberPoolNo> [--city-code 010]

# AXN 指定 X 号绑定
python3 scripts/secret_number.py bind_axn \
    --phone-a <PhoneA> --phone-x <PhoneX> \
    --number-pool-no <NumberPoolNo>

# 平台选号 + AXN 绑定 (推荐)
python3 scripts/secret_number.py select_and_bind_axn \
    --phone-a <PhoneA> --phone-b <PhoneB> \
    --number-pool-no <NumberPoolNo> [--city-code 010] \
    [--expire-time 2592000] [--audio-record-flag 0] \
    [--city-code-by-phone-no A|B] [--random-flag false]

# AXNE 带分机号
python3 scripts/secret_number.py bind_axne \
    --phone-a <PhoneA> --phone-x <PhoneX> --phone-b <PhoneB> \
    --extension 8001 --number-pool-no <NumberPoolNo>

# 解绑 (AXB / AXN / AXNE 各自独立 Action, 任选其一)
python3 scripts/secret_number.py unbind_axb --sub-id <SubId> --number-pool-no <NumberPoolNo>
python3 scripts/secret_number.py unbind_axn --sub-id <SubId> --number-pool-no <NumberPoolNo>
python3 scripts/secret_number.py unbind_axne --sub-id <SubId> --number-pool-no <NumberPoolNo>

# 查询绑定关系 (单条, 服务端强制按 SubId 精查)
python3 scripts/secret_number.py query_subscription --sub-id <SubId>

# 批量查询绑定关系列表 (QuerySubscriptionForList)
# --number-pool-no 必填. 若用户只给了 X 号, 先调 byted-vms-number-pool 的
# `query_number --phone <X>` 反查号码所属号码池, 拿到 NumberPoolNo 后再回到本 skill.
python3 scripts/secret_number.py query_subscription_list \
    --number-pool-no <NumberPoolNo> \
    [--phone-a <PhoneA>] [--phone-b <PhoneB>] [--phone-x <PhoneX>] \
    [--sub-type AXB|AXN|AXNE] [--limit 20] [--offset 0]
```

## 关键差异 (相对语音通知)

- 用户没指定 X 号 → 用 `select_and_bind_axb` (`SelectNumberAndBindAXB`), 让平台依据 `--city-code` 同城选号.
- `--expire-time` 是绑定生命周期, 接受两种写法: ① **相对秒数** (`< 1e9`, 例如 `2592000` = 30 天后过期), skill 会自动叠加当前时间戳; ② **绝对秒级 unix 时间戳** (`>= 1e9`), 直接透传到 TOP. 默认 30 天. TOP 端要求最终值至少比当前时间晚 60 秒, 否则返回 `ExpireTime must be 1 minute later`. 用户说「半年」「3 个月」时, 用相对秒数即可 (例如 180 天 = `15552000`).
- `--record-flag` 控制是否对该绑定关系开启录音, `--asr-flag` 控制是否开启 ASR 识别.

## 标准执行流程

1. 从用户语义抽取 A / B 号码、可选 X、过期时长、是否录音.
2. 通过 **byted-vms-number-pool** 查隐私号号码池: 隐私号 SubServiceType 是 201~206 (`201` AXB / `202` AXN / `203` AXNE / `204` AXYB / `205` PAXYB / `206` AXG), 通常用 `--sub-service-type 201`. 没有就引导用户去 https://console.volcengine.com/cloud_vms/number 申请号码池+号码.
3. 默认走 `select_and_bind_axb`. 用户明确「我要用某个特定 X 号」才走 `bind_axb`.
4. 返回 `SubId` + `PhoneNoX` 给用户; 后续解绑/排查时拿 `SubId` 调 `unbind_axb` 或 `query_subscription`.
5. 用户只给出某个号码 (常见是 X 号) 要查绑定关系时, 先调度 **byted-vms-number-pool**
   的 `query_number --phone <号码>` 拿到 `NumberPoolNo` (返回里还会带
   `SubServiceType` / `Pool` / `Number` 详情), 再回到本 skill 执行
   `query_subscription_list --number-pool-no <NumberPoolNo> --phone-x <号码>`.
   不在本 skill 内部直接调 NumberPoolList / NumberList, 保持原子能力分层.

## 错误兜底

- 鉴权失败: 提示检查 AK/SK. 普通 agent (个人版 arkclaw / openclaw / coco / aime / claudecode) 检查 `VOLC_ACCESS_KEY`/`VOLC_SECRET_KEY`; 火山引擎 arkclaw 企业版需先在火山后台页面配置好 AK/SK, 再确认 `ARK_SKILL_API_KEY`/`ARK_SKILL_API_BASE` 已注入.
- `NOT_IN_NUMBER_POOL`: 号码池下无可用 X 号 → 引导用户去 https://console.volcengine.com/cloud_vms/number 增购隐私号.
- `QUALIFICATION_*`: 资质问题 → https://console.volcengine.com/cloud_vms/qualification.

## 参考

- 隐私号官方文档: https://www.volcengine.com/docs/6358/172141?lang=zh
- [SelectNumberAndBindAXN](https://www.volcengine.com/docs/6358/172141?lang=zh)
- [QuerySubscriptionForList](https://www.volcengine.com/docs/6358/172141?lang=zh)
- [UnbindAXB / UnbindAXN / UnbindAXNE](https://www.volcengine.com/docs/6358/172141?lang=zh)

## 📚 基础知识 / 参数传递参考

`bind_axb` / `bind_axn` / `bind_axne` 的 `--expire-time` 支持相对秒数 (默认 30 天)
或绝对秒级 unix 时间戳, skill 会自动归一化, 同步参考下面 §错误兜底.
`--record-flag` / `--asr-flag` 取值, `--city-code-by-phone-no` 的 A/B 选号
策略, 以及隐私号 SubServiceType (201~206) 的区分等通用规范, 都沉淀在本 skill
内置的本地基础知识文档:

> `references/vms-fundamentals.md`

所有 vms-* skill 共用同一份内容, 本地加载无外网依赖.
飞书原文 (可选): https://bytedance.sg.larkoffice.com/docx/Mv32dc0yooBn7txDxW8lsDdDgYb
