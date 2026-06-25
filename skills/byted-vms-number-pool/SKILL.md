---
name: byted-vms-number-pool
version: 2.0.0
description: 火山云通信通用能力层 Skill. 号码池 / 号码 / 资质三类资源管理. 当用户问号码池有哪些、要新建号码池、查/启停号码、提交或查询资质时调用. 业务层 Skill 在预检阶段也会复用本 Skill.
license: Apache-2.0
metadata:
  author: leixin.alex@bytedance.com
  homepage: https://www.volcengine.com/docs/6358/173340?lang=zh
  knowledge_base: references/vms-fundamentals.md
  openclaw:
    emoji: "🏷️"
    requires:
      env:
        - VOLC_ACCESS_KEY
        - VOLC_SECRET_KEY
    os:
      - darwin
      - linux
    triggers:
      - 号码池
      - 创建号码池
      - 更新号码池
      - 查号码
      - 反查号码池
      - 号码归属
      - 启用号码
      - 停用号码
      - 资质管理
      - 提交资质
      - 上传资质
      - 查资质
---

# byted-vms-number-pool · 号码池 / 号码 / 资质

## 环境变量

按以下优先级解析鉴权 (与其他 vms-* skill 一致):

1. `ARK_SKILL_API_KEY` + `ARK_SKILL_API_BASE` → 火山引擎 arkclaw 企业版. 请先在火山后台页面配置好 AK/SK, 由 arkclaw 注入这两个环境变量 (`ARK_SKILL_API_KEY` 为 API 密钥, `ARK_SKILL_API_BASE` 为 API 基础地址), 脚本以 `Bearer` 鉴权直连该网关, 无需本地签名;
2. `VOLC_ACCESS_KEY` + `VOLC_SECRET_KEY` (兼容 `VOLCENGINE_ACCESS_KEY`/`VOLCENGINE_SECRET_KEY`) → 个人版 arkclaw / openclaw / coco / aime / claudecode 等普通 agent, 用户直接把 AK/SK 告诉 agent, 脚本本地做 HMAC-SHA256 (Volc V4) 签名;
3. 否则报错并提示用户填入 AK/SK.

## 命令

```bash
# 1. 查号码池 (默认 SubServiceType=102 语音通知, 智能外呼填 104, 隐私号填 201~206)
#    完整枚举见 references/vms-fundamentals.md §1
python3 scripts/number_pool.py list_pool [--sub-service-type 102] [--name 北京]

# 2. 创建号码池
python3 scripts/number_pool.py create_pool \
    --name "语音通知-默认池" --sub-service-type 102 \
    --qualification-id <QualificationId> [--choose-pretty false]

# 2.1. 更新号码池 (改名/改备注/换资质)
python3 scripts/number_pool.py update_pool \
    --number-pool-no <NumberPoolNo> \
    [--name "新名称"] [--remark "新备注"] [--qualification-id <NewQualId>]

# 3. 查号码池下号码
python3 scripts/number_pool.py list_number --number-pool-no <NumberPoolNo>

# 3.0. 按手机号反查所属号码池 + 号码详情 (业务层 skill 在只拿到号码时的入口)
#      不传 --sub-service-type 会按 101~108 / 201~206 默认顺序遍历;
#      命中返回 { ok:true, NumberPoolNo, SubServiceType, Pool, Number },
#      未命中返回 { ok:false, errorCode:"NUMBER_NOT_FOUND" }.
python3 scripts/number_pool.py query_number --phone <Phone> [--sub-service-type 201]

# 3.1. 申请号码 (购号 / 入池)
#      平台未开放 OpenAPI 写入, 命令仅返回控制台引导信息.
#      请前往 https://console.volcengine.com/cloud_vms/number 页面点击「申请号码」操作.
python3 scripts/number_pool.py apply_number \
    [--number-pool-no <NumberPoolNo>] [--count 5] [--qualification-id <Id>]

# 3.2. 查申请记录 (QueryNumberApplyRecordList, 看审核进度/号码归属/数量等)
python3 scripts/number_pool.py query_apply_record \
    [--number-pool-no <NumberPoolNo>] [--sub-service-type 102] \
    [--apply-status 7] [--limit 20] [--offset 0]

# 4. 启用/停用号码
python3 scripts/number_pool.py toggle_number \
    --number-pool-no <NumberPoolNo> --phone-list <PhoneA>,<PhoneB> --enable true

# 5. 提交资质
python3 scripts/number_pool.py add_qualification \
    --payload '{"Name":"xx有限公司","QualificationType":0,"BusinessType":1,...}'

# 5.1. 上传资质材料 (营业执照/身份证 等图片或 PDF, FileUrl 必须公网可访问)
python3 scripts/number_pool.py upload_qualification_file \
    --file-url "https://your-tos.com/license.jpg" \
    --qualification-id <QualificationId> \
    --file-type 1 --file-name "营业执照"

# 6. 查资质 (单条精查)
python3 scripts/number_pool.py query_qualification [--status 1]

# 6.1. 查资质列表 (QueryQualificationList, 推荐, doc=173331)
#      支持按主体名称/状态/资质类型/业务类型筛选, 已规整 Items 字段
python3 scripts/number_pool.py list_qualification \
    [--status 1] [--name "广州"] \
    [--qualification-type 0] [--business-type 3] \
    [--limit 20] [--offset 0]

# 7. 更新资质
python3 scripts/number_pool.py update_qualification \
    --qualification-id <Id> --payload '{"BusinessType":2}'
```

