---
name: volcengine-web-search
version: 1.2.0
author: volcengine-search-team
description: 使用火山引擎融合信息搜索 API 进行联网搜索，返回适合 AI 使用的网页结果或图片结果。当用户要求联网检索、确认最新信息、搜索新闻、查官网资料、限定站点搜索、获取权威来源，或需要有来源支撑的搜索结果时使用。支持 API Key 和 AK/SK 两种鉴权方式。
homepage: https://www.volcengine.com/docs/85508/1650263
---

# 火山引擎联网搜索

使用火山引擎融合信息搜索 API 执行联网搜索，返回适合 AI 处理的网页结果或图片结果。

## 何时使用

当用户有以下需求时，优先使用本 skill：

- 需要联网搜索，而不是依赖模型记忆
- 需要确认“今天 / 最近 / 最新 / 当前”的信息
- 需要搜索新闻、公告、政策、价格、活动、产品动态
- 需要从特定站点或官网获取信息
- 需要给回答附上来源链接
- 需要图片搜索结果

## 使用前检查

优先检查是否已配置以下任一凭证：

- `TORCHLIGHT_API_KEY`
- `VOLCENGINE_ACCESS_KEY` + `VOLCENGINE_SECRET_KEY`

如果缺少凭证，打开 `references/setup-guide.md` 查看开通、申请和配置方式。

## 基本搜索

```bash
python3 scripts/web_search.py "搜索词"
python3 scripts/web_search.py "搜索词" --count 10
python3 scripts/web_search.py "搜索词" --type image
```

## 常用参数

- `--count <n>`：返回条数；`web` 最多 50 条，`image` 最多 5 条
- `--type <type>`：搜索类型，可选 `web` 或 `image`
- `--time-range <range>`：时间范围，可选 `OneDay`、`OneWeek`、`OneMonth`、`OneYear`，或日期区间 `2024-12-30..2025-12-30`
- `--sites <a|b>`：限定站点搜索，多个站点用 `|` 分隔
- `--block-hosts <a|b>`：排除站点，多个站点用 `|` 分隔
- `--auth-level 1`：优先权威来源

## 模式选择

- 用 `web`：普通事实查询、网页检索、查官网内容
- 用 `image`：用户明确要图片结果
- 加 `--time-range`：用户关心最近动态、新闻、时效性内容
- 加 `--sites`：用户指定官网、官方媒体、文档站或垂直站点
- 加 `--auth-level 1`：医疗、政策、金融、科研等更看重可信度的主题

## 推荐用法示例

```bash
# 查最近新闻
python3 scripts/web_search.py "OpenAI 最新发布" --time-range OneWeek

# 查官网资料
python3 scripts/web_search.py "Responses API 文档" --sites "platform.openai.com|openai.com"

# 查权威来源
python3 scripts/web_search.py "流感疫苗安全性" --auth-level 1

# 查图片
python3 scripts/web_search.py "故宫博物院" --type image
```

## 回答规则

- 基于搜索结果作答，不要编造搜索结果中没有支持的信息
- 优先保留标题、站点名、URL
- 涉及时效性问题时，优先使用时间过滤并明确说明时间范围
- 涉及高可信度主题时，优先使用限定站点或权威来源过滤
- 如果搜索结果不足以支持明确结论，应直接说明证据不足

## 故障排查

- 缺少凭证：打开 `references/setup-guide.md`
- 需要查 API 参数、字段、错误码：打开 `references/docs-index.md`
- 如果脚本返回权限错误，优先检查服务是否已开通、凭证是否有效、子账号是否已授权

## 参考资料

按需打开以下文件，不必默认全部加载：

- `references/setup-guide.md`：服务开通、凭证申请、环境变量配置
- `references/docs-index.md`：API 文档索引、参数说明、错误码速查
