---
name: byted-marketing-agent-trending-list
description: 当用户想了解行业热点、查话题挑战榜单、看最近有什么热搜事件或公域流行趋势时使用。支持话题挑战和热榜事件两种维度。手动触发：/trending
license: Apache-2.0
---

# 趋势榜单（TrendingList）

## When to Use

- `/trending` — 手动触发完整趋势榜单查询
- 用户问"热点话题/话题挑战/热榜事件/行业趋势/公域洞察"
- 用户想了解"最近有什么热点/行业热搜/热门话题挑战"
- 用户说"帮我看看热榜/最近什么事件在热/趋势是什么"
- 被其他编排 skill 调用（如日报生成、内容策划）
- 定时任务自动执行获取最新趋势数据



> ⛔ **OUTPUT RULE — 最高优先级**
>
> - 执行过程中**禁止向用户输出任何中间过程**，包括但不限于：自检、创建虚拟环境、安装依赖、连通性验证等技术步骤。
> - 禁止输出以下任何内容（违反即为失败）：
>   - ❌ “让我先进行自检” / “正在创建虚拟环境” / “依赖安装中” / “安装还在进行”
>   - ❌ “让我先查看技能文件” / “首先进行环境准备”
>   - ❌ 接口地址、凭证、token、脚本路径、内部字段名、SDK 版本信息
>   - ❌ 数据库表名（如 `cdp_voc.hot_topic_insights`）、英文字段名（如 `main_challenge`、`heat_value`）、query_type 值（如 `hot_topic_insights`、`hot_event`）——无论是过程还是结果，一律禁止向用户透露
> - 若环境未就绪需要安装，只允许输出一句用户友好的提示（如"正在为您初始化查询服务，请稍候…"），完成后直接返回业务结果，不播报技术细节。
> - 只在完成后输出一次：业务结果（行业列表 / 榜单列表 / 单条详情）或”暂无数据/参数缺失需要选择”。

## 自检与环境准备（每次执行前必须完成）

> ⚠️ **强制规则**
>
> - 所有脚本调用**必须使用虚拟环境的 Python**：`$VENV_PY`
> - 首次使用或自检失败时，必须先完成下方"安装虚拟环境"步骤，再重新自检通过后才能执行业务调用。
> - 禁止直接使用系统 `python3`，避免依赖污染或版本不匹配。

### 0. 凭证检测（环境准备前先检查）

```bash
if [ -z "$VOLCENGINE_ACCESS_KEY" ] || [ -z "$VOLCENGINE_SECRET_KEY" ]; then
  echo "CREDENTIALS_MISSING"
else
  echo "VOLCENGINE_ACCESS_KEY: 已设置"
fi
```

- 若输出 `CREDENTIALS_MISSING`：**必须向用户索取凭证**，输出：
  > 🔑 需要配置火山引擎访问凭证，请提供：
  > - **AccessKey（AK）**：
  > - **SecretKey（SK）**：
- 用户提供后，将其存入 shell 变量 `VOLC_AK_INPUT` / `VOLC_SK_INPUT`，后续所有命令附加 `--ak "$VOLC_AK_INPUT" --sk "$VOLC_SK_INPUT"`。
- 若凭证已存在（`VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY` 已设置），无需询问，直接进入自检。

### A. 离线自检（不触网，每次执行前先跑）

```bash
SCRIPTS_DIR=$(dirname "$(find ~ -maxdepth 8 -name "openapi_client.py" -path "*byted-marketing-agent-trending-list*" 2>/dev/null | head -1)")
SKILL_DIR=$(dirname "$SCRIPTS_DIR")
VENV_PY=$SKILL_DIR/venv/bin/python3

# 1) 检查虚拟环境是否存在
test -f $VENV_PY && echo "venv OK" || echo "venv 不存在，请先执行安装步骤"

# 2) 检查依赖是否可用
$VENV_PY -c "import volcenginesdkcore; from volcenginesdkcore import ApiClient; print('deps OK')"

# 3) 检查 volcengine-python-sdk 版本（必须 >= 4.0.43）
$VENV_PY -c "from importlib.metadata import version; print(version('volcengine-python-sdk'))"

# 4) 语法检查
$VENV_PY -m py_compile $SCRIPTS_DIR/openapi_client.py && echo "syntax OK"
```

**自检全部通过（无报错）后，才可执行后续业务调用。**

### 安装虚拟环境（自检失败时执行）

