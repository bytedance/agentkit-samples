---
name: byted-data-search
description: |
  行业数据查询与分析工具。接入多种合规公开数据源，支持精确匹配、模糊搜索、聚合统计、分组排序等查询方式。当前已覆盖工商企业基本信息、产业链节点区域指标、产业链企业信息、A股相关信息以及其他等大部分场景。完整的可用数据源清单及其字段结构需通过 describe_datasource 接口动态获取。

  当用户提出任何涉及企业、公司、行业或产业链的数据查询意图时，都应触发此 Skill。典型场景包括但不限于：
  - 查询某家公司的工商注册信息（名称、法人、注册资本、成立日期、经营范围、股东、融资历史等）
  - 查询 A 股上市公司基本面、证券信息、F10 数据、IPO 信息、分红派息、高管信息
  - 查询某条产业链的结构，包括节点企业、区域分布、各类标签企业统计（龙头、高新、专精特新、独角兽、小巨人等）
  - 查询产业链区域指标（营收、资产、利润率、ROE、知识产权、招投标数据等）
  - 按地域、行业、企业标签等维度做聚合统计或分组分析
  - 用户提到"查一下某某公司"、"帮我看看这家企业"、"xx产业有哪些龙头"等任何公开数据查询意图

  即使无法确定所需数据是否已覆盖，也应先调用数据源列表接口探查，不可直接拒绝或猜测。数据来自合规公开渠道，结果仅供参考，不构成决策依据。
---

# 数据查询工具

## 前置要求

需要环境变量（脚本会自动读取，若读取不到需提醒用户设置）：
- `VOLCENGINE_ACCESS_KEY`（或 `VOLC_ACCESS_KEY`）
- `VOLCENGINE_SECRET_KEY`（或 `VOLC_SECRET_KEY`）

## 工作流程（严格按顺序执行）

### 第一步：查询可用数据源（必须先执行）

在构造任何查询之前，**必须先调用此步骤**了解有哪些数据源及其字段定义。这一步的作用是：确认用户需要的数据存在于哪个数据源中，以及该数据源有哪些字段和过滤规则。跳过这一步直接去猜字段名几乎一定会出错。

```bash
# 列出所有可用数据源摘要（含 datasource_id、名称、描述、维度/过滤字段数量）
python3 scripts/describe_datasource.py --datasource-id all

# 获取某个数据源的完整字段定义（维度 dimensions、字段类型、可用过滤操作符）
python3 scripts/describe_datasource.py --datasource-id <数据源ID>
```

返回内容包含：
- `datasource_id`：数据源唯一标识
- `datasource_name`：数据源中文名称
- `description`：数据源说明
- `dimensions`：所有字段列表，每个字段包含 field（字段名）、label（显示名）、type（类型）、description（描述）、filterable（是否可作为过滤条件字段）
- `notes`：使用备注

**关键：根据返回的字段信息（尤其是 field 名称和 type 类型），确定需要用到的字段和过滤操作符，再进入第二步。**

### 字段类型与操作符对照表

每种字段类型只支持特定操作符。用错操作符会直接报错，所以在构造 filters 之前请务必对照此表。

| 字段类型 | 支持的操作符 | 说明 |
|---------|------------|------|
| `keyword` | `eq`, `in`, `not_in` | 精确匹配类字段（如编码、状态、类型） |
| `text` | `like`, `keyword` | 文本类字段（如名称、地址、描述），支持模糊搜索 |
| `date` / `datetime` | `between`, `eq` | 日期类字段，范围查询用 between |
| `long` / `integer` / `float` / `double` | `range`, `eq` | 数值类字段，范围查询用 range |

> 注意：`long` 类型字段如企业标签（`is_longtou_flag` 等）虽然是数值类型，但用于布尔判断时用 `eq` 即可，如 `is_longtou_flag:eq:1`。

### 字段取值不确定时：先探查再过滤

构造过滤条件时，经常会遇到"知道要按某个字段过滤，但不确定该字段的实际取值是什么"的情况。比如用户想按企业状态筛选，但不知道取值是"存续"、"在业"还是"正常"；或者想按产业分类过滤，但不确定分类名称的准确写法。

