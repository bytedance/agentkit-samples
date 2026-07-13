---
name: byted-volcengine-finops
description: 火山引擎费用中心账单分析技能，根据用户场景，使用 Python SDK 查询账单明细、成本账单明细、账号汇总、产品汇总与分账账单，支持按账期、分摊月、日期、产品、账号、实例、分拆项进行多维度的账单分析。
---

# 火山引擎账单 Skill

这个 Skill 用于通过火山引擎 Python SDK 查询费用中心账单数据，并围绕账期、分摊月、日期、实例、产品、账号、分账维度做汇总分析。

## 何时使用此 Skill

当用户要求：

- 分析火山引擎账单、成本和消费趋势的时候
- 查询账号维度账单总览信息的时候
- 查询产品维度成本分布的时候
- 核对账单明细、实例费用或账单类型的时候
- 查询分摊后成本、摊销成本或成本账单明细的时候
- 查询分账账单、分拆项费用或分摊结果的时候

## 主要功能

### 1. 账号账单总览查询

- 使用 `ListBillOverviewByCategory` 查询账号维度账单总览
- 适合先看整月整体账单金额和大盘趋势

### 2. 产品月度账单查询

- 使用 `ListBillOverviewByProd` 查询单产品、多产品、全量产品月度账单
- 支持分页获取完整产品列表
- 适合识别高成本产品和主要费用来源

### 3. 账单明细与分账查询

- 使用 `ListBillDetail` 查询账单明细
- 使用 `ListAmortizedCostBillDetail` 查询成本账单明细
- 使用 `ListSplitBillDetail` 查询分账账单
- 支持按账期、分摊月、日期、产品、账号、实例、分拆项筛选

### 4. 配置与调用方式

- 支持环境变量配置 `AK/SK`
- 支持 `.env` 文件配置
- 支持 Python 代码调用
- 支持通过 `scripts/` 下的独立脚本直接调用
- 支持分页拉取与本地汇总分析
- 支持 JSON 结构化结果处理

## 处理逻辑

### 账单查询处理流程

1. **根据用户目标确定接口**
   - 整体账单使用 `ListBillOverviewByCategory`
   - 产品月度账单使用 `ListBillOverviewByProd`
   - 明细核对使用 `ListBillDetail`
   - 成本明细使用 `ListAmortizedCostBillDetail`
   - 分账排查使用 `ListSplitBillDetail`
2. **根据时间要求确定账期与日期范围**
   - 优先确定 `BillPeriod`
   - 成本账单优先确定 `AmortizedMonth`
   - 需要单日细查时补充 `ExpenseDate`
   - 成本账单按日细查时补充 `AmortizedDay`
   - 跨月查询需要拆成多个账期分别查询
3. **根据过滤条件组装 SDK 请求参数**
   - 例如产品、账号、实例、账单类型、分拆项等
4. **如为分页接口则循环查询**
   - 使用 `Offset + Limit + NeedRecordNum` 分页拉全量
   - 可使用 `common.py` 中的 `fetch_all_pages` 工具函数自动翻页
5. **对结果做汇总分析**
   - 输出金额、排行、异常波动和待核对项

## 前置要求

需要安装火山引擎 Python SDK：

```bash
pip install --upgrade "volcengine-python-sdk>=5.0.30"
```

说明：

- 建议使用 5.x 最新版本
- 历史版本 `4.0.1 ~ 4.0.42` 存在 SDK 重试缺陷，尽量不要继续使用

## 配置方式

需要配置火山引擎的 Access Key 和 Secret Key。推荐使用以下两种方式之一：

### 方式 1：环境变量

```bash
export VOLCENGINE_AK="your-ak"
export VOLCENGINE_SK="your-sk"
export VOLCENGINE_REGION="cn-beijing"
```

### 方式 2：`.env` 文件

在 `~/.openclaw/workspace/.env` 中配置：

```env
VOLCENGINE_AK=your-ak
VOLCENGINE_SK=your-sk
VOLCENGINE_REGION=cn-beijing
```

## 账单参数说明