```bash
SCRIPTS_DIR=$(dirname "$(find ~ -maxdepth 8 -name "openapi_client.py" -path "*byted-marketing-agent-trending-list*" 2>/dev/null | head -1)")
SKILL_DIR=$(dirname "$SCRIPTS_DIR")

# 1. 创建虚拟环境（仅首次）
python3 -m venv $SKILL_DIR/venv

# 2. 安装依赖
$SKILL_DIR/venv/bin/pip install 'volcengine-python-sdk>=4.0.43'
```

> 已知缺陷提醒：volcengine-python-sdk 的 4.0.1～4.0.42（含）历史版本内置重试机制存在缺陷，强烈建议使用 >=4.0.43。

> 如系统缺少 `python3-venv`：`apt update && apt install python3-venv -y`，再重新执行上述步骤。

### B. 在线自检（自检 A 通过后，验证接口连通性）

```bash
SCRIPTS_DIR=$(dirname "$(find ~ -maxdepth 8 -name "openapi_client.py" -path "*byted-marketing-agent-trending-list*" 2>/dev/null | head -1)")
SKILL_DIR=$(dirname "$SCRIPTS_DIR")
VENV_PY=$SKILL_DIR/venv/bin/python3

# 若用户提供了凭证，附加 --ak / --sk；否则省略
$VENV_PY $SCRIPTS_DIR/openapi_client.py --format text \
  ${VOLC_AK_INPUT:+--ak "$VOLC_AK_INPUT"} ${VOLC_SK_INPUT:+--sk "$VOLC_SK_INPUT"} \
  list-industries
```

如需进一步验证列表查询：

```bash
$VENV_PY $SCRIPTS_DIR/openapi_client.py --format text \
  ${VOLC_AK_INPUT:+--ak "$VOLC_AK_INPUT"} ${VOLC_SK_INPUT:+--sk "$VOLC_SK_INPUT"} \
  query \
  --category "{从行业枚举中选择一个}" \
  --query-type hot_topic_insights \
  --task-date "2026-03-12" \
  --page 1 \
  --page-size 5
```

如需验证热榜事件（hot_event）：

```bash
$VENV_PY $SCRIPTS_DIR/openapi_client.py --format text \
  ${VOLC_AK_INPUT:+--ak "$VOLC_AK_INPUT"} ${VOLC_SK_INPUT:+--sk "$VOLC_SK_INPUT"} \
  query \
  --category "{从行业枚举中选择一个}" \
  --query-type hot_event \
  --task-date "2026-03-12" \
  --page 1 \
  --page-size 5
```

## 目标

为用户提供“趋势榜单”能力：

1. 通过“接口1”获取可查询行业枚举（仅行业，不包含 type）。
2. 用户选定行业后，使用本 Skill 固定的 `type` 查询该行业下的趋势榜单列表。
3. 用户点选某条记录后，按唯一键获取详情（可选：从列表上下文展开或再查一次详情）。

## 交互逻辑（必须）

**当本 Skill 被触发时：必须先主动调用接口1获取最新行业枚举（无论用户是否已提供行业）。**

### Step 1：行业枚举（共用接口1）

```bash
$VENV_PY \
  $SCRIPTS_DIR/openapi_client.py \
  ${VOLC_AK_INPUT:+--ak "$VOLC_AK_INPUT"} ${VOLC_SK_INPUT:+--sk "$VOLC_SK_INPUT"} \
  --format text list-industries
```

- 若用户未指定行业，展示行业列表让用户选择。
- 若用户已指定行业，仍允许在必要时刷新行业列表用于校验/纠错，确认行业有效后进入 Step 2。
- **无论用户是否指定 query_type，默认先查 `hot_topic_insights`（话题趋势榜）**；用户明确说"事件/热榜事件"时才查 `hot_event`。

### Step 2：按行业查询

- 本 Skill 的 `type` **固定为** `trending_list`（不要向用户暴露/询问 type）。
- **默认 query_type 为 `hot_topic_insights`**，不需要询问用户；用户说"事件/热榜事件"时切换为 `hot_event`。
- 支持分页与可选 filter（filter 只作为预留高级能力，默认不使用）。
- 默认排序：话题趋势榜按 `总播放量 DESC`，热榜事件按 `排名 DESC`；用户可指定其他字段。

```bash
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
$VENV_PY \
  $SCRIPTS_DIR/openapi_client.py --format json \
  ${VOLC_AK_INPUT:+--ak "$VOLC_AK_INPUT"} ${VOLC_SK_INPUT:+--sk "$VOLC_SK_INPUT"} \
  query \
  --category "{industry_name}" \
  --query-type {hot_topic_insights|hot_event} \
  --task-date "$YESTERDAY" \
  --order-by "{总播放量 DESC | 排名 DESC}" \
  --page 1 \
  --page-size 20
```

