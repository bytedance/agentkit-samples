# Data Analysis with Datalake Project

## 概述

这是一个基于 LanceDB 构建的数据分析框架，使用 IMDB 数据集，支持结构化数据查询、非结构化混合检索、元数据搜索和非结构化数据处理等多种功能。

## 技术栈

- **LanceDB**: 用于高效元数据搜数、向量和结构化数据存储与检索
- **DuckDB**: 用于结构化数据的 SQL 查询

## 核心功能

### 结构化数据查询 (`duckdb_sql_execution.py`)

- **功能**: 允许用户通过 SQL 语句查询结构化数据
- **技术**: 基于 DuckDB 数据库引擎
- **应用场景**: 执行传统的结构化数据查询、过滤和聚合操作

### 非结构化混合检索 (`lancedb_hybrid_execution.py`)

- **功能**: 支持将结构化查询与向量检索相结合，实现混合查询
- **技术**: 基于 LanceDB 的向量检索能力
- **应用场景**: 处理同时包含结构化属性和非结构化内容的查询需求

### 元数据搜索 (`catalog_discovery.py`)

- **功能**: 提供数据集元数据的搜索和发现功能
- **技术**: 基于目录结构的元数据管理
- **应用场景**: 帮助用户了解可用数据集的结构和内容

### 非结构化数据处理 (`video_generation.py`)

- **功能**: 支持将非结构化数据（如图片）转换为视频
- **技术**: 基于视频生成算法
- **应用场景**: 实现图片到视频的转换功能

## Agent 能力

- 工具调用
- 大模型

## 目录结构说明

```bash
05_data_analysis_with_datalake/
├── agent.py
├── prompts.py
├── requirements.txt
├── settings.txt
└── tools/
    ├── catalog_discovery.py
    ├── duckdb_sql_execution.py
    ├── lancedb_hybrid_execution.py
    └── video_generation.py
├── client.py
└── web/
    └── app.py
```

## 数据集说明

本项目使用 IMDB 数据集，包含以下两个主要组成部分：

### 1. 元数据表

提供数据集的整体描述和结构信息，帮助用户了解可用的数据资源，其中包含每一列的描述、数据类型、样例值和可能的取值范围。

### 2. IMDB 电影数据表 (`imdb_top_1000`)

包含 1000 部电影的详细信息，主要字段包括：

| 字段名                  | 类型   | 描述                                                                     |
| ----------------------- | ------ | ------------------------------------------------------------------------ |
| `series_title`          | 字符串 | 电影标题                                                                 |
| `released_year`         | 字符串 | 上映年份（注意：虽然是年份数字，但为字符串类型，比较操作需用单引号包裹） |
| `director`              | 字符串 | 导演                                                                     |
| `genre`                 | 字符串 | 电影类型                                                                 |
| `imdb_rating`           | 浮点数 | IMDB 评分                                                                |
| `poster_curde_link`     | 字符串 | 电影缩略图海报链接                                                       |
| `poster_precision_link` | 字符串 | 电影海报高清链接                                                         |

## 本地运行

### 方式一：使用 Python 客户端

当使用 agentkit 运行时可以通过 client 进行连接

```bash
python client.py
```

### 方式二：使用 Web 界面

```bash
streamlit run web/app.py
```

## AgentKit 部署

### 配置文件设置

编辑 `05_data_analysis_with_datalake/settings.txt` 文件，可选配置以下 or export these env variable instead.

```text
MODEL_AGENT_API_KEY=your_api_key_here
VOLCENGINE_ACCESS_KEY=your_ak
VOLCENGINE_SECRET_KEY=your_sk
```

### 使用命令行部署

```bash
uv python install 3.12
uv venv -p 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt

# cli run
adk run 05_data_analysis_with_datalake
#Prompt: what is data and list movies with score > 9 from director Francis Ford

# veadk运行
veadk web

# 在agentkit上运行
agentkit config --tos_bucket <your bucket name>
agentkit launch
```

