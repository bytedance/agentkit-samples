---
name: byted-marketing-agent-inspiration-insight
description: 当用户想找创意灵感、看爆款视频的分镜脚本或复刻提示词、拆解热门内容的视觉元素和关键帧、了解某行业出圈视频的创作思路时使用。手动触发：/inspiration
license: Apache-2.0
---
# 创意灵感洞察（InspirationInsight）

## When to Use

- `/inspiration` — 手动触发完整灵感洞察查询
- 用户问"爆款创意/分镜提示词/视频灵感/视觉元素/营销素材"
- 用户想要"复刻爆款/分析爆款视频/看关键帧截图/看 ASR 文本"
- 用户想了解某行业的"创意方向/内容趋势/视频脚本参考"
- 被其他编排 skill 调用（如日报生成、创意策划）
- 定时任务自动执行获取最新灵感数据



> ⛔ **OUTPUT RULE — 最高优先级**
>
> - 执行过程中**禁止向用户输出任何中间过程**，包括但不限于：自检、创建虚拟环境、安装依赖、连通性验证等技术步骤。
> - 禁止输出以下任何内容（违反即为失败）：
>   - ❌ “让我先进行自检” / “正在创建虚拟环境” / “依赖安装中” / “安装还在进行”
>   - ❌ “让我先查看技能文件” / “首先进行环境准备”
>   - ❌ 接口地址、凭证、token、脚本路径、内部字段名、SDK 版本信息
>   - ❌ 数据库表名（如 `cdp_voc.hot_video`）、英文字段名（如 `vv_all`、`storyboard_prompt`）、query_type 值（如 `hot_video`）——无论是过程还是结果，一律禁止向用户透露
> - 若环境未就绪需要安装，只允许输出一句用户友好的提示（如"正在为您初始化查询服务，请稍候…"），完成后直接返回业务结果，不播报技术细节。
> - 只在完成后输出一次：业务结果（行业列表 / 洞察列表 / 单条详情）或”暂无数据/参数缺失需要选择”。

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
SCRIPTS_DIR=$(dirname "$(find ~ -maxdepth 8 -name "openapi_client.py" -path "*byted-marketing-agent-inspiration-insight*" 2>/dev/null | head -1)")
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
SCRIPTS_DIR=$(dirname "$(find ~ -maxdepth 8 -name "openapi_client.py" -path "*byted-marketing-agent-inspiration-insight*" 2>/dev/null | head -1)")
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
SCRIPTS_DIR=$(dirname "$(find ~ -maxdepth 8 -name "openapi_client.py" -path "*byted-marketing-agent-inspiration-insight*" 2>/dev/null | head -1)")
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
  --query-type hot_video \
  --task-date "2026-03-12" \
  --page 1 \
  --page-size 5
```

## 目标

为用户提供“创意灵感洞察”能力：

1. 通过“接口1”获取可查询行业枚举（仅行业，不包含 type）。
2. 用户选定行业后，使用本 Skill 固定的 `type` 查询该行业下的灵感洞察列表。
3. 用户点选某条记录后，按唯一键获取详情（可选：从列表上下文展开或再查一次详情）。

## 交互逻辑（必须）

**当本 Skill 被触发时：必须先主动调用接口1获取最新行业枚举（无论用户是否已提供行业）。**

### Step 1：行业枚举（共用接口1）

- 当用户未明确行业时：先获取行业列表并让用户选择。
- 当用户明确行业时：仍允许在必要时刷新行业列表用于校验/纠错。

通过 Bash 调用脚本（必须使用虚拟环境 Python）：

```bash
$VENV_PY \
  $SCRIPTS_DIR/openapi_client.py \
  ${VOLC_AK_INPUT:+--ak "$VOLC_AK_INPUT"} ${VOLC_SK_INPUT:+--sk "$VOLC_SK_INPUT"} \
  --format text list-industries