**正确做法：先做一次不带该过滤条件（或只带其他确定条件）的查询，从返回数据中观察目标字段的实际取值，再用准确的值构造过滤条件。**

具体步骤：
1. 先用宽松条件查询几条数据，观察目标字段返回了哪些值
2. 如果需要看该字段有哪些不同取值，可以用 `--group-by` + `--aggregation` 做分组统计
3. 确认取值后，再加上精确的过滤条件做正式查询

示例——想按"企业状态"过滤但不确定取值：
```bash
# 第 1 步：先查几条数据，观察 reg_status 字段的实际值
python3 scripts/query_datasource.py \
  --datasource-id enterprise_basic_wide \
  --filters 'company_name:like:科技'

# 第 2 步：或者直接做分组统计，看 reg_status 有哪些取值及各有多少条
python3 scripts/query_datasource.py \
  --datasource-id enterprise_basic_wide \
  --filters 'company_name:like:科技' \
  --group-by 'reg_status' \
  --aggregation 'company_id:count'

# 第 3 步：确认取值后，加上精确过滤条件
python3 scripts/query_datasource.py \
  --datasource-id enterprise_basic_wide \
  --filters 'company_name:like:科技;reg_status:eq:存续'
```

这个策略适用于所有 `keyword` 类型的枚举字段（如 `reg_status`、`category`、`region_level`、`taxpayer_type`、`company_org_type` 等），因为这些字段使用 `eq` 精确匹配，写错一个字都会导致零结果。

### 查询字段枚举值

当你不确定某个字段有哪些可选值时（尤其是 `keyword` 类型的枚举字段），可以用专门的枚举值查询脚本一步获取，而不必手动组合 `--group-by` 和 `--aggregation` 参数。该脚本返回最多 200 个不同取值，按出现频次从高到低排列。

这在以下场景特别有用：
- 构造 `eq` 或 `in` 过滤条件前，需要知道字段的准确取值（如 `reg_status` 到底是"存续"还是"在业"）
- 想快速了解某个分类字段（如 `category`、`region_level`、`company_org_type`）有哪些选项
- 需要在特定条件范围内（如某条产业链内）查看字段的取值分布

```bash
# 基本用法：查看某个字段有哪些取值
python3 scripts/get_field_enums.py \
  --datasource-id <数据源ID> \
  --field <字段名>

# 带过滤条件：只看满足条件的数据中该字段有哪些取值
python3 scripts/get_field_enums.py \
  --datasource-id <数据源ID> \
  --field <字段名> \
  --filters '<过滤条件>'
```

参数说明：

| 参数 | 必填 | 说明 |
|------|------|------|
| `--datasource-id` | 是 | 数据源 ID |
| `--field` | 是 | 要查询枚举值的字段名 |
| `--filters` | 否 | 前置过滤条件，格式同 query_datasource |
| `--limit` | 否 | 最多返回的枚举值数量（默认 20，上限 50） |

输出示例：
```
数据源: enterprise_basic_wide
字段:   reg_status
共找到 8 个不同取值（最多显示 200 个）:

   1. 存续  (5832174 条)
   2. 注销  (3021487 条)
   3. 在业  (1245633 条)
   4. 吊销  (412056 条)
   ...

[JSON] ["存续", "注销", "在业", "吊销", ...]
```

最后一行的 `[JSON]` 行是机器可读格式，方便程序化提取枚举值列表。

常见示例：
```bash
# 查看企业状态有哪些取值
python3 scripts/get_field_enums.py \
  --datasource-id enterprise_basic_wide --field reg_status

# 查看所属行业分类有哪些
python3 scripts/get_field_enums.py \
  --datasource-id enterprise_basic_wide --field category

# 查看产业链区域指标中 region_level 的取值
python3 scripts/get_field_enums.py \
  --datasource-id industry_chain_node_region_metric --field region_level

# 在"新能源汽车"产业链范围内，查看企业省份分布
python3 scripts/get_field_enums.py \
  --datasource-id industry_chain_company_info --field base_name \
  --filters 'chain_name:like:新能源汽车'

# 查看纳税人类型有哪些
python3 scripts/get_field_enums.py \
  --datasource-id enterprise_basic_wide --field taxpayer_type
```

