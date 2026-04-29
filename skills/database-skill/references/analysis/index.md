# 数据分析

## 核心原则

1. **先理解，后执行**：动手前先理解用户真实需求和数据环境。
2. **专家视角**：从数据分析师角度提供专业分析，不只返回查询结果。
3. **多想一步**：主动发现异常、趋势和洞察，不仅回答字面问题。
4. **数据诚实**：绝不编造数据，图表不误导。如实呈现异常值和缺失值。
5. **结论先行**：先说好还是不好，再说为什么。

## 全局要求

- **语言适配**：跟随用户输入语言（中文→全流程中文，English→English）
- **核心产出**：每次完整分析必须包含 ① HTML 交互报告 ② PNG 静态截图 ③ 结构化文字结论
- **生成报告前必须问**：受众是谁？用途是什么？

> 函数参数、数据库兼容性、返回格式详见 [api/metadata-query.md](../api/metadata-query.md)。

## 工作流（7 步）

| 步骤 | 目标 | 关键 API | 输出 |
|------|------|----------|------|
| 1. 数据探查 | 理解数据环境，确定目标表和字段 | `list_tables`, `get_table_info`, `query_sql`(LIMIT 10) | 表结构、字段含义、样例数据 |
| 2. 数据获取 | 获取原始数据 | `query_sql` / `execute_sql` / `nl2sql` + `MultiSourceAnalyzer` | DataFrame / CSV |
| 3. 质量检查 | 检查缺失值、重复行、异常值 | pandas: `isnull()`, `duplicated()`, `describe()` | 质量问题列表 |
| 4. EDA 分析 | 探索性分析，发现规律和异常 | pandas 聚合 + 框架分析 | 统计指标、趋势、对比 |
| 5. 结论提炼 | 输出结构化结论 | — | 核心洞察 + 行动建议 |
| 6. 报告生成 | HTML 可视化报告 + PNG 截图 | Write 工具 + Playwright | `analysis_report.html` + `.png` |
| 7. 交付 | 展示 PNG + HTML 链接给用户 | — | 最终回复 |

**自主执行原则**：用户给出了明确分析任务时（如"帮我分析某表"），自主选表、自主构造 SQL 并执行。只在以下阻断点才询问：字段含义不明、找不到目标表、列值无法对应业务含义。

**趋势查询**：用户要求"趋势"、"变化"、"时间维度"时，SQL 必须包含时间列的 GROUP BY（如 `GROUP BY DATE(create_time)`），输出时间序列数据。不能只返回总量统计。

## 数据探查策略

探查顺序：实例 → 数据库 → 表 → 字段 → 样例数据。

```python
from toolbox import create_client, list_instances, list_databases, list_tables, get_table_info, query_sql

client = create_client()

# 找实例
instances = list_instances(client, instance_name="my_instance")

# 找数据库
dbs = list_databases(client, instance_id="mysql-xxx")

# 找表
tables = list_tables(client, instance_id="mysql-xxx", database="company", fetch_all=True)

# 查结构 + 样例
schema = get_table_info(client, table="orders", instance_id="mysql-xxx", database="company")
sample = query_sql(client, sql="SELECT * FROM orders LIMIT 10", instance_id="mysql-xxx", database="company")
```

## 数据获取

### 3000 行截断规则（必须理解）

`query_sql` / `execute_sql` 单次最多返回 **3000 行**，超出部分**静默截断**（不报错、不提示）。

> ⚠️ **返回 3000 行 = 数据被截断**，绝不能把 3000 当作真实总数。
> 需要真实计数时，必须用 `SELECT COUNT(*) FROM table WHERE ...`。

### 查询策略（必须遵守）

| 场景 | 做法 |
|------|------|
| 需要总数/聚合指标 | **必须用聚合 SQL**：`SELECT COUNT(*)`, `SUM()`, `AVG()` 等，在数据库端完成计算 |
| 小表（确认 < 3000 行） | 一条 SQL 拉原始数据，pandas 本地 groupby |
| 大表多维度分析 | SQL 端聚合：`SELECT a, b, COUNT(*), SUM(x) GROUP BY a, b`，1-2 条 SQL 覆盖所有维度 |
| ❌ 禁止 | 用返回行数当总数；每个维度单独发一条 SQL |

### 大表防护（防止超时）

聚合 SQL 也可能触发全表扫描导致超时。**查询前必须先评估表大小和索引**：