## 示例提示词

1. **Q1: 你有哪些数据？**
2. **Q2: 给我一些样例数据？**
3. **Q3: Ang Lee 评分超过 7 分的有哪些电影？**
4. **Q4: Ang Lee 评分超过 7 分的电影中，有哪个电影海报中含有动物？**
5. **Q5: Life of Pi 的电影海报，变成视频**
6. **Q6: Hayao Miyazaki（宫崎骏）的电影评分超过 7.5，包含飞机的海报，生成视频**
7. **Q7: 全库概览 - 列出当前数据库中所有的表名，并描述各表的主要用途。**
8. **Q8: Schema 校验 - 查询 imdb_top_1000 表的详细 Schema 信息，确认 released_year 字段的具体数据类型。**
9. **Q9: 数据采样 - 从 imdb_top_1000 表中随机抽取 5 条完整记录进行展示。**
10. **Q10: 总量统计 - 统计数据集中电影记录的总条数。**
11. **Q11: 等值过滤 - 查询导演（Director）为 "Christopher Nolan" 的所有电影列表。**
12. **Q12: 数值范围 - 筛选出 IMDB 评分（imdb_rating）严格大于 9.0 的电影。**
13. **Q13: 类型隐式转换 - 检索 2000 年以后（含 2000 年）上映的所有电影。**
14. **Q14: 多条件复合 - 查询类型（Genre）包含 "Sci-Fi" 且评分高于 8.5 的电影。**
15. **Q15: 排序检索 - 按评分从高到低排序，返回前 10 部电影的标题。**
16. **Q16: 聚合计算 - 计算导演 "Steven Spielberg" 所有电影的平均评分。**
17. **Q17: 视觉特征检索 - 检索海报画面中包含“汽车（Car）”视觉元素的电影。**
18. **Q18: 具体物体识别 - 查找海报画面中出现“枪支（Gun）”或“武器（Weapon）”的电影。**
19. **Q19: 混合条件过滤 - 筛选出评分超过 8.0 且海报画面中包含“动物（Animal）”的电影。**
20. **Q20: 语义模糊匹配 - 基于语义检索推荐关于“太空探索（Space Exploration）”或“星际旅行”主题的电影。**
21. **Q21: 指定对象生成 - 调用视频生成工具，将电影《The Godfather》的海报转化为视频。**
22. **Q22: 条件触发生成 - 识别数据集中评分最高的电影，并基于其海报生成视频。**
23. **Q23: 特定实体生成 - 查询导演 "Hayao Miyazaki" 评分最高的作品，并对其海报执行视频生成操作。**
24. **Q24: 比较分析 - 统计并对比 "Christopher Nolan" 与 "Quentin Tarantino" 各自执导且评分大于 8.5 的电影数量。**
25. **Q25: 模糊时间范围 - 列出 1990 年至 1999 年间上映且评分最高的 3 部动作片（Action）。**
26. **Q26: 全链路综合测试 - 检索 2010 年之后上映、评分最高且海报中包含“人物肖像”的电影，并将其海报生成为视频。**

## 运行流程

当用户提出问题时，系统将遵循以下流程处理：

1. **搜数阶段 (Discovery)**：调用 `catalog_discovery` 工具确认可用的表名和字段信息。
2. **数据分析阶段 (Query)**：
   - 对于结构化统计或过滤查询，调用 `duckdb_sql_execution` 工具执行 SQL 查询
   - 对于语义、视觉或混合检索查询，调用 `lancedb_hybrid_execution` 工具执行向量检索
   - 对于图生视频等非结构化数据处理，调用 `video_generation` 工具执行相应操作
3. **结果处理阶段 (Result Handling)**：
   - 如果结果为空 `[]`，直接回答用户"未找到"
   - 如果结果正常，立即返回最终答案

## 效果展示

Datalake 效果展示。

## 常见问题

无。

## 代码许可

本工程遵循 Apache 2.0 License