### 账单查询核心参数

- **BillPeriod**: 账务账期，格式为 `YYYY-MM`
- **ExpenseDate**: 账单日期，格式为 `YYYY-MM-DD`
- **AmortizedMonth**: 分摊月，格式为 `YYYY-MM`
- **AmortizedDay**: 分摊日，格式为 `YYYY-MM-DD`
- **Offset**: 分页偏移量
- **Limit**: 单页数量，范围 `[1,300]`
- **NeedRecordNum**: 是否返回总记录数，`1` 返回 `Total`，否则常为 `-1`
- **IgnoreZero**: 是否忽略折后价为 0 的数据，`0` 不忽略、`1` 忽略
- **Product**: 产品筛选条件。可选的产品 Code 请参考 `references/product-code.md`

### 关键参数枚举值

| 参数 | 值 | 含义 |
|------|-----|------|
| `BillingMode` | `1` | 包年包月 |
| | `2` | 按量计费 |
| | `3` | 合同计费 |
| | `4` | 履约计费 |
| `BillCategoryParent` | `consume` | 消费 |
| | `refund` | 退款 |
| | `transfer` | 调账 |
| `BillCategory` | `consume-use` | 消费-使用 |
| | `consume-new` | 消费-新购 |
| | `consume-renew` | 消费-续费 |
| | `consume-formalize` | 消费-转正 |
| | `consume-modify` | 消费-更配 |
| | `consume-trial` | 消费-试用 |
| | `refund-terminate` | 退款-退订 |
| | `refund-modify` | 退款-更配 |
| | `transfer-manual` | 调账-人工 |
| | `transfer-system` | 调账-系统 |
| `GroupTerm` | `0` | 计费项 |
| | `1` | 实例 |
| | `2` | 产品 |
| | `3` | 账号 |
| `GroupPeriod` | `0` | 账期 |
| | `1` | 按天 |
| | `2` | 明细 |
| `AmortizedType` | `1` | 履约计费分摊 |
| | `2` | 合同计费分摊 |
| | `3` | 按量计费分摊 |
| | `4` | 新购分摊 |
| | `5` | 更配分摊 |
| | `6` | 续费分摊 |
| | `7` | 退订分摊 |
| | `8` | 预留实例调整分摊 |
| | `9` | 试用分摊 |
| | `10` | 转正分摊 |
| `SplitDimension` | JSON 字符串 | 分拆维度，如 `{"ark_bd":"apikey_id"}`，商品不支持多维度拆分时会报错 |

### 时间参数说明

- `BillPeriod` 是账单查询的核心时间参数，按月查询
- `AmortizedMonth` 是成本账单查询的核心时间参数，按月查询
- 如果不指定单日过滤，则默认按整月口径查询
- 若要查询单月中的某一天，可补充 `ExpenseDate`
- 若要查询单月中的某一天成本分摊，可补充 `AmortizedDay`
- 如果用户给出跨月日期范围，需要拆成多个 `BillPeriod` 分别查询后再汇总
- 如果用户给出跨月成本范围，需要拆成多个 `AmortizedMonth` 分别查询后再汇总

### 分页参数说明

- `ListBillOverviewByProd`
- `ListBillDetail`
- `ListAmortizedCostBillDetail`
- `ListSplitBillDetail`

以上四个接口都应按分页处理。

推荐策略：

- `Offset` 从 `0` 开始
- `Limit` 优先取 `100` 或 `300`
- `NeedRecordNum` 设为 `1`
- 每次查询完成后按 `Offset += Limit` 继续拉取
- 如果返回数量小于 `Limit`，或累计条数覆盖 `Total`，则结束分页
- 可直接使用 `common.py` 中的 `fetch_all_pages` 工具函数自动翻页

`fetch_all_pages` 使用示例：

```python
from common import build_billing_api, fetch_all_pages
import volcenginesdkbilling

api = build_billing_api()

# 自动拉取全量账单明细
rows = fetch_all_pages(
    api_instance=api,
    request_cls=volcenginesdkbilling.ListBillDetailRequest,
    list_method_name="list_bill_detail",
    raw_kwargs={"BillPeriod": "2025-05"},
    limit=100,
)
print(f"共拉取 {len(rows)} 条记录")
```