```

### Step 2：按行业查询（type 由本 Skill 固定控制）

- 本 Skill 的 `query_type` **固定为** `hot_video`（不要向用户暴露/询问 type）。
- **始终使用 `--format json`**，脚本返回完整字段，由你负责格式化展示。
- 默认按 `播放量 DESC`（播放量倒序）排序；用户可指定其他字段排序。

```bash
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
$VENV_PY \
  $SCRIPTS_DIR/openapi_client.py --format json \
  ${VOLC_AK_INPUT:+--ak "$VOLC_AK_INPUT"} ${VOLC_SK_INPUT:+--sk "$VOLC_SK_INPUT"} \
  query \
  --category "{industry_name}" \
  --query-type hot_video \
  --task-date "$YESTERDAY" \
  --order-by "播放量 DESC" \
  --page 1 \
  --page-size 20
```

用户要求按其他维度排序时，替换 `--order-by` 的值，例如：
- `"点赞数 DESC"` — 点赞最多
- `"评论数 DESC"` — 评论最多
- `"分享数 DESC"` — 分享最多
- `"5秒完看率 DESC"` — 5秒完看率最高
- `"完播次数 DESC"` — 完播次数最多

**每次返回列表结果后，主动告知用户可以按哪些字段排序**，示例引导语：
> 💡 当前按播放量排序，你也可以让我改成按「点赞数」「评论数」「分享数」「5秒完看率」排序。

### Step 3：详情展开（可选）

```bash
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
$VENV_PY \
  $SCRIPTS_DIR/openapi_client.py --format json \
  ${VOLC_AK_INPUT:+--ak "$VOLC_AK_INPUT"} ${VOLC_SK_INPUT:+--sk "$VOLC_SK_INPUT"} \
  query \
  --category "{industry_name}" \
  --query-type hot_video \
  --task-date "$YESTERDAY" \
  --filter "视频ID = '{item_id}'" \
  --page 1 \
  --page-size 1
```

## 数据字段说明

接口返回每条记录为一个爆款视频，**全部透传、不裁剪**：

| 字段名     | 含义                           |
| ---------- | ------------------------------ |
| 视频ID     | 视频唯一 ID                    |
| 标题       | 视频标题                       |
| 创建日期   | 视频创建日期                   |
| 链接       | 抖音视频链接                   |
| 播放量     | 累计播放量                     |
| 点赞数     | 累计点赞数                     |
| 评论数     | 累计评论数                     |
| 分享数     | 累计分享数                     |
| 关注数     | 累计关注数                     |
| 收藏数     | 累计收藏数                     |
| 自然流播放量 | 自然流播放量                 |
| 软广播放量 | 软广播放量                     |
| 硬广播放量 | 硬广播放量                     |
| 5秒完看率  | 5秒完看率                      |
| 完播次数   | 完播次数                       |
| 跳过次数   | 被跳过的总播放次数             |
| 商业类型   | 商业类型标签                   |
| 语音文本   | 视频语音转文字（ASR）          |
| 画面文字   | 视频画面文字（OCR）            |
| 润色文案   | 润色后的语音文本               |
| 视频分析   | 多模态视频逐镜分析（JSON）     |
| 分析提示词 | 生成视频分析的提示词           |
| 分镜脚本   | 分镜脚本提示词                 |
| 关键帧截图 | 关键帧截图 URL（JSON）         |
| 复刻提示词 | 复刻视频的生成提示词（JSON）   |
| 当日播放 / 当日点赞 等 | 当日播放/点赞/评论/分享/关注 |
| 产出日期   | 任务运行结束日期               |
| 任务名 / 行业 / 任务日期 | 任务元信息            |

## 展示规范

> ⛔ **禁止**在下方模板规定的结构之外添加任何内容，包括引言、总结、个人分析或额外说明。禁止直接粘贴原始 JSON。

### 列表视图（固定模板，不可更改列或顺序）

```
## 📊 {行业} 热门视频（{task_date}）｜按{排序字段中文名}排序

| # | 标题 | 播放量 | 点赞 | 5秒完看率 | 完播 | 链接 |
|---|------|--------|------|-----------|------|------|
| 1 | {标题} | {播放量}万 | {点赞数}万 | {5秒完看率}% | {完播次数}万 | [▶](url) |
...

