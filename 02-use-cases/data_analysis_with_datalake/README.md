# Data Analysis with Code Project

## 项目概述

这是一个基于 LanceDB 构建的数据分析框架，使用 IMDB 数据集，支持结构化数据查询、非结构化混合检索、元数据搜索和非结构化数据处理等多种功能。

## 架构

### 技术栈

- **LanceDB**: 用于高效元数据搜数、向量和结构化数据存储与检索
- **DuckDB**: 用于结构化数据的 SQL 查询
- **LAS**: 用于非结构化数据的处理和生成，如视频生成

### 核心组件

#### 1. 结构化数据查询 (`duckdb_sql_execution.py`)

- **功能**: 允许用户通过 SQL 语句查询结构化数据
- **技术**: 基于 DuckDB 数据库引擎
- **应用场景**: 执行传统的结构化数据查询、过滤和聚合操作

#### 2. 非结构化混合检索 (`lancedb_hybrid_execution.py`)

- **功能**: 支持将结构化查询与向量检索相结合，实现混合查询
- **技术**: 基于 LanceDB 的向量检索能力
- **应用场景**: 处理同时包含结构化属性和非结构化内容的查询需求

#### 3. 元数据搜索 (`catalog_discovery.py`)

- **功能**: 提供数据集元数据的搜索和发现功能
- **技术**: 基于目录结构的元数据管理
- **应用场景**: 帮助用户了解可用数据集的结构和内容

#### 4. 非结构化数据处理 (`video_generation.py`)

- **功能**: 支持将非结构化数据（如图片）转换为视频
- **技术**: 基于视频生成算法
- **应用场景**: 实现图片到视频的转换功能

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

## 配置流程

### 1. 配置文件设置

编辑 `data_analysis_with_code/agentkit_deploy/settings.txt` 文件，可选配置以下：

```
MODEL_AGENT_API_KEY=your_api_key_here
VOLCENGINE_ACCESS_KEY=your_ak
VOLCENGINE_SECRET_KEY=your_sk

```

### 2. 项目部署

```bash
uv python install 3.12
uv venv -p 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt

# veadk运行
veadk web

# 在agentkit上运行
agentkit config --tos_bucket <your bucket name>
agentkit launch
```

## 客户端连接

### 方式一：使用 Python 客户端

当使用 agentkit 运行时可以通过 client 进行连接

```bash
python client.py
```

### 方式二：使用 Web 界面

```bash
streamlit run web/app.py
```

## 示例问题

1. **Q1: 你有哪些数据？**
2. **Q2: 给我一些样例数据？**
3. **Q3: Ang Lee 评分超过 7 分的有哪些电影？**
4. **Q4: Ang Lee 评分超过 7 分的电影中，有哪个电影海报中含有动物？**
5. **Q5: Life of Pi 的电影海报，变成视频**
6. **Q6: 帮我找一张海报里有红色机车的电影，并把它做成视频**

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

## 文件结构

```
data_analysis_with_code/
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