> **提示**：拿到枚举值后，就可以在正式查询中使用 `eq` 或 `in` 精确过滤了。比如确认取值为"存续"后，就可以用 `reg_status:eq:存续` 过滤。

### 第二步：查询数据

根据第一步获取的字段信息构造查询命令：

```bash
python3 scripts/query_datasource.py \
  --datasource-id <数据源ID> \
  --filters '<过滤条件>' \
  --page 1
```

完整参数说明：

| 参数 | 必填 | 说明 |
|------|------|------|
| `--datasource-id` | 是 | 数据源 ID，从第一步获取 |
| `--filters` | 否 | 过滤条件，格式见下方，多个条件用 `;` 分隔 |
| `--aggregation` | 否 | 聚合操作：`count`（总数统计）、`field:count`（字段计数）、`field:distinct`（去重计数）、`field:sum/avg/max/min` |
| `--group-by` | 否 | 分组字段，逗号分隔，需配合 `--aggregation` 使用 |
| `--sort-field` | 否 | 排序字段名，不填使用默认排序 |
| `--sort-order` | 否 | `asc` 或 `desc`（默认 desc） |
| `--page` | 否 | 页码，从 1 开始（默认 1） |

## 过滤条件格式

格式：`字段名:操作符:值`，多个条件用 `;` 分隔。

| 操作符 | 含义 | 示例 | 适用字段类型 |
|--------|------|------|------------|
| `eq` | 精确匹配 | `reg_status:eq:存续` | keyword, date, 数值 |
| `like` | 模糊匹配（短语匹配） | `company_name:like:字节跳动` | text |
| `in` | 多值匹配（逗号分隔） | `reg_status:in:存续,在业` | keyword |
| `not_in` | 排除匹配（逗号分隔） | `reg_status:not_in:注销,吊销` | keyword |
| `between` | 日期范围（起始,结束） | `estiblish_time:between:2020-01-01,2025-12-31` | date, datetime |
| `range` | 数值范围（min,max；半开区间用 `,100` 或 `50,`） | `company_total_count:range:100,` | long, integer, float, double |
| `keyword` | 全文搜索 | `keyword:keyword:新能源补贴` | text |

**常见错误**：
- `text` 类型字段（如 `company_name`）不能用 `eq`，须用 `like` 或 `keyword`
- `keyword` 类型字段（如 `reg_status`）不能用 `like`，须用 `eq` / `in` / `not_in`
- 如果查询报错"字段不支持操作符"，回到第一步检查字段 type

多条件组合示例：
```
company_name:like:科技;region_province_name:like:广东;estiblish_time:between:2020-01-01,2025-12-31
```

## 当前已知数据源速查

以下为常见数据源，完整清单请调用 `describe_datasource.py --datasource-id all` 获取：

| 数据源ID | 名称 | 典型用途 | 关键注意 |
|---------|------|---------|---------|
| `enterprise_basic_wide` | 企业基本信息 | 工商注册信息、法人、注册资本、经营范围、股东融资等 | `company_name` 是 text 类型→用 `like`；max_page_size=5 |
| `industry_chain_company_info` | 产业链企业信息 | 产业链下的企业、按标签筛选（龙头/高新/专精特新/独角兽等） | `chain_name`/`node_name` 是 text→用 `like`；标签字段（is_longtou_flag 等）是 long→用 `eq:1` |
| `industry_chain_node_region_metric` | 产业链节点区域指标 | 产业链的区域分布统计、企业数量、财务指标、知识产权等 | 支持聚合统计，max_page_size=50 |
| `stock_company_brief` | 上市公司简况 | A 股上市公司基本面、F10、IPO、分红、高管等 | **必须**用 `code:eq:证券编码` 查询（如 `code:eq:000001`）；max_page_size=5 |

## 常见查询示例