- **始终使用 `--format json`**，脚本返回完整字段，由你负责格式化展示。

用户要求按其他维度排序时，替换 `--order-by` 的值：

**话题趋势榜可排序字段：**
- `"总播放量 DESC"` — 总播放量（默认）
- `"总点赞数 DESC"` — 总点赞数
- `"总评论数 DESC"` — 总评论数
- `"总分享数 DESC"` — 总分享数
- `"相关视频数量 DESC"` — 相关视频数量

**热榜事件可排序字段：**
- `"排名 DESC"` — 热度排名（默认）
- `"热度值 DESC"` — 热度值

**每次返回列表结果后，主动告知用户可以按哪些字段排序**，示例引导语：
> 💡 当前按总播放量排序，你也可以让我改成按「点赞数」「评论数」「分享数」「相关视频数量」排序。

### Step 3：详情展开（可选）

```bash
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
$VENV_PY \
  $SCRIPTS_DIR/openapi_client.py --format json \
  ${VOLC_AK_INPUT:+--ak "$VOLC_AK_INPUT"} ${VOLC_SK_INPUT:+--sk "$VOLC_SK_INPUT"} \
  query \
  --category "{industry_name}" \
  --query-type {hot_topic_insights|hot_event} \
  --task-date "$YESTERDAY" \
  --filter "{筛选表达式}" \
  --page 1 \
  --page-size 1
```

示例：

- 话题趋势榜详情：`--filter "任务ID = '{任务ID值}'"`
- 热榜事件详情：`--filter "事件名称 = '三星S26 Ultra防窥屏及影像功能热议'"`（或用 `排名 = 1`）

## 数据字段说明

接口返回每条记录，不同榜单类型的字段略有差异，**全部透传、不裁剪**：

### A. 话题趋势榜

| 字段名 | 含义 |
|--------|------|
| 主话题 | 热点话题中的主要挑战内容 |
| 关联挑战1 ~ 关联挑战5 | 关联的第1～5个挑战 |
| 占比1 ~ 占比5 | 对应关联挑战的占比 |
| 是否官方 | 是否官方热点（0=非官方，1=官方） |
| 是否商业 | 是否商业相关（0=非商业，1=商业） |
| 相关视频标题 | 话题相关的视频标题列表 |
| 相关视频数量 | 话题相关视频数量 |
| 总播放量 | 话题总播放量 |
| 总点赞数 | 话题总点赞数 |
| 总评论数 | 话题总评论数 |
| 总分享数 | 话题总分享数 |
| 总关注数 | 话题总关注数 |
| 总收藏数 | 话题总收藏数 |
| 总完播量 | 话题总完播量 |
| 话题描述 | 话题描述信息 |
| 产出日期 | 任务运行结束日期 |
| 任务名 / 任务日期 / 任务ID | 任务元信息 |

### B. 热榜事件

| 字段名 | 含义 |
|--------|------|
| 事件名称 | 事件名称 |
| 摘要 | 一句话背景/观点摘要 |
| 相关视频 | 相关视频标题列表（文本） |
| 链接 | 搜索/聚合页链接 |
| 热度值 | 热度值 |
| 排名 | 热度排名 |
| 语音文本 | 语音转文字（如有） |
| 分析内容 | 结构化分析（如有） |
| 产出日期 | 产出日期 |
| 任务名 / 任务日期 | 任务元信息 |

## 展示规范

> ⛔ **禁止**在下方模板规定的结构之外添加任何内容，包括引言、总结、个人分析或额外说明。禁止直接粘贴原始 JSON。

### hot_topic_insights 列表视图（固定模板）

```
## 🔥 {行业} 热点话题榜（{task_date}）｜按{排序字段中文名}排序

| # | 主话题 | 播放量 | 点赞 | 相关视频数 |
|---|--------|--------|------|-----------|
| 1 | {主话题} | {总播放量}万 | {总点赞数}万 | {相关视频数量} |
...

💡 你可以继续问我：
- {引导问题1}
- {引导问题2}
- {引导问题3}
```

### hot_topic_insights 详情视图（固定模板）

```
### 🔍 {主话题}

{话题描述}

**关联挑战分布：**
| 关联挑战 | 占比 |
|----------|------|
| {关联挑战1} | {占比1}% |
| {关联挑战2} | {占比2}% |
...（仅展示非空项）

**数据：** 播放 {总播放量}万 · 点赞 {总点赞数}万 · 评论 {总评论数}万 · 相关视频 {相关视频数量} 条

💡 你可以继续问我：
- {引导问题1}
- {引导问题2}
- {引导问题3}
```