```python
# 1. 查表大小
from toolbox import create_client, execute_sql
client = create_client()
row_count = execute_sql(client, sql="SELECT COUNT(*) as cnt FROM my_table", database="mydb")

# 2. 查索引
index_info = execute_sql(client, sql="SHOW CREATE TABLE my_table", database="mydb")
plan = execute_sql(client, sql="EXPLAIN SELECT ...", database="mydb")
```

**按表大小选策略**：

| 表大小 | 有索引覆盖 WHERE/GROUP BY | 无索引 |
|--------|--------------------------|--------|
| < 10 万行 | 直接查 | 直接查 |
| 10 万 ~ 500 万行 | 直接聚合 | 加 WHERE 缩小范围（时间、主键区间） |
| > 500 万行 | 直接聚合 | **必须**加 WHERE 缩小范围，或分段采样 |

### 三种查询方式

1. **nl2sql**：`nl2sql(client, query, tables=[...])` → `execute_sql(client, sql=...)`。快但可能有字段偏差。
2. **查 schema 后自写 SQL**：`get_table_info` → 根据真实字段名写 SQL → `query_sql`。更精准。
3. **直接执行**：用户给了完整 SQL，或 `SHOW TABLES` / `EXPLAIN` 等固定语句。

## 多数据源联合（MultiSourceAnalyzer）

数据分散在多个数据库或需要 DB + 文件联合分析时使用。

```python
from toolbox import create_client, query_sql
from multi_source_analyzer import MultiSourceAnalyzer

analyzer = MultiSourceAnalyzer()

# 注册数据库查询结果
client = create_client()
df_orders = query_sql(client, sql="SELECT * FROM orders LIMIT 1000", database="company")
analyzer.register_dataframe('orders', df_orders)

# 注册本地文件（路径替换为用户实际文件）
analyzer.register_file('sales', '<path/to/sales.csv>')
analyzer.register_file('products', '<path/to/products.xlsx>', sheet='Product Inventory')

# 跨源 SQL 联合查询（基于 DuckDB）
result = analyzer.query("""
    SELECT o.order_id, s.region, s.target
    FROM orders o JOIN sales s ON o.region = s.region_code
""")
```

| 方法 | 说明 |
|------|------|
| `register_dataframe(name, df)` | 注册 DataFrame |
| `register_file(name, path, sheet=None)` | 注册文件（CSV/Excel/JSON/Parquet） |
| `list_sources()` | 查看已注册数据源 |
| `preview(name, n=5)` | 预览数据 |
| `describe(name)` | 查看结构 |
| `query(sql, limit=100)` | 执行跨源 SQL |

## AnalysisWorkflow（跨执行持久化）

每次 `python3 -c "..."` 都是独立进程，变量全部丢失。AnalysisWorkflow 将中间结果保存到磁盘。

**何时用**：需要 2 步以上的分析任务（探查→查询→分析→报告）。单步查询不需要。

**按需持久化**：核心需要持久化的：① 原始数据 ② 最终报告（HTML + PNG）。同一个 `python3 -c` 中能连续完成的步骤不需要分开持久化。

```python
from analysis_workflow import create_workflow, resume_workflow

# 创建
wf = create_workflow()
print(wf.get_analysis_id())

# 恢复
wf = resume_workflow("analysis_20260308_143022")

# 保存/加载
wf.save_step_output("02_acquisition", "raw_data.csv", df)
df = wf.load_step_output("02_acquisition", "raw_data.csv")

# 报告路径
html_path = wf.get_output_path("06_report", "analysis_report.html")
```

| 方法 | 说明 |
|------|------|
| `create_workflow()` | 创建工作区 |
| `resume_workflow(analysis_id)` | 恢复工作区 |
| `wf.save_step_output(step, filename, data)` | 保存（JSON/CSV） |
| `wf.load_step_output(step, filename)` | 加载 |
| `wf.get_output_path(step, filename)` | 获取输出文件路径 |

### 工作区目录

| 步骤 | 目录 | 典型输出 |
|------|------|----------|
| 数据探查 | 01_exploration/ | tables.json |
| 数据获取 | 02_acquisition/ | raw_data.csv |
| 质量检查 | 03_quality/ | quality_report.json |
| EDA 分析 | 04_eda/ | metrics.json |
| 结论提炼 | 05_conclusion/ | conclusion.md |
| 报告生成 | 06_report/ | analysis_report.html, .png |

## 报告生成

详见 [report.md](./report.md)。