### 企业工商信息查询
```bash
# 模糊搜索企业
python3 scripts/query_datasource.py \
  --datasource-id enterprise_basic_wide \
  --filters 'company_name:like:字节跳动'

# 按省份+行业筛选企业
python3 scripts/query_datasource.py \
  --datasource-id enterprise_basic_wide \
  --filters 'region_province_name:eq:广东;category:eq:信息传输、软件和信息技术服务业'

# 查询特定日期后成立的企业
python3 scripts/query_datasource.py \
  --datasource-id enterprise_basic_wide \
  --filters 'company_name:like:科技;estiblish_time:between:2023-01-01,2025-12-31'
```

### 产业链企业查询
```bash
# 查某产业链下的龙头企业
python3 scripts/query_datasource.py \
  --datasource-id industry_chain_company_info \
  --filters 'chain_name:like:新能源汽车;is_longtou_flag:eq:1'

# 查某产业链下的专精特新企业（按省份筛选）
python3 scripts/query_datasource.py \
  --datasource-id industry_chain_company_info \
  --filters 'chain_name:like:半导体;is_ssdi_flag:eq:1;base_name:eq:广东'
```

### 产业链区域指标查询
```bash
# 查某产业链在各省份的企业数量
python3 scripts/query_datasource.py \
  --datasource-id industry_chain_node_region_metric \
  --filters 'chain_name:like:新能源;region_level:eq:省' \
  --sort-field company_total_count \
  --sort-order desc

# 聚合统计某产业链的总企业数
python3 scripts/query_datasource.py \
  --datasource-id industry_chain_node_region_metric \
  --filters 'chain_name:like:人工智能' \
  --aggregation 'company_total_count:sum'
```

### 上市公司查询
```bash
# 按证券编码查询上市公司简况（code 必传）
python3 scripts/query_datasource.py \
  --datasource-id stock_company_brief \
  --filters 'code:eq:000001'
```

### 探查字段取值后再过滤
```bash
# 不确定 category（所属行业）有哪些取值？用枚举值查询一步搞定
python3 scripts/get_field_enums.py \
  --datasource-id enterprise_basic_wide --field category

# 看到取值后，用精确值过滤
python3 scripts/query_datasource.py \
  --datasource-id enterprise_basic_wide \
  --filters 'category:eq:信息传输、软件和信息技术服务业'
```

### 聚合统计查询
```bash
# 统计符合条件的总记录数
python3 scripts/query_datasource.py \
  --datasource-id industry_chain_company_info \
  --filters 'chain_name:like:新能源汽车' \
  --aggregation 'count'

# 按省份分组统计企业数量
python3 scripts/query_datasource.py \
  --datasource-id industry_chain_company_info \
  --filters 'chain_name:like:新能源汽车' \
  --group-by 'base_name' \
  --aggregation 'company_id:count'

# 按省份分组统计并去重
python3 scripts/query_datasource.py \
  --datasource-id industry_chain_company_info \
  --filters 'chain_name:like:新能源汽车' \
  --group-by 'base_name' \
  --aggregation 'company_id:distinct'
```

## 调用限制

- **频率限制**：每分钟最多 10 次调用
- **每日上限**：每天最多 200 次调用
- 如需更多调用次数，请购买 [火山引擎-高质量数据集](https://console.volcengine.com/high-quality-dataset)

## 错误处理

| 错误类型 | 原因 | 解决方案 |
|---------|------|---------|
| 认证失败 | 环境变量未设置或凭证无效 | 检查 `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY`，参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK |
| 数据源不存在 | datasource_id 错误 | 调用 `describe_datasource.py --datasource-id all` 确认 |
| 字段不支持操作符 | 操作符与字段类型不匹配 | 检查字段 type 并参照"字段类型与操作符对照表" |
| 字段不可用 | 字段名拼写错误或不可过滤 | 调用 `describe_datasource.py --datasource-id <ID>` 确认 |
| 无结果返回 | 过滤条件过严或字段取值不对 | 先用 `get_field_enums.py` 探查字段实际取值，或放宽条件（如 `eq` 改为 `like`） |
| 频率限制 | 调用次数超限 | 分钟限流等 1 分钟，日限流等次日 |

环境变量配置方式：
```bash
export VOLCENGINE_ACCESS_KEY="your-access-key"
export VOLCENGINE_SECRET_KEY="your-secret-key"
```
