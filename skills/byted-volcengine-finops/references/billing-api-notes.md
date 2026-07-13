# 火山引擎 Billing API 参考整理

本文整理自火山引擎 API Explorer 账单中心接口文档：

- [ListBillDetail](https://api.volcengine.com/api-explorer?action=ListBillDetail&groupName=%E8%B4%A6%E5%8D%95%E4%B8%AD%E5%BF%83&serviceCode=billing&tab=1&version=2022-01-01)
- [ListBillOverviewByCategory](https://api.volcengine.com/api-explorer?action=ListBillOverviewByCategory&groupName=%E8%B4%A6%E5%8D%95%E4%B8%AD%E5%BF%83&serviceCode=billing&tab=1&version=2022-01-01)
- [ListBillOverviewByProd](https://api.volcengine.com/api-explorer?action=ListBillOverviewByProd&groupName=%E8%B4%A6%E5%8D%95%E4%B8%AD%E5%BF%83&serviceCode=billing&tab=1&version=2022-01-01)
- [ListSplitBillDetail](https://api.volcengine.com/api-explorer?action=ListSplitBillDetail&groupName=%E8%B4%A6%E5%8D%95%E4%B8%AD%E5%BF%83&serviceCode=billing&tab=1&version=2022-01-01)
- [ListAmortizedCostBillDetail](https://api.volcengine.com/api-explorer?action=ListAmortizedCostBillDetail&groupName=%E8%B4%A6%E5%8D%95%E4%B8%AD%E5%BF%83&serviceCode=billing&tab=1&version=2022-01-01)

## 通用说明

- 版本：`2022-01-01`
- 服务 Region：`cn-beijing`
- 限流：这 5 个接口都受单账号 `5 QPS` 限制。
- 分页：除 `ListBillOverviewByCategory` 外，其余 4 个接口都建议按 `Offset + Limit + NeedRecordNum` 翻页。
- 月度完整性：普通账单建议在"每月第 2 个自然日 12 点后"再取上月完整数据。
- 分账延迟：`ListSplitBillDetail` 相比普通账单明细存在约 2 天延迟，项目/标签信息最晚延迟 12 小时补充。
- 成本账单延迟：`ListAmortizedCostBillDetail` 相比普通账单明细也存在约 2 天延迟，且需要先开通成本账单能力。

## 接口选择建议

| 接口 | 主要用途 | 是否分页 | 核心时间字段 | 备注 |
|---|---|---|---|---|
| `ListBillOverviewByCategory` | 看账号维度总账 | 否 | `BillPeriod` | 适合总览，不适合下钻 |
| `ListBillOverviewByProd` | 看产品维度汇总 | 是 | `BillPeriod` | 适合做产品成本排行 |
| `ListBillDetail` | 看原始账单明细 | 是 | `BillPeriod` / `ExpenseDate` | 适合核对消费与实例级费用 |
| `ListSplitBillDetail` | 看分账账单 | 是 | `BillPeriod` / `ExpenseDate` | 适合项目、标签、分拆项归因 |
| `ListAmortizedCostBillDetail` | 看分摊后成本明细 | 是 | `AmortizedMonth` / `AmortizedDay` | 适合摊销/分摊口径成本分析 |

## 1. ListBillOverviewByCategory

### 用途

- 查询账号维度账单总览。
- 适合先看总账，再决定是否继续下钻产品或明细。

### 请求参数

| 参数 | 类型 | 必填 | 说明 | 备注 |
|---|---|---|---|---|
| `BillPeriod` | `string` | 是 | 账务账期，格式 `YYYY-MM` | 仅支持单月查询，最多回溯 24 个月 |
| `BillCategoryParent` | `string[]` | 否 | 账单大类 | `consume` 消费、`refund` 退款、`transfer` 调账 |
| `BillingMode` | `string[]` | 否 | 计费模式 | `1` 包年包月、`2` 按量计费、`3` 合同计费、`4` 履约计费 |
| `OwnerID` | `integer[]` | 否 | Owner 账号 ID | 财务托管场景下可精确限定子账号 |
| `PayerID` | `integer[]` | 否 | Payer 账号 ID | 适合多账号或财务管理场景 |

### 返回参数

#### 返回结构

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `Result.List` | `object[]` | 账号汇总列表 | 官方示例中存在嵌套 `List` 结构，消费时建议先打印实际返回再做字段解析 |

#### 常用业务字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `PayerID` / `PayerUserName` / `PayerCustomerName` | `string` | 支付账号信息 | 用于识别实际付款主体 |
| `OwnerID` / `OwnerUserName` / `OwnerCustomerName` | `string` | 资源使用账号信息 | 财务管理/托管场景尤其重要 |
| `SellerID` / `SellerUserName` / `SellerCustomerName` | `string` | 售卖方信息 | 代销/代售场景可能变化 |
| `BillPeriod` | `string` | 账期 | 和请求中的账期一致 |
| `BillCategoryParent` | `string` | 账单大类 | 返回通常是中文含义 |
| `BusinessMode` | `string` | 业务类型 | 如普通业务、财务托管 |
| `SettlementType` | `string` | 结算类型 | `结算`、`非结算` |
| `SubjectNo` / `SubjectName` | `string` | 主体编号 / 主体名称 | 售卖方主体信息 |
| `CountryArea` | `string` | 国家/地区 | 跨区域场景关注 |
| `OriginalBillAmount` | `string` | 原价 | 未优惠前金额 |
| `DiscountBillAmount` | `string` | 折后价 | 常用核对口径 |
| `CouponAmount` | `string` | 代金券抵扣 | 不等于总优惠 |
| `PayableAmount` | `string` | 应付金额 | 重点关注字段 |
| `PaidAmount` | `string` | 现金支付 | 已支付部分 |
| `UnpaidAmount` | `string` | 欠费金额 | 可用于识别未结清账单 |
| `CreditCarriedAmount` | `string` | 信控额度退款抵扣 | 特殊场景字段 |

### 备注

- 这是汇总接口，适合做"账号大盘"视图。
- 如果要做产品排名或实例排查，应继续调用 `ListBillOverviewByProd` 或 `ListBillDetail`。

## 2. ListBillOverviewByProd

### 用途

- 查询产品维度账单总览。
- 适合做成本排行、按产品拆分费用来源。

### 请求参数

| 参数 | 类型 | 必填 | 说明 | 备注 |
|---|---|---|---|---|
| `BillPeriod` | `string` | 是 | 账期，格式 `YYYY-MM` | 仅支持单月查询 |
| `Limit` | `integer` | 是 | 单页数量 | 范围 `[1,300]` |
| `Offset` | `integer` | 否 | 偏移量 | 按 `offset += limit` 翻页 |
| `NeedRecordNum` | `integer` | 否 | 是否返回总数 | `1` 返回 `Total`，否则常为 `-1` |
| `IgnoreZero` | `integer` | 否 | 是否忽略零金额 | 建议账单排行场景设为 `1` |
| `BillingMode` | `string[]` | 否 | 计费模式 | `1` 包年包月、`2` 按量计费、`3` 合同计费、`4` 履约计费 |
| `BillCategoryParent` | `string[]` | 否 | 账单大类 | `consume` 消费、`refund` 退款、`transfer` 调账 |
| `Product` | `string[]` | 否 | 产品名称 | 可用于精确筛选产品 |
| `OwnerID` | `integer[]` | 否 | Owner 账号 ID | 财务托管场景常用 |
| `PayerID` | `integer[]` | 否 | Payer 账号 ID | 多账号场景常用 |

### 返回参数

#### 分页结构

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `Result.List` | `object[]` | 产品汇总列表 | 每条对应一个产品维度汇总 |
| `Result.Total` | `integer` | 总数 | 仅 `NeedRecordNum=1` 时有意义 |
| `Result.Limit` | `integer` | 步长 | 回显请求分页大小 |
| `Result.Offset` | `integer` | 偏移量 | 回显当前页起点 |

#### 常用业务字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `BillPeriod` | `string` | 账期 | 汇总月份 |
| `Product` | `string` | 产品英文名称 | 适合程序聚合 |
| `ProductZh` | `string` | 产品中文名称 | 适合展示 |
| `BillingMode` | `string` | 计费模式 | 返回中通常已转为中文含义 |
| `BillCategoryParent` | `string` | 账单大类 | 常见为消费 |
| `PayerID` / `OwnerID` | `string` | 支付 / 使用账号 | 多账号对账常用 |
| `OriginalBillAmount` | `string` | 原价 | 原始标价金额 |
| `PreferentialBillAmount` | `string` | 优惠金额 | 不含代金券抵扣 |
| `RoundBillAmount` | `string` | 抹零金额 | 小额费用常出现 |
| `DiscountBillAmount` | `string` | 折后价 | 常用成本口径 |
| `CouponAmount` | `string` | 代金券抵扣 | 与优惠金额分开看 |
| `PayableAmount` | `string` | 应付金额 | 常用于成本排行 |
| `PaidAmount` / `UnpaidAmount` | `string` | 已付 / 欠费 | 对账补充字段 |
| `SettlementType` | `string` | 结算类型 | `结算`、`非结算` |

### 备注

- 该接口非常适合先做产品成本排行，再对高费用产品调用明细接口下钻。
- 若跨月分析，建议保留月份字段，不要把不同月结果直接合并后丢失时间维度。

## 3. ListBillDetail

### 用途

- 查询普通账单明细。
- 适合核对资源、实例、账单类型、价格与优惠明细。

### 请求参数

| 参数 | 类型 | 必填 | 说明 | 备注 |
|---|---|---|---|---|
| `BillPeriod` | `string` | 是 | 账期，格式 `YYYY-MM` | 单月查询，最多回溯 24 个月 |
| `Limit` | `integer` | 是 | 单页数量 | 范围 `[1,300]` |
| `Offset` | `integer` | 否 | 偏移量 | 分页主键 |
| `NeedRecordNum` | `integer` | 否 | 是否返回总数 | 建议设为 `1` |
| `IgnoreZero` | `integer` | 否 | 是否忽略折后价为 0 的数据 | `0` 不忽略、`1` 忽略 |
| `ExpenseDate` | `string` | 否 | 账单日期，格式 `YYYY-MM-DD` | 在 `GroupPeriod=1` 或 `2` 时支持，必须与 `BillPeriod` 同月，建议填写以提升性能 |
| `GroupTerm` | `integer` | 否 | 统计项 | `0` 计费项、`1` 实例、`2` 产品、`3` 账号 |
| `GroupPeriod` | `integer` | 否 | 统计周期 | `0` 账期、`1` 按天、`2` 明细 |
| `Product` | `string[]` | 否 | 产品名称 | 精确下钻产品时常用 |
| `BillingMode` | `string[]` | 否 | 计费模式 | `1` 包年包月、`2` 按量计费、`3` 合同计费、`4` 履约计费 |
| `BillCategory` | `string[]` | 否 | 账单类型 | `consume-use` 消费-使用、`consume-new` 消费-新购、`consume-renew` 消费-续费、`consume-formalize` 消费-转正、`consume-modify` 消费-更配、`consume-trial` 消费-试用、`refund-terminate` 退款-退订、`refund-modify` 退款-更配、`transfer-manual` 调账-人工、`transfer-system` 调账-系统 |
| `InstanceNo` | `string` | 否 | 实例 ID | 排查单实例最有效 |
| `OwnerID` | `integer[]` | 否 | Owner 账号 ID | 财务管理场景常用 |
| `PayerID` | `integer[]` | 否 | Payer 账号 ID | 财务管理场景常用 |
| `Project` | `string[]` | 否 | 项目筛选 | 按项目过滤 |

### 返回参数

#### 分页结构

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `Result.List` | `object[]` | 账单明细列表 | 每条通常对应一条资源/计费项级别费用 |
| `Result.Total` | `integer` | 总数 | `NeedRecordNum=0` 时可能为 `-1` |
| `Result.Limit` | `integer` | 步长 | 分页回显 |
| `Result.Offset` | `integer` | 偏移量 | 分页回显 |

#### 标识与归属字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `BillDetailId` | `string` | 账单明细 ID | 明细主键 |
| `BillID` | `string` | 订单号/账单号 | 预付费和后付费场景含义不同 |
| `PayerID` / `PayerUserName` / `PayerCustomerName` | `string` | 支付账号信息 | 付款主体 |
| `OwnerID` / `OwnerUserName` / `OwnerCustomerName` | `string` | Owner 信息 | 实际资源使用主体 |
| `SellerID` / `SellerUserName` / `SellerCustomerName` | `string` | 售卖主体信息 | 代销/代售场景重要 |
| `Project` / `ProjectDisplayName` | `string` | 项目信息 | 成本归属常用 |
| `Tag` | `string` | 标签 JSON | 资源标签归因 |

#### 时间与维度字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `BillPeriod` | `string` | 账期 | 账务归属月份 |
| `BusiPeriod` | `string` | 业务账期 | 跨月调账时与账务账期不同 |
| `ExpenseDate` | `string` | 日期 | 按天/明细分析常用 |
| `ExpenseBeginTime` / `ExpenseEndTime` | `string` | 消费起止时间 | 后付费最常见 |
| `TradeTime` | `string` | 交易时间 | 实际扣费/出账时间 |

#### 资源与商品字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `Product` / `ProductZh` | `string` | 产品英文 / 中文名 | 产品维度分析核心字段 |
| `BusinessMode` | `string` | 业务类型 | 普通业务、财务管理等 |
| `BillingMode` | `string` | 计费模式 | 包年包月 / 按量等 |
| `BillCategory` | `string` | 账单类型 | 如消费-使用、退款-退订 |
| `InstanceNo` / `InstanceName` | `string` | 实例 ID / 名称 | 排查资源费用常用 |
| `ConfigName` | `string` | 配置名称 | SKU 配置说明 |
| `Element` / `ElementCode` | `string` | 计费单元及编码 | 定位计费项 |
| `Region` / `RegionCode` | `string` | 地域及编码 | 地域成本分析 |
| `Zone` / `ZoneCode` | `string` | 可用区及编码 | 可用区级归因 |
| `Factor` / `FactorCode` | `string` | 影响因子及编码 | 价格影响因素 |
| `ConfigurationCode` | `string` | 配置编码 | 结构化排障字段 |

#### 价格与金额字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `Price` / `PriceUnit` | `string` | 单价 / 单位 | 计费规则核对常用 |
| `Count` / `Unit` | `string` | 用量 / 用量单位 | 用量核对基础字段 |
| `UseDuration` / `UseDurationUnit` | `string` | 使用时长 / 单位 | 时长计费场景关键 |
| `OriginalBillAmount` | `string` | 原价 | 未优惠前金额 |
| `PreferentialBillAmount` | `string` | 优惠金额 | 官方优惠口径 |
| `RoundAmount` | `double/string` | 抹零金额 | 可能为负数 |
| `DiscountBillAmount` | `string` | 折后价 | 常用账单金额口径 |
| `CouponAmount` | `string` | 代金券抵扣 | 与优惠金额分开 |
| `PayableAmount` | `string` | 应付金额 | 实际应结算 |
| `PaidAmount` / `UnpaidAmount` | `string` | 已付 / 欠费 | 对账常用 |
| `CreditCarriedAmount` | `string` | 信控额度退款抵扣 | 特殊场景字段 |
| `Currency` | `string` | 币种 | 定价币种 |
| `SettlementType` | `string` | 结算类型 | `结算`、`非结算` |

#### 优惠与定价规则字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `BillingMethodCode` | `string` | 计费方式 | 如按配置小时结 |
| `BillingFunction` | `string` | 单价价格类型 | 固定单价 / 阶梯价等 |
| `DiscountBizBillingFunction` | `string` | 优惠类型 | 固定单价 / 单一折扣 / 阶梯价 |
| `DiscountBizUnitPrice` / `DiscountBizUnitPriceInterval` | `string` | 优惠价格信息 | 优惠明细 |
| `DiscountBizMeasureInterval` | `string` | 优惠用量区间 | 阶梯优惠使用 |
| `MeasureInterval` / `PriceInterval` | `string` | 价格区间 | 阶梯定价使用 |
| `MarketPrice` | `string` | 市场价 | 和实际结算价比较 |
| `EffectiveFactor` | `string` | 有效因子 | 价格影响因子 |

### 备注

- 普通账单明细最适合做"为什么这笔钱产生了"的排查。
- `ExpenseDate` 与 `BillPeriod` 必须处于同一月份，这一点在 Skill 中已作为硬约束。

## 4. ListSplitBillDetail

### 用途

- 查询分账账单。
- 适合按项目、标签、分拆项、部门归属做内部成本分摊。

### 请求参数

| 参数 | 类型 | 必填 | 说明 | 备注 |
|---|---|---|---|---|
| `BillPeriod` | `string` | 是 | 账务账期，格式 `YYYY-MM` | 单月查询，最多回溯 24 个月 |
| `Limit` | `integer` | 是 | 单页数量 | 范围 `[1,300]` |
| `Offset` | `integer` | 否 | 偏移量 | 分页使用 |
| `NeedRecordNum` | `integer` | 否 | 是否返回总数 | 建议设 `1` |
| `IgnoreZero` | `integer` | 否 | 是否忽略折后价为 0 的数据 | `0` 不忽略、`1` 忽略 |
| `ExpenseDate` | `string` | 否 | 账单日期 | 在 `GroupPeriod=1` 或 `2` 时支持，且必须与 `BillPeriod` 同月 |
| `GroupPeriod` | `integer` | 否 | 统计周期 | `0` 账期、`1` 按天、`2` 明细 |
| `Product` | `string[]` | 否 | 产品名称 | 精确筛选产品 |
| `BillingMode` | `string[]` | 否 | 计费模式 | `1` 包年包月、`2` 按量计费、`3` 合同计费、`4` 履约计费 |
| `BillCategory` | `string[]` | 否 | 账单类型 | `consume-use` 消费-使用、`consume-new` 消费-新购 等 |
| `OwnerID` | `integer[]` | 否 | Owner 账号 ID | 财务托管场景常用 |
| `PayerID` | `integer[]` | 否 | Payer 账号 ID | 多账号场景常用 |
| `InstanceNo` | `string` | 否 | 实例 ID | 单实例排查 |
| `SplitItemID` | `string` | 否 | 分拆项 ID | 精确定位分账对象 |
| `SplitDimension` | `string` | 否 | 分拆维度 JSON 字符串 | 例如 `{"ark_bd":"apikey_id"}`，商品不支持多维度拆分时会报错 |
| `Project` | `string[]` | 否 | 项目筛选 | 按项目过滤 |

### 返回参数

#### 分页结构

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `Result.List` | `object[]` | 分账账单列表 | 每条带项目 / 标签 / 分拆项信息 |
| `Result.Total` / `Limit` / `Offset` | `integer` | 分页信息 | `NeedRecordNum=0` 时 `Total` 可能为 `-1` |

#### 常用业务字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `BillPeriod` / `BusiPeriod` | `string` | 账期 / 业务账期 | 和普通明细一致 |
| `ExpenseTime` | `string` | 消费时间 | 在不同 `GroupPeriod` 下含义不同 |
| `TradeTime` | `string` | 交易时间 | `GroupPeriod=2` 时最有意义 |
| `BillID` | `string` | 订单号/账单号 | `GroupPeriod=2` 时更稳定 |
| `BillCategory` | `string` | 账单类型 | 消费、退款、调账等 |
| `Product` / `ProductZh` | `string` | 产品英文 / 中文名 | |
| `InstanceNo` / `InstanceName` | `string` | 实例 ID / 名称 | |
| `Project` / `ProjectDisplayName` | `string` | 项目 / 项目中文名 | 内部成本归属最关键字段之一 |
| `Tag` | `string` | 标签 JSON | 标签成本归因关键字段 |
| `SplitItemID` / `SplitItemName` | `string` | 分拆项 ID / 名称 | 分账主键 |
| `SplitItemAmount` / `SplitItemRatio` | `string` | 分拆项用量 / 分拆占比 | 明细模式下最有意义 |
| `SplitBillDetailId` | `string` | 分账明细 ID | 分账明细主键 |

#### 金额与定价字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `OriginalBillAmount` | `string` | 原价 | |
| `PreferentialBillAmount` | `string` | 优惠金额 | |
| `DiscountBillAmount` | `string` | 折后价 | |
| `CouponDeductionAmount` | `string` | 代金券抵扣 | 注意：此接口字段名是 `CouponDeductionAmount`，不是 `CouponAmount` |
| `PayableAmount` / `PaidAmount` / `UnpaidAmount` | `string` | 应付、已付、欠费 | |
| `CreditCarriedAmount` | `string` | 信控额度退款抵扣 | |
| `Price` / `PriceUnit` | `string` | 单价 / 单位 | |
| `DiscountBizUnitPrice` / `DiscountBizBillingFunction` | `string` | 优惠价格与优惠类型 | |
| `BillingFunction` / `BillingMethodCode` | `string` | 定价函数 / 计费方式 | |
| `Currency` | `string` | 币种 | |

### 备注

- 这个接口适合"内部成本归属"分析，而不是单纯看计费事实。
- `Project`、`Tag`、`SplitItemID` 是它与普通账单明细最大的差异。
- 文档明确提到分账账单相对普通账单有延迟，项目/标签会进一步延迟补全。
- 代金券字段名是 `CouponDeductionAmount`，与普通账单的 `CouponAmount` 不同。

## 5. ListAmortizedCostBillDetail

### 用途

- 查询成本账单明细，即分摊/摊销口径的账单。
- 适合把预付费、履约计费、合同计费等费用分摊到实际使用周期进行分析。

### 请求参数

| 参数 | 类型 | 必填 | 说明 | 备注 |
|---|---|---|---|---|
| `AmortizedMonth` | `string` | 是 | 分摊月，格式 `YYYY-MM` | 核心时间字段，单月查询，最早仅能查到 `2023-04` |
| `Limit` | `integer` | 是 | 单页数量 | 范围 `[1,300]` |
| `Offset` | `integer` | 否 | 偏移量 | 分页使用 |
| `NeedRecordNum` | `integer` | 否 | 是否返回总数 | 建议设 `1` |
| `IgnoreZero` | `integer` | 否 | 是否忽略折后价为 0 的数据 | `0` 不忽略、`1` 忽略 |
| `AmortizedDay` | `string` | 否 | 分摊日，格式 `YYYY-MM-DD` | 官方明确建议填写，可提升查询性能 |
| `BillPeriod` | `string` | 否 | 账务账期 | 只是过滤条件，不能替代 `AmortizedMonth` |
| `AmortizedType` | `string[]` | 否 | 分摊类型 | `1` 履约计费分摊、`2` 合同计费分摊、`3` 按量计费分摊、`4` 新购分摊、`5` 更配分摊、`6` 续费分摊、`7` 退订分摊、`8` 预留实例调整分摊、`9` 试用分摊、`10` 转正分摊 |
| `Product` | `string[]` | 否 | 产品名称 | 精确筛选产品 |
| `BillingMode` | `string[]` | 否 | 计费模式 | `1` 包年包月、`2` 按量计费、`3` 合同计费、`4` 履约计费 |
| `BillCategory` | `string[]` | 否 | 账单类型 | `consume-use` 消费-使用 等 |
| `OwnerID` | `integer[]` | 否 | Owner 账号 ID | 财务托管场景常用 |
| `PayerID` | `integer[]` | 否 | Payer 账号 ID | 多账号场景常用 |
| `InstanceNo` | `string` | 否 | 实例 ID | 单实例排查常用 |
| `Project` | `string[]` | 否 | 项目筛选 | 按项目过滤 |

### 返回参数

#### 分页结构

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `Result.List` | `object[]` | 成本明细列表 | 每条对应一个分摊后的成本明细 |
| `Result.Total` / `Limit` / `Offset` | `integer` | 分页信息 | 常规翻页逻辑 |

#### 时间与主键字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `CostID` | `string` | 成本账单明细业务主键 | 成本明细主键 |
| `AmortizedMonth` | `string` | 分摊月 | 成本归属月份 |
| `AmortizedDay` | `string` | 分摊日 | 成本归属日期 |
| `AmortizedBeginTime` / `AmortizedEndTime` | `string` | 分摊起止时间 | 表示成本如何分配到使用周期 |
| `ExpenseBeginTime` / `ExpenseEndTime` | `string` | 原始消费起止时间 | 和分摊起止时间不是同一概念 |
| `BillPeriod` / `BusiPeriod` | `string` | 账务账期 / 业务账期 | 与分摊时间维度并存 |
| `TradeTime` | `string` | 交易时间 | 交易发生时间 |

#### 标识与维度字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `PayerID` / `OwnerID` / `SellerID` | `string` | 支付、使用、售卖账号 | 账号主体 |
| `Product` / `ProductZh` | `string` | 产品英文 / 中文名 | 产品维度 |
| `BusinessMode` | `string` | 业务类型 | |
| `BillingMode` | `string` | 计费模式 | 原始计费模式 |
| `BillCategory` | `string` | 账单类型 | 消费、退款等 |
| `AmortizedType` | `string` | 分摊类型 | 成本账单核心维度 |
| `InstanceNo` / `InstanceName` | `string` | 实例 ID / 名称 | 单实例成本分析 |
| `Element` / `ConfigName` | `string` | 计费单元 / 配置 | |
| `Project` / `ProjectDisplayName` | `string` | 项目信息 | 内部归属分析 |
| `Tag` | `string` | 标签 JSON | 标签归属分析 |
| `SplitItemID` / `SplitItemName` | `string` | 分拆项信息 | 与分账体系联动时有用 |
| `CountryArea` | `string` | 国家/地区 | 跨区域场景关注 |

#### 金额字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `OriginalBillAmount` / `DiscountBillAmount` / `PreferentialBillAmount` | `string` | 原价、折后价、优惠金额 | 原始口径金额 |
| `DailyAmortizedOriginalBillAmount` | `string` | 每日分摊原价 | 成本口径关键字段 |
| `DailyAmortizedDiscountBillAmount` | `string` | 每日分摊折后价 | 常见成本分析主字段 |
| `DailyAmortizedPayableAmount` | `string` | 每日分摊应付金额 | 常用成本金额口径 |
| `DailyAmortizedPaidAmount` | `string` | 每日分摊现金支付 | |
| `DailyAmortizedCouponAmount` | `string` | 每日分摊代金券抵扣 | |
| `DailyAmortizedRoundAmount` | `string` | 每日分摊抹零金额 | |
| `DailyAmortizedRealValue` | `string` | 每日分摊真实金额 | |
| `DailyAmortizedPreTaxPayableAmount` | `string` | 每日分摊税前应付金额 | 税前口径 |
| `DailyAmortizedPreTaxRealValue` | `string` | 每日分摊税前真实金额 | |
| `DailyAmortizedPreferentialBillAmount` | `string` | 每日分摊优惠金额 | |
| `DailyAmortizedSettlePayableAmount` | `string` | 每日分摊结算币种应付金额 | 多币种场景 |
| `DailyAmortizedSettlePreTaxPayableAmount` | `string` | 每日分摊结算币种税前应付金额 | |
| `DailyAmortizedSettleRealValue` | `string` | 每日分摊结算币种真实金额 | |
| `DailyAmortizedSettlePreTaxRealValue` | `string` | 每日分摊结算币种税前真实金额 | |
| `DailyAmortizedTaxAmount` | `string` | 每日分摊税额 | |
| `DailyAmortizedSettleTaxAmount` | `string` | 每日分摊结算币种税额 | |
| `PayableAmount` / `PreTaxPayableAmount` | `string` | 应付金额 / 税前应付金额 | 非每日分摊口径 |
| `PaidAmount` / `RealValue` / `PreTaxRealValue` | `string` | 已付 / 真实金额 / 税前真实金额 | |
| `SettlePayableAmount` / `SettlePreTaxPayableAmount` | `string` | 结算币种金额 | 多币种场景 |
| `SettleRealValue` / `SettlePreTaxRealValue` | `string` | 结算币种真实金额 | |
| `TaxAmount` / `SettleTaxAmount` | `string` | 税额 / 结算币种税额 | |
| `TaxRate` | `string` | 税率 | 如 `0.09` |
| `CouponAmount` | `string` | 代金券抵扣（总额） | 与每日分摊口径区分 |
| `RoundAmount` | `string` | 抹零金额（总额） | |
| `CreditCarriedAmount` | `string` | 信控额度退款抵扣 | |
| `Currency` / `ExchangeRate` | `string` | 币种 / 汇率 | 多币种分析需统一 |

#### 定价与优惠字段

| 参数 | 类型 | 说明 | 备注 |
|---|---|---|---|
| `Price` / `PriceUnit` | `string` | 单价 / 单位 | |
| `Count` / `Unit` | `string` | 用量 / 单位 | |
| `UseDuration` / `UseDurationUnit` | `string` | 使用时长 / 单位 | |
| `BillingMethodCode` | `string` | 计费方式 | |
| `BillingFunction` | `string` | 价格类型 | 固定单价 / 阶梯价 |
| `DiscountBizBillingFunction` | `string` | 优惠类型 | |
| `DiscountBizUnitPrice` / `DiscountBizUnitPriceInterval` | `string` | 优惠价格 / 区间 | |
| `DiscountBizMeasureInterval` | `string` | 优惠用量区间 | |
| `MeasureInterval` / `PriceInterval` | `string` | 价格区间 | |
| `MarketPrice` | `string` | 市场价 | |
| `EffectiveFactor` | `string` | 有效因子 | |
| `DeductionUseDuration` | `string` | 抵扣使用时长 | |

### 备注

- 成本账单与普通账单最重要的区别是：时间维度按"分摊月 / 分摊日"而不是"账期 / 账单日"组织。
- 若要做"摊销后成本"分析，应优先以 `DailyAmortized*` 系列字段为主，不要直接混用普通账单的 `PayableAmount`。
- 该接口在 Skill 中已实现为独立脚本，且强制要求 `--AmortizedMonth`。

## 落地建议

- 汇总看板：先调 `ListBillOverviewByCategory`。
- 产品排行：再调 `ListBillOverviewByProd`。
- 费用排查：普通账单用 `ListBillDetail`。
- 内部归属：分账分析用 `ListSplitBillDetail`。
- 摊销口径：成本分析用 `ListAmortizedCostBillDetail`。

## 维护建议

- 该文档适合作为 Skill 的本地"读文档入口"，不是官方文档的替代品。
- 当 API Explorer 页面字段、限流、示例或说明更新时，应同步回刷本文件。