## 返回字段速查

所有接口的返回结构都是 `Result.List` + `Result.Total`（分页接口），完整字段定义见 `references/billing-api-notes.md`。以下是各接口最常用的业务字段：

### 通用金额字段（ListBillOverviewByCategory / ListBillOverviewByProd / ListBillDetail）

| 字段 | 说明 | 常用场景 |
|------|------|----------|
| `PayableAmount` | 应付金额 | 成本排行、总账核对 |
| `OriginalBillAmount` | 原价 | 未优惠前金额 |
| `DiscountBillAmount` | 折后价 | 优惠后口径 |
| `PreferentialBillAmount` | 优惠金额 | 不含代金券的优惠 |
| `CouponAmount` | 代金券抵扣 | 与优惠金额分开看 |
| `PaidAmount` | 已付金额 | 对账 |
| `UnpaidAmount` | 欠费金额 | 识别未结清 |

### 通用维度字段（ListBillDetail / ListSplitBillDetail / ListAmortizedCostBillDetail）

| 字段 | 说明 | 常用场景 |
|------|------|----------|
| `Product` / `ProductZh` | 产品英文 / 中文名 | 产品维度聚合 |
| `Region` / `RegionCode` | 地域 | 地域成本分析 |
| `Zone` / `ZoneCode` | 可用区 | 可用区级归因 |
| `InstanceNo` / `InstanceName` | 实例 ID / 名称 | 单实例排查 |
| `Project` / `ProjectDisplayName` | 项目信息 | 成本归属 |
| `Tag` | 标签 JSON | 标签归因 |
| `BillCategory` | 账单类型 | 区分消费/退款/调账 |
| `BillingMode` | 计费模式 | 区分包年包月/按量 |
| `ConfigName` | 配置名称 | SKU 说明 |

### ListSplitBillDetail 特有字段

| 字段 | 说明 | 备注 |
|------|------|------|
| `SplitItemID` / `SplitItemName` | 分拆项 ID / 名称 | 分账主键 |
| `SplitItemAmount` / `SplitItemRatio` | 分拆项用量 / 占比 | 明细模式下有意义 |
| `CouponDeductionAmount` | 代金券抵扣 | 注意：不是 `CouponAmount` |

### ListAmortizedCostBillDetail 特有字段

| 字段 | 说明 | 备注 |
|------|------|------|
| `AmortizedMonth` / `AmortizedDay` | 分摊月 / 分摊日 | 成本归属时间 |
| `AmortizedType` | 分摊类型 | 新购/续费/更配等 |
| `DailyAmortizedPayableAmount` | 每日分摊应付金额 | 成本分析主字段 |
| `DailyAmortizedDiscountBillAmount` | 每日分摊折后价 | 折后口径 |
| `DailyAmortizedOriginalBillAmount` | 每日分摊原价 | 原价口径 |

## 核心接口说明

每个接口的完整请求参数和返回参数定义见 `references/billing-api-notes.md`，以下为最简参数模板。

### 1. `ListBillOverviewByCategory`

查询账单总览账号汇总信息。

适用场景：

- 查看整月总账
- 先看整体账单，再决定是否下钻

SDK 请求参数模板：

```python
# 账号账单总览查询参数
category_request = {
    "BillPeriod": "2025-05"
}
```

### 2. `ListBillOverviewByProd`

分页查询产品月度账单。

适用场景：

- 看产品成本排行（单产品、多产品、全量产品月度账单）
- 识别高成本产品

SDK 请求参数模板：

```python
# 产品账单总览查询参数
prod_request = {
    "BillPeriod": "2025-05",
    "Limit": 100,
}
```

### 3. `ListBillDetail`

分页查询账单明细。

适用场景：

- 核对某个产品或实例的费用组成
- 查某月、某天、某类账单或某个实例的费用明细

SDK 请求参数模板：