## 何时被业务层 Skill 调用

- `byted-vms-voice-notify` 预检号码池 → `list_pool --sub-service-type 102`
- `byted-vms-aicall` 预检 → `list_pool --sub-service-type 104`
- `byted-vms-secret-number` 预检 → `list_pool --sub-service-type 201` (或其他隐私号子类型 202~206)
- 业务层只拿到号码 (例如 X 号、A 号) 需要 NumberPoolNo 时 → `query_number --phone <X>`,
  Agent 拿到返回里的 `NumberPoolNo` 后再去调用业务层接口 (如
  `byted-vms-secret-number query_subscription_list` / `unbind_*`).

业务层 Skill 通过 Agent 触发本 Skill 执行命令, 拿回结果后再决定下一步, **不直接 import 本包的 python**.

## 错误兜底

- 资质 `Status=0` (待审核) → 提示用户审核约 1 工作日, 期间不能创建号码池.
- 资质 `Status=2` (驳回) → 引导用户用 `update_qualification` 修改后重新提交.
- 没有任何号码池 → 引导用户先 `add_qualification` → `create_pool` → 在控制台购号 https://console.volcengine.com/cloud_vms/number .
- **申请号码 / 购号**: 平台 **未开放 OpenAPI 写入**, 用户调 `apply_number` 时
  返回控制台引导, **必须前往 https://console.volcengine.com/cloud_vms/number
  页面点击「申请号码」操作**, 提交申请单等待平台审核, 审核通过后号码自动入池.
  申请进度可用 `query_apply_record` 接口查询.
- 鉴权失败: 提示检查 AK/SK. 普通 agent (个人版 arkclaw / openclaw / coco / aime / claudecode) 检查 `VOLC_ACCESS_KEY`/`VOLC_SECRET_KEY`; 火山引擎 arkclaw 企业版需先在火山后台页面配置好 AK/SK, 再确认 `ARK_SKILL_API_KEY`/`ARK_SKILL_API_BASE` 已注入.

## 📚 基础知识 / 参数传递参考

`add_qualification` 的 `payload` 字段对资质类型 (QualificationType) /
业务类型 (BusinessType) / 主体材料字段有强约束, `create_pool` /
`update_pool` 的 SubServiceType (101/102/103/104/201~206) 不能混用.
这些通用规范沉淀在本 skill 内置的本地基础知识文档:

> `references/vms-fundamentals.md`

所有 vms-* skill 共用同一份内容. 本地加载无外网依赖, 比拉飞书更快更稳.
飞书原文 (可选): https://bytedance.sg.larkoffice.com/docx/Mv32dc0yooBn7txDxW8lsDdDgYb
