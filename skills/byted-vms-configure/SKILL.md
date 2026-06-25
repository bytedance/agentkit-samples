---
name: byted-vms-configure
version: 2.0.0
description: 火山云通信「通用配置」Skill (通用层). 仅负责跨业务的号码可呼性 / 风控 / 主叫鉴权类查询 QueryRiskDenyInfo / QueryCanCall / QueryAuth. 注意 所有 TTS 模板操作 (创建/更新/删除/查询) 以及录音文件 / 通用资源管理 (create_voice / query_voice / delete_voice / get_upload_url / submit_upload / list_resource / list_usable / update_resource / delete_resource) 均已迁移到 byted-vms-voice-notify (语音通知) skill, 本 skill 不再提供任何 TTS 或录音/资源入口.
license: Apache-2.0
metadata:
  author: leixin.alex@bytedance.com
  homepage: https://www.volcengine.com/docs/6358/172143?lang=zh
  knowledge_base: references/vms-fundamentals.md
  openclaw:
    emoji: "⚙️"
    requires:
      env:
        - VOLC_ACCESS_KEY
        - VOLC_SECRET_KEY
    os:
      - darwin
      - linux
    triggers:
      - 风控黑名单
      - 号码可呼叫
      - 号码鉴权
      - QueryRiskDenyInfo
      - QueryCanCall
      - QueryAuth
---

# byted-vms-configure · 火山云通信 跨业务通用查询/校验

通用能力层 Skill, 只封装火山云通信 TOP **跨业务**的号码状态 / 鉴权类查询接口:

- 风控黑名单: `QueryRiskDenyInfo`
- 号码可呼叫综合状态: `QueryCanCall`
- 主叫鉴权 (Click2Call): `QueryAuth`

> **不再包含**任何 TTS / 录音 / 通用资源 (list_resource / list_usable / update_resource / delete_resource / get_upload_url / submit_upload) 入口, 全部已迁移至 `byted-vms-voice-notify` skill.

## 何时使用

用户出现以下表达时直接调用本 skill:

- 「这个号码在风控黑名单里吗」「号码命中黑名单吗」
- 「这个号码现在能不能呼叫」「批量校验一批号码可呼性」
- 「查一下主叫鉴权状态」「Click2Call 主叫鉴权」

**不要**用本 skill 处理 TTS 或录音/资源:

| 用户诉求 | 该走的 skill / 命令 |
|----------|---------------------|
| 创建 / 删除 / 查询 TTS 模板 | `byted-vms-voice-notify` 的 `open_create_tts` / `delete_tts` / `list_resource --type 1` (改名/改文案不支持, 走控制台) |
| 上传 / 删除 / 查询录音, 录音直传 | `byted-vms-voice-notify` 的 `create_voice` / `query_voice` / `delete_voice` / `get_upload_url` + `submit_upload` |
| 列出录音 / IVR / TTS, 改名, 通用删除 | `byted-vms-voice-notify` 的 `list_resource` / `list_usable` / `update_resource` / `delete_resource` |

## 环境变量

按以下优先级解析鉴权 (与其他 vms-* skill 一致):

1. `ARK_SKILL_API_KEY` + `ARK_SKILL_API_BASE` → 火山引擎 arkclaw 企业版. 请先在火山后台页面配置好 AK/SK, 由 arkclaw 注入这两个环境变量 (`ARK_SKILL_API_KEY` 为 API 密钥, `ARK_SKILL_API_BASE` 为 API 基础地址), 脚本以 `Bearer` 鉴权直连该网关, 无需本地签名;
2. `VOLC_ACCESS_KEY` + `VOLC_SECRET_KEY` (兼容 `VOLCENGINE_ACCESS_KEY`/`VOLCENGINE_SECRET_KEY`) → 个人版 arkclaw / openclaw / coco / aime / claudecode 等普通 agent, 用户直接把 AK/SK 告诉 agent, 脚本本地做 HMAC-SHA256 (Volc V4) 签名;
3. 否则报错并提示用户填入 AK/SK.

## 核心命令

```bash
# 1. 查号码是否在平台风控黑名单 (默认明文)
python3 scripts/configure.py query_risk_deny --mobile 13800138000 \
    [--account-request-id biz-uuid-xxx] [--encrypt-type 0|1]

# 2. 查号码当前是否可被呼叫 (综合状态), 多个用逗号分隔
python3 scripts/configure.py query_can_call --numbers 13800138000,13900139000 \
    [--business-line-id 1] [--call-type 1]

# 3. 查主叫鉴权状态 (Click2Call 主叫必填鉴权), Phone 需 AES 加密后再传入
python3 scripts/configure.py query_auth --phone <AES_ENCRYPTED_PHONE>
```

## 标准执行流程

### 风控/可呼叫性预检 (业务下游推荐前置)

1. `query_risk_deny`: 单号码命中平台黑名单直接返回拒绝, 业务可在落库前剔除;
2. `query_can_call`: 多号码批量综合校验 (号码归属 / 黑名单 / 禁呼时段等), 适合外呼任务前批量过滤;
3. `query_auth`: Click2Call 场景下主叫号码鉴权状态校验.

## 错误兜底

- `OperationDenied`: 语音服务未开通 → https://console.volcengine.com/cloud_vms.
- `NOT_AUTH`: 账号未实名 → https://console.volcengine.com/user/authentication/enterprise/.
- `BLACK_LIST_PHONE`: 命中平台黑名单 → 业务侧需在外呼前用 `query_risk_deny` / `query_can_call` 预检.
- 鉴权失败: 提示检查 AK/SK. 普通 agent (个人版 arkclaw / openclaw / coco / aime / claudecode) 检查 `VOLC_ACCESS_KEY`/`VOLC_SECRET_KEY`; 火山引擎 arkclaw 企业版需先在火山后台页面配置好 AK/SK, 再确认 `ARK_SKILL_API_KEY`/`ARK_SKILL_API_BASE` 已注入.

错误码到提示的映射在 `scripts/_topclient.py` 的 `ERROR_MAP` 中, 失败时脚本会输出 `errorCode + suggest`.

## 参考接口

- [QueryRiskDenyInfo](https://www.volcengine.com/docs/6358/172143?lang=zh)
- [QueryCanCall](https://www.volcengine.com/docs/6358/172143?lang=zh)
- [QueryAuth](https://www.volcengine.com/docs/6358/172139?lang=zh)

## 📚 基础知识 / 参数传递参考

`query_auth` 的 `Phone` 字段需 AES 加密, `query_can_call` 的批量号码格式、
`encrypt_type` 取值等通用规范, 都沉淀在本 skill 内置的本地基础知识文档:

> `references/vms-fundamentals.md`

该文档覆盖鉴权 / 加解密 / 错误码 / SubServiceType / 号码状态映射 / 出口 IP
白名单等. 所有 vms-* skill 共用同一份内容, 本地加载无外网依赖.
飞书原文 (可选): https://bytedance.sg.larkoffice.com/docx/Mv32dc0yooBn7txDxW8lsDdDgYb