```python
# 账单明细查询参数
detail_request = {
    "BillPeriod": "2025-05",
    "Limit": 100,
}
```

### 4. `ListSplitBillDetail`

分页查询分账账单。

适用场景：

- 核对分拆项费用
- 排查项目、标签或资源粒度的分账结果

SDK 请求参数模板：

```python
# 分账账单查询参数
split_request = {
    "BillPeriod": "2025-05",
    "Limit": 100,
}
```

### 5. `ListAmortizedCostBillDetail`

分页查询成本账单明细。

适用场景：

- 查看分摊后成本
- 核对摊销口径下的产品、实例和账单类型费用

SDK 请求参数模板：

```python
# 成本账单明细查询参数
amortized_detail_request = {
    "AmortizedMonth": "2025-05",
    "Limit": 100,
}
```

说明：

- 该接口的核心时间字段是 `AmortizedMonth` / `AmortizedDay`，不是普通账单接口里的 `BillPeriod` / `ExpenseDate`
- `BillPeriod` 在这个接口里是可选过滤条件，不能替代 `AmortizedMonth`

## 脚本目录

Skill 已将 5 个接口的调用示例提取为独立脚本，位于 `scripts/` 目录：

- `scripts/list_bill_overview_by_category.py`
- `scripts/list_bill_overview_by_prod.py`
- `scripts/list_bill_detail.py`
- `scripts/list_amortized_cost_bill_detail.py`
- `scripts/list_split_bill_detail.py`
- `scripts/common.py`

说明：

- `common.py` 负责加载 `.env`、初始化 Billing SDK、统一输出 JSON，以及提供 `fetch_all_pages` 翻页工具函数
- 5 个接口脚本都支持命令行参数调用，参数名默认与接口文档中的请求参数名一致
- 数组类型参数使用"重复传参"的方式输入，例如重复传 `--Product`
- 分页脚本会在本地校验月份格式、日期归属月份、`Limit` 范围和 `SplitDimension` 的 JSON 格式
- 所有可选参数按需传入，不传则不出现在请求体中

## 请求调用示例

### 账号总览

```bash
python3 scripts/list_bill_overview_by_category.py \
  --BillPeriod 2025-05
```

### 产品总览

```bash
# 最小调用
python3 scripts/list_bill_overview_by_prod.py \
  --BillPeriod 2025-05 \
  --Limit 100

# 按产品筛选
python3 scripts/list_bill_overview_by_prod.py \
  --BillPeriod 2025-05 \
  --Limit 100 \
  --Product ECS --Product VKE
```

### 账单明细

```bash
# 最小调用
python3 scripts/list_bill_detail.py \
  --BillPeriod 2025-05 \
  --Limit 100

# 按天 + 按产品 + 按实例筛选
python3 scripts/list_bill_detail.py \
  --BillPeriod 2025-05 \
  --Limit 100 \
  --ExpenseDate 2025-05-15 \
  --Product ECS \
  --InstanceNo i-xxxxxxxx
```

### 分账明细

```bash
# 最小调用
python3 scripts/list_split_bill_detail.py \
  --BillPeriod 2025-05 \
  --Limit 100

# 按标签维度分账
python3 scripts/list_split_bill_detail.py \
  --BillPeriod 2025-05 \
  --Limit 100 \
  --SplitDimension '{"TOS":"project"}'
```

### 成本账单明细

```bash
# 最小调用
python3 scripts/list_amortized_cost_bill_detail.py \
  --AmortizedMonth 2025-05 \
  --Limit 100

# 按天 + 按分摊类型筛选
python3 scripts/list_amortized_cost_bill_detail.py \
  --AmortizedMonth 2025-05 \
  --Limit 100 \
  --AmortizedDay 2025-05-15 \
  --AmortizedType 4
```

## 参考资料

- 本地准备说明：`references/install.md`
- 接口请求参数和响应参数参考文档：`references/billing-api-notes.md`
- 产品 Code 映射表：`references/product-code.md`
- 官方 Python SDK 安装包：`volcengine-python-sdk`