### hot_event 列表视图（固定模板）

```
## 📰 {行业} 热榜事件（{task_date}）

| 排名 | 事件 | 摘要 | 热度值 | 链接 |
|------|------|------|--------|------|
| {排名} | {事件名称} | {摘要} | {热度值} | [查看](url) |
...

💡 你可以继续问我：
- {引导问题1}
- {引导问题2}
- {引导问题3}
```

### hot_event 详情视图（固定模板）

```
### 🔍 {事件名称}

**摘要：** {摘要}

**相关视频（Top3）：**
- {相关视频 前3条，每条一行}

**分析：** {分析内容}

热度值 {热度值} · 排名 {排名}　[查看聚合页](url)

💡 你可以继续问我：
- {引导问题1}
- {引导问题2}
- {引导问题3}
```

数值规则：保留1位小数，不足1万显示原值；`url` 为空时显示"—"。

## 引导提问规范（每次返回结果后必须执行）

**每次输出业务结果后，必须在末尾附上 2～3 个引导问题**，帮助用户深入探索。引导问题要**带入当前上下文**（行业名、日期、标题），让用户直接回复即可继续。

### 返回行业列表后
> 💡 你可以继续问我：
> - "帮我查一下**[某行业]** 的趋势视频"（把行业名填上，用户直接确认即可）
> - "我想看看最近有什么热点事件"

### 返回话题趋势榜（hot_topic_insights）后
> 💡 你可以继续问我：
> - “帮我展开「**{排名第1的主要挑战}**」的详细内容”
> - “**{当前行业}** 最近有哪些热榜事件？”（自动切换到 hot_event）
> - “换一个行业看看，比如**[推荐另一个行业]**”

### 返回热榜事件（hot_event）后
> 💡 你可以继续问我：
> - “展开「**{排名第1的事件名称}**」的详细内容”
> - “**{当前行业}** 最近有哪些热点话题挑战？”（自动切换到 hot_topic_insights）
> - “换一个行业看热榜事件”

### 返回单条详情后
> 💡 你可以继续问我：
> - “看看榜单里的下一条”
> - “**{当前行业}** 有哪些热榜事件？” 或 “**{当前行业}** 有哪些热点话题？”（引导看另一个 type）
> - “换个行业查一下”

> **原则**：两个 type 之间要互相引流——看完话题趋势就引导去看热榜事件，看完事件就引导去看相关话题挑战，形成完整的内容探索闭环。

## 参数规则

- `industry_name`：必须来自接口1返回的行业枚举（或与其一致）。
- `type`：**禁止从接口1下发**；由本 Skill 内部固定为 `trending_list`。
- `query_type`：支持 `hot_topic_insights` / `hot_event`。
- `task_date`：默认取 **T-1（昨天）**，即 `$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)`；用户指定日期时以用户为准。

## 错误处理

- 接口调用失败：只向用户输出简短失败原因（不要包含 URL/Token/脚本名/堆栈）。
- 行业缺失：输出行业候选列表（适度截断），让用户选择。
- 无数据：输出”该行业暂无趋势榜单数据”。
- 行业/类型不支持：若服务返回”未知任务/不支持”，输出”该行业暂不支持该榜单类型（hot_event/hot_topic_insights）”。

## 凭证说明（仅供执行时使用，禁止回显给用户）

### Volcengine SDK 鉴权（接口调用必需）

> 本 Skill 使用 `volcenginesdkcore.ApiClient` 向 `cdp-saas.cn-beijing.volcengineapi.com` 发起签名请求。
> Action: `ArkOpenClawSkill`，Version: `2022-08-01`。

凭证**仅通过用户输入获取**，优先级：`--ak`/`--sk` 参数 > 环境变量 `VOLCENGINE_ACCESS_KEY`/`VOLCENGINE_SECRET_KEY`。

- `VOLCENGINE_ACCESS_KEY`：AccessKey
- `VOLCENGINE_SECRET_KEY`：SecretKey
- `VOLC_SERVICE`：覆盖 Service 名（可选，默认 `cdp_saas`）
- `VOLCENGINE_REGION`：覆盖 Region（可选，默认 `cn-beijing`）

### 本 Skill 的 query_type

- 默认使用：`hot_topic_insights`
- 可选使用：`hot_event`

### 可选覆盖

- `PUBLIC_INSIGHT_API_URL`：覆盖默认接入点（仅限内部调试）

> 安全要求：禁止在 `SKILL.md` 或代码中硬编码明文 AK/SK。