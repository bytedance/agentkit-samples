本文档用于说明 `byted-volcengine-finops` Skill 的本地准备方式。这个 Skill 固定依赖火山引擎 Python SDK，并通过 `billing` 服务的账单接口完成查询和分析。

如果您需要查阅接口字段说明、请求参数和返回参数备注，可同时参考：

- `references/billing-api-notes.md`

## 目标

完成以下准备后，才适合使用本 Skill 做账单分析：

- 本机已安装可用的 Python 运行环境
- 当前环境已安装火山引擎 Python SDK
- 已具备查询账单所需的火山引擎凭证与权限

## 步骤一：安装 Python SDK

建议安装或升级到较新的 5.x 版本：

```bash
pip install --upgrade "volcengine-python-sdk>=5.0.30"
```

如果您使用虚拟环境，推荐先激活虚拟环境再安装依赖。

## 步骤二：验证 SDK 可用

建议先验证 SDK 已正确安装：

```bash
python3 -c "import volcenginesdkcore; print('volcengine sdk ready')"
```

如果输出 `volcengine sdk ready`，说明基础 SDK 已可用。

如果还要确认 Skill 自带脚本已经就位，可继续执行：

```bash
python3 scripts/list_bill_overview_by_category.py --help
python3 scripts/list_bill_overview_by_prod.py --help
python3 scripts/list_bill_detail.py --help
python3 scripts/list_amortized_cost_bill_detail.py --help
python3 scripts/list_split_bill_detail.py --help
```

以上命令建议在 `byted-volcengine-finops` Skill 目录下执行。

## 步骤三：配置认证信息

这个 Skill 虽然只做账单查询，但仍然依赖有效的火山引擎认证信息与账单读取权限。推荐通过环境变量或 `.env` 文件配置：

### 方式一：环境变量

```bash
export VOLCENGINE_AK="your-ak"
export VOLCENGINE_SK="your-sk"
export VOLCENGINE_REGION="cn-beijing"
```

### 方式二：`.env` 文件

在 `~/.openclaw/workspace/.env` 中配置：

```env
VOLCENGINE_AK=your-ak
VOLCENGINE_SK=your-sk
VOLCENGINE_REGION=cn-beijing
```

## 步骤四：确认账单查询权限

执行前请确认：

- 所使用账号具备 `billing` 相关查询权限
- 能访问费用中心账单相关接口
- 账期和目标账号在当前凭证下可见

如果您的环境有统一的凭证配置规范，优先遵循团队已有方式，不要在代码中硬编码密钥。

## 推荐使用顺序

实际分析账单时，建议按以下顺序使用接口：

1. `ListBillOverviewByCategory`
   - 先看账号整体账单总览
2. `ListBillOverviewByProd`
   - 再看产品维度成本分布
3. `ListBillDetail`
   - 需要下钻时查看账单明细
4. `ListAmortizedCostBillDetail`
   - 需要看分摊后成本时查询成本账单明细
5. `ListSplitBillDetail`
   - 需要核对分账结果时查看分账明细

对应脚本：

- `scripts/list_bill_overview_by_category.py`
- `scripts/list_bill_overview_by_prod.py`
- `scripts/list_bill_detail.py`
- `scripts/list_amortized_cost_bill_detail.py`
- `scripts/list_split_bill_detail.py`

## 注意事项

- `ListBillDetail`、`ListBillOverviewByProd`、`ListSplitBillDetail` 都是分页接口，分析时不要遗漏翻页
- `ListAmortizedCostBillDetail` 也是分页接口，分析时不要遗漏翻页
- 账单查询以 `BillPeriod` 为核心时间参数，跨月范围应拆成多个账期分别查询
- 成本账单查询以 `AmortizedMonth` 为核心时间参数，跨月范围应拆成多个分摊月分别查询
- 需要精确到单日时，可在单月内补充 `ExpenseDate`
- 需要精确到单日成本时，可在单月内补充 `AmortizedDay`
- 账单分析结论依赖时间范围、过滤条件和汇总口径，执行前应先确认这些前置条件