💡 你可以继续问我：
- {引导问题1}
- {引导问题2}
- {引导问题3}
```

数值规则：保留1位小数，不足1万显示原值；标题超20字截断加"…"；`url` 为空时显示"—"。

### 详情视图（保留自由度）

按用户问题意图选择展示字段，但必须遵循：

- 以视频标题为 H3 标题开头
- `关键帧截图` 图片用 `![](url)` 内嵌
- `视频分析`、`复刻提示词` 等 JSON 字段解析后按内容逻辑展示
- `润色文案`、`分镜脚本` 等长文本全量输出，不截断

**意图 → 优先字段映射：**

| 用户问的是… | 优先展示 |
|-------------|----------|
| 分镜 / 脚本 | `分镜脚本` |
| 说了什么 / 台词 / 文案 | `润色文案` |
| 关键帧 / 截图 | `关键帧截图`（图片内嵌） |
| 复刻 / 生成提示词 | `复刻提示词` |
| 视频分析 / 镜头 | `视频分析` |
| 看全部 / 详情 | 所有非空字段，按上表顺序依次展示 |

末尾必须附 3 条引导问题。

## 引导提问规范（每次返回结果后必须执行）

**每次输出业务结果后，必须在末尾附上 2～3 个引导问题**，帮助用户深入探索。引导问题要根据当前结果内容动态生成，不要每次都一样。

### 返回行业列表后

> 💡 你可以继续问我：
>
> - "帮我查一下**美妆**行业的创意灵感洞察"
> - "我想看**服饰**行业最近有哪些爆款创意"

### 返回洞察列表后

> 💡 你可以继续问我：
>
> - "帮我展开第 1 条的详细分析"（或点名某个标题）
> - "这条视频的分镜提示词是什么？"
> - "帮我看看它的关键帧截图"
> - "换一个行业查创意灵感"

### 返回单条详情后

> 💡 你可以继续问我：
>
> - "把这条的分镜提示词完整给我"
> - "看看列表里其他的创意"
> - "换成**食品**行业查一下有没有类似风格的爆款"

> **原则**：引导问题要具体（带上当前行业名、视频标题或字段名），让用户感觉只需直接回复即可继续探索。

## 参数规则

- `industry_name`：用户可感知维度；必须来自接口1返回的行业枚举（或与其一致）。
- `task_date`：默认取 **T-1（昨天）**，即 `$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)`；用户指定日期时以用户为准。
- `type`：**禁止从接口1下发**；由本 Skill 内部固定为 `inspiration_insight`。

## 错误处理

- 接口调用失败：只向用户输出简短失败原因（不要包含 URL/Token/脚本名/堆栈）。
- 行业缺失：输出行业候选列表（适度截断），让用户选择。
- 无数据：输出“该行业暂无灵感洞察数据”。

## 凭证说明（仅供执行时使用，禁止回显给用户）

### Volcengine SDK 鉴权（接口调用必需）

> 本 Skill 使用 `volcenginesdkcore.ApiClient` 向 `cdp-saas.cn-beijing.volcengineapi.com` 发起签名请求。
> Action: `ArkOpenClawSkill`，Version: `2022-08-01`。

凭证**仅通过用户输入获取**，优先级：`--ak`/`--sk` 参数 > 环境变量 `VOLCENGINE_ACCESS_KEY`/`VOLCENGINE_SECRET_KEY`。

- `VOLCENGINE_ACCESS_KEY`：AccessKey
- `VOLCENGINE_SECRET_KEY`：SecretKey
- `VOLC_SERVICE`：覆盖 Service 名（可选，默认 `cdp_saas`）
- `VOLCENGINE_REGION`：覆盖 Region（可选，默认 `cn-beijing`）

### 可选覆盖

- `PUBLIC_INSIGHT_API_URL`：覆盖默认接入点（仅限内部调试）

> 安全要求：禁止在 `SKILL.md` 或代码中硬编码明文 AK/SK。